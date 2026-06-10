"""08-rag-conversational — RAG Q&A agent with explicit retrieval span recording.

Demonstrates Retrieval-Augmented Generation where each conversational turn:
1. Embeds the user's question via OpenAI ``text-embedding-3-small``.
2. Cosine-ranks a tiny in-memory recipe knowledge base.
3. Feeds the top-3 snippets into the LLM as ``system`` context.
4. Records each retrieved document to the active WaxellContext via
   ``ctx.record_retrieval_result(...)`` so Waxell's retrieval governance
   category has real signal to evaluate.

Because retrieval data lands on the run, a ``retrieval`` policy COULD
enforce rules such as "answers must cite a document with
relevance_score >= 0.70" — without any code changes here.

Run::

    ./setup.sh                       # one-time
    source .venv/bin/activate
    python agent.py

Then type cooking questions at the ``you>`` prompt. Use ``/reset`` to
start a fresh conversation, ``/exit`` to quit.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import uuid

import numpy as np
import waxell_observe as waxell

waxell.init()

_SESSION_ID = uuid.uuid4().hex  # stable for this REPL process; shared across all turns

from openai import OpenAI

# ---------------------------------------------------------------------------
# Knowledge base — 8 short, public-domain cooking/recipe snippets.
# Each entry has a stable ``id`` used as the ``source`` in retrieval spans.
# ---------------------------------------------------------------------------

_KB: list[dict] = [
    {
        "id": "pasta-boiling",
        "text": (
            "For dried pasta, bring a large pot of salted water to a rolling boil "
            "before adding the pasta. Cooking time is typically 8–12 minutes "
            "depending on the shape; start tasting 2 minutes before the package "
            "minimum for al-dente texture."
        ),
    },
    {
        "id": "bread-yeast",
        "text": (
            "Active dry yeast must be proofed in warm water (38–43 °C / 100–110 °F) "
            "with a pinch of sugar for 5–10 minutes until foamy before mixing into "
            "dough. Water that is too hot (above 60 °C) kills the yeast."
        ),
    },
    {
        "id": "caramelising-onions",
        "text": (
            "True caramelised onions require low heat and patience — 45–60 minutes "
            "in a wide pan with a little butter or oil. Rushing with high heat "
            "browns the outside before the sugars inside have time to develop, "
            "producing bitter rather than sweet results."
        ),
    },
    {
        "id": "egg-soft-boil",
        "text": (
            "For a soft-boiled egg with a fully set white and runny yolk, lower "
            "the egg into already-boiling water and cook for exactly 6 minutes, "
            "then transfer immediately to an ice bath for 1 minute to stop cooking."
        ),
    },
    {
        "id": "roux-thickening",
        "text": (
            "A roux (equal parts butter and flour by weight, cooked together) "
            "thickens sauces. A white roux is cooked 2 minutes; a blond roux "
            "5–7 minutes for a nutty flavour; a dark (brown) roux 20–30 minutes "
            "for gumbo-style depth, losing some thickening power as it darkens."
        ),
    },
    {
        "id": "searing-meat",
        "text": (
            "Pat meat dry before searing — surface moisture steams rather than "
            "browns. Use a heavy pan (cast iron or stainless) preheated over "
            "medium-high heat until a drop of water beads and skitters. Do not "
            "move the meat for the first 2–3 minutes so a crust can form."
        ),
    },
    {
        "id": "vinaigrette-ratio",
        "text": (
            "The classic vinaigrette ratio is 3 parts oil to 1 part acid "
            "(vinegar or citrus juice). Whisk the acid with salt and any "
            "emulsifiers (mustard, honey) first, then drizzle in the oil while "
            "whisking continuously to form a temporary emulsion."
        ),
    },
    {
        "id": "tempering-chocolate",
        "text": (
            "Tempering chocolate aligns cocoa-butter crystals for a glossy finish "
            "and satisfying snap. Melt dark chocolate to 50 °C, cool on a marble "
            "slab to 27 °C while working it, then reheat to 32 °C for use. "
            "Milk and white chocolate temper at slightly lower temperatures."
        ),
    },
]

# ---------------------------------------------------------------------------
# Embedding cache — built once at startup, reused every turn.
# ---------------------------------------------------------------------------

_client: OpenAI | None = None
_kb_embeddings: np.ndarray | None = None  # shape (n_docs, dim)


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def _embed(texts: list[str]) -> np.ndarray:
    """Call OpenAI text-embedding-3-small and return a (n, dim) float32 array."""
    resp = _get_client().embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    vectors = [item.embedding for item in resp.data]
    return np.array(vectors, dtype=np.float32)


def _cosine_scores(query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
    """Return cosine similarity of ``query_vec`` against each row of ``doc_vecs``."""
    q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    norms = np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-9
    d = doc_vecs / norms
    return (d @ q).astype(float)


def _build_kb_embeddings() -> None:
    """Embed all KB snippets at startup. Runs once; result cached in module globals."""
    global _kb_embeddings
    print("Embedding knowledge base… ", end="", flush=True)
    texts = [doc["text"] for doc in _KB]
    _kb_embeddings = _embed(texts)
    print("done.\n")


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

_TOP_K = 3
_TRUNCATE_CHARS = 400  # max content chars forwarded to Waxell span


def _retrieve(question: str) -> list[dict]:
    """Embed ``question``, rank KB snippets, return top-k with scores."""
    q_vec = _embed([question])[0]
    scores = _cosine_scores(q_vec, _kb_embeddings)
    top_indices = np.argsort(scores)[::-1][:_TOP_K]
    return [
        {
            "doc": _KB[i],
            "score": float(scores[i]),
        }
        for i in top_indices
    ]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

_ANSWER_SYSTEM = (
    "You are a knowledgeable cooking assistant. You are given CONTEXT — "
    "a set of relevant recipe and technique snippets. Use them to answer "
    "the user's question accurately and concisely. If none of the snippets "
    "are relevant, say so and answer from general knowledge. "
    "Keep replies to 2–4 sentences."
)


@waxell.observe(agent_name="rag-conversational", session_id=_SESSION_ID)
def chat_turn(history: list[dict], user_message: str) -> str:
    """One conversational turn with RAG.

    Retrieves the top-3 KB snippets, records each one via
    ``ctx.record_retrieval_result()``, then calls the LLM with the
    snippets as additional system context.
    """
    # 1. Retrieve
    results = _retrieve(user_message)

    # 2. Record retrieval results to Waxell (one call per document)
    ctx = waxell.get_current_context()
    if ctx is not None:
        ctx.record_user_message(content=user_message)
    if ctx is not None:
        for hit in results:
            ctx.record_retrieval_result(
                relevance_score=hit["score"],
                source=hit["doc"]["id"],
                collection="cooking-kb",
            )

    # 3. Build context block for the LLM
    context_block = "\n\n".join(
        f"[{hit['doc']['id']}] {hit['doc']['text']}" for hit in results
    )
    system_prompt = (
        f"{_ANSWER_SYSTEM}\n\nCONTEXT:\n{context_block}"
    )

    # 4. Thread conversation history + call LLM
    history.append({"role": "user", "content": user_message})
    resp = _get_client().chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[{"role": "system", "content": system_prompt}, *history],
    )
    reply = resp.choices[0].message.content or ""
    history.append({"role": "assistant", "content": reply})
    if ctx is not None:
        ctx.record_agent_response(reply)
    return reply


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------


def repl() -> None:
    _build_kb_embeddings()
    print("rag-conversational — ask me anything about cooking.")
    print("Commands: /reset  /exit\n")
    history: list[dict] = []
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user == "/exit":
            break
        if user == "/reset":
            history.clear()
            print("(conversation reset)\n")
            continue
        reply = chat_turn(history, user)
        print(f"assistant> {reply}\n")


def main() -> None:
    missing = [k for k in ("OPENAI_API_KEY", "WAXELL_API_KEY") if not os.environ.get(k)]
    if missing:
        sys.stderr.write(
            f"Missing env vars: {', '.join(missing)}\n"
            "Add them to the repo-root .env and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
