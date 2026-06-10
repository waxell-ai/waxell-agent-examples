# 02-anthropic-tool-use

A travel concierge REPL where Claude has two tools — `get_weather(city)`
and `get_local_time(timezone)` — and decides when to call them.
Waxell's Anthropic auto-instrumentor captures every tool call as a child
span inside the run, with no manual span code.

## What it shows

- The same two-line pattern from `01-hello-waxell`, now with the
  Anthropic Messages API instead of OpenAI.
- Anthropic's `tools=` parameter and the `tool_use` / `tool_result`
  message cycle that drives multi-step tool calls.
- The full agentic loop: the model may call one tool, several tools, or
  none — depending on what the user asks.
- Each tool call appears as an automatic child span in the Waxell run.
  You get span-level visibility into which tool fired, what input it
  received, and what it returned — without writing a single span by hand.
- Multi-turn conversation — history is threaded across turns so the model
  remembers earlier destinations and preferences.

## What it does NOT show

- Custom spans, manual instrumentation, streaming, sub-agents, retrieval,
  or policy enforcement. See `03-…` through `10-…` for each of those.

## Setup

```bash
# from the repo root, if you haven't already
./scripts/seed-env-from-wax.sh
$EDITOR .env                     # paste your ANTHROPIC_API_KEY

# from this folder
./setup.sh
```

`setup.sh` creates a per-example `.venv/`, installs deps, and verifies
your `.env` has the needed keys. No policies needed for this example.

## Run

```bash
source .venv/bin/activate
python agent.py
```

You'll get a `you>` prompt. Try inputs that force one or both tools:

```
you> what's the weather in Tokyo and what time is it there?
you> is it a good time to visit London given the weather?
you> compare the weather in Paris and Bangkok
you> /reset
you> it's early morning in New York — what should I pack for a day trip?
you> /exit
```

The first prompt ("Tokyo weather and time") reliably triggers both tools
in a single turn and is the best starting point to verify everything works.

## What to look for in the Waxell UI

After a few turns:

```bash
wax runs list --limit 5
```

You should see one run per `chat_turn` call, all under
`agent_name=anthropic-tool-use`. Drill into a run that asked about
weather and time:

```bash
wax runs show <id>
```

Inside that run you'll see:

- The top-level Anthropic `messages.create` call as an LLM span
- One child span per tool call (`get_weather`, `get_local_time`) showing
  the exact inputs the model passed and the JSON the stub returned
- A second `messages.create` span for the follow-up call that received
  the tool results and produced the final reply
- Token in/out + cost across the full turn
- The complete message history (if `WAXELL_CAPTURE_CONTENT=1`)

Or open `https://app.waxell.dev/agent-executions` and filter by
`agent_name=anthropic-tool-use`.

## The pattern, in 4 lines

```python
import waxell_observe as waxell
waxell.init()

@waxell.observe(agent_name="my-agent")
def run_turn(history, user_message): ...
```

`waxell.init()` registers the Anthropic auto-instrumentor alongside the
OpenAI one. No further changes are needed — tool spans appear
automatically once the instrumentor is active.
