from warehouse_mcp.context import SessionContext
from warehouse_mcp.errors import ErrorCode, ToolError
from warehouse_mcp.store import DockSlot, Store, StockRow

BIN_PREFIXES = {
    "LEEDS-01": ("A-", "YARD-"),
    "READING-02": ("B-",),
    "GLASGOW-03": ("C-",),
}


def site_of_bin(bin_name: str) -> str | None:
    for site, prefixes in BIN_PREFIXES.items():
        if bin_name.startswith(prefixes):
            return site
    return None


class Scope:
    def __init__(self, store: Store, ctx: SessionContext) -> None:
        self._store = store
        self._ctx = ctx

    @property
    def site(self) -> str:
        return self._ctx.site
    
    @property
    def caller_id(self) -> str:
        return self._ctx.caller_id

    def stock_rows(self) -> list[StockRow]:
        return [r for r in self._store.stock if r.site == self.site]

    def rows_for_sku(self, sku: str) -> list[StockRow]:
        own = [r for r in self.stock_rows() if r.sku == sku]
        if own:
            return own
        if any(r.sku == sku for r in self._store.stock):
            raise self._denied(sku)
        raise ToolError(
            ErrorCode.NOT_FOUND,
            f"No product with SKU {sku} exists.",
            field="sku",
            details={"sku": sku},
            suggested_action=(
                "Check the SKU with the user, or search by description instead."
            ),
            example_call={
                "tool": "search_stock",
                "arguments": {"query": "<words describing the product>"},
            },
        )

    def dock_slots(self, date: str) -> list[DockSlot]:
        return [
            s for s in self._store.docks if s.site == self.site and s.date == date
        ]

    def scheduled_dates(self) -> list[str]:
        return sorted({s.date for s in self._store.docks if s.site == self.site})

    def dock_slot(self, date: str, slot: str) -> DockSlot | None:
        return next((s for s in self.dock_slots(date) if s.slot == slot), None)

    def record(self, entry: dict) -> None:
        self._store.audit.append(
            {**entry, "site": self.site, "caller_id": self.caller_id}
        )

    def add_stock_row(self, row: StockRow) -> None:
        self._store.stock.append(row)

    def remove_stock_row(self, row: StockRow) -> None:
        self._store.stock[:] = [r for r in self._store.stock if r is not row]

    def exceptions(self) -> list[dict]:
        return [e for e in self._store.exceptions if e["site"] == self.site]

    def next_exception_id(self) -> str:
        return f"EX-{len(self._store.exceptions) + 1:03d}"

    def add_exception(self, record: dict) -> None:
        self._store.exceptions.append({**record, "site": self.site})

    def require_own_bin(self, bin_name: str, field: str = "bin") -> None:
        owner = site_of_bin(bin_name)
        if owner is None:
            raise ToolError(
                ErrorCode.INVALID_ARGUMENT,
                f"Bin {bin_name!r} is not a recognised bin name.",
                field=field,
                details={"valid_prefixes": list(BIN_PREFIXES[self.site])},
                suggested_action=(
                    "Use a bin name from get_stock, or ask the user for the exact bin."
                ),
            )
        if owner != self.site:
            raise self._denied(bin_name, kind="bin")

    def get_exception(self, exception_id: str) -> dict:
        for exc in self._store.exceptions:
            if exc["exception_id"] == exception_id:
                if exc["site"] != self.site:
                    raise self._denied(exception_id, kind="exception")
                return exc
        raise ToolError(
            ErrorCode.NOT_FOUND,
            f"No exception with ID {exception_id} exists.",
            field="exception_id",
            details={"exception_id": exception_id},
            suggested_action="List open exceptions and ask the user which one they mean.",
            example_call={"tool": "list_exceptions", "arguments": {}},
        )

    def _denied(self, identifier: str, kind: str = "item") -> ToolError:
        return ToolError(
            ErrorCode.SITE_ACCESS_DENIED,
            f"{identifier} is not available at your site ({self.site}).",
            details={"identifier": identifier, "kind": kind},
            suggested_action=(
                "Do not retry. Tell the user this is not held at their site, "
                "and do not quote any figures for it."
            ),
        )