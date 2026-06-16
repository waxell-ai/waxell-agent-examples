# 13-bedrock-agentcore-harness

A conversational REPL backed by an **Amazon Bedrock AgentCore Harness**.
AgentCore is AWS's modular agent platform — distinct from the legacy
"Bedrock Agents" service that example `12-bedrock-agent` covers. A
Harness is a fully managed agent loop: pick a model, set a system
prompt, optionally attach tools/skills/memory, and AWS runs the
orchestration server-side.

## What it shows

- The AgentCore tier of waxell-observe instrumentation.
  `waxell.init()` patches `botocore`, so every `InvokeHarness` call
  emits a span automatically.
- A stable `runtimeSessionId` per process — AgentCore manages session
  state server-side, so we just pass the same id on every turn and
  the agent remembers.
- Streaming response capture — the Harness returns the same event
  stream shape as `bedrock-runtime.ConverseStream`
  (`messageStart` → `contentBlockDelta` → `messageStop` → `metadata`),
  which our instrumentor sums into final span attrs (tokens, latency).

## What it does NOT show

- Custom tools or MCP gateways attached to the Harness — those are
  configured on the Harness itself via `bedrock-agentcore-control`.
  This example uses a minimal Harness with just a model + system prompt.
- The other AgentCore primitives — Browser, Code Interpreter, Memory
  ops, Evaluations. They have their own boto3 surfaces (`InvokeBrowser`,
  `InvokeCodeInterpreter`, `RetrieveMemoryRecords`, `Evaluate`) and
  show up as separate spans when called.

## Prerequisites — AWS side (one-time)

1. **Bedrock model access** — auto-granted on first invoke in modern
   accounts. If you're hitting `resourceNotFoundException` on the model
   ARN, check Bedrock console → Model access → grant Amazon Nova Lite
   (or your preferred model).
2. **Execution role for the Harness** — needs `bedrock:InvokeModel*` +
   `bedrock:Converse*` and `bedrock-agentcore.amazonaws.com` as the
   trust principal. Minimal policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "bedrock:InvokeModel",
           "bedrock:InvokeModelWithResponseStream",
           "bedrock:Converse",
           "bedrock:ConverseStream"
         ],
         "Resource": "*"
       },
       {
         "Effect": "Allow",
         "Action": [
           "logs:CreateLogGroup",
           "logs:CreateLogStream",
           "logs:PutLogEvents",
           "logs:DescribeLogStreams"
         ],
         "Resource": "*"
       }
     ]
   }
   ```
3. **Create the Harness** — easiest via boto3:
   ```python
   import boto3
   c = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
   r = c.create_harness(
       harnessName="my_test_harness",                  # alphanumeric+underscore only
       executionRoleArn="arn:aws:iam::ACCT:role/...",  # from step 2
       model={"bedrockModelConfig": {"modelId": "amazon.nova-lite-v1:0"}},
       systemPrompt=[{"text": "You are a concise research assistant..."}],
   )
   print(r["harness"]["arn"])
   ```
   Then poll `get_harness(harnessId=...)` until `status == "READY"`
   (usually 30–60s while AWS spins up the runtime).
4. **IAM creds for the invoker** — your local IAM user needs at minimum:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["bedrock-agentcore:InvokeHarness"],
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
#   AWS_REGION=us-east-1
#   AGENTCORE_HARNESS_ARN=arn:aws:bedrock-agentcore:us-east-1:ACCT:harness/NAME-RANDOM

python scripts/setup_example.py 13-bedrock-agentcore-harness
```

## Run

```bash
source examples/13-bedrock-agentcore-harness/.venv/bin/activate
python examples/13-bedrock-agentcore-harness/agent.py
```

## What to look for in the Waxell UI

```bash
wax runs list --limit 5
```

You should see one run per `chat_turn` call under
`agent_name=bedrock-agentcore-harness`. Drill in with
`wax runs show <id>` and you'll see:

- `waxell.agentcore.harness` span (the `InvokeHarness` API call)
- `harness.arn`, `runtime_session_id`, input/output text, token usage
- The full streamed assistant response

Or open `https://app.waxell.dev/agent-executions` and filter by
`agent_name=bedrock-agentcore-harness`.

## The pattern, in 4 lines

```python
import waxell_observe as waxell
waxell.init()

@waxell.observe(agent_name="bedrock-agentcore-harness", session_id=session_id)
def chat_turn(user_message): ...
```

Identical to `01-hello-waxell` — only the body changed. Switching from
"OpenAI chat completion" to "AWS AgentCore Harness" is a body change,
not a framework change. That's the point.
