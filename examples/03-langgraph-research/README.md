# 03-langgraph-research

A multi-node LangGraph state machine wrapped in a conversational REPL.
Shows that Waxell's LangChain/LangGraph auto-instrumentor captures every
node's LLM call as a child span — zero manual span work.

## What it shows

- A `StateGraph` with three nodes and a conditional loop edge:
  - **plan** — breaks the user's question into 3 subtopics (JSON list).
  - **research** — researches one subtopic at a time; a conditional edge
    loops back to `research` until all 3 subtopics are covered, then
    routes forward to `synthesize`.
  - **synthesize** — composes the final answer from all three findings.
- That Waxell's LangGraph instrumentor (registered by `waxell.init()`)
  sees inside the graph automatically. Each `ChatOpenAI` call in every node
  is captured as a child LLM span on the run — **5 spans per turn**:
  `plan` (×1) + `research` (×3) + `synthesize` (×1).
- `@waxell.observe(agent_name="langgraph-research")` on the entry function
  is the only Waxell-specific line in `agent.py` beyond `waxell.init()`.
- Multi-turn memory: prior Q&A pairs are prepended as context on each new
  graph invocation, so the model remembers what was already discussed.

## What it does NOT show

- Tools, retrieval, streaming, policy enforcement, custom spans.
- Parallel fan-out within the graph (subtopics are researched sequentially).
- See `04-…` through `10-…` for those patterns.

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
you> explain how black holes form
you> how does that relate to neutron stars?
you> /reset
you> what caused the Bronze Age collapse?
you> /exit
```

## What to look for in the Waxell UI

After a turn or two:

```bash
wax runs list --limit 5
```

You should see one run per `research_turn` call under
`agent_name=langgraph-research`. Drill into one with `wax runs show <id>`
and you'll see **5 child LLM spans**:

| Span | Node | What it does |
|------|------|--------------|
| 1 | `plan` | Calls the LLM once to produce the 3-subtopic JSON list |
| 2 | `research` | Researches subtopic 1 |
| 3 | `research` | Researches subtopic 2 |
| 4 | `research` | Researches subtopic 3 |
| 5 | `synthesize` | Calls the LLM once to compose the final answer |

Each span includes token in/out, cost, and (if `WAXELL_CAPTURE_CONTENT=1`)
the full prompt and response.

Or open `https://app.waxell.dev/agent-executions`, filter by
`agent_name=langgraph-research`, and expand any run to see the span tree.

## The pattern, in 4 lines

```python
import waxell_observe as waxell
waxell.init()

@waxell.observe(agent_name="langgraph-research")
def research_turn(question, context): ...
```

LangGraph nodes are instrumented automatically by `init()` — no callbacks,
no manual `with waxell.span(...)` blocks needed inside the nodes.
