# tests/test_tools.py

_SAMPLE_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "description": "Vintage-style bootleg tee with faded graphic.",
    "category": "tops",
    "style_tags": ["graphic tee", "vintage", "streetwear"],
    "size": "L",
    "condition": "good",
    "price": 24.0,
    "colors": ["black"],
    "brand": None,
    "platform": "depop",
}

_SAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "Baggy straight-leg jeans",
            "category": "bottoms",
            "colors": ["dark blue"],
            "style_tags": ["denim", "streetwear"],
            "notes": None,
        }
    ]
}

_EMPTY_WARDROBE = {"items": []}


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results(search_listings):
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results(search_listings):
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception

def test_search_price_filter(search_listings):
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_returns_string(suggest_outfit):
    result = suggest_outfit(_SAMPLE_ITEM, _SAMPLE_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_empty_wardrobe(suggest_outfit):
    result = suggest_outfit(_SAMPLE_ITEM, _EMPTY_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0   # graceful fallback — not an empty string or exception


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_fitcard_returns_string(create_fit_card):
    outfit = "Pair the tee with baggy jeans and chunky white sneakers."
    result = create_fit_card(outfit, _SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0

def test_fitcard_empty_outfit(create_fit_card):
    result = create_fit_card("", _SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "Could not generate fit card" in result   # error string, no exception

def test_fitcard_whitespace_outfit(create_fit_card):
    result = create_fit_card("   ", _SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "Could not generate fit card" in result   # whitespace-only treated as empty
