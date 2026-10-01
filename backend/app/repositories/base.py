from abc import ABC, abstractmethod
from typing import Any, Optional


class Repository(ABC):
    """Abstract interface for data persistence"""

    @abstractmethod
    def save(self, key: str, data: Any) -> None:
        """Save data with a key"""
        pass

    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        """Load data by key"""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete data by key"""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        pass
