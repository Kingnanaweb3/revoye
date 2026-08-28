from google.adk.agents.llm_agent import Agent

from ..models import build_model
from ..resilience import degrade_on_model_error
from ..identity import enforce_scope
from ..catalog import describe
from ..armor import screen_tool_result

from .memory import save_to_memory


def check_stock_trend(sku: str, days: int = 30) -> dict:
    """Checks live stock position for a SKU and flags stockout risk.

    Reads the inventory collection in Firestore. Risk is weeks of cover
    (units on hand divided by weekly sales) measured against the SKU's
    reorder point.

    Args:
        sku: The product SKU to check.
        days: Sales history window, retained for interface compatibility.

    Returns:
        A dict with the live stock position and a risk level.
    """
    from ..inventory import stock_position

    return stock_position(sku)


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
    before_tool_callback=enforce_scope,
    after_tool_callback=screen_tool_result,
)
