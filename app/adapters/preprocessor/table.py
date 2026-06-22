from app.adapters.preprocessor.base import BaseStep, ExtractedPDF
from app.core.config import get_settings


def _rows_to_markdown(rows: list[list[str]]) -> str:
    """Convert a list of row lists to a Markdown table string.

    Args:
        rows: Each inner list is a row of cell strings. The first row
              is treated as the header.

    Returns:
        Markdown table string, e.g.:
        | Col 1 | Col 2 |
        |-------|-------|
        | A     | B     |
    """
    if not rows:
        return ""

    lines = []
    # Header row
    header = " | ".join(str(cell) for cell in rows[0])
    lines.append(f"| {header} |")

    # Separator
    separators = ["---"] * len(rows[0])
    lines.append("| " + " | ".join(separators) + " |")

    # Data rows
    for row in rows[1:]:
        cells = " | ".join(str(cell) for cell in row)
        lines.append(f"| {cells} |")

    return "\n".join(lines)


class TableExtractor(BaseStep):
    """Convert detected table regions to Markdown format.

    Reads `table_regions` from the input ExtractedPDF and produces
    `tables` output with markdown representations.

    Skips processing when:
    - has_tables is False, or
    - preprocessor_table_enabled setting is False.
    """

    async def run(self, data: ExtractedPDF) -> ExtractedPDF:
        settings = get_settings()

        if not data.has_tables or not settings.preprocessor_table_enabled:
            return data

        tables = []
        for region in data.table_regions:
            rows = region.get("rows", [])
            if not rows:
                continue
            markdown = _rows_to_markdown(rows)
            tables.append({
                "page": region["page"],
                "index": region["index"],
                "markdown": markdown,
            })

        return ExtractedPDF(
            pages=data.pages,
            full_text=data.full_text,
            page_boundaries=data.page_boundaries,
            has_tables=data.has_tables,
            table_regions=data.table_regions,
            tables=tables,
        )
