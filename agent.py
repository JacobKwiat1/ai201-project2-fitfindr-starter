"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq, BadRequestError

from tools import search_listings, suggest_outfit, create_fit_card

load_dotenv()

_MODEL = "llama-3.3-70b-versatile"
_MAX_TOOL_CALLS = 5

# Tool definitions shown to the LLM. suggest_outfit and create_fit_card take no
# LLM-supplied parameters — the agent passes state from the session automatically.
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_listings",
            "description": "Search the secondhand clothing database for matching items.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "size":        {"type": "string"},
                    "max_price":   {"type": "number"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_outfit",
            "description": "Suggest outfit combinations for an item using the user's wardrobe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_title": {"type": "string"},
                },
                "required": ["item_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_fit_card",
            "description": "Generate a short, shareable OOTD caption for a thrifted item and outfit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_title": {"type": "string"},
                },
                "required": ["item_title"],
            },
        },
    },
]


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Add it to a .env file in the project root.")
    return Groq(api_key=api_key)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _minimal_item(args: dict) -> dict:
    """Build a bare-minimum item dict from LLM-supplied args when no search ran."""
    return {
        "title": args.get("item_title", "Item"),
        "description": args.get("item_description", ""),
        "price": 0.0,
        "platform": "unknown",
        "category": "clothing",
        "style_tags": [],
        "size": "unknown",
        "condition": "unknown",
        "brand": None,
    }


# ── tool dispatcher ───────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict, session: dict) -> str:
    """
    Execute a single tool call, update session state, and return a result
    string the LLM can read in the next turn.
    """
    if name == "search_listings":
        session["parsed"] = args
        results = search_listings(
            description=args["description"],
            size=args.get("size"),
            max_price=args.get("max_price"),
        )
        session["search_results"] = results
        if not results:
            session["error"] = (
                "No listings found matching your search — "
                "try a broader description or raise your price limit."
            )
            return "No listings found matching those criteria."
        session["selected_item"] = results[0]
        top = results[0]
        return f"Found {len(results)} item(s). Top: {top['title']} — ${top['price']}, size {top['size']}."

    if name == "suggest_outfit":
        if not session.get("selected_item"):
            session["selected_item"] = _minimal_item(args)
        suggestion = suggest_outfit(session["selected_item"], session["wardrobe"])
        session["outfit_suggestion"] = suggestion
        return "Outfit suggestion ready."

    if name == "create_fit_card":
        outfit = session.get("outfit_suggestion") or args.get("outfit", "")
        if not outfit:
            return "Error: no outfit available. Call suggest_outfit first."
        if not session.get("selected_item"):
            session["selected_item"] = _minimal_item(args)
        card = create_fit_card(outfit, session["selected_item"])
        session["fit_card"] = card
        return "Fit card ready."

    return f"Unknown tool: {name}"


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    The LLM drives the loop: each turn it decides whether to call a tool or
    return a final answer. The loop stops when the LLM makes no tool call or
    when the _MAX_TOOL_CALLS limit is reached.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    session = _new_session(query, wardrobe)
    client = _get_groq_client()

    messages = [
        {
            "role": "system",
            "content": (
                "You are FitFindr, a secondhand fashion assistant. "
                "Use the available tools to help the user. "
                "Call search_listings to find items for sale; "
                "skip it only if the user is describing items they already own. "
                "For a general item search with no specific output requested, call all three tools in order. "
                "For a specific request (outfit idea only, fit card only, etc.), call only the tools needed. "
                "Stop calling tools once you have produced what the user asked for. "
                "Call tools immediately without any preamble text."
            ),
        },
        {"role": "user", "content": query},
    ]

    tool_call_count = 0

    while tool_call_count < _MAX_TOOL_CALLS:
        try:
            response = client.chat.completions.create(
                model=_MODEL,
                messages=messages,
                tools=_TOOLS,
                tool_choice="auto",
                max_tokens=512,
            )
        except BadRequestError:
            # Model generated a malformed tool call — retry without tools
            response = client.chat.completions.create(
                model=_MODEL,
                messages=messages,
                max_tokens=512,
            )

        message = response.choices[0].message

        # Record the assistant turn in history (include tool_calls if present)
        assistant_turn = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant_turn["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        messages.append(assistant_turn)

        # No tool calls → LLM is done
        if not message.tool_calls:
            break

        # Execute each tool and feed results back into the conversation
        for tc in message.tool_calls:
            tool_call_count += 1
            raw_args = tc.function.arguments
            args = json.loads(raw_args) if raw_args else {}
            if not isinstance(args, dict):
                args = {}
            result = _execute_tool(tc.function.name, args, session)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        # Stop as soon as the final output is ready or a terminal error occurred
        if session["fit_card"] or session["error"]:
            break

    else:
        # while condition exhausted — hit the tool call limit
        session["error"] = (
            f"Reached the maximum of {_MAX_TOOL_CALLS} tool calls. "
            "The response may be incomplete."
        )

    # Guard against a text-only response that left the session entirely empty.
    if not session["selected_item"] and not session["error"]:
        session["error"] = "Something went wrong. Please try your query again."

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
