from google.adk.agents.llm_agent import Agent

from ..models import build_model
from ..resilience import degrade_on_model_error
from ..identity import enforce_scope
from ..armor import screen_tool_result

from .inbox import fetch_supplier_message
from .memory import save_to_memory


def check_delivery_status(sku: str, supplier: str) -> dict:
    """Checks delivery status and ETA for an outstanding order.

    Args:
        sku: The product SKU being shipped.
        supplier: The supplier fulfilling the order.

    Returns:
        A dict with shipment status and estimated days until arrival.
    """
    # TODO: replace with a real call to your logistics/webhook provider
    return {
        "sku": sku,
        "supplier": supplier,
        "status": "in_transit",
        "eta_days": 5,
    }


logistics_tracker = Agent(
    model=build_model(),
    name="logistics_tracker",
    description="Monitors delivery status and ETAs for outstanding purchase orders.",
    instruction=(
        "You are a logistics tracking agent. When asked about an order, "
        "call check_delivery_status to get its current status and ETA. "
        "If asked about carrier correspondence, call fetch_supplier_message. "
        "then report it clearly."
    ),
    tools=[check_delivery_status, fetch_supplier_message],
    after_agent_callback=save_to_memory,
    on_model_error_callback=degrade_on_model_error,
    before_tool_callback=enforce_scope,
    after_tool_callback=screen_tool_result,
)
