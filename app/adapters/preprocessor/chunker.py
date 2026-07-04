"""Parent-child chunking step for preprocessed PDF documents."""

import hashlib
import re

from app.adapters.preprocessor.base import BaseStep, ChunkedDocument, ExtractedPDF


# Heading detection patterns — ordered by specificity.
# PDFs rarely have Markdown markers, so we rely on structural cues.
_HEADING_PATTERNS = [
    re.compile(r"^#{1,6}\s+.+$"),                          # Markdown: # Title

    # Keyword-based: "Chapter 1", "Section 2.3", etc.
    re.compile(r"^(Chapter|Section|Article|Part|Appendix)\s+\d+(?:[./]\d+)*$"),

    # Numbered heading: "1. Intro", "2.3 Results", "4.1.2 Sub", etc.
    # \d+(?:[./]\d*)* allows "1." (zero digits after dot) as well as "2.3", "4.1.2".
    re.compile(r"^\d+(?:[./]\d*)*\s+.+$"),
]


def _check_unnumbered_heading(stripped: str) -> bool:
    """Heuristic for unnumbered headings like 'RESULTS AND DISCUSSION' or 'Magnetic Ground State'."""
    words = stripped.split()
    if len(words) > 12 or len(stripped) > 80:
        return False
    # Must have at least one uppercase letter
    if not any(c.isupper() for c in stripped):
        return False
    # Reject if it looks like a full sentence (article + verb)
    has_article = any(w.lower() in ('the', 'a', 'an') for w in words)
    has_verb = any(w.lower() in ('is', 'are', 'was', 'were', 'has', 'have',
                                  'show', 'shows', 'demonstrate', 'indicate',
                                  'suggest', 'suggests', 'predict', 'predicts',
                                  'confirm', 'confirms', 'report', 'reports')
                   for w in words)
    if has_article and has_verb:
        return False
    return True


def _is_heading(line: str) -> bool:
    """Return True if the line looks like a section heading.

    Heuristics:
    - Headings are typically short (≤ 60 chars after numbering)
    - Headings rarely end with terminal punctuation (. ! ?)
    - Section numbers are integer sequences: "1", "2.3", "4.1.2"
    - Decimal values like "4.0", "1.58" are NOT headings
    """
    stripped = line.strip()
    if not stripped:
        return False

    # Quick rejection: terminal punctuation -> not a heading
    if stripped[-1] in ".!?":
        return False

    # Must match at least one pattern (for numbered/keyword/markdown headings)
    if not any(pat.match(stripped) for pat in _HEADING_PATTERNS):
        # Fallback: check unnumbered heading heuristics
        return _check_unnumbered_heading(stripped)

    # Markdown headings: # Title, ## Methods
    if stripped.startswith("#"):
        return len(stripped) <= 80

    # Keyword headings: Chapter 1, Section 2.3
    if re.match(r"^(Chapter|Section|Article|Part|Appendix)\s+", stripped):
        return True

    # Numbered headings: "1. Intro", "2.3 Results", "4.1.2 Subsection"
    # vs decimal values: "4.0 eV...", "1.58 meV..."
    num_match = re.match(r"^(\d+(?:[./]\d*)*)\s+(.+)$", stripped)
    if not num_match:
        return False

    number_part = num_match.group(1)
    text_part = num_match.group(2)

    # Count separators to distinguish section outline from decimals
    dot_count = number_part.count('.')
    slash_count = number_part.count('/')

    if dot_count + slash_count >= 2:
        # Multi-level section: "4.1.2", "2.3.1" -> definitely a section number
        pass
    elif dot_count == 1 and slash_count == 0:
        # Could be "2.3" (section) or "4.0" (decimal)
        last_dot = number_part.rfind('.')
        after_last_dot = number_part[last_dot + 1:]
        if not after_last_dot:
            # "1." -> section marker with trailing dot
            pass
        else:
            # Has digits after dot: "2.3" or "4.0"
            # Disambiguate by checking text_part case
            first_word = text_part.split()[0] if text_part.split() else ""
            if first_word and first_word[0].isupper():
                # Title case -> likely a section heading
                pass
            else:
                # Lowercase -> likely a decimal value followed by sentence
                return False
    # else: plain digit "1", "2", "3" -> section number

    # Length and word count constraints
    if len(text_part) > 60:
        return False
    if len(text_part.split()) > 15:
        return False

    return True


def _extract_heading_text(line: str) -> str:
    """Strip leading markers from a heading line to get the heading label."""
    # Markdown headings: remove leading #s and whitespace
    stripped = re.sub(r"^#+\s*", "", line)
    return stripped.strip()



