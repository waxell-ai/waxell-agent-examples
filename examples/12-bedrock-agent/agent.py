"""12-bedrock-agent — invoke a managed Amazon Bedrock Agent.

This is the Bedrock-Agents counterpart to 01-hello-waxell. Two lines do
everything: ``waxell.init()`` registers the Bedrock-Agents auto-
instrumentor (which patches ``botocore`` so every ``InvokeAgent`` call
emits a span), and ``@waxell.observe(...)`` declares the entry point.

Subject: a conversational REPL backed by a real Bedrock Agent. Multi-
turn — we keep the same ``sessionId`` across turns so the Bedrock
managed session retains conversation state on AWS's side. Each turn =
one observed run, with the underlying ``InvokeAgent`` API call captured
as a child span.

Required env (in the repo-level .env):

    BEDROCK_AGENT_ID        — the 10-char agent id from the Bedrock console
    BEDROCK_AGENT_ALIAS_ID  — the alias id of the agent alias to invoke
    AWS_ACCESS_KEY_ID       — IAM user creds with bedrock:InvokeAgent
    AWS_SECRET_ACCESS_KEY
    AWS_REGION              — defaults to us-west-2 if unset

Run::

    python scripts/setup_example.py 12-bedrock-agent     # one-time
    source examples/12-bedrock-agent/.venv/bin/activate
    python examples/12-bedrock-agent/agent.py

Then type a message at the ``you>`` prompt. ``/reset`` starts a fresh
Bedrock session; ``/exit`` quits.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import waxell_observe as waxell

waxell.init()

import boto3

_AGENT_ID = os.environ.get("BEDROCK_AGENT_ID", "")
_AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "")
_REGION = os.environ.get("AWS_REGION", "us-west-2")
_SESSION_ID = uuid.uuid4().hex  # stable for this REPL process; threads to AWS


@waxell.observe(agent_name="bedrock-agent", session_id=_SESSION_ID)
def chat_turn(user_message: str) -> str:
    """One conversational turn against a real Bedrock Agent. We pass the
    same ``sessionId`` on every call so the managed session retains
    history server-side — Bedrock handles the threading, we just send
    the new user message."""
    client = boto3.client("bedrock-agent-runtime", region_name=_REGION)
    ctx = waxell.get_current_context()
    if ctx is not None:
        ctx.record_user_message(content=user_message)

    response = client.invoke_agent(
        agentId=_AGENT_ID,
        agentAliasId=_AGENT_ALIAS_ID,
        sessionId=_SESSION_ID,
        inputText=user_message,
        enableTrace=True,  # opt-in: returns the inner model/tool/KB trace
        # event stream alongside chunks. waxell-observe parses these into
        # child spans so the Waxell UI shows LLM token counts, tool calls,
        # and KB retrievals — not just the outer InvokeAgent call.
    )

    # InvokeAgent returns an EventStream of chunks — concatenate the
    # bytes payloads to get the full assistant text.
    parts: list[str] = []
    for event in response["completion"]:
        chunk = event.get("chunk")
        if chunk and "bytes" in chunk:
            parts.append(chunk["bytes"].decode("utf-8"))
    reply = "".join(parts)

    if ctx is not None:
        ctx.record_agent_response(reply)
    return reply


def repl() -> None:
    global _SESSION_ID  # noqa: PLW0603 — /reset rotates the Bedrock session
    print(
        f"bedrock-agent — type a topic, or /reset, /exit.\n"
        f"  agentId={_AGENT_ID}  aliasId={_AGENT_ALIAS_ID}  region={_REGION}\n"
        f"  sessionId={_SESSION_ID}"
    )
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
            _SESSION_ID = uuid.uuid4().hex
            print(f"(new bedrock session: {_SESSION_ID})")
            continue
        reply = chat_turn(user)
        print(f"assistant> {reply}\n")


def main() -> None:
    missing = [
        name
        for name in (
            "BEDROCK_AGENT_ID",
            "BEDROCK_AGENT_ALIAS_ID",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
        )
        if not os.environ.get(name)
    ]
    if missing:
        sys.stderr.write(
            "missing required env vars in .env: " + ", ".join(missing) + "\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
