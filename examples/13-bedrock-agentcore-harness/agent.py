"""13-bedrock-agentcore-harness — invoke an Amazon Bedrock AgentCore Harness.

AgentCore is AWS's modular agent platform, distinct from the legacy
"Bedrock Agents" service. A *Harness* is a fully managed agent loop:
you configure a model, system prompt, optional tools/skills/memory,
and AWS runs the orchestration on its own infrastructure.

This is the AgentCore counterpart to ``01-hello-waxell`` and
``12-bedrock-agent``. Two lines do everything: ``waxell.init()``
registers the Bedrock-AgentCore auto-instrumentor (which patches
``botocore`` so every ``InvokeHarness`` call emits a span), and
``@waxell.observe(...)`` declares the entry point.

Required env (in the repo-level .env):

    AGENTCORE_HARNESS_ARN   — the ARN of a Harness you've created
                              via ``bedrock-agentcore-control.create_harness``
    AWS_ACCESS_KEY_ID       — IAM creds with bedrock-agentcore:InvokeHarness
    AWS_SECRET_ACCESS_KEY
    AWS_REGION              — defaults to us-east-1 if unset

Run::

    python scripts/setup_example.py 13-bedrock-agentcore-harness     # one-time
    source examples/13-bedrock-agentcore-harness/.venv/bin/activate
    python examples/13-bedrock-agentcore-harness/agent.py
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

_HARNESS_ARN = os.environ.get("AGENTCORE_HARNESS_ARN", "")
_REGION = os.environ.get("AWS_REGION", "us-east-1")
# InvokeHarness requires runtimeSessionId of min length 33 — prefix to be safe.
_SESSION_ID = "waxell-" + uuid.uuid4().hex


@waxell.observe(agent_name="bedrock-agentcore-harness", session_id=_SESSION_ID)
def chat_turn(user_message: str) -> str:
    """One conversational turn against a managed AgentCore Harness. We
    pass the same ``runtimeSessionId`` on every call so the managed
    session retains history server-side — AgentCore handles the
    threading, we just send the new message."""
    client = boto3.client("bedrock-agentcore", region_name=_REGION)
    ctx = waxell.get_current_context()
    if ctx is not None:
        ctx.record_user_message(content=user_message)

    response = client.invoke_harness(
        harnessArn=_HARNESS_ARN,
        runtimeSessionId=_SESSION_ID,
        messages=[{"role": "user", "content": [{"text": user_message}]}],
    )

    # The `stream` is an event stream with messageStart / contentBlockDelta /
    # contentBlockStop / messageStop / metadata events — same schema as
    # bedrock-runtime.ConverseStream. Concatenate delta text for the reply.
    parts: list[str] = []
    usage: dict | None = None
    for event in response["stream"]:
        delta = event.get("contentBlockDelta", {}).get("delta", {})
        text = delta.get("text")
        if text:
            parts.append(text)
        elif "metadata" in event:
            usage = event["metadata"].get("usage")
    reply = "".join(parts)

    if ctx is not None:
        ctx.record_agent_response(reply)

    return reply


def repl() -> None:
    global _SESSION_ID  # noqa: PLW0603 — /reset rotates the harness session
    print(
        f"bedrock-agentcore-harness — type a topic, or /reset, /exit.\n"
        f"  harnessArn={_HARNESS_ARN}\n"
        f"  region={_REGION}\n"
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
            _SESSION_ID = "waxell-" + uuid.uuid4().hex
            print(f"(new agentcore session: {_SESSION_ID})")
            continue
        reply = chat_turn(user)
        print(f"assistant> {reply}\n")


def main() -> None:
    missing = [
        name
        for name in (
            "AGENTCORE_HARNESS_ARN",
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
