# FitFindr

A secondhand clothing assistant with a Gradio UI. Describe what you're looking for, and FitFindr searches a mock listings dataset, suggests outfits using your wardrobe, and generates a shareable OOTD caption.

## How It Works

A tool-calling agent (LLM-driven loop with `tool_choice="auto"`) orchestrates three tools:

1. **`search_listings`** — filters and keyword-scores 40 mock secondhand listings by description, size, and price ceiling
2. **`suggest_outfit`** — calls the LLM to suggest 1–2 outfits pairing the found item with named pieces from your wardrobe (or gives general styling advice if the wardrobe is empty)
3. **`create_fit_card`** — calls the LLM to generate a casual 2–4 sentence Instagram/TikTok OOTD caption mentioning the item name, price, and platform

State flows through a `session` dict (`selected_item` → `outfit_suggestion` → `fit_card`). If the LLM stops early, a post-loop fill-in calls the remaining tools directly so all three UI panels are always populated.

## Project Structure

```
fitfindr/
├── app.py                     # Gradio interface — run this to launch the app
├── agent.py                   # Planning loop (run_agent)
├── tools.py                   # search_listings, suggest_outfit, create_fit_card
├── main.py                    # Runs all tests directly (no pytest required)
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + 10-item example wardrobe
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── tests/
│   └── test_tools.py          # 8 unit tests for the three tools
└── planning.md                # Architecture spec, state management, error handling
```

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

## Running the App

```bash
python app.py
```

Open the URL printed in the terminal (typically `http://localhost:7860`).

The UI has a query box, a wardrobe selector (example 10-item wardrobe or empty), and three output panels: top listing found, outfit idea, and fit card.

## Running the Tests

```bash
python main.py
```

Tests call the tool functions directly — no pytest fixtures required. Tests cover: search with results, search with no results, price filtering, outfit suggestion with/without wardrobe, fit card generation, and empty/whitespace outfit guards.

## Data

**Listings** (`data/listings.json`): 40 mock items across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear). Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`.

**Wardrobe** (`data/wardrobe_schema.json`): Wardrobe items have `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`. The example wardrobe has 10 items (jeans, blazer, shirts, skirts, sneakers, etc.).

```python
from utils.data_loader import load_listings, get_example_wardrobe, get_empty_wardrobe
```

## Model

All LLM calls use `llama-3.3-70b-versatile` via the Groq API. The planning loop caps at 3 tool calls. Tool schemas are kept minimal (no per-parameter descriptions, no unused optional params) to reduce token overhead — roughly 1,800 tokens per full happy-path run.

## AI Usage

**Instance 1 — Implementing `suggest_outfit` and `create_fit_card` (tools.py)**

Input given to Claude: the Tool 2 and Tool 3 spec sections from `planning.md` (input parameters, return format, failure modes), the `suggest_outfit` and `create_fit_card` docstrings from `tools.py`, and the wardrobe schema from `data/wardrobe_schema.json`.

What it produced: working implementations of both functions with separate LLM prompts for empty vs. non-empty wardrobes in `suggest_outfit`, and a guard for empty/whitespace `outfit` input in `create_fit_card`.

What I changed: the original planning spec said `suggest_outfit` should return `-1` for an empty wardrobe. I overrode this — returning a sentinel value would force every caller to handle a special case. Instead I kept the return type a plain string in both branches and had the LLM give general styling advice when the wardrobe was empty.

---

**Instance 2 — Rewriting `agent.py` from a linear pipeline to a tool-calling loop**

Input given to Claude: the Planning Loop and State Management sections of `planning.md` (including the session dict table), the tool signatures from `tools.py`, and the `_new_session()` definition already in `agent.py`.

What it produced: an initial linear pipeline that called all three tools in fixed order every run, regardless of what the user asked for.

What I changed: I asked Claude to rewrite the loop so the LLM drives tool selection via `tool_choice="auto"` rather than hard-coding the call order. This required several follow-up iterations — the first system prompt it wrote over-specified when to skip `search_listings`, which caused the model to stop searching entirely for normal queries. I simplified the system prompt down to two sentences and added a `_minimal_item()` fallback so the agent could handle "make a fit card for my red shirt" (no search needed) without crashing when `session["selected_item"]` was `None`.

---

## Error Handling

| Situation | Behavior |
|---|---|
| No listings match the query | `session["error"]` set with a user-friendly message; other panels left blank |
| Wardrobe is empty | `suggest_outfit` returns general styling advice instead of referencing specific pieces |
| Empty/whitespace outfit passed to fit card | Returns `"Could not generate fit card: outfit suggestion was empty."` — no exception raised |
| User provides items they already own (no search needed) | Agent skips `search_listings`; a minimal item dict is built from the LLM's args |
| Model returns malformed tool call JSON | `BadRequestError` caught; retried without tools |
