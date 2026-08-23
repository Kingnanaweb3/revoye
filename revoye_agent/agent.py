from google.adk.agents.llm_agent import Agent

from .models import build_model
from .resilience import degrade_on_model_error
from .armor import screen_tool_result

from .sub_agents.forecaster import demand_forecaster
from .sub_agents.negotiator import supplier_negotiator
from .sub_agents.tracker import logistics_tracker
from .sub_agents.memory import save_to_memory

root_agent = Agent(
    model=build_model(),
    name="revoye_orchestrator",
    description=(
        "Coordinates a retail supply chain swarm: demand forecasting, "
        "supplier negotiation, and delivery tracking."
    ),
    instruction=(
        "You are the orchestrator for Revoyé, a retail supply chain agent "
        "swarm. Route each request to the right specialist:\n"
        "- demand_forecaster: for questions about stock levels or stockout risk\n"
        "- supplier_negotiator: for drafting purchase orders to restock\n"
        "- logistics_tracker: for checking delivery status and ETAs\n"
        "Typical flow: check risk with demand_forecaster first. If risk is "
        "high, hand off to supplier_negotiator to draft a PO, then use "
        "logistics_tracker to monitor the resulting shipment."
    ),
    sub_agents=[demand_forecaster, supplier_negotiator, logistics_tracker],
    after_agent_callback=save_to_memory,
    on_model_error_callback=degrade_on_model_error,
    after_tool_callback=screen_tool_result,
)
