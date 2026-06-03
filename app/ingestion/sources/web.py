import os
import tempfile
import hashlib
import httpx
from bs4 import BeautifulSoup
from app.ingestion.sources.base import BaseSource


class WebSource(BaseSource):
    """Web 摄入源：httpx 获取 + BeautifulSoup 正文提取。"""

    def __init__(self, urls: list[str], max_depth: int = 1, tmp_dir: str | None = None):
        self._urls = urls
        self._max_depth = max_depth
        self._tmp_dir = tmp_dir or tempfile.gettempdir()
        self._saved_files: list[str] = []

    async def list_files(self) -> list[str]:
        """爬取所有 URL，保存为临时 txt 文件，返回文件路径列表。"""
        self._saved_files = []
        for url in self._urls:
            try:
                text = await self._fetch_and_extract(url)
                file_path = self._save_text(text, url)
                self._saved_files.append(file_path)
            except Exception:
                continue
        return self._saved_files

    async def get_file_content(self, file_path: str) -> bytes:
        """读取临时文件的原始内容。"""
        with open(file_path, "rb") as f:
            return f.read()

    async def _fetch_and_extract(self, url: str) -> str:
        """获取 URL 内容并提取正文文本。"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return self._extract_text(resp.text)

    def _extract_text(self, html: str) -> str:
        """从 HTML 中提取正文，去除噪音标签。"""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    def _save_text(self, text: str, url: str) -> str:
        """保存文本到临时文件。"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"web_{url_hash}.txt"
        file_path = os.path.join(self._tmp_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)
        return file_path