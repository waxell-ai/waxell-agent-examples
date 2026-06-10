# 01-hello-waxell

The smallest possible Waxell-instrumented agent. Conversational REPL,
OpenAI under the hood, two-line instrumentation pattern.

## What it shows

- The default Waxell pattern: `waxell.init()` once at module top +
  `@waxell.observe(agent_name="…")` on the entry function.
- That's it. The OpenAI auto-instrumentor (registered by `init()`)
  captures every `chat.completions.create` call as a span on the run.
- Multi-turn conversation — chat history is threaded into each call,
  so the model has memory across turns. Each turn produces one run.

## What it does NOT show

- Tools, sub-agents, retrieval, streaming, policy enforcement, custom
  spans. See `02-…` through `10-…` for each of those.

## Setup

```bash
# from the repo root, if you haven't already
./scripts/seed-env-from-wax.sh
$EDITOR .env                     # paste your OPENAI_API_KEY

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

You'll get a `you>` prompt. Try:

```
you> tell me about deep-sea anglerfish
you> what about their reproduction?
you> /reset
you> different topic entirely — vintage espresso machines
you> /exit
```

## What to look for in the Waxell UI

After a few turns:

```bash
wax runs list --limit 5
```

You should see one run per `chat_turn` call, all under
`agent_name=hello-waxell`. Drill into one with `wax runs show <id>`
and you'll see:

- The OpenAI `chat.completions.create` call captured as an LLM span
- Token in/out + cost
- The full message history that was sent (if `WAXELL_CAPTURE_CONTENT=1`)
- The model response captured as `agent_response`

Or open `https://app.waxell.dev/agent-executions` and filter by the
agent name.

## The pattern, in 4 lines

```python
import waxell_observe as waxell
waxell.init()

@waxell.observe(agent_name="my-agent")
def run_turn(history, user_message): ...
```

If you copy nothing else from this repo, copy these four lines into your
own agent. Everything else here is a more elaborate version of the same
shape.
