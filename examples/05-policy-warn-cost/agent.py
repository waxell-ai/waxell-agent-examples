"""05-policy-warn-cost — creative-writing REPL with a budget warn policy.

Demonstrates a ``warn``-disposition budget policy: the run always
completes, but when a single turn exceeds the token / cost threshold the
Waxell governance plane records a warning incident.  The REPL prints a
"(cost warning)" notice after each turn by inspecting the most recent
run via ``wax runs list``.

Subject: a creative-writing partner that elaborates richly on any prompt.
The system prompt instructs the model to write long, evocative responses
so the 500-token / $0.01 per-workflow threshold is easy to trip.

Run::

    ./setup.sh                       # one-time
    source .venv/bin/activate
    python agent.py

At the ``you>`` prompt try something like::

    you> write me a 500-word gothic horror story set in a lighthouse
    you> continue the story, describing the creature in vivid detail
    you> /reset
    you> /exit
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import waxell_observe as waxell

waxell.init()

from openai import OpenAI

_SYSTEM = (
    "You are a passionate creative-writing partner. When given any prompt, "
    "you always write a LONG, richly detailed, evocative response — at minimum "
    "four or five paragraphs with vivid sensory language, compelling characters, "
    "and layered atmosphere. Never give a short reply; the user is here for "
    "immersive prose. Continue and build on previous turns when the conversation "
    "has context."
)


@waxell.observe(agent_name="policy-warn-cost")
def chat_turn(history: list[dict], user_message: str) -> str:
    """One conversational turn. Each call = one observed run.

    ``history`` is mutated in place — the new user message and the
    assistant reply are appended so the next turn has full context.
    """
    client = OpenAI()
    history.append({"role": "user", "content": user_message})
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.9,
        messages=[{"role": "system", "content": _SYSTEM}, *history],
    )
    reply = resp.choices[0].message.content or ""
    history.append({"role": "assistant", "content": reply})
    return reply


def _check_warn_incident() -> bool:
    """Return True if the most recent run has a warning incident.

    Uses ``wax runs list --limit 1 --format=json`` to fetch the latest
    run, then checks its ``incident_count`` or ``policy_results`` fields.
    Returns False (silently) if the CLI is unavailable or the output is
    unparsable — the demo still works, the user just won't see the inline
    notice.
    """
    try:
        out = subprocess.check_output(
            ["wax", "runs", "list", "--limit", "1", "--format=json"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        runs = json.loads(out)
        if not runs:
            return False
        latest = runs[0] if isinstance(runs, list) else runs
        # Field names vary slightly across CLI versions — try both.
        incident_count = (
            latest.get("incident_count")
            or latest.get("incidents")
            or latest.get("warning_count")
            or 0
        )
        if isinstance(incident_count, list):
            incident_count = len(incident_count)
        return int(incident_count) > 0
    except Exception:  # noqa: BLE001
        return False


def repl() -> None:
    print("policy-warn-cost — creative-writing partner with budget warn policy.")
    print("Type a prompt, or /reset to start fresh, /exit to quit.")
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
            print("(conversation reset)")
            print()
            continue

        reply = chat_turn(history, user)
        print(f"\nassistant> {reply}\n")

        if _check_warn_incident():
            print("(cost warning: budget policy 'example-cost-warn' fired — "
                  "run completed but a warning incident was recorded)")
            print("  -> wax runs list --limit 1  # to see the run")
            print("  -> wax runs show <id>        # to see the incident detail")
            print()


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write(
            "OPENAI_API_KEY is not set in .env — add it and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
