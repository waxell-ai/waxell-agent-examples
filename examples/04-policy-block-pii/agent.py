"""04-policy-block-pii — conversational support-intake agent with PII blocking.

Demonstrates Waxell's preventive ``content`` policy: when the user types a
US Social Security Number (pattern NNN-NN-NNNN), the ``example-pii-block``
policy fires a ``block`` disposition *before* the LLM call completes, and a
``PolicyViolationError`` is raised.  The REPL catches it, prints a refusal
message, and continues — the run is recorded as BLOCKED in the Waxell
controlplane.

Subject: customer-support intake.  The agent greets the user, then handles
free-form support requests as a normal LLM chat — unless PII is detected.

Run::

    ./setup.sh                       # one-time: push policies + verify
    source .venv/bin/activate
    python agent.py

Commands at the ``you>`` prompt:

- ``/reset``   — start a fresh conversation
- ``/exit``    — quit

To trigger the block, type something like::

    you> Hi, my SSN is 123-45-6789, can you look up my account?
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
from waxell_observe import PolicyViolationError
from waxell_observe.instrumentors._guard import PromptGuardError

_SYSTEM = (
    "You are a helpful customer-support intake assistant. "
    "Greet the user, ask how you can help, then address their request clearly "
    "and concisely. You handle general support questions: account issues, "
    "billing inquiries, product questions, and troubleshooting. "
    "Keep responses under 150 words. Stay in character across turns."
)

_REFUSAL = (
    "I can't process that — it looks like your message contains sensitive "
    "personal information (such as a Social Security Number). For your "
    "security, please contact us through a secure channel: "
    "https://support.example.com/secure or call 1-800-555-0100."
)


@waxell.observe(agent_name="policy-block-pii")
def chat_turn(history: list[dict], user_message: str) -> str:
    """One conversational turn.  ``history`` is the running message list;
    we append the new user message and the assistant's reply in place so the
    next turn sees both.  Each turn = one observed run.

    If a ``PolicyViolationError`` or ``PromptGuardError`` is raised by the
    Waxell policy layer, we re-raise it so the REPL can handle it gracefully
    without marking the function body as the failure site.
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
    print("policy-block-pii — support intake agent.")
    print("Type a support question, /reset to restart, /exit to quit.")
    print()
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

        try:
            reply = chat_turn(history, user)
            print(f"assistant> {reply}\n")
        except (PolicyViolationError, PromptGuardError) as exc:
            # Remove the user message we just appended — this turn is blocked
            # and should not pollute the conversation history.
            if history and history[-1]["role"] == "user":
                history.pop()
            print(f"assistant> {_REFUSAL}\n")
            print(f"[waxell] run blocked by policy: {exc}\n")


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write(
            "OPENAI_API_KEY is not set in .env — add it and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
