"""
Cost-warn policy for example 05-policy-warn-cost.

The ``budget`` category handler checks per-workflow token and cost usage
after each run.  ``action_on_exceed: warn`` means the run always
completes — the policy fires a detective warning incident rather than
blocking execution.

Thresholds are kept intentionally low (500 tokens / $0.01) so the demo
trips on a single verbose response.
"""

from waxell_sdk import policy

example_cost_warn = policy(
    name="example-cost-warn",
    category="budget",
    scope={"agents": ["policy-warn-cost"]},
    rules={
        "per_workflow_token_limit": 500,
        "per_workflow_cost_limit": 0.01,
        "action_on_exceed": "warn",
    },
    description=(
        "Warn when a single creative-writing turn exceeds 500 tokens or $0.01. "
        "Run still completes — this is a detective (warn) policy, not a block."
    ),
)
