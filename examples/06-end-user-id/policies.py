"""Policy definitions for 06-end-user-id.

The ``end-user-budget`` category handler enforces a monthly spend cap
PER END USER (keyed by ``tenant_sub_user_id`` on the run context). The
cap itself lives on the ``WaxellUser`` row (``monthly_budget_cap_cents``)
— this policy just turns the enforcement on, and ``setup.sh`` provisions
the two demo end-users via ``wax end-users create``.

After setup:

  - alice@example.com has a $1000/month cap → effectively unlimited for
    the demo. Her runs always pass.
  - bob@example.com has a 1¢/month cap → exhausts on the very first
    real LLM turn. From his second turn onward, every run is blocked
    by this policy.

Same agent, same code, completely different per-end-user enforcement —
that's the whole point of the ``end_user_id`` parameter.
"""

from waxell_sdk import policy

example_end_user_budget = policy(
    name="example-end-user-budget",
    category="end-user-budget",
    scope={"agents": ["end-user-id"]},
    description=(
        "Enforce per-end-user monthly spend caps. The cap value lives on "
        "the WaxellUser row (monthly_budget_cap_cents); this policy just "
        "turns the enforcement on. Exceeded users get the run blocked; "
        "users at 80% of their cap get a warning incident."
    ),
    rules={
        "enabled": True,
        "action_on_exceed": "block",
        "warning_threshold_percent": 80,
    },
)
