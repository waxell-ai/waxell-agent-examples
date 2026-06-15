# Waxell Agent Examples

A skeleton library of small, runnable agents that each demonstrate a single
Waxell observability or governance capability. Pick the one closest to what
you're building, copy it, and start there.

Every example is self-contained: one folder, one `agent.py`, one
`requirements.txt`, one README. None of them depend on each other.

---

## Quickstart (3 minutes)

The bootstrap scripts are pure Python so they work the same on Windows,
macOS, and Linux — no bash, no platform-specific shims. You need Python
3.12 or 3.13 on PATH (the `waxell-observe` wheel only ships for those
two right now).

```text
# 1. Clone + cd
git clone https://github.com/waxell-ai/waxell-agent-examples.git
cd waxell-agent-examples

# 2. Seed .env from your local wax profile
python scripts/seed_env_from_wax.py              # uses the [default] profile
# or specify a profile: python scripts/seed_env_from_wax.py my-profile

# 3. Open .env and paste your LLM provider key(s) — OPENAI_API_KEY, ANTHROPIC_API_KEY, …

# 4. Pick an example, install its deps, run it
python scripts/setup_example.py 01-hello-waxell
#    (this prints the right activate command for your platform)

# 5. Activate the per-example venv, then run the agent
#    macOS / Linux / WSL:
source examples/01-hello-waxell/.venv/bin/activate
python examples/01-hello-waxell/agent.py
#    Windows PowerShell:
.\examples\01-hello-waxell\.venv\Scripts\Activate.ps1
python examples\01-hello-waxell\agent.py
#    Windows cmd.exe:
examples\01-hello-waxell\.venv\Scripts\activate.bat
python examples\01-hello-waxell\agent.py

# 6. Watch the run land
wax runs list --limit 3
# (or open https://app.waxell.dev/agent-executions)
```

If your default `python` doesn't work, try `py -3.13` (Windows launcher)
or `python3.13` / `python3.12` (macOS / Linux). The setup script auto-
detects the right one when creating each example's venv.

If you don't have `wax` installed yet: `pipx install waxell` (or
`pip install waxell`) — the `waxell` meta package is what registers the
`wax` CLI on PATH. The instrumentation SDK (`waxell-observe`) is a
separate package and does **not** ship the CLI. After install, run
`wax setup` and follow the prompts before step 2.

### Bash users (macOS / Linux)

The legacy `./scripts/setup-example.sh` and `./scripts/seed-env-from-wax.sh`
shell scripts are still here and work the same. The Python scripts are the
canonical entry point now because they work on Windows too — pick whichever
matches your shell.

---

## Examples

| # | Folder | What it shows | Frameworks | Provider |
|---|--------|---------------|------------|----------|
| 01 | [`hello-waxell`](examples/01-hello-waxell) | The two-line decorator pattern — the default Waxell instrumentation | OpenAI Python SDK | OpenAI |
| 02 | [`anthropic-tool-use`](examples/02-anthropic-tool-use) | Tool-use spans on Claude, captured automatically | Anthropic Python SDK | Anthropic |
| 03 | [`langgraph-research`](examples/03-langgraph-research) | Multi-node LangGraph with a conditional loop edge | LangGraph + LangChain | OpenAI |
| 04 | [`policy-block-pii`](examples/04-policy-block-pii) | Preventive policy: PII in user input → run blocked | OpenAI | OpenAI |
| 05 | [`policy-warn-cost`](examples/05-policy-warn-cost) | Detective policy: cost threshold breached → incident recorded | OpenAI | OpenAI |
| 06 | [`end-user-id`](examples/06-end-user-id) | Per-end-user attribution via `end_user_id=` | OpenAI | OpenAI |
| 07 | [`streaming-chat`](examples/07-streaming-chat) | Streaming response capture in a span | OpenAI streaming | OpenAI |
| 08 | [`rag-pipeline`](examples/08-rag-pipeline) | RAG with explicit retrieval spans for retrieval policies | OpenAI + in-memory store | OpenAI |
| 09 | [`crewai-multi-agent`](examples/09-crewai-multi-agent) | Sub-agent lineage — nested runs visible as one tree | CrewAI | OpenAI |
| 10 | [`judge-evaluation`](examples/10-judge-evaluation) | LLM-judge policy disposition — model grades the model | OpenAI | OpenAI |

---

## Repo layout

```
.
├── README.md                 ← you are here
├── LICENSE                   ← MIT
├── .env.example              ← template for your local .env
├── scripts/
│   ├── seed-env-from-wax.sh  ← writes .env from your wax profile
│   └── setup-example.sh      ← venv + pip install for one example
└── examples/
    └── NN-name/
        ├── README.md         ← what this example shows, how to run it
        ├── agent.py          ← the agent code
        └── requirements.txt  ← pinned deps for this example
```

## What's *not* in here

- Production hardening — these are minimal scaffolds. Add error handling,
  retries, and timeouts for real workloads.
- Multi-tenant patterns — every example runs as a single user. See
  `06-end-user-id` for the sub-user attribution primitive.
- Waxell control-plane setup — these examples *use* a running Waxell
  controlplane (your local dev stack or `api.waxell.dev`). They don't set
  one up.

## Contributing a new example

1. Copy `examples/01-hello-waxell` to a new numbered folder.
2. Replace `agent.py` with the new pattern.
3. Update the local `README.md` (what it shows, setup, run, what to look
   for in the UI).
4. Update the table in this top-level README.
5. Open a PR.

Each example should demonstrate **one** clearly-named capability. If two
capabilities can be split into two examples, split them.

## License

MIT — see [LICENSE](LICENSE).
