"""02-anthropic-tool-use — travel concierge REPL with Anthropic tool use.

Demonstrates Claude with tools, captured as automatic spans by Waxell's
Anthropic auto-instrumentor. Two tools are available to the model:
``get_weather(city)`` and ``get_local_time(timezone)``. The model decides
when to call them; every tool call shows up as a child span inside the run
in the Waxell UI — no manual span code required.

Subject: a travel concierge. Ask it things like "what's the weather in
Tokyo and what time is it there?" and watch both tools fire in one turn.

Anthropic's tool-use message flow:
  1. Send user message + ``tools=`` list to the API.
  2. Model replies with ``stop_reason="tool_use"`` and one or more
     ``tool_use`` content blocks.
  3. We execute the requested tools locally.
  4. We send a ``tool_result`` message back to get the final answer.
  This loop repeats until ``stop_reason="end_turn"``.

Run::

    ./setup.sh                       # one-time
    source .venv/bin/activate
    python agent.py

Then type at the ``you>`` prompt. Use ``/reset`` to start a fresh
conversation, ``/exit`` to quit.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import waxell_observe as waxell

waxell.init()

import anthropic

# ---------------------------------------------------------------------------
# Tool implementations — synthetic stubs, no real API calls.
# ---------------------------------------------------------------------------

_WEATHER_DATA: dict[str, dict] = {
    "tokyo": {"condition": "Partly cloudy", "temp_c": 22, "humidity_pct": 68},
    "london": {"condition": "Overcast", "temp_c": 14, "humidity_pct": 80},
    "new york": {"condition": "Sunny", "temp_c": 26, "humidity_pct": 45},
    "paris": {"condition": "Light rain", "temp_c": 17, "humidity_pct": 75},
    "sydney": {"condition": "Clear", "temp_c": 19, "humidity_pct": 55},
    "dubai": {"condition": "Sunny and hot", "temp_c": 38, "humidity_pct": 30},
    "bangkok": {"condition": "Thunderstorm", "temp_c": 32, "humidity_pct": 88},
    "amsterdam": {"condition": "Windy", "temp_c": 12, "humidity_pct": 72},
}

_TIME_DATA: dict[str, dict] = {
    "asia/tokyo": {"local_time": "14:42", "utc_offset": "+09:00", "tz_abbr": "JST"},
    "europe/london": {"local_time": "06:42", "utc_offset": "+01:00", "tz_abbr": "BST"},
    "america/new_york": {"local_time": "01:42", "utc_offset": "-04:00", "tz_abbr": "EDT"},
    "europe/paris": {"local_time": "07:42", "utc_offset": "+02:00", "tz_abbr": "CEST"},
    "australia/sydney": {"local_time": "16:42", "utc_offset": "+11:00", "tz_abbr": "AEDT"},
    "asia/dubai": {"local_time": "10:42", "utc_offset": "+04:00", "tz_abbr": "GST"},
    "asia/bangkok": {"local_time": "13:42", "utc_offset": "+07:00", "tz_abbr": "ICT"},
    "europe/amsterdam": {"local_time": "07:42", "utc_offset": "+02:00", "tz_abbr": "CEST"},
}


def get_weather(city: str) -> str:
    """Return a JSON string with current weather for *city*.

    Uses a synthetic stub — no real API is called. Falls back to a generic
    response for unknown cities so the model always gets a valid answer.
    """
    key = city.lower().strip()
    data = _WEATHER_DATA.get(key, {"condition": "Clear", "temp_c": 20, "humidity_pct": 60})
    result = {
        "city": city.title(),
        "condition": data["condition"],
        "temperature_c": data["temp_c"],
        "temperature_f": round(data["temp_c"] * 9 / 5 + 32, 1),
        "humidity_pct": data["humidity_pct"],
    }
    return json.dumps(result)


def get_local_time(timezone: str) -> str:
    """Return a JSON string with the current local time for *timezone*.

    Accepts IANA timezone names (e.g. "Asia/Tokyo"). Uses a synthetic stub.
    Falls back gracefully for unknown timezones.
    """
    key = timezone.lower().strip()
    data = _TIME_DATA.get(key, {"local_time": "12:00", "utc_offset": "+00:00", "tz_abbr": "UTC"})
    result = {
        "timezone": timezone,
        "local_time": data["local_time"],
        "utc_offset": data["utc_offset"],
        "tz_abbreviation": data["tz_abbr"],
    }
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Tool registry — maps name → callable and provides the schema Anthropic needs.
# ---------------------------------------------------------------------------

_TOOL_CALLABLES: dict[str, callable] = {
    "get_weather": get_weather,
    "get_local_time": get_local_time,
}

_TOOLS: list[dict] = [
    {
        "name": "get_weather",
        "description": (
            "Get the current weather conditions for a city. "
            "Returns temperature in Celsius and Fahrenheit, sky condition, and humidity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. 'Tokyo', 'London', 'New York'.",
                }
            },
            "required": ["city"],
        },
    },
    {
        "name": "get_local_time",
        "description": (
            "Get the current local time and UTC offset for a timezone. "
            "Accepts IANA timezone names such as 'Asia/Tokyo' or 'Europe/London'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "IANA timezone identifier, e.g. 'Asia/Tokyo', 'America/New_York'."
                    ),
                }
            },
            "required": ["timezone"],
        },
    },
]

_SYSTEM = (
    "You are an expert travel concierge. You help travellers plan trips and "
    "answer destination questions. When asked about weather or local time, "
    "always use your tools to fetch current data before answering — never "
    "guess. Combine results from multiple tools in a single, clear reply. "
    "Remember context across turns so you can give personalised advice."
)


# ---------------------------------------------------------------------------
# Core turn logic — Anthropic tool-use agentic loop.
# ---------------------------------------------------------------------------


def _run_tool(tool_name: str, tool_input: dict) -> str:
    """Dispatch a single tool call and return its JSON result string."""
    fn = _TOOL_CALLABLES.get(tool_name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {tool_name}"})
    try:
        return fn(**tool_input)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


@waxell.observe(agent_name="anthropic-tool-use")
def chat_turn(history: list[dict], user_message: str) -> str:
    """One conversational turn with Anthropic tool use.

    Implements the full tool-use agentic loop:
    - Send message to Claude with ``tools=`` list.
    - If the model calls tools, execute them and feed results back.
    - Repeat until ``stop_reason == "end_turn"``.

    ``history`` is mutated in place so the next turn sees the full thread.
    Each call to this function = one Waxell run; tool calls appear as
    child spans inside that run automatically.
    """
    client = anthropic.Anthropic()
    history.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            system=_SYSTEM,
            tools=_TOOLS,
            messages=history,
        )

        if response.stop_reason == "end_turn":
            # Extract plain text from the response content blocks.
            reply = " ".join(
                block.text
                for block in response.content
                if hasattr(block, "text")
            ).strip()
            history.append({"role": "assistant", "content": response.content})
            return reply

        if response.stop_reason == "tool_use":
            # Record the assistant's tool_use turn in history.
            history.append({"role": "assistant", "content": response.content})

            # Execute every requested tool and build the tool_result message.
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_content = _run_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_content,
                        }
                    )

            history.append({"role": "user", "content": tool_results})
            # Loop: send tool results back to the model.
            continue

        # Unexpected stop reason — surface it and exit the loop.
        reply = f"(unexpected stop_reason: {response.stop_reason})"
        history.append({"role": "assistant", "content": response.content})
        return reply


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------


def repl() -> None:
    print("anthropic-tool-use — travel concierge with weather + time tools.")
    print("Try: 'what's the weather in Tokyo and what time is it there?'")
    print("Commands: /reset, /exit\n")
    history: list[dict] = []
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user == "/exit":
            break
        if user == "/reset":
            history.clear()
            print("(conversation reset)\n")
            continue
        reply = chat_turn(history, user)
        print(f"assistant> {reply}\n")


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.stderr.write(
            "ANTHROPIC_API_KEY is not set in .env — add it and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
