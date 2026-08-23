"""Agent Gateway: policy enforcement at the tool boundary.

Model Armor persuades the model. The gateway removes the option: returning a
value from before_tool_callback means the tool never executes, so a confused
or compromised model cannot draft a purchase order regardless of what it
decides to do.

Two policies:
  1. No PO against a supplier whose latest correspondence Armor quarantined.
  2. No PO above APPROVAL_THRESHOLD without explicit human approval.
"""

APPROVAL_THRESHOLD = 10000
GATED_TOOLS = {"draft_purchase_order"}
ASSUMED_UNIT_PRICE = 25


def enforce_policy(*, tool, args, tool_context):
    if tool.name not in GATED_TOOLS:
        return None

    supplier = args.get("supplier")
    quantity = args.get("quantity") or 0

    verdict = None
    if tool_context is not None and supplier:
        verdict = tool_context.state.get(f"armor:{supplier}")

    if verdict == "BLOCKED":
        return {
            "status": "DENIED_BY_GATEWAY",
            "policy": "tainted_source",
            "detail": (
                f"Correspondence from {supplier} was quarantined by Model "
                "Armor. Purchase orders cannot be raised against a supplier "
                "whose inbound data failed screening. No PO was created."
            ),
        }

    value = quantity * ASSUMED_UNIT_PRICE
    if value > APPROVAL_THRESHOLD:
        return {
            "status": "HELD_FOR_APPROVAL",
            "policy": "value_threshold",
            "estimated_value": value,
            "threshold": APPROVAL_THRESHOLD,
            "detail": (
                f"Estimated order value {value} exceeds the automatic "
                f"approval limit of {APPROVAL_THRESHOLD}. Queued for human "
                "sign-off. No PO was created."
            ),
        }

    return None
