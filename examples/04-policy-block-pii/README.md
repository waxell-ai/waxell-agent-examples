# 04-policy-block-pii

A conversational customer-support intake agent that demonstrates Waxell's
preventive content policy: the moment a user types a US Social Security Number
(pattern `NNN-NN-NNNN`), the `example-pii-block` policy fires a **block**
disposition and the run is recorded as BLOCKED — before any LLM call can
process or echo the sensitive data.

## What it shows

- **Code-first policy definition** — `policies.py` declares the policy using
  `@policy` from `waxell_sdk`; `setup.sh` pushes it to the controlplane with
  `wax policies push`.
- **Preventive blocking** — the `content` category handler scans the agent
  input for SSN patterns (`\b\d{3}-\d{2}-\d{4}\b`) *before* the LLM call and
  raises `PolicyViolationError` when a match is found.
- **Graceful REPL recovery** — `agent.py` catches `PolicyViolationError` (and
  `PromptGuardError`), prints a refusal message, and keeps the session alive.
  The blocked turn is not added to conversation history.
- **Multi-turn memory** — conversation history is threaded across turns so the
  model remembers context (as long as turns are not blocked).
- **Audit trail** — every run (including BLOCKED ones) is recorded in Waxell
  under `agent_name=policy-block-pii`.

## What it does NOT show

- Redaction (the policy blocks, not redacts — see a future example for that).
- Output scanning (`scan_outputs` is disabled to keep the demo focused on
  input blocking).
- Other PII types (email, phone, credit card) — add them to `types` in
  `policies.py` to extend coverage.

## Setup

```bash
# from the repo root, if you haven't already
./scripts/seed-env-from-wax.sh
$EDITOR .env                     # paste your OPENAI_API_KEY

# from this folder
chmod +x setup.sh
./setup.sh
```

`setup.sh` will:
1. Verify `.env` has both `WAXELL_API_KEY` and `OPENAI_API_KEY`.
2. Create a per-example `.venv/` and install dependencies.
3. Run `wax policies push policies.py` — exits 1 if this fails.
4. Run `wax policies list --format=json | grep example-pii-block` to confirm
   the policy landed.
5. Print run instructions.

## Run

```bash
source .venv/bin/activate
python agent.py
```

You'll get a `you>` prompt. Normal support questions flow through to the LLM:

```
you> Hi, I can't log in to my account
assistant> I'm sorry to hear that! Let's get that sorted out. Could you
           tell me what happens when you try to log in? ...

you> I keep getting an "invalid password" error
assistant> That usually means the password on file doesn't match. Here
           are a few steps to try: ...
```

### Triggering the PII block

Type a message that contains a US SSN pattern (`NNN-NN-NNNN`):

```
you> Hi, my SSN is 123-45-6789, can you look up my account?
assistant> I can't process that — it looks like your message contains
           sensitive personal information (such as a Social Security
           Number). For your security, please contact us through a
           secure channel: https://support.example.com/secure or call
           1-800-555-0100.

[waxell] run blocked by policy: ...
```

The REPL continues — type another message and the session resumes normally.

Other inputs that trigger the block:

```
you> please verify: 987-65-4321
you> my social is 001-01-0001
```

Use `/reset` to start a fresh conversation, `/exit` to quit.

## What to look for in the Waxell UI

After triggering a block:

```bash
wax runs list --limit 5
```

The blocked run shows **status = BLOCKED** (not COMPLETED or FAILED).

Drill into it with `wax runs show <id>` and you'll see:

- `disposition: block` recorded by the `example-pii-block` policy
- The policy violation metadata (scan target: input, type: pii, matched: ssn)
- No LLM span — the block fired before the OpenAI call was made

In the Waxell web app (`https://app.waxell.dev`):

- **Agent Executions** — filter by `policy-block-pii`; blocked runs appear
  with a red BLOCKED badge.
- **Governance tab** — the incident is listed under Policy Incidents.
- **Policies page** — `example-pii-block` appears with category `content`,
  scope `agents: [policy-block-pii]`, and action `block`.

## The policy, in full

```python
from waxell_sdk import policy

example_pii_block = policy(
    name="example-pii-block",
    category="content",
    scope={"agents": ["policy-block-pii"]},
    rules={
        "scan_inputs": True,
        "scan_outputs": False,
        "pii_detection": {
            "enabled": True,
            "action": "block",
            "types": ["ssn"],
        },
    },
    description="Blocks any prompt containing US SSN-like patterns (NNN-NN-NNNN).",
)
```

The `content` category handler (`ContentHandler`) owns SSN detection via the
built-in `\b\d{3}-\d{2}-\d{4}\b` regex in `content_detection.py`. No custom
regex needed — just enable `pii_detection` and set `types: ["ssn"]`.
