# 08-rag-conversational

Retrieval-Augmented Generation (RAG) with **explicit retrieval span recording**.
A conversational Q&A agent over a tiny in-memory cooking knowledge base.
Each turn embeds the user's question, cosine-ranks 8 recipe snippets, feeds
the top-3 into the LLM, and records each retrieved document to Waxell via
`ctx.record_retrieval_result(...)`.

## What it shows

- **RAG loop in ~30 lines** — embed question → rank snippets → inject as
  `system` context → generate answer.
- **Explicit retrieval recording** — `waxell.get_current_context()` fetches
  the active `WaxellContext` inside the `@observe` function; calling
  `ctx.record_retrieval_result(relevance_score=…, source=…, collection=…)`
  once per retrieved document populates Waxell's retrieval governance buffer.
- **Why it matters** — because the retrieval data lands on the run, a
  `retrieval` policy *could* enforce rules such as "answers must cite a
  document with `relevance_score >= 0.70`" with no code changes.
- **OpenAI embeddings** — `text-embedding-3-small` is called twice per turn
  (once for the KB at startup, once for the question); both calls are captured
  as LLM spans alongside the chat completion.
- Multi-turn conversation — history is threaded across turns. Each turn
  produces one run under `agent_name=rag-conversational`.

## What it does NOT show

- External vector stores (Pinecone, pgvector). The KB lives entirely in memory.
- Retrieval governance enforcement — no `policies.py` is shipped. Add one to
  the Waxell UI to see policy evaluation fire against the recorded scores.
- Streaming responses.

## Setup

```bash
# from the repo root, if you haven't already
./scripts/seed-env-from-wax.sh
$EDITOR .env                     # paste your OPENAI_API_KEY

# from this folder
./setup.sh
```

`setup.sh` creates a per-example `.venv/`, installs deps, and verifies your
`.env` has `WAXELL_API_KEY` and `OPENAI_API_KEY`.

## Run

```bash
source .venv/bin/activate
python agent.py
```

The agent embeds the 8 KB snippets on first launch (one OpenAI API call),
then drops you into the REPL.

### Example session

```
you> how long do I boil pasta?
assistant> For dried pasta, bring a large pot of heavily salted water to
a rolling boil first. Add the pasta and cook for 8–12 minutes depending
on the shape; start tasting 2 minutes before the package minimum to catch
the al-dente window.

you> what temperature kills yeast?
assistant> Water above 60 °C (140 °F) will kill active dry yeast. The
ideal proofing range is 38–43 °C (100–110 °F) — warm enough to activate
the yeast but not so hot as to denature it.

you> how do I make a good pan sauce with caramelised onions?
assistant> ...

you> /reset
(conversation reset)

you> /exit
```

## What to look for in the Waxell UI

After a few turns:

```bash
wax runs list --limit 5
```

You should see one run per `chat_turn` call under `agent_name=rag-conversational`.
Drill into a run with `wax runs show <id>` (or open
`https://app.waxell.dev/agent-executions`) and look for:

- **LLM span** — the `gpt-4o-mini` chat completion with the RAG system prompt
  that includes the top-3 snippets as `CONTEXT`.
- **Embedding spans** — `text-embedding-3-small` calls captured automatically
  by the OpenAI auto-instrumentor (one per turn for the question embedding;
  the KB warm-up call on startup may appear on the first run).
- **Retrieval tab / context tab** — the three `record_retrieval_result` calls
  per turn appear here, each with `source` (the snippet ID, e.g.
  `pasta-boiling`), `collection` (`cooking-kb`), and `relevance_score`
  (cosine similarity, 0–1). The running average is also auto-surfaced as the
  `retrieval_relevance` score on the run.

## The retrieval recording pattern

```python
ctx = waxell.get_current_context()   # only valid inside @observe
if ctx is not None:
    for hit in top_k_results:
        ctx.record_retrieval_result(
            relevance_score=hit["score"],   # float 0.0–1.0
            source=hit["doc"]["id"],        # document identifier
            collection="cooking-kb",        # index / collection name
        )
```

`record_retrieval_result` also accepts `age_days` for freshness-based
governance policies.
