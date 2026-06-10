"""Policy definitions for 04-policy-block-pii.

Push with::

    wax policies push policies.py

The ``example-pii-block`` policy uses the ``content`` category handler
(``ContentHandler``).  Its ``pii_detection`` sub-config enables SSN-pattern
scanning with ``action: block``, so any prompt containing a US Social Security
Number (NNN-NN-NNNN) causes the run to be blocked before the LLM call lands.

Rules shape mirrors ``ContentHandler`` exactly — see:
  infra/waxell-infra/src/waxell_infra/policies/dynamic/handlers/content.py
"""

from waxell_sdk import policy

example_pii_block = policy(
    name="example-pii-block",
    category="content",
    scope={"agents": ["policy-block-pii"]},
    description=(
        "Blocks any prompt containing US SSN-like patterns (NNN-NN-NNNN). "
        "Uses the built-in SSN regex from the content handler."
    ),
    rules={
        "scan_inputs": True,
        "scan_outputs": False,
        "pii_detection": {
            "enabled": True,
            "action": "block",
            "types": ["ssn"],
        },
    },
)
