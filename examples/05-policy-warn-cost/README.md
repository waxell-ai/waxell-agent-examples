# 05-policy-warn-cost

A conversational creative-writing partner that demonstrates **warn-disposition
budget policies** in Waxell.  The agent always completes — `warn` is
*detective*, not *preventive* — but when a single turn exceeds the token or
cost threshold, the governance plane records a warning incident on the run.
The REPL prints an inline `(cost warning)` notice when it detects the incident.

## What it shows

- Defining a `budget` policy with `action_on_exceed: warn` via the `@policy`
  DSL in `policies.py`.
- Scoping the policy to a single agent (`policy-warn-cost`) so it only fires
  for this example.
- Thresholds intentionally low (`per_workflow_token_limit: 500`,
  `per_workflow_cost_limit: $0.01`) so a single verbose response trips them.
- Run always finishes with `status=success`; the Governance panel on the run
  shows **1 warning incident** with policy `example-cost-warn`.

## What it does NOT show

- Blocking or throttling (see `04-policy-block-pii` for block disposition).
- Multi-agent or sub-agent patterns, tools, or streaming.

## Setup

```bash
# from the repo root, if you haven't already
./scripts/seed-env-from-wax.sh
$EDITOR .env                     # paste your OPENAI_API_KEY

# from this folder
chmod +x setup.sh
./setup.sh
```

`setup.sh` creates a per-example `.venv/`, installs deps, runs
`wax policies push policies.py`, and verifies the policy landed.

## Run

```bash
source .venv/bin/activate
python agent.py
```

## Prompts that reliably trip the warning

The system prompt instructs the model to always write long, evocative prose.
Any of these will exceed 500 tokens in a single reply:

```
you> write me a 500-word gothic horror story set in a lighthouse
you> continue the story — describe the creature emerging from the fog
you> now write the final confrontation scene in exhaustive detail
```

After the first verbose reply you should see:

```
assistant> [long atmospheric prose …]

(cost warning: budget policy 'example-cost-warn' fired —
 run completed but a warning incident was recorded)
  -> wax runs list --limit 1  # to see the run
  -> wax runs show <id>        # to see the incident detail
```

## What to look for in the Waxell UI

1. Run `wax runs list --limit 3` — the run appears with `status=success`.
2. Run `wax runs show <id>` — the **Governance** section shows:
   - `policy: example-cost-warn`
   - `disposition: warn`
   - `reason: Workflow exceeded token limit (NNN/500)` or similar
3. In `https://app.waxell.dev/agent-executions`, filter by
   `agent_name=policy-warn-cost`. Open the run and click the
   **Governance** tab — you'll see **1 warning incident** with the
   policy name, the exact token/cost usage, and the configured limit.

## Policy definition

```python
# policies.py
example_cost_warn = policy(
    name="example-cost-warn",
    category="budget",
    scope={"agents": ["policy-warn-cost"]},
    rules={
        "per_workflow_token_limit": 500,
        "per_workflow_cost_limit": 0.01,
        "action_on_exceed": "warn",
    },
)
```

The `budget` handler evaluates this in `after_workflow` — it sees the
final token/cost count for the run and fires a `WARN` result if either
limit is exceeded.  Because the disposition is `warn`, the runtime records
the incident but does not raise an exception or halt execution.

## Adjusting the threshold

Edit `policies.py` and re-run `wax policies push policies.py`.  To make the
policy harder to trip (useful once you're satisfied the demo works), raise
`per_workflow_token_limit` to `2000` or `per_workflow_cost_limit` to `0.05`.
