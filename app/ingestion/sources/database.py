import os
import tempfile
import hashlib
from sqlalchemy import create_engine, text
from app.ingestion.sources.base import BaseSource


class DBSource(BaseSource):
    """数据库摄入源：SQLAlchemy 通用连接器，行→文档映射。"""

    def __init__(
        self,
        db_url: str,
        query: str,
        title_column: str,
        content_columns: list[str],
        tmp_dir: str | None = None,
    ):
        self._db_url = db_url
        self._query = query
        self._title_col = title_column
        self._content_cols = content_columns
        self._tmp_dir = tmp_dir or tempfile.gettempdir()
        self._saved_files: list[str] = []

    async def list_files(self) -> list[str]:
        """执行查询，每行保存为临时 md 文件，返回文件路径列表。"""
        engine = create_engine(self._db_url)
        self._saved_files = []

        with engine.connect() as conn:
            result = conn.execute(text(self._query))
            for i, row in enumerate(result.mappings()):
                doc_text = self._row_to_document(row)
                file_path = self._save_text(doc_text, i)
                self._saved_files.append(file_path)

        return self._saved_files

    async def get_file_content(self, file_path: str) -> bytes:
        """读取临时文件的原始内容。"""
        with open(file_path, "rb") as f:
            return f.read()

    def _row_to_document(self, row) -> str:
        """将一行数据转为结构化 Markdown 文本。

        格式: # {title}\n\n{col1_content}\n\n{col2_content}...
        """
        title = row[self._title_col] or ""
        parts = [f"# {title}"]

        for col in self._content_cols:
            value = row.get(col)
            if value is not None:
                parts.append(str(value))

        return "\n\n".join(parts)

    def _save_text(self, text: str, index: int) -> str:
        """保存文本到临时文件。"""
        content_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        filename = f"db_{index}_{content_hash}.md"
        file_path = os.path.join(self._tmp_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)
        return file_path