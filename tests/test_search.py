import pytest

from warehouse_mcp.search import match_skus, tokenize

CASES = [
    # Leeds
    ("LEEDS-01", "pallet wrap", ["SKU-8801", "SKU-8802"]),
    ("LEEDS-01", "Pallet Wraps", ["SKU-8801", "SKU-8802"]),
    ("LEEDS-01", "pallet", ["SKU-8801", "SKU-8802", "SKU-8815", "SKU-8816"]),
    ("LEEDS-01", "void fill", ["SKU-8811"]),
    ("LEEDS-01", "strapping 12", ["SKU-8803"]),
    ("LEEDS-01", "strapping", ["SKU-8803", "SKU-8804"]),
    ("LEEDS-01", "air pillow boxes", []),
    ("LEEDS-01", "edge board", []),
    # Reading
    ("READING-02", "tape", ["SKU-8812", "SKU-8813"]),
    ("READING-02", "edge board", ["SKU-8807"]),
    ("READING-02", "corner protector 75", ["SKU-8806"]),
    # Glasgow
    ("GLASGOW-03", "shrink film", ["SKU-8808", "SKU-8809"]),
    ("GLASGOW-03", "600mm shrink film", ["SKU-8809"]),
    ("GLASGOW-03", "void fill", ["SKU-8810"]),
    ("GLASGOW-03", "label roll", ["SKU-8814"]),
]


@pytest.mark.parametrize("site,query,expected", CASES)
def test_search_oracle(make_scope, site, query, expected):
    rows = make_scope(site).stock_rows()
    assert match_skus(rows, query) == expected


def test_zero_stock_product_is_still_a_match(make_scope):
    rows = make_scope("GLASGOW-03").stock_rows()
    assert "SKU-8809" in match_skus(rows, "shrink film")


def test_same_query_gives_different_answers_per_site(make_scope):
    leeds = match_skus(make_scope("LEEDS-01").stock_rows(), "void fill")
    glasgow = match_skus(make_scope("GLASGOW-03").stock_rows(), "void fill")
    assert leeds == ["SKU-8811"]
    assert glasgow == ["SKU-8810"]


def test_plural_forms(make_scope):
    rows = make_scope("LEEDS-01").stock_rows()
    assert match_skus(rows, "void fills") == ["SKU-8811"]


def test_punctuation_only_query_matches_nothing(make_scope):
    assert match_skus(make_scope("LEEDS-01").stock_rows(), "!!") == []


def test_tokenize():
    assert tokenize("Pallet-Wrap, 500MM!") == ["pallet", "wrap", "500mm"]