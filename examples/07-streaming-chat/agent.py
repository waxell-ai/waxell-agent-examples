"""07-streaming-chat — conversational poetry REPL with OpenAI streaming.

Demonstrates that Waxell's OpenAI auto-instrumentor handles streaming
responses correctly out of the box. Tokens print to stdout as they arrive
so the user sees a visible "typing" effect, and Waxell still records the
full final response + token counts as a single LLM span on the run.

Two lines instrument everything: ``waxell.init()`` registers the
auto-instrumentor, and ``@waxell.observe(...)`` declares the entry point.
No manual span work is needed — the instrumentor stitches the stream
back into a complete span after the last chunk.

Subject: a streaming poetry assistant. Ask for a poem on any topic and
watch it materialise word-by-word.

Run::

    ./setup.sh                       # one-time
    source .venv/bin/activate
    python agent.py

Then type requests at the ``you>`` prompt. Use ``/reset`` to start a
fresh conversation, ``/exit`` to quit.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import uuid

import waxell_observe as waxell

waxell.init()

_SESSION_ID = uuid.uuid4().hex  # stable for this REPL process; shared across all turns

from openai import OpenAI

_SYSTEM = (
    "You are a poetry assistant. When the user gives you a subject or mood, "
    "write a short, vivid poem — haiku, free verse, or a compact rhyming "
    "stanza, your choice. Keep poems under 12 lines. Remember earlier "
    "topics across turns so you can weave callbacks and contrast into new "
    "poems when it's interesting."
)


@waxell.observe(agent_name="streaming-chat", session_id=_SESSION_ID)
def chat_turn(history: list[dict], user_message: str) -> str:
    """One conversational turn with a streaming OpenAI response.

    Tokens are printed to stdout as they arrive. After the stream ends
    the full accumulated text is appended to ``history`` so the next
    turn has memory. Each call = one observed run in Waxell.
    """
    client = OpenAI()
    history.append({"role": "user", "content": user_message})
    ctx = waxell.get_current_context()
    if ctx is not None:
        ctx.record_user_message(content=user_message)

    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.7,
        messages=[{"role": "system", "content": _SYSTEM}, *history],
        stream=True,
    )

    print("assistant> ", end="", flush=True)
    chunks: list[str] = []
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            print(delta, end="", flush=True)
            chunks.append(delta)

    print("\n")  # blank line after the poem
    reply = "".join(chunks)
    history.append({"role": "assistant", "content": reply})
    if ctx is not None:
        ctx.record_agent_response(reply)
    return reply


def repl() -> None:
    print("streaming-chat — ask for a poem, or /reset, /exit.")
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
        chat_turn(history, user)


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write(
            "OPENAI_API_KEY is not set in .env — add it and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
