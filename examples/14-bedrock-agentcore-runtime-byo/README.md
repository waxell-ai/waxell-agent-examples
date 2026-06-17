# 14-bedrock-agentcore-runtime-byo

Your own Python agent code, deployed to **Amazon Bedrock AgentCore
Runtime** (the BYO-code path), with `waxell-observe` running **inside
the AgentCore microVM**. Distinct from:

- `12-bedrock-agent` — legacy managed Bedrock Agent service (we
  instrument from the calling process only)
- `13-bedrock-agentcore-harness` — managed AgentCore Harness (we
  instrument from the calling process only, plus a `GetHarness`
  metadata pull)
- this example — **`waxell-observe` runs inside AWS-managed compute**,
  so we capture LLM calls, tool calls, policy gates, and sub-agents
  with the same depth as a local agent

## What it shows

- `pip install waxell-observe` works inside an AgentCore Runtime
  microVM — wheels ship for cp312 / cp313 (set `runtime_type:
  PYTHON_3_13` in `.bedrock_agentcore.yaml`)
- `WAXELL_API_KEY` + `WAXELL_API_URL` get wired into the runtime via
  `agentcore deploy --env KEY=VALUE` flags
- Default `network_mode: PUBLIC` gives the microVM NAT egress to
  `api.waxell.dev` out of the box
- `@waxell.observe` + `ctx.check_policy` work unchanged — the microVM
  boundary is transparent to the SDK

## Prerequisites — AWS side

1. **`pipx install bedrock-agentcore-starter-toolkit`** — provides the
   `agentcore` CLI
2. **`pipx install uv`** — required by `direct_code_deploy` for
   dependency resolution
3. **IAM creds** for an account that can call `bedrock-agentcore-control`
   (the toolkit auto-creates the runtime execution role on first
   deploy)
4. **Bedrock model access** — Nova Lite (or whichever model you point
   `MODEL_ID` at) must be available in your region

## Setup

```bash
# from this folder
agentcore configure          # one-time: creates execution role + S3 bucket
agentcore deploy \
    --env "WAXELL_API_KEY=$WAXELL_API_KEY" \
    --env "WAXELL_API_URL=https://api.waxell.dev"
```

**⚠ Shell quoting gotcha:** if you set `WAXELL_API_KEY` inline in the
same command line as `agentcore deploy`, Bash may expand
`$WAXELL_API_KEY` *before* the prefix assignment runs and you end up
with an empty value in the runtime. Export it first or read it from
an env file:

```bash
export WAXELL_API_KEY=$(grep '^WAXELL_API_KEY=' ../../.env | cut -d= -f2-)
agentcore deploy --env "WAXELL_API_KEY=$WAXELL_API_KEY" --env "WAXELL_API_URL=https://api.waxell.dev"
```

Verify on the live runtime:

```bash
aws bedrock-agentcore-control get-agent-runtime \
    --agent-runtime-id <id> --query environmentVariables
```

Should show `WAXELL_API_KEY` with a non-empty value.

## Run

```bash
agentcore invoke '{"prompt": "what is the deepest known cave?"}'
```

## What to look for in the Waxell UI

```bash
wax runs list --limit 5
```

Run shows up under `agent_name=bedrock-agentcore-runtime-byo` with the
full shape: parent agent span + `chat amazon.nova-lite-v1:0 (llm)`
child span + prompt/response previews + real cost + token counts.
**Identical to running the same code on your laptop** — the only
difference is the agent process lives inside AWS's microVM.

Or open `https://app.waxell.dev/agent-executions`.

## Why this matters

For customers who use **managed Harness** (example 13), we can only
instrument from outside the runtime — observability is good, but
enforcement is limited to pre/post-call policies on the calling side.

For customers who use **BYO Runtime** (this example — and the more
common production path for non-trivial agents), `waxell-observe` runs
*inside* AWS's managed compute. That means:

- Every LLM call: instrumented
- Every tool call (MCP, function, anything): instrumented
- Every `ctx.check_policy(...)` gate: **enforced inside the runtime**
- Sub-agent lineage, memory ops, custom spans: captured

Same governance story as instrumenting any other Python agent — the
AgentCore Runtime boundary is invisible to the SDK.
