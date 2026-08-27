"""Agent Identity: zero-trust scoping of what each agent may reach.

Every agent declares the tools it is entitled to call and the data domains it
may touch. Enforcement runs as a before_tool_callback ahead of the Gateway:
returning a value means the tool never executes, so an agent cannot reach
outside its scope even if the model decides it should.

The principle is least privilege at the agent level. The negotiator can raise
purchase orders and read supplier correspondence; it cannot query inventory.
The forecaster can read inventory; it cannot spend money. Compromising one
agent does not hand an attacker the whole fleet.
"""

# Each agent's entitlements: the tools it may call, and the data domains those
# tools reach. Domains are declarative — they document the blast radius of a
# compromised agent for audit, and would map to real IAM scopes in production.
SCOPES = {
    "demand_forecaster": {
        "tools": {"check_stock_trend"},
        "domains": {"inventory:read", "sales:read"},
    },
    "supplier_negotiator": {
        "tools": {
            "draft_purchase_order",
            "fetch_supplier_message",
            "recall_supplier_history",
            "record_supplier_note",
        },
        "domains": {"procurement:write", "supplier_comms:read", "memory:read"},
    },
    "logistics_tracker": {
        "tools": {"check_delivery_status", "fetch_supplier_message"},
        "domains": {"logistics:read", "supplier_comms:read"},
    },
    "revoye_orchestrator": {
        # The orchestrator may only delegate. It holds no data entitlements of
        # its own and cannot call a single domain tool directly.
        "tools": {"transfer_to_agent"},
        "domains": set(),
    },
}


def enforce_scope(*, tool, args, tool_context):
    """Denies any tool call outside the calling agent's declared entitlements."""
    agent = getattr(tool_context, "agent_name", None)
    if agent is None:
        return None

    scope = SCOPES.get(agent)
    if scope is None:
        return {
            "status": "DENIED_BY_IDENTITY",
            "reason": "unregistered_agent",
            "detail": (
                f"Agent '{agent}' has no registered identity. Tool calls from "
                "unregistered agents are denied by default."
            ),
        }

    if tool.name not in scope["tools"]:
        return {
            "status": "DENIED_BY_IDENTITY",
            "reason": "out_of_scope",
            "detail": (
                f"Agent '{agent}' is not entitled to call '{tool.name}'. "
                f"Its scope covers {sorted(scope['tools']) or 'no tools'}. "
                "No action was taken."
            ),
        }

    return None
