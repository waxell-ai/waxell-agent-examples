# 09-crewai-multi-agent

A CrewAI crew of two agents (researcher + writer) wrapped in a
conversational REPL. Waxell's CrewAI auto-instrumentor captures every
sub-agent's LLM call automatically — the run tree in the Waxell UI
shows the parent crew kickoff with each agent's call nested underneath
it as child spans.

## What it shows

- `waxell.init()` registers the CrewAI auto-instrumentor. No callbacks,
  no manual span work.
- `@waxell.observe(agent_name="crewai-multi-agent")` marks the entry
  point. One crew kickoff = one parent run in Waxell.
- Two agents run sequentially inside the crew:
  - **researcher** — gathers 3 key facts about the user's topic.
  - **writer** — turns those facts into a 2-paragraph blog summary.
- The run tree in Waxell shows the parent run for the crew with the
  researcher's LLM call and the writer's LLM call nested under it,
  all linked as lineage.
- Conversation memory: prior topics are threaded into the researcher's
  task description so follow-up questions have context.

## What it does NOT show

- Tools, retrieval, policy enforcement, custom spans, streaming. See
  other examples for those patterns.

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
you> blog about the future of remote work
you> what about its effect on city housing markets?
you> /reset
you> blog about open-source large language models
you> /exit
```

The crew prints `(crew is working…)` while the two agents run, then
shows the finished blog summary.

## What to look for in the Waxell UI

After one or two turns:

```bash
wax runs list --limit 5
```

You should see one run per `blog_turn` call under
`agent_name=crewai-multi-agent`. Drill into a run with
`wax runs show <id>` and you'll see:

- A **parent span** for the crew kickoff (`crewai-multi-agent`)
- A **child span** for the researcher agent's LLM call, with its
  prompt and the 3-fact list it produced
- A **child span** for the writer agent's LLM call, with the facts
  as input and the 2-paragraph summary as output
- Token counts and cost for each span
- All spans linked under a single lineage tree

Or open `https://app.waxell.dev/agent-executions`, filter by
`crewai-multi-agent`, and expand any run to see the full sub-agent
hierarchy.

## The pattern, in 4 lines

```python
import waxell_observe as waxell
waxell.init()                         # registers CrewAI auto-instrumentor

@waxell.observe(agent_name="my-crew")
def run_turn(topic): ...              # every crew.kickoff() inside is traced
```

The CrewAI instrumentor attaches to `Crew.kickoff` automatically after
`waxell.init()`. Sub-agent spans appear as children of the parent run
without any further changes to your CrewAI code.
