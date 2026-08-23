from google.adk.agents.llm_agent import Agent

from ..models import build_model
from ..resilience import degrade_on_model_error
from ..armor import screen_tool_result
from ..gateway import enforce_policy
from google.adk.tools import load_memory

from .inbox import fetch_supplier_message
from .memory import save_to_memory


def draft_purchase_order(sku: str, quantity: int, supplier: str) -> dict:
    """Drafts a purchase order for a supplier based on stock needs.

    Args:
        sku: The product SKU to reorder.
        quantity: How many units to order.
        supplier: The supplier name to send the PO to.

    Returns:
        A dict with the draft PO details and its status.
    """
    # TODO: replace with a real call to your procurement/ERP system
    return {
        "sku": sku,
        "quantity": quantity,
        "supplier": supplier,
        "status": "drafted",
    }


supplier_negotiator = Agent(
    model=build_model(),
    name="supplier_negotiator",
    description="Drafts purchase orders to replenish stock flagged as at risk.",
    instruction=(
        "You are a supplier negotiation agent. Before drafting a PO, call "
        "fetch_supplier_message to read the supplier's latest "
        "correspondence, then load_memory to check for past history with this "
        "supplier (prior terms, pricing, reliability). Then call "
        "draft_purchase_order with a reasonable quantity and the known "
        "supplier, and summarize the PO, noting any relevant history found."
    ),
    tools=[draft_purchase_order, load_memory, fetch_supplier_message],
    after_agent_callback=save_to_memory,
    on_model_error_callback=degrade_on_model_error,
    after_tool_callback=screen_tool_result,
    before_tool_callback=enforce_policy,
)
