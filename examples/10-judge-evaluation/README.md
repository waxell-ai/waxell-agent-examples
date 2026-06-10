# 10 — Judge Evaluation

**What this demonstrates:** The LLM-judge governance pattern — the most sophisticated policy category in Waxell. After every agent turn, a separate evaluator model scores the assistant's response on tone and quality. If the score falls below the threshold, Waxell records a WARN incident in the Governance panel without interrupting the conversation.

## How it works

| Layer | Detail |
|---|---|
| Agent model | `gpt-4o-mini` — generates customer-support replies |
| Judge model | `gpt-4o` — evaluates each reply server-side after the run completes |
| Policy category | `quality` (handled by `QualityHandler` via its `llm_checks` path) |
| Policy name | `example-tone-judge` |
| Scope | `agents: ["judge-evaluation"]` |
| Score threshold | `0.65` — replies below this trigger a WARN incident |
| Action on violation | `warn` — conversation continues; incident recorded in Governance panel |

The agent does **not** call the judge itself. The `example-tone-judge` policy fires server-side, asynchronously, after each `@waxell.observe`-wrapped function returns. The conversation flow is never interrupted.

## Setup

```bash
./setup.sh        # one-time: creates .venv, installs deps, pushes policy
```

`setup.sh` requires a repo-root `.env` with both `WAXELL_API_KEY` and `OPENAI_API_KEY`.

## Running the agent

```bash
source .venv/bin/activate
python agent.py
```

## Example REPL session

```
judge-evaluation — customer-support agent with LLM-judge governance.
Type a customer issue, or /reset to start over, /exit to quit.

you> I want a refund for my broken laptop that arrived damaged.
assistant> I'm really sorry to hear your laptop arrived damaged — that's
completely unacceptable and I understand how frustrating that must be.
Here's what to do next: please take a photo of the damage and reply to
your order confirmation email with the subject "Damaged on arrival —
[order number]". Our returns team will authorise a full refund or
replacement within 2 business days. Is there anything else I can help
with in the meantime?

you> It has been two weeks and nobody has replied.
assistant> I sincerely apologise for the lack of response — two weeks is
far too long and that's on us. I'm escalating your case right now. Please
share your order number here and I will personally ensure a member of our
senior support team contacts you within 24 hours with a resolution.

you> /exit
```

## What to look for in the Waxell UI

1. **Runs list** (`wax runs list --limit 5`) — each REPL turn appears as a separate run named `judge-evaluation`.
2. **Run detail** (`wax runs show <run-id>`) — expand the spans to see the OpenAI call captured by the auto-instrumentor.
3. **Governance panel** — this is where the judge verdict lands:
   - Find the run and open its **Policy evaluations** tab.
   - You will see the `example-tone-judge` entry with:
     - **Score** — the judge's 0.0–1.0 rating for empathy + actionability.
     - **Reasoning** — the judge's free-text explanation of the score.
     - **Status** — `PASS` (score ≥ 0.65) or `WARN` (score < 0.65).
   - If the run scored below threshold, a **WARN incident** also appears in the Incidents tab with the score, reasoning, and a timestamp.

## How to trigger a low-score incident deliberately

The agent is instructed to write empathetic, actionable replies, so most turns will pass. To deliberately trigger a WARN:

- Try pasting a terse, dismissive reply scenario and testing with a modified system prompt, **or**
- Note that the judge grades the *agent's output* — if you ask something the model struggles with (e.g. a very niche technical request with no clear action path), the empathy/actionability score may dip below 0.65.

## Policy rules shape (verbatim)

```python
rules={
    "llm_checks": [
        {
            "criteria": "Score this customer-support reply on empathy and actionability ...",
            "action": "warn",
            "model": "gpt-4o",
            "threshold": 0.65,
        }
    ]
}
```

`llm_checks` entries accepted by `QualityHandler`:

| Key | Type | Required | Notes |
|---|---|---|---|
| `criteria` | `str` | yes | The evaluation prompt sent to the judge model |
| `action` | `"warn"` \| `"error"` \| `"retry"` | no | Default `"warn"` |
| `model` | `str` | no | Default `"gpt-4o-mini"` |
| `threshold` | `float` 0–1 | no | Default `0.5`; scores below this = fail |

## Files

| File | Purpose |
|---|---|
| `agent.py` | Conversational customer-support REPL, `@waxell.observe` entry point |
| `policies.py` | `example-tone-judge` policy — LLM-judge via `quality` category |
| `setup.sh` | venv + deps + `wax policies push` + verification |
| `requirements.txt` | `waxell-observe`, `waxell-sdk`, `openai`, `python-dotenv` |
