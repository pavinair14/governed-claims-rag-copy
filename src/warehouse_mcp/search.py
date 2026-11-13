import re

from warehouse_mcp.store import StockRow


def tokenize(query: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", query.lower())


def _variants(word: str) -> set[str]:
    forms = {word}
    if len(word) > 3 and word.endswith("s"):
        forms.add(word[:-1])
        if word.endswith("es"):
            forms.add(word[:-2])
    return forms


def match_skus(rows: list[StockRow], query: str) -> list[str]:
    """SKUs (in order, no repeats) whose description contains every query word."""
    words = tokenize(query)
    if not words:
        return []

    found: list[str] = []
    for row in rows:
        if row.sku in found:
            continue
        text = row.description.lower()
        if all(any(form in text for form in _variants(w)) for w in words):
            found.append(row.sku)
    return found