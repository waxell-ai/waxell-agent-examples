"""03-langgraph-research — conversational REPL with a multi-node LangGraph state machine.

Demonstrates that Waxell's LangChain/LangGraph auto-instrumentor captures
every node's LLM call as a child span automatically — no manual span work,
no callback handlers. One graph invocation = one Waxell run with 5 LLM
spans nested inside it (plan / research × 3 / synthesize).

The graph has three nodes:

  plan       — LLM call. Breaks the user's question into 3 subtopics (JSON list).
  research   — LLM call. Researches one subtopic at a time; a conditional
               edge loops back to ``research`` until all 3 are covered, then
               routes forward to ``synthesize``.
  synthesize — LLM call. Composes the final answer from all three findings.

Subject: research assistant on any topic the user types.

Run::

    ./setup.sh                       # one-time
    source .venv/bin/activate
    python agent.py

Then type messages at the ``you>`` prompt. Use ``/reset`` to start a
fresh conversation, ``/exit`` to quit.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import uuid

import waxell_observe as waxell

waxell.init()

_SESSION_ID = uuid.uuid4().hex  # stable for this REPL process; shared across all turns

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

# ---------------------------------------------------------------------------
# Shared LLM
# ---------------------------------------------------------------------------

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------


class ResearchState(TypedDict):
    question: str
    context: str                  # prior conversation memory prepended by the REPL
    subtopics: list[str]          # filled by ``plan``
    findings: list[str]           # one entry per ``research`` iteration
    current_index: int            # which subtopic we're on
    final_answer: str             # filled by ``synthesize``


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


def plan_node(state: ResearchState) -> dict:
    """Break the question into 3 subtopics and return them as a JSON list."""
    context_block = (
        f"\n\nConversation so far:\n{state['context']}" if state["context"] else ""
    )
    prompt = (
        f"You are a research planner.{context_block}\n\n"
        f"Question: {state['question']}\n\n"
        "Break this question into exactly 3 distinct subtopics to research. "
        "Return ONLY a JSON array of 3 short strings, e.g. "
        '[\"subtopic 1\", \"subtopic 2\", \"subtopic 3\"]. No other text.'
    )
    response = _llm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    subtopics: list[str] = json.loads(raw)
    return {"subtopics": subtopics[:3], "findings": [], "current_index": 0}


def research_node(state: ResearchState) -> dict:
    """Research the current subtopic and append findings."""
    idx = state["current_index"]
    subtopic = state["subtopics"][idx]
    prompt = (
        f"You are a thorough research assistant.\n"
        f"Overall question: {state['question']}\n"
        f"Subtopic to research now: {subtopic}\n\n"
        "Write 2-3 sentences of key findings about this subtopic. "
        "Be specific and factual."
    )
    response = _llm.invoke([HumanMessage(content=prompt)])
    findings = list(state["findings"]) + [response.content.strip()]
    return {"findings": findings, "current_index": idx + 1}


def synthesize_node(state: ResearchState) -> dict:
    """Compose the final answer from all three findings."""
    subtopics = state["subtopics"]
    findings = state["findings"]
    findings_block = "\n".join(
        f"- {subtopics[i]}: {findings[i]}" for i in range(len(findings))
    )
    context_block = (
        f"\n\nConversation so far:\n{state['context']}" if state["context"] else ""
    )
    prompt = (
        f"You are a synthesis writer.{context_block}\n\n"
        f"Original question: {state['question']}\n\n"
        f"Research findings:\n{findings_block}\n\n"
        "Write a clear, cohesive answer that integrates all three findings. "
        "Aim for 3-5 sentences. Reference earlier conversation context if relevant."
    )
    response = _llm.invoke([HumanMessage(content=prompt)])
    return {"final_answer": response.content.strip()}


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------


def should_continue_research(state: ResearchState) -> str:
    """Route back to ``research`` until all 3 subtopics are covered."""
    if state["current_index"] < len(state["subtopics"]):
        return "research"
    return "synthesize"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------


def _build_graph() -> object:
    g = StateGraph(ResearchState)
    g.add_node("plan", plan_node)
    g.add_node("research", research_node)
    g.add_node("synthesize", synthesize_node)

    g.set_entry_point("plan")
    g.add_edge("plan", "research")
    g.add_conditional_edges("research", should_continue_research)
    g.add_edge("synthesize", END)

    return g.compile()


_graph = _build_graph()

# ---------------------------------------------------------------------------
# Observed entry point
# ---------------------------------------------------------------------------


@waxell.observe(agent_name="langgraph-research", session_id=_SESSION_ID)
def research_turn(question: str, context: str) -> str:
    """One conversational turn. Each call = one Waxell run with 5 LLM spans.

    ``question`` is the user's current message; ``context`` is a compact
    summary of prior turns so the model has memory across REPL sessions.
    """
    ctx = waxell.get_current_context()
    if ctx is not None:
        ctx.record_user_message(content=question)
    initial_state: ResearchState = {
        "question": question,
        "context": context,
        "subtopics": [],
        "findings": [],
        "current_index": 0,
        "final_answer": "",
    }
    result = _graph.invoke(initial_state)
    final_answer = result["final_answer"]
    if ctx is not None:
        ctx.record_agent_response(final_answer)
    return final_answer


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------


def repl() -> None:
    print("langgraph-research — type any research question, or /reset, /exit.")
    # conversation_memory holds compact prior-answer summaries for context
    conversation_memory: list[str] = []

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
            conversation_memory.clear()
            print("(conversation reset)")
            continue

        context = "\n".join(conversation_memory) if conversation_memory else ""
        answer = research_turn(user, context)
        print(f"\nassistant> {answer}\n")

        # Keep a rolling memory of the last 3 turns (question + answer pairs)
        conversation_memory.append(f"Q: {user}\nA: {answer}")
        if len(conversation_memory) > 3:
            conversation_memory.pop(0)


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write(
            "OPENAI_API_KEY is not set in .env — add it and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
