# 14-bedrock-agentcore-runtime-byo

Your own Python agent code, deployed to **Amazon Bedrock AgentCore
Runtime** (the BYO-code path), with `waxell-observe` running **inside
the AgentCore microVM**. Distinct from:

- `12-bedrock-agent` — legacy managed Bedrock Agent service (we
  instrument from the calling process only)
- `13-bedrock-agentcore-harness` — managed AgentCore Harness (we
  instrument from the calling process + a `GetHarness` lookup; we
  can't run code inside the harness)
- this example — **`waxell-observe` runs inside AWS-managed compute**,
  so we capture LLM calls AND **enforce controlplane-managed policies**
  with the same depth as a local agent

## What it shows

- `pip install waxell-observe` works inside an AgentCore Runtime
  microVM — wheels ship for cp312 / cp313 (set `runtime_type:
  PYTHON_3_13` in `.bedrock_agentcore.yaml`)
- `WAXELL_API_KEY` + `WAXELL_API_URL` get wired into the runtime via
  `agentcore deploy --env KEY=VALUE` flags
- Default `network_mode: PUBLIC` gives the microVM NAT egress to
  `api.waxell.dev` out of the box
- `@waxell.observe` works unchanged — the microVM boundary is
  transparent to the SDK
- **Tenant-managed content policies enforce inside the runtime.** No
  inline gating in the agent code. A `PII Protection` content policy
  created in the Waxell UI (or via `wax policies push`) is fetched at
  request time, scans inputs, and raises `PolicyViolationError` before
  the Bedrock Converse call ever lands. The agent catches at the outer
  call site and returns a clean refusal. Switching the policy between
  BLOCK / WARN in the UI changes behavior live without redeploying the
  agent.

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

## Prerequisites — Waxell side

In the Waxell UI: `Govern → Policies → Create Policy` with category
`Content`, enable `Scan Inputs`, enable `PII Detection`. Scope can be
global or limited to this agent name. The policy starts firing
immediately — no agent redeploy needed.

## Setup

```bash
# from this folder
agentcore configure          # one-time: creates execution role + S3 bucket
export WAXELL_API_KEY=$(grep '^WAXELL_API_KEY=' ../../.env | cut -d= -f2-)
agentcore deploy \
    --env "WAXELL_API_KEY=$WAXELL_API_KEY" \
    --env "WAXELL_API_URL=https://api.waxell.dev"
```

**⚠ Shell quoting gotcha:** if you set `WAXELL_API_KEY` inline in the
same command line as `agentcore deploy`, Bash may expand
`$WAXELL_API_KEY` *before* the prefix assignment runs and you end up
with an empty value in the runtime. **Export it first** (as shown
above) — single-line inline assignment loses the value.

Verify the env vars landed on the live runtime:

```bash
aws bedrock-agentcore-control get-agent-runtime \
    --agent-runtime-id <id> --query environmentVariables
```

Both `WAXELL_API_KEY` and `WAXELL_API_URL` should show non-empty.

## Run

Clean prompt — full LLM trace:

```bash
agentcore invoke '{"prompt": "what is the deepest known cave?"}'
```

Policy-triggering prompt — refusal returned, Bedrock never called:

```bash
agentcore invoke '{"prompt": "my SSN is 123-45-6789"}'
```

The second call comes back with the refusal text from the agent
(set in `_REFUSAL`), and the run lands in Waxell as BLOCKED with two
`policy:PII Protection` governance spans.

## What to look for in the Waxell UI

```bash
wax runs list --limit 5
```

The clean run shows up as `agent_name=bedrock-agentcore-runtime-byo`
with the full shape: parent agent span + `chat amazon.nova-lite-v1:0`
LLM child span + IO events. Real cost + token counts.

The blocked run shows up with `status=error`, 0 tokens, 2
`policy:PII Protection` governance spans, and the Governance panel
populated with the policy violation linked back to the policy you
created in Govern. The user input is still in the run's Inputs panel
even though no LLM call was made.

Open `https://app.waxell.dev/agent-executions` for the visual view.

## The production pattern, in one paragraph

The agent code makes a Bedrock call and catches `PolicyViolationError`
at the outer call site. **That's it.** No PII checks, no SSN regex, no
denied-topic lists, no inline content scanning. Policies are tenant
configuration on the Waxell controlplane, managed by your governance /
security team in the UI. The `waxell-observe` SDK inside the microVM
fetches active policies at run start, applies them to the agent's
inputs, and raises a typed exception before the foundation-model
provider ever sees the request. Block / warn switching, scope
narrowing, new policy categories — all editable in the UI, no agent
code changes.
