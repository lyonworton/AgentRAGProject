import os
from app.ingestion.sources.base import BaseSource

class LocalSource(BaseSource):
    def __init__(self, paths):
        self._paths = paths

    async def list_files(self):
        files = []
        for p in self._paths:
            if os.path.isfile(p): files.append(p)
            elif os.path.isdir(p):
                for root, _, filenames in os.walk(p):
                    for fn in filenames: files.append(os.path.join(root, fn))
        return files

    async def get_file_content(self, file_path):
        with open(file_path, "rb") as f: return f.read()
