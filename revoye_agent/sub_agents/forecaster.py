from google.adk.agents.llm_agent import Agent

from ..models import build_model
from ..resilience import degrade_on_model_error
from ..armor import screen_tool_result

from .memory import save_to_memory


def check_stock_trend(sku: str, days: int = 30) -> dict:
    """Checks recent sales trend for a SKU and flags stockout risk.

    Args:
        sku: The product SKU to check.
        days: How many past days of sales history to analyze.

    Returns:
        A dict with the trend direction and risk level.
    """
    # TODO: replace with a real query against your inventory/sales data
    return {"sku": sku, "trend": "declining", "risk": "high"}


demand_forecaster = Agent(
    model=build_model(),
    name="demand_forecaster",
    description="Flags stockout risk by analyzing sales trends for a SKU.",
    instruction=(
        "You are a demand forecasting agent. When asked about a product, "
        "call check_stock_trend to assess its risk level, then report the "
        "trend and risk clearly."
    ),
    tools=[check_stock_trend],
    after_agent_callback=save_to_memory,
    on_model_error_callback=degrade_on_model_error,
    after_tool_callback=screen_tool_result,
)
