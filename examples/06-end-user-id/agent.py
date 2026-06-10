"""06-end-user-id — per-end-user attribution with a conversational REPL.

This example shows how to tag every run with the end user who triggered
it. The same agent serves multiple end users (alice@example.com,
bob@example.com). Each REPL turn forwards the current ``end_user_id``
through ``@waxell.observe(end_user_id=...)`` so Waxell tags every run
with the user. The controlplane can then filter runs by end-user.

Key points:
- ``end_user_id`` is a first-class ``@waxell.observe`` kwarg — the
  decorator intercepts it (because it appears in ``_CONTEXT_PARAMS`` and
  is NOT declared in the function signature) and forwards it to
  ``WaxellContext`` before the function body even runs.
- Conversation history is kept PER USER in a dict keyed by email.
  Switching users with ``/switch`` preserves each user's history.
- The tutor remembers what each user said they were studying because
  the history dict is never cleared on a switch.

REPL commands::

    /whoami               — print the current end_user_id
    /switch <email>       — change to a different end user
    /reset                — clear the current user's conversation history
    /exit                 — quit

Run::

    ./setup.sh                       # one-time
    source .venv/bin/activate
    python agent.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import uuid

import waxell_observe as waxell
from waxell_observe import PolicyViolationError

waxell.init()

_SESSION_ID = uuid.uuid4().hex  # stable for this REPL process; shared across all turns

from openai import OpenAI

_SYSTEM = (
    "You are a personal study tutor. Your job is to help the user learn "
    "whatever subject they are working on. Ask what they are studying if "
    "you don't know yet. Keep track of their subject and progress across "
    "turns — refer back to what they told you earlier when relevant. "
    "Keep answers concise but genuinely useful."
)

# Per-user conversation history.  Key = end_user_id, value = list[dict].
_histories: dict[str, list[dict]] = {}


@waxell.observe(agent_name="end-user-id", session_id=_SESSION_ID)
def chat_turn(history: list[dict], user_message: str) -> str:
    """One conversational turn.

    ``end_user_id`` is NOT in this signature — that's intentional. The
    decorator intercepts it from call-time kwargs (because it's in
    ``_CONTEXT_PARAMS``) and passes it to ``WaxellContext``, tagging the
    run without it ever reaching this function body.
    """
    client = OpenAI()
    history.append({"role": "user", "content": user_message})
    ctx = waxell.get_current_context()
    if ctx is not None:
        ctx.record_user_message(content=user_message)
    # This example uses gpt-4o (not gpt-4o-mini) because the
    # end-user-budget policy reads cumulative spend from
    # WaxellUserActivity.cost_cents — an INTEGER field. gpt-4o-mini
    # turns cost ~$0.0001 each, which rounds to 0 integer cents and
    # never accumulates, so a 1¢ cap would never trip. gpt-4o turns
    # cost ~1-2¢ each, so bob's 1¢ cap exhausts on the very first
    # turn — which is the point of the demo.
    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.4,
        messages=[{"role": "system", "content": _SYSTEM}, *history],
    )
    reply = resp.choices[0].message.content or ""
    history.append({"role": "assistant", "content": reply})
    if ctx is not None:
        ctx.record_agent_response(reply)
    return reply


def repl() -> None:
    current_user: str = "anonymous"
    print("end-user-id tutor — type a message, or /whoami, /switch <email>, /reset, /exit.")
    print(f"current user: {current_user}\n")

    while True:
        try:
            raw = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        if raw == "/exit":
            break

        if raw == "/whoami":
            print(f"(current user: {current_user})\n")
            continue

        if raw.startswith("/switch "):
            new_user = raw[len("/switch "):].strip()
            if not new_user:
                print("(usage: /switch <email>)\n")
                continue
            current_user = new_user
            print(f"(switched to {current_user})\n")
            continue

        if raw == "/reset":
            _histories[current_user] = []
            print(f"(conversation reset for {current_user})\n")
            continue

        # Retrieve or create this user's history.
        history = _histories.setdefault(current_user, [])

        # Pass the current user as BOTH `end_user_id` (the policy-side
        # sub-user identity used by end-user-* policy handlers) AND
        # `user_id` (the observability-side identifier that surfaces as
        # the "USER" field in the controlplane UI). The SDK keeps these
        # separate because B2B apps often need to distinguish the
        # logged-in operator from the end customer; for this single-user
        # demo we set them to the same value so the switch is visible in
        # both places. Both are in _CONTEXT_PARAMS and absent from
        # chat_turn's signature, so the decorator intercepts both and
        # forwards them to WaxellContext without polluting the function.
        try:
            reply = chat_turn(
                history,
                raw,
                end_user_id=current_user,
                user_id=current_user,
            )
            print(f"assistant> {reply}\n")
        except PolicyViolationError as exc:
            # The end-user-budget policy fires when this end-user has
            # exceeded their monthly_budget_cap_cents. The run is recorded
            # as Blocked in the controlplane; the REPL keeps running so
            # the user can /switch to a different end-user and continue.
            print(f"assistant> ⛔ blocked for {current_user}: {exc}\n")
            # Drop the turn from history so the next turn doesn't replay
            # the user message into the LLM context.
            if history and history[-1].get("role") == "user":
                history.pop()


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write(
            "OPENAI_API_KEY is not set in .env — add it and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
