from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


class WarehouseDataStore:
    """Read-only access to the supplied warehouse data files."""

    def __init__(
        self,
        stock_file: str | Path,
        dock_file: str | Path,
    ) -> None:
        self.stock_file = Path(stock_file)
        self.dock_file = Path(dock_file)

    def load_stock(self) -> list[dict[str, Any]]:
        """Load all stock records from the CSV file."""
        with self.stock_file.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            return list(reader)

    def load_dock_schedule(self) -> list[dict[str, Any]]:
        """Load all dock records from the JSONL file."""
        records: list[dict[str, Any]] = []

        with self.dock_file.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                records.append(json.loads(line))

        return records