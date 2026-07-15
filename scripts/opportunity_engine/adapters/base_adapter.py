from abc import ABC, abstractmethod
from typing import List, Any
import logging
from ..models.opportunity import RawSignal

logging.basicConfig(level=logging.INFO)

class BaseAdapter(ABC):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def _fetch_raw_data(self) -> List[Any]:
        """Execute network I/O. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def _normalize(self, raw_item: Any) -> RawSignal:
        """Normalize a single raw item into a RawSignal."""
        pass

    async def execute(self) -> List[RawSignal]:
        self.logger.info("Starting extraction...")
        try:
            raw_items = await self._fetch_raw_data()
        except Exception as e:
            self.logger.error(f"Critical Fetch Failure: {e}")
            return [] # Fail gracefully, don't crash pipeline

        if not raw_items:
            return []

        normalized = []
        for item in raw_items:
            try:
                norm = self._normalize(item)
                normalized.append(norm)
            except Exception as e:
                self.logger.error(f"Normalization exception on item: {e}")

        self.logger.info(f"Yielded {len(normalized)} normalized items.")
        return normalized
