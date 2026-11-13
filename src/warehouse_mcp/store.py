import csv
import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass
class StockRow:
    sku: str
    description: str
    site: str
    bin: str
    quantity: int
    unit: str


@dataclass
class DockSlot:
    site: str
    date: str
    slot: str
    status: str
    carrier: str | None


class Store:
    def __init__(self, stock: list[StockRow], docks: list[DockSlot]) -> None:
        self.stock = stock
        self.docks = docks
        self.exceptions: list[dict] = []
        self.audit: list[dict] = []

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR) -> "Store":
        with open(data_dir / "stock_snapshot.csv", newline="", encoding="utf-8") as f:
            stock = [
                StockRow(
                    sku=r["sku"],
                    description=r["description"],
                    site=r["site"],
                    bin=r["bin"],
                    quantity=int(r["quantity"]),
                    unit=r["unit"],
                )
                for r in csv.DictReader(f)
            ]

        with open(data_dir / "dock_schedule.jsonl", encoding="utf-8") as f:
            docks = [DockSlot(**json.loads(line)) for line in f if line.strip()]

        return cls(stock, docks)