"""14-bedrock-agentcore-runtime-byo — Waxell-instrumented agent deployed
to Amazon Bedrock AgentCore Runtime via the BYO-code path.

Unlike example 12 (managed Bedrock Agent) and example 13 (managed
AgentCore Harness), this example deploys YOUR Python agent code to
AgentCore Runtime. The microVM that AWS spins up runs your code
directly — so ``waxell-observe`` runs INSIDE the runtime with full
visibility on every LLM call.

This example demonstrates BOTH halves:

1. **Observability** — the agent makes a Bedrock Converse call, the
   instrumentor captures the LLM child span with real model id,
   tokens, and cost. Same shape as ``01-hello-waxell``.

2. **Enforcement (input-side)** — an inline PII guard scans the input
   for an SSN pattern and short-circuits before the LLM call fires.
   The guard runs inside the AgentCore microVM, proving Waxell-style
   policy enforcement works in AWS-managed compute.

Deployment is two commands::

    agentcore configure   # one-time
    export WAXELL_API_KEY=...
    agentcore deploy \
        --env "WAXELL_API_KEY=$WAXELL_API_KEY" \
        --env "WAXELL_API_URL=https://api.waxell.dev"

Then exercise both paths::

    agentcore invoke '{"prompt": "what is the deepest known cave?"}'
    agentcore invoke '{"prompt": "my SSN is 123-45-6789"}'

The clean call lands as a successful run with an LLM child span at
``api.waxell.dev``. The SSN call returns the refusal text and never
makes the Bedrock call.
"""

from __future__ import annotations

import os
import re

import waxell_observe as waxell

waxell.init()

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = "amazon.nova-lite-v1:0"
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_REFUSAL = (
    "I can't process that — your message looked like it contained a "
    "Social Security Number, which the agent's PII policy blocks."
)


@waxell.observe(agent_name="bedrock-agentcore-runtime-byo")
def chat_turn(user_message: str) -> str:
    """One LLM turn against Bedrock Nova Lite, guarded by an inline
    PII check. Decorated with @observe so the run + LLM child span
    surface in the Waxell controlplane."""
    ctx = waxell.get_current_context()
    if ctx is not None:
        ctx.record_user_message(content=user_message)

    # Pre-flight PII guard — short-circuits before the LLM call when
    # the input matches an SSN pattern. The fact that this branch
    # fires inside the AgentCore Runtime microVM proves enforcement
    # works in AWS-managed compute.
    if _SSN_RE.search(user_message):
        if ctx is not None:
            ctx.record_agent_response(_REFUSAL)
        return _REFUSAL

    client = boto3.client("bedrock-runtime", region_name=REGION)
    response = client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": user_message}]}],
    )
    reply = response["output"]["message"]["content"][0]["text"]

    if ctx is not None:
        ctx.record_agent_response(reply)
    return reply


@app.entrypoint
async def invoke(payload, context):
    """AgentCore Runtime entry point. Receives ``payload`` (dict) +
    ``context`` (session info). Streams the reply back via yield."""
    user_message = payload.get("prompt", "")
    reply = chat_turn(user_message)
    yield reply


if __name__ == "__main__":
    app.run()
