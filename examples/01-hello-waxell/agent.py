"""01-hello-waxell — conversational REPL with the two-line decorator.

This is the smallest possible Waxell-instrumented agent. Two lines do
everything: ``waxell.init()`` registers the OpenAI auto-instrumentor,
and ``@waxell.observe(...)`` declares the entry point. Every OpenAI
call this agent makes is captured as a span on a run named after the
decorator's ``agent_name`` — no manual span work, no callback handlers.

Subject: a conversational trivia bot. Multi-turn — conversation history
is threaded into every LLM call so the model remembers what you've
already discussed.

Run::

    ./setup.sh                       # one-time
    source .venv/bin/activate
    python agent.py

Then type messages at the ``you>`` prompt. Use ``/reset`` to start a
fresh conversation, ``/exit`` to quit.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import waxell_observe as waxell

waxell.init()

from openai import OpenAI

_SYSTEM = (
    "You are a trivia companion. Answer the user's question with a tight, "
    "verifiable fact and one follow-up question to deepen the topic. Keep "
    "context across turns — refer back to earlier topics when relevant."
)


@waxell.observe(agent_name="hello-waxell")
def chat_turn(history: list[dict], user_message: str) -> str:
    """One conversational turn. ``history`` is the running message list;
    we append the new user message and the assistant's reply to it in
    place so the next turn sees both. Each turn = one observed run."""
    client = OpenAI()
    history.append({"role": "user", "content": user_message})
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=[{"role": "system", "content": _SYSTEM}, *history],
    )
    reply = resp.choices[0].message.content or ""
    history.append({"role": "assistant", "content": reply})
    return reply


def repl() -> None:
    print("hello-waxell — type a topic, or /reset, /exit.")
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
            print("(conversation reset)")
            continue
        reply = chat_turn(history, user)
        print(f"assistant> {reply}\n")


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write(
            "OPENAI_API_KEY is not set in .env — add it and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
