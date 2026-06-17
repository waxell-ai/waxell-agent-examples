"""14-bedrock-agentcore-runtime-byo — Waxell-instrumented agent deployed
to Amazon Bedrock AgentCore Runtime via the BYO-code path.

Unlike example 12 (managed Bedrock Agent) and example 13 (managed
AgentCore Harness), this example deploys YOUR Python agent code to
AgentCore Runtime. The microVM that AWS spins up runs your code
directly — so ``waxell-observe`` runs INSIDE the runtime with full
visibility on every LLM call.

**Policies are managed in Waxell — not in code.** The agent does NOT
contain any inline PII / content checks. A content policy (PII
detection, denied topics, etc.) is registered on the Waxell
controlplane (via the Govern UI or ``wax policies push``). The SDK's
content handler fetches active policies at request time, scans the
inputs, and raises ``PolicyViolationError`` *before* the Bedrock
Converse call ever lands. The agent catches and returns a refusal —
that's the entire production pattern. The blocked run + policy
violation show up in the Waxell run UI under the Governance panel.

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
``api.waxell.dev``. The SSN call lands as a BLOCKED run with the
policy violation recorded; the Bedrock call never fires.
"""

from __future__ import annotations

import os

import waxell_observe as waxell
from waxell_observe import PolicyViolationError
from waxell_observe.instrumentors._guard import PromptGuardError

waxell.init()

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = "amazon.nova-lite-v1:0"


@waxell.observe(agent_name="bedrock-agentcore-runtime-byo")
def chat_turn(user_message: str) -> str:
    """One LLM turn against Bedrock Nova Lite. waxell-observe handles
    policy enforcement transparently: it fetches active content
    policies from the controlplane during @observe context entry (on
    record_user_message) and raises PolicyViolationError before
    ``chat_turn``'s body ever runs if any pre-flight rule fires."""
    ctx = waxell.get_current_context()
    if ctx is not None:
        ctx.record_user_message(content=user_message)

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
    ``context`` (session info). The PolicyViolationError catch lives
    HERE — not inside ``chat_turn`` — because the SDK's pre-flight
    check fires during the @observe context's entry phase, before
    the decorated function's body executes. Catching at the outer
    call site is the canonical pattern for tenant-managed content
    policies."""
    user_message = payload.get("prompt", "")
    try:
        reply = chat_turn(user_message)
    except (PolicyViolationError, PromptGuardError) as exc:
        # Pre-flight content policy blocked the call — Waxell already
        # recorded the violation server-side. Surface the actual policy
        # reason from the exception (e.g. "Input content violations:
        # PII detected: ssn") so the caller knows what to fix.
        reply = f"Request blocked by Waxell policy: {exc}"
    yield reply


if __name__ == "__main__":
    app.run()
