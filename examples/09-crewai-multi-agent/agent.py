"""09-crewai-multi-agent — conversational REPL backed by a CrewAI crew.

Demonstrates that Waxell's CrewAI auto-instrumentor captures every
sub-agent invocation automatically. One crew kickoff = one Waxell run
with each agent's LLM calls nested underneath it as child spans — no
manual span work, no callback handlers.

The crew has two agents running sequentially:

  researcher — asks the LLM for 3 key facts about the user's topic.
  writer     — turns those 3 facts into a tight 2-paragraph blog-post
               summary.

Subject: a short-blog-post assistant. The user types a topic; the crew
researches and writes; the REPL prints the result. Prior topics are
threaded into the researcher's task description so follow-up questions
have context.

Run::

    ./setup.sh                       # one-time
    source .venv/bin/activate
    python agent.py

Then type topics at the ``you>`` prompt. Use ``/reset`` to start a
fresh session, ``/exit`` to quit.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import uuid

import waxell_observe as waxell

waxell.init()

_SESSION_ID = uuid.uuid4().hex  # stable for this REPL process; shared across all turns

from crewai import Agent, Crew, Process, Task

# ---------------------------------------------------------------------------
# Observed entry point
# ---------------------------------------------------------------------------


def _build_researcher() -> Agent:
    """Build a fresh researcher each turn.

    CrewAI Agents carry mutable state (internal AgentExecutor, conversation
    memory, cached tool calls). Reusing a module-level Agent across turns
    causes the second turn to inherit the first turn's executor state and
    can hang indefinitely while CrewAI tries to reconcile the stale
    context. Rebuilding per turn keeps each crew kickoff hermetic.

    ``max_iter`` bounds the agent's internal "re-prompt the model when
    output doesn't parse" loop so a malformed response can never spin
    forever; ``allow_delegation=False`` stops the agent from trying to
    hand work off to its peers (the most common CrewAI hang).
    """
    return Agent(
        role="Research Analyst",
        goal="Gather exactly 3 key facts about the given topic.",
        backstory=(
            "You are a meticulous research analyst. When given a topic you "
            "identify the 3 most interesting, verifiable facts and present "
            "them as a numbered list. You are concise and factual."
        ),
        llm="gpt-4o-mini",
        verbose=False,
        max_iter=3,
        allow_delegation=False,
    )


def _build_writer() -> Agent:
    """Build a fresh writer each turn (same rationale as the researcher)."""
    return Agent(
        role="Blog Writer",
        goal="Turn research findings into a polished 2-paragraph blog summary.",
        backstory=(
            "You are a skilled technology blogger. Given a numbered list of "
            "research facts you craft an engaging, well-structured 2-paragraph "
            "summary suitable for a general audience. You do not invent new "
            "facts — you work only from what the researcher provided."
        ),
        llm="gpt-4o-mini",
        verbose=False,
        max_iter=3,
        allow_delegation=False,
    )


@waxell.observe(agent_name="crewai-multi-agent", session_id=_SESSION_ID)
def blog_turn(topic: str, prior_topics: list[str]) -> str:
    """One conversational turn.

    Each call = one Waxell run. The CrewAI auto-instrumentor nests each
    agent's LLM call underneath the parent run automatically, so the run
    tree shows:

      crewai-multi-agent (parent)
        └── researcher LLM call
        └── writer LLM call

    ``prior_topics`` is the list of topics discussed so far, threaded
    into the researcher's task so the crew can handle follow-up questions.
    """
    ctx = waxell.get_current_context()
    if ctx is not None:
        ctx.record_user_message(content=topic)
    context_block = ""
    if prior_topics:
        listed = "\n".join(f"  - {t}" for t in prior_topics)
        context_block = (
            f"\n\nFor context, the user has already asked about these topics "
            f"in this session:\n{listed}\n"
            "If the current topic is a follow-up, acknowledge the connection."
        )

    # Fresh agents + tasks + crew every turn. See _build_researcher for why.
    researcher = _build_researcher()
    writer = _build_writer()

    research_task = Task(
        description=(
            f"Research the following topic and return exactly 3 key facts "
            f"as a numbered list (1. ... 2. ... 3. ...).\n\n"
            f"Topic: {topic}{context_block}"
        ),
        expected_output="A numbered list of exactly 3 key facts about the topic.",
        agent=researcher,
    )

    write_task = Task(
        description=(
            "You have been given a numbered list of 3 research facts. "
            "Write a 2-paragraph blog-post summary based solely on those facts. "
            "The first paragraph introduces the topic and covers facts 1–2. "
            "The second paragraph covers fact 3 and ends with a forward-looking "
            "sentence. Keep each paragraph to 3-4 sentences. "
            f"The topic is: {topic}"
        ),
        expected_output=(
            "A 2-paragraph blog summary (no headings, plain prose)."
        ),
        agent=writer,
        context=[research_task],
    )

    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
        process=Process.sequential,
        verbose=False,
        memory=False,  # Don't share memory across runs — each turn is hermetic.
    )

    result = crew.kickoff()
    # CrewAI returns a CrewOutput object; .raw holds the final string.
    final = str(result.raw) if hasattr(result, "raw") else str(result)
    if ctx is not None:
        ctx.record_agent_response(final)
    return final


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------


def repl() -> None:
    print("crewai-multi-agent — type a topic for a short blog post, or /reset, /exit.")
    prior_topics: list[str] = []

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
            prior_topics.clear()
            print("(conversation reset)")
            continue

        print("(crew is working…)\n")
        answer = blog_turn(user, prior_topics)
        print(f"assistant>\n{answer}\n")

        prior_topics.append(user)
        # Keep a rolling window of the last 5 topics for context
        if len(prior_topics) > 5:
            prior_topics.pop(0)


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write(
            "OPENAI_API_KEY is not set in .env — add it and re-run.\n"
        )
        sys.exit(1)
    repl()


if __name__ == "__main__":
    main()
