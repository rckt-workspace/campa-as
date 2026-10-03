import json
from pathlib import Path
from typing import Any, Optional

from app.repositories.base import Repository


class JsonRepository(Repository):
    """JSON file-based persistence"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def _get_path(self, key: str) -> Path:
        return self.data_dir / f"{key}.json"

    def save(self, key: str, data: Any) -> None:
        path = self._get_path(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def load(self, key: str) -> Optional[Any]:
        path = self._get_path(key)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def delete(self, key: str) -> None:
        path = self._get_path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._get_path(key).exists()
