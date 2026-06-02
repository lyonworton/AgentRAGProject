from abc import ABC, abstractmethod

class BaseSource(ABC):
    @abstractmethod
    async def list_files(self) -> list[str]: ...
    @abstractmethod
    async def get_file_content(self, file_path: str) -> bytes: ...
