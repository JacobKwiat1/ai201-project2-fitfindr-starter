"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

_MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()

    # Step 1: filter by price and size
    filtered = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and size.lower() not in listing["size"].lower():
            continue
        filtered.append(listing)

    # Step 2: score each listing by keyword overlap with description
    words = set(description.lower().split())
    scored = []
    for listing in filtered:
        searchable = " ".join([
            listing["title"].lower(),
            listing["description"].lower(),
        ] + [tag.lower() for tag in listing["style_tags"]]
          + ([listing["brand"].lower()] if listing.get("brand") else []))

        score = sum(1 for word in words if word in searchable)
        if score > 0:
            scored.append((score, listing))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    client = _get_groq_client()

    item_summary = (
        f"{new_item['title']} "
        f"(${new_item['price']}, {new_item['category']}, "
        f"tags: {', '.join(new_item['style_tags'])})"
    )

    if not wardrobe.get("items"):
        prompt = (
            f"I'm considering buying this thrifted item: {item_summary}. "
            "I don't have a wardrobe entered yet. Give me general styling advice — "
            "what kinds of pieces pair well with this, what vibe it suits, and a few "
            "specific styling tips. "
            "do not name specific pieces that the user does not own. Be vague"
            "Be casual and practical, 2–3 sentences."
        )
    else:
        wardrobe_lines = []
        for item in wardrobe["items"]:
            line = (
                f"- {item['name']} "
                f"(colors: {', '.join(item['colors'])}, "
                f"tags: {', '.join(item['style_tags'])})"
            )
            if item.get("notes"):
                line += f" — {item['notes']}"
            wardrobe_lines.append(line)

        prompt = (
            f"I'm considering buying this thrifted item: {item_summary}.\n\n"
            f"My current wardrobe:\n" + "\n".join(wardrobe_lines) + "\n\n"
            "Suggest 1–2 complete outfits using this new item and specific pieces "
            "from my wardrobe. Name each wardrobe piece by name. Keep it casual, "
            "like a friend giving honest advice. 3–5 sentences total."
        )

    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )
    return response.choices[0].message.content


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception. 

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)
    """
    if not outfit or not outfit.strip():
        return "Could not generate fit card: outfit suggestion was empty."

    client = _get_groq_client()

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok OOTD caption for this thrifted find.\n\n"
        f"Item: {new_item['title']}\n"
        f"Price: ${new_item['price']}\n"
        f"Platform: {new_item['platform']}\n"
        f"Outfit: {outfit}\n\n"
        "Requirements:\n"
        "- Sound casual and authentic, like a real OOTD post — not a product description\n"
        "- Mention the item name, price, and platform naturally (each exactly once)\n"
        "- Capture the specific outfit vibe in concrete terms\n"
        "- 2–4 sentences only, no hashtags"
    )

    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=1.0,
    )
    return response.choices[0].message.content
