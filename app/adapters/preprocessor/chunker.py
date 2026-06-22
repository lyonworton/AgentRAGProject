"""Parent-child chunking step for preprocessed PDF documents."""

import hashlib
import re

from app.adapters.preprocessor.base import BaseStep, ChunkedDocument, ExtractedPDF


# Heading detection patterns
_HEADING_PATTERNS = [
    re.compile(r"^#{1,6}\s+.+$"),                          # Markdown: # Title
    re.compile(r"^\d+(?:\.\d+)*\s+[A-Za-z一-鿿].+$"),  # Numbered: 1. Title
    re.compile(r"^(Chapter|Section|Article|Part)\s+\d+"),   # Keyword: Chapter 1
]


def _is_heading(line: str) -> bool:
    """Return True if the line looks like a section heading."""
    return any(pat.match(line) for pat in _HEADING_PATTERNS)


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
        """Assign content_start/content_end offsets for parent groups and children."""
        for pg_id, pg in parent_groups.items():
            heading = pg["heading"]
            # Find the heading position in full_text
            pos = full_text.find(heading)
            if pos >= 0:
                pg["content_start"] = pos
                pg["content_end"] = pos + len(pg["text"])

            for child in child_chunks:
                if child["parent_group_id"] == pg_id:
                    child["metadata"]["content_start"] = pg["content_start"]
                    child["metadata"]["content_end"] = (
                        pg["content_start"] + child["metadata"]["content_end"]
                    )

    @staticmethod
    def _parent_id(heading: str) -> str:
        """Generate a deterministic parent-group ID from a heading."""
        h = hashlib.md5(heading.encode()).hexdigest()[:8]
        return f"parent_{h}"
