"""Policy definitions for 10-judge-evaluation.

Push with::

    wax policies push policies.py

The ``example-tone-judge`` policy uses the ``quality`` category handler
(``QualityHandler``) with an ``llm_checks`` entry — the LLM-judge path.
After each agent run completes, Waxell sends the agent's output to a
separate evaluator model which scores the response on empathy and
actionability.  A score below 0.65 triggers a WARN incident.  The
conversation is never blocked (``action: "warn"``), so you can read the
verdict in the Governance panel without interrupting the REPL.

Rules shape mirrors ``QualityHandler.llm_checks`` exactly — see:
  infra/waxell-infra/src/waxell_infra/policies/dynamic/handlers/misc.py
  infra/waxell-infra/src/waxell_infra/policies/dynamic/handlers/quality_checks.py
"""

from waxell_sdk import policy

example_tone_judge = policy(
    name="example-tone-judge",
    category="quality",
    scope={"agents": ["judge-evaluation"]},
    description=(
        "LLM-judge policy that grades every customer-support reply on "
        "empathy and actionability.  Scores below 0.65 raise a WARN "
        "incident visible in the Governance panel."
    ),
    rules={
        "llm_checks": [
            {
                "criteria": (
                    "Score this customer-support reply on two dimensions: "
                    "(1) Empathy — does the reply acknowledge the customer's "
                    "frustration and make them feel heard? "
                    "(2) Actionability — does the reply give the customer a "
                    "clear next step or concrete resolution path? "
                    "Return a single score between 0.0 (completely fails both) "
                    "and 1.0 (excellent on both). A score of 0.65 or higher "
                    "means the reply is acceptable."
                ),
                "action": "warn",
                "model": "gpt-4o",
                "threshold": 0.65,
            }
        ]
    },
)
