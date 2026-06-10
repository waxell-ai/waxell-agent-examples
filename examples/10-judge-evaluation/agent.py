"""10-judge-evaluation — customer-support REPL with LLM-judge governance.

This example shows the most sophisticated Waxell governance pattern: an
LLM-judge policy that grades every reply the agent produces.  The agent
itself is a simple customer-support assistant.  After each turn completes,
Waxell's ``quality`` policy handler sends the reply to a separate evaluator
model (``gpt-4o``) which scores it on empathy and actionability.  If the
score falls below the 0.65 threshold the policy records a WARN incident
— visible in the Governance panel — without blocking the conversation.

The agent does NOT call the judge itself.  The ``example-tone-judge``
policy (defined in ``policies.py``) fires server-side after every run.

Run::

    ./setup.sh                       # one-time: installs deps + pushes policy
    source .venv/bin/activate
    python agent.py

Then type customer messages at the ``you>`` prompt.  Use ``/reset`` to
start a fresh conversation, ``/exit`` to quit.

To see a low-score incident deliberately, try an abrupt, unhelpful reply
by keeping your test message terse — e.g. "I want a refund" — and observe
whether the Governance panel flags the response.
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
    "You are a customer-support specialist for a consumer electronics retailer. "
    "A customer has contacted you with a problem or complaint. "
    "Your replies must: "
    "(1) Acknowledge the customer's frustration with genuine empathy, "
    "(2) Apologise where appropriate, "
    "(3) Offer a clear, concrete next step or resolution path (e.g. refund "
    "process, replacement steps, escalation path, timeline). "
    "Keep responses focused and under 150 words. "
    "Maintain context across turns — refer back to earlier details when relevant."
)


@waxell.observe(agent_name="judge-evaluation")
def chat_turn(history: list[dict], user_message: str) -> str:
    """One conversational turn.

    ``history`` is the running message list; we append the new user message
    and the assistant reply in place so each subsequent turn sees the full
    conversation.  Each call = one observed run, which the ``example-tone-judge``
    policy grades after completion.
    """
    client = OpenAI()
    history.append({"role": "user", "content": user_message})
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[{"role": "system", "content": _SYSTEM}, *history],
    )
    reply = resp.choices[0].message.content or ""
    history.append({"role": "assistant", "content": reply})
    return reply


def repl() -> None:
    print("judge-evaluation — customer-support agent with LLM-judge governance.")
    print("Type a customer issue, or /reset to start over, /exit to quit.\n")
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
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write(
            "OPENAI_API_KEY is not set in .env — add it and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
