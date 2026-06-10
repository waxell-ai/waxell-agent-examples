# 06-end-user-id

Per-end-user attribution. The same agent serves multiple end users;
every run is tagged with the end user who triggered it so you can
filter runs by user in the Waxell UI.

## What it shows

- `end_user_id` as a call-time kwarg on `@waxell.observe` — the
  decorator intercepts it from kwargs (it lives in `_CONTEXT_PARAMS`
  and is not in the function signature) and forwards it to
  `WaxellContext`, tagging the run without any manual span work.
- Per-user conversation memory — each user's history is stored
  separately; switching users preserves all histories so switching
  back restores the prior conversation.
- `/switch <email>` REPL command to change the active end user
  mid-session; the very next turn ships under the new user.
- `/whoami` REPL command to inspect the current end_user_id.

## What it does NOT show

- Tools, sub-agents, retrieval, streaming, or policy enforcement.
  See `03-…` through `10-…` for each of those.

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

## Exercising end-user switching — exact REPL inputs

Work through this sequence to see two separate users' runs appear in
Waxell:

```
you> I'm studying calculus, specifically integrals
assistant> ...

you> /whoami
(current user: anonymous)

you> /switch alice@example.com
(switched to alice@example.com)

you> I'm studying machine learning, starting with linear regression
assistant> ...

you> what was I studying?
assistant> (recalls linear regression / machine learning)

you> /switch bob@example.com
(switched to bob@example.com)

you> what was I studying?
assistant> (no history — asks what Bob is studying)

you> I'm studying ancient Roman history
assistant> ...

you> /switch alice@example.com
(switched to alice@example.com)

you> what was I studying?
assistant> (recalls linear regression — alice's history restored)

you> /exit
```

## What to look for in the Waxell UI

After the session above:

```bash
wax runs list --limit 10
```

You'll see runs for three distinct `end_user_id` values: `anonymous`,
`alice@example.com`, and `bob@example.com`.

In the Waxell UI at `https://app.waxell.dev/agent-executions`:

1. Filter by **end_user_id = alice@example.com** — you'll see only
   Alice's turns, tagged under `agent_name=end-user-id`.
2. Filter by **end_user_id = bob@example.com** — you'll see only Bob's
   turns, completely separate from Alice's.
3. Each run record shows the `end_user_id` field in the run metadata,
   so you can build per-user dashboards, audit trails, or cost reports.

## The pattern, in 5 lines

```python
import waxell_observe as waxell
waxell.init()

@waxell.observe(agent_name="my-agent")
def run_turn(history, user_message): ...

# At call time, forward the current end user:
run_turn(history, message, end_user_id=current_user)
```

The decorator intercepts `end_user_id` from call-time kwargs and stamps
it on the run — no manual span work required.
