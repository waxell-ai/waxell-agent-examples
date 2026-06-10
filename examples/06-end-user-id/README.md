# 06-end-user-id

Per-end-user attribution and enforcement. One agent serves multiple end
users; every run is tagged with the end user who triggered it, AND a
policy enforces a **separate monthly budget per end user**. Switching
end users in the REPL exercises both: tagging happens for everyone, but
only the user whose cap is exhausted gets blocked.

## Why end_user_id exists (the actual use case)

A typical B2B / multi-customer Waxell setup: your company is the Waxell
tenant. Inside that tenant you serve many end customers — Acme,
BetaCo, your own users, whatever. `end_user_id` is the identifier of
the end customer on whose behalf the agent is acting on each run. That
unlocks four real things you can't get without it:

1. **Per-end-user budgets.** The `end-user-budget` policy enforces a
   monthly cap PER end user. One runaway end customer can't burn the
   whole tenant's budget.
2. **Per-end-user rate limits.** Same pattern, throttled instead of
   capped.
3. **Compliance / audit lookups.** GDPR data requests: pull every run
   that ever ran on a specific end user's behalf with one filter.
4. **Per-customer cost attribution.** Roll up usage by end user to bill
   back, build dashboards, segment analytics.

`user_id` is a SEPARATE concept — it's typically the logged-in
operator inside YOUR product (e.g. the dev/agent who triggered the
run). This example sets both to the same value because there's no
operator-vs-customer distinction in a single-user demo; in a real B2B
app they'd usually be different.

## What it shows

- `end_user_id` AND `user_id` as call-time kwargs on `@waxell.observe`
  — the decorator intercepts them from kwargs and forwards them to
  `WaxellContext`, tagging every run with both identities.
- An `end-user-budget` policy that enforces a separate monthly cap PER
  end user, sourced from the `WaxellUser.monthly_budget_cap_cents`
  field that `setup.sh` provisions via `wax end-users create`.
- Per-user conversation memory — each user's history is stored
  separately; switching preserves it.
- `/switch <email>` and `/whoami` REPL commands.
- Graceful in-REPL handling of `PolicyViolationError` — when a user's
  budget exhausts, the REPL prints the block reason and lets you
  /switch to another user instead of crashing.

## What it does NOT show

- Tools, sub-agents, retrieval, streaming. See the other examples.
- B2B operator-vs-end-customer separation. In a real B2B app, `user_id`
  would be the logged-in dev / operator and `end_user_id` would be the
  customer they're serving. This demo sets them equal for simplicity.

## Setup

```bash
# from the repo root, if you haven't already
./scripts/seed-env-from-wax.sh
$EDITOR .env                     # paste your OPENAI_API_KEY

# from this folder
./setup.sh
```

`setup.sh` (idempotent):

1. Creates a per-example `.venv/` and installs deps.
2. Provisions two end-users via `wax end-users create`:
   - `alice@example.com` — monthly cap = $1000 (`--budget 100000`).
     Effectively unlimited for the demo.
   - `bob@example.com` — monthly cap = 1¢ (`--budget 1`). Exhausts
     immediately.
3. Pushes the `end-user-budget` policy (`policies.py`) via
   `wax policies push`.
4. Verifies both end-users and the policy are live.

## Run

```bash
source .venv/bin/activate
python agent.py
```

## The demo sequence — exact REPL inputs

```
you> /switch alice@example.com
(switched to alice@example.com)

you> I'm studying calculus, specifically integrals
assistant> ...

you> what was I studying?
assistant> (recalls calculus — alice's history)

you> /switch bob@example.com
(switched to bob@example.com)

you> hi
assistant> ...                            # may succeed once if spend < 1¢

you> tell me about ancient Rome
assistant> ⛔ blocked for bob@example.com:
           End-user 'bob@example.com' monthly budget exceeded
           ($0.00 / $0.01).

you> /switch alice@example.com
(switched to alice@example.com)

you> can you summarise where we are?
assistant> ...                            # alice keeps working

you> /exit
```

The point: **same agent, same code, same session**. Bob is blocked
because his end-user-budget policy fired on his cap. Alice is unaffected
because her cap is separate. That's only possible because every run is
tagged with `end_user_id` and the policy keys off it.

## What to look for in the Waxell UI

```bash
# All of alice's runs
wax end-users runs --tenant-sub-user-id alice@example.com --limit 5

# All of bob's runs (the blocked ones show status=blocked)
wax end-users runs --tenant-sub-user-id bob@example.com --limit 5
```

In the Waxell controlplane:

1. Open any run. The **Context** tab shows USER = the end user who
   triggered it (alice or bob, not "anonymous").
2. Bob's blocked runs show status=Blocked + an `example-end-user-budget`
   incident in the Governance tab with the exact reason and amounts.
3. Filter the executions list by USER to see one user's runs in
   isolation — that's the audit/compliance use case.
4. Open the conversation page — turn-by-turn switching is visible,
   and blocked turns render with the rose "policy blocked" indicator.

## The pattern, in 6 lines

```python
import waxell_observe as waxell
waxell.init()

@waxell.observe(agent_name="my-agent")
def run_turn(history, message): ...

# At call time, forward the current end user (and operator, if separate):
run_turn(history, message, end_user_id=customer_id, user_id=operator_id)
```

The decorator intercepts both kwargs and stamps them on the run — no
manual span work required.
