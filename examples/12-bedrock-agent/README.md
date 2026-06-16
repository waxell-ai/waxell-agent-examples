# 12-bedrock-agent

A conversational REPL backed by a real **Amazon Bedrock Agent**. Same
two-line Waxell pattern as `01-hello-waxell`, but the LLM call is
replaced by `bedrock-agent-runtime.invoke_agent(...)` — the managed
agent orchestration layer that runs on AWS's side, with optional
action groups, knowledge bases, and guardrails.

## What it shows

- The Bedrock-Agents auto-instrumentor: `waxell.init()` patches
  `botocore`, so every `InvokeAgent` call emits a span automatically.
  No manual span work.
- Multi-turn conversation — we keep the same `sessionId` across turns,
  so Bedrock's managed session retains conversation state server-side.
- The Bedrock-Agents tier sitting alongside the direct-LLM tier:
  this is the AWS-managed orchestration layer, distinct from a raw
  `bedrock-runtime.Converse` call.

## What it does NOT show

- Action groups (Lambda-backed tools), knowledge bases, or guardrails.
  Those are configured on the Agent itself in the Bedrock console;
  once attached, the same `InvokeAgent` call captures them in trace
  events. This example uses a minimal Agent with none of those, on
  purpose — it's the smallest possible Bedrock-Agents demo.

## Prerequisites — AWS side (one-time)

1. **Model access** — Bedrock console → "Model access" (left nav) →
   request Anthropic Claude 3.5 Sonnet (or your preferred model) in
   the region you'll use. Usually instant for established accounts.
2. **Create the Agent** — Bedrock console → "Agents" → "Create Agent":
   - Name: anything (e.g. `waxell-test-agent`).
   - Service role: **Create and use a new service role** (AWS
     auto-creates `AmazonBedrockExecutionRoleForAgents_…`).
   - Foundation model: Claude 3.5 Sonnet v2 (or your choice).
   - Instructions: paste anything sensible — e.g.
     *"You are a concise research assistant. Answer in 1-2 sentences."*
   - Skip action groups, knowledge bases, guardrails.
   - Save → **Prepare** (top-right) → wait ~10s → **Create alias**
     pointing at the DRAFT version (name the alias anything, e.g.
     `live`).
3. Copy the **Agent ID** (10-char string) and **Agent alias ID** off
   the Agent overview page.
4. **IAM credentials** — an IAM user (or role) with at minimum:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": [
         "bedrock:InvokeAgent",
         "bedrock:InvokeModel",
         "bedrock:Converse"
       ],
       "Resource": "*"
     }]
   }
   ```

## Setup

```bash
# from the repo root, if you haven't already
python scripts/seed_env_from_wax.py

# add these to .env at the repo root:
#   AWS_ACCESS_KEY_ID=...
#   AWS_SECRET_ACCESS_KEY=...
#   AWS_REGION=us-west-2              # defaults to us-west-2 if unset
#   BEDROCK_AGENT_ID=XXXXXXXXXX
#   BEDROCK_AGENT_ALIAS_ID=TSTALIASID  # see "Which alias ID?" below

python scripts/setup_example.py 12-bedrock-agent
```

### Which alias ID?

For first-run testing, use the literal string **`TSTALIASID`** — every
Bedrock Agent has a built-in test alias with that ID that always
points at the current DRAFT version. This means whatever model + prompt
is in your agent right now is what `InvokeAgent` will hit.

For production: create a real numbered alias (e.g. `live`). The
gotcha to know: Bedrock Agent versions are **immutable**, and the
console's `Create Alias` button snapshots the *last* numbered version
— **not** the current DRAFT. If you change the model in DRAFT, you
must `PrepareAgent` first then create a fresh alias to capture the
new state. Until then, the existing alias still routes to the old
model. The `TSTALIASID` flow sidesteps this whole problem during
development.

## Run

```bash
source examples/12-bedrock-agent/.venv/bin/activate
python examples/12-bedrock-agent/agent.py
```

You'll get a `you>` prompt. Try:

```
you> what is the deepest known cave?
you> tell me more about how it was mapped
you> /reset
you> totally different topic — sourdough starters
you> /exit
```

`/reset` rotates the local `sessionId`, so Bedrock starts a new
managed session and the agent forgets prior turns.

## What to look for in the Waxell UI

```bash
wax runs list --limit 5
```

You should see one run per `chat_turn` call under
`agent_name=bedrock-agent`. Drill in with `wax runs show <id>` and
you'll see:

- The Bedrock `InvokeAgent` call captured as a span
- `aws.bedrock.agent.id` + `aws.bedrock.agent.alias_id` + `aws.region`
  on the span
- The user input + concatenated assistant output

Or open `https://app.waxell.dev/agent-executions` and filter by
`agent_name=bedrock-agent`.

## The pattern, in 4 lines

```python
import waxell_observe as waxell
waxell.init()

@waxell.observe(agent_name="bedrock-agent", session_id=session_id)
def chat_turn(user_message): ...
```

Same shape as `01-hello-waxell` — only the body changed. That's the
point: switching providers is a body change, not a framework change.