class ParentChildChunker(BaseStep):
    """Split preprocessed PDF text into parent groups (sections) and child chunks.

    Algorithm:
    1. Detect headings in the cleaned full text to identify section boundaries.
    2. Group text between headings into parent blocks.
    3. If a parent block exceeds ``parentchunk_size``, split it into multiple
       parent groups using a sliding window with 50-character overlap.
    4. Split each parent group into child chunks of ``subchunk_size``.

    Returns a ``ChunkedDocument`` with ``child_chunks``, ``parent_groups``, and
    ``cleaned_full_text``.
    """

    def __init__(
        self,
        parentchunk_size: int = 2000,
        subchunk_size: int = 128,
    ):
        self.parentchunk_size = parentchunk_size
        self.subchunk_size = subchunk_size

    async def run(self, data: ExtractedPDF) -> ChunkedDocument:
        cleaned_text = data.full_text
        if not cleaned_text.strip():
            return ChunkedDocument(
                child_chunks=[],
                parent_groups={},
                cleaned_full_text=cleaned_text,
            )

        # Step 1: Detect headings and build sections
        sections = self._detect_sections(cleaned_text)

        # Step 2: Build parent groups (handling oversized sections)
        parent_groups = {}
        child_chunks = []
        child_counter = 0

        for heading, text in sections:
            if not text.strip():
                continue

            # Split oversized sections into multiple parents via sliding window
            parent_blocks = self._split_section(text, heading)

            for block_idx, block in enumerate(parent_blocks):
                if len(parent_blocks) == 1:
                    pg_id = self._parent_id(heading)
                else:
                    pg_id = self._parent_id(f"{heading}[{block_idx}]")

                parent_groups[pg_id] = {
                    "text": block,
                    "content_start": 0,
                    "content_end": len(block),
                    "child_ids": [],
                    "heading": heading,
                }

                # Step 3: Split parent block into child chunks
                chunk_overlap = 50
                chunks = self._split_into_chunks(block, self.subchunk_size, chunk_overlap)
                for chunk_text in chunks:
                    chunk_id = f"chunk_{child_counter}"
                    child_counter += 1
                    child_chunk = {
                        "chunk_id": chunk_id,
                        "parent_group_id": pg_id,
                        "text": chunk_text,
                        "metadata": {
                            "parent_group_id": pg_id,
                            "content_start": 0,
                            "content_end": len(chunk_text),
                            "source_page": 1,
                            "content_type": "chunk",
                        },
                    }
                    child_chunks.append(child_chunk)
                    parent_groups[pg_id]["child_ids"].append(chunk_id)

        # Update content_start/content_end based on positions in cleaned text
        self._assign_offsets(parent_groups, child_chunks, cleaned_text)

        return ChunkedDocument(
            child_chunks=child_chunks,
            parent_groups=parent_groups,
            cleaned_full_text=cleaned_text,
        )

    def _detect_sections(self, full_text: str) -> list[tuple[str, str]]:
        """Detect headings and return list of (heading_label, section_text)."""
        lines = full_text.split("\n")
        sections = []
        current_heading = "Unassigned"
        current_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                current_lines.append(stripped)
                continue
            if _is_heading(stripped):
                # Save previous section
                if current_lines:
                    sections.append((current_heading, "".join(current_lines)))
                current_heading = _extract_heading_text(stripped)
                current_lines = [stripped + "\n"]
            else:
                current_lines.append(line + "\n")

        # Don't forget the last section
        if current_lines:
            sections.append((current_heading, "".join(current_lines)))
        elif not sections:
            # No headings at all — treat entire text as one section
            sections.append(("Unassigned", full_text))

        return sections

    def _split_section(self, text: str, heading: str) -> list[str]:
        """Split a section into parent-sized blocks using sliding window overlap."""
        if len(text) <= self.parentchunk_size:
            return [text]

        blocks = []
        start = 0
        overlap = 50
        while start < len(text):
            end = start + self.parentchunk_size
            block = text[start:end]
            blocks.append(block)
            if end >= len(text):
                break
            start = end - overlap

        return blocks

    @staticmethod
    def _split_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
        """Split text into fixed-size chunks with overlap.

        Overlap must be strictly less than chunk_size, otherwise we get
        an infinite loop.  Clamp to chunk_size - 1 when needed.
        """
        if overlap >= chunk_size:
            overlap = chunk_size - 1
        if chunk_size <= 0:
            return []

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = end - overlap

        return chunks

    def _assign_offsets(self, parent_groups: dict, child_chunks: list[dict], full_text: str) -> None:
        """Assign content_start/content_end offsets for parent groups and children.

        Uses positional tracking instead of string search: walk through
        full_text and match each parent-group's heading text against the
        ordered headings from the sections, anchoring offsets to the
        actual position where that heading appears.
        """
        # Re-detect sections to get the ordered list of (heading_label, section_text)
        lines = full_text.split("\n")
        sections = []
        current_heading = "Unassigned"
        current_lines = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                current_lines.append(stripped)
                continue
            if _is_heading(stripped):
                if current_lines:
                    sections.append((current_heading, "".join(current_lines)))
                current_heading = _extract_heading_text(stripped)
                current_lines = [stripped + "\n"]
            else:
                current_lines.append(line + "\n")

        if current_lines:
            sections.append((current_heading, "".join(current_lines)))
        elif not sections:
            sections.append(("Unassigned", full_text))

        # Walk through sections and find each heading's position in full_text
        pos = 0
        for heading_label, section_text in sections:
            # Search for the heading text at or after current position
            idx = full_text.find(heading_label, pos)
            if idx < 0:
                pos += len(section_text)
                continue

            # Find all parent groups whose heading matches this section
            for pg_id, pg in parent_groups.items():
                if pg["heading"] == heading_label:
                    pg["content_start"] = idx
                    pg["content_end"] = idx + len(pg["text"])

                    # Assign child offsets relative to parent group
                    for child in child_chunks:
                        if child["parent_group_id"] == pg_id:
                            child["metadata"]["content_start"] = pg["content_start"]
                            child["metadata"]["content_end"] = (
                                pg["content_start"] + child["metadata"]["content_end"]
                            )

            pos = idx + len(section_text)

    @staticmethod
    def _parent_id(heading: str) -> str:
        """Generate a deterministic parent-group ID from a heading."""
        h = hashlib.md5(heading.encode()).hexdigest()[:8]
        return f"parent_{h}"
