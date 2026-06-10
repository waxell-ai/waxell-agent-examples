# 07-streaming-chat

Streaming OpenAI responses captured by Waxell. Tokens print to the
terminal as they arrive — you see the poem materialise word-by-word —
while Waxell records the full final response and token counts as a
single LLM span on the run.

## What it shows

- OpenAI streaming via `stream=True` with per-chunk `print(end="", flush=True)`
  so the "typing" effect is visible in the terminal.
- Waxell's OpenAI auto-instrumentor handles streaming out of the box:
  it stitches the chunks back into one complete LLM span after the last
  chunk arrives. No extra code needed.
- The full assembled response is appended to conversation history, so
  the model has memory across turns even though delivery was streamed.
- Each call to the `@waxell.observe`-decorated function = one run in
  the Waxell UI.

## What it does NOT show

- Tools, sub-agents, retrieval, policy enforcement, or custom spans.
  See sibling examples for those patterns.

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
you> haiku about an old typewriter
you> now make it sadder
you> a limerick about the same typewriter being replaced by a laptop
you> /reset
you> sonnet about fog rolling in over a harbour
you> /exit
```

Each request streams token-by-token to your terminal. Press Ctrl-C at
any point to quit cleanly.

## What to look for in the Waxell UI

After a few poems:

```bash
wax runs list --limit 5
```

You should see one run per `chat_turn` call, all under
`agent_name=streaming-chat`. Drill into one with `wax runs show <id>`
and you'll see:

- A single LLM span for the streaming `chat.completions.create` call —
  Waxell captures the **full final response** (not individual chunks)
  once the stream completes.
- Token in/out counts and cost, exactly as with a non-streaming call.
- The full assembled poem in `agent_response` (set `WAXELL_CAPTURE_CONTENT=1`
  in your `.env` to see the complete text in the UI).

Or open `https://app.waxell.dev/agent-executions` and filter by the
agent name.

## Key implementation note

The only streaming-specific lines are:

```python
stream = client.chat.completions.create(..., stream=True)

for chunk in stream:
    delta = chunk.choices[0].delta.content if chunk.choices else None
    if delta:
        print(delta, end="", flush=True)   # visible typing effect
        chunks.append(delta)

reply = "".join(chunks)   # full text for history + Waxell span
```

`flush=True` on every chunk print is what makes the streaming effect
visible — without it, the OS buffers output and you see the whole poem
at once.

## The pattern, in 4 lines

```python
import waxell_observe as waxell
waxell.init()

@waxell.observe(agent_name="streaming-chat")
def run_turn(history, user_message): ...
```

`waxell.init()` registers the auto-instrumentor once; the decorator
declares the entry point. Streaming vs. non-streaming is transparent
to Waxell — the instrumentor handles both.
