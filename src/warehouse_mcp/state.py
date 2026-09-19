from __future__ import annotations

from copy import deepcopy
from typing import Any


class WarehouseState:
    """Mutable in-memory state initialized from the supplied warehouse data."""

    def __init__(
        self,
        stock_records: list[dict[str, Any]],
        dock_records: list[dict[str, Any]],
    ) -> None:
        self.stock = deepcopy(stock_records)
        self.dock_schedule = deepcopy(dock_records)
        self.exceptions: dict[str, dict[str, Any]] = {}
        self._next_exception_number = 1

    def create_exception_id(self) -> str:
        exception_id = f"EXC-{self._next_exception_number:04d}"
        self._next_exception_number += 1
        return exception_id