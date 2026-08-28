"""Revoyé autonomous run.

Scans Bellworth Home's live inventory, and for every SKU at risk of stockout
hands the problem to the agent swarm. Nobody types anything. The agents decide
what to do; the guardrails decide what they are allowed to do.

Each run writes a summary document to Firestore. That summary is the exception
queue an operator actually reads: what was ordered, what needs a signature, and
what was refused.

Deployed as a Cloud Run Job on a 5-hour schedule.
"""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

# adk run/web load the agent's .env automatically; a bare python invocation
# does not, so Vertex settings have to be read in explicitly.
_env = Path(__file__).parent / "revoye_agent" / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from google.cloud import firestore
from google.genai import types

from revoye_agent.agent import root_agent
from revoye_agent.inventory import scan_catalogue

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService

APP_NAME = "revoye_agent"
OPERATOR = "bellworth_autorun"
AT_RISK = {"critical", "high"}
KEY_PATH = os.environ.get("FIRESTORE_KEY_PATH", "firebase-key.json")


def _db():
    if os.path.exists(KEY_PATH):
        return firestore.Client.from_service_account_json(KEY_PATH)
    return firestore.Client()


def _tool_results(events):
    """Pulls every function response out of a turn's events."""
    out = []
    for event in events:
        content = getattr(event, "content", None)
        for part in (getattr(content, "parts", None) or []):
            fr = getattr(part, "function_response", None)
            if fr is not None:
                out.append({"tool": fr.name, "response": fr.response})
    return out


def _classify(results):
    """Reads the outcome off the tool results, not off the model's prose."""
    for r in results:
        resp = r.get("response")
        if not isinstance(resp, dict):
            continue
        status = resp.get("status") or resp.get("armor_status")
        if status == "DENIED_BY_GATEWAY":
            return "blocked", resp.get("detail", "")
        if status == "HELD_FOR_APPROVAL":
            return "held_for_approval", resp.get("detail", "")
        if status == "BLOCKED":
            return "blocked", resp.get("armor_reason", "")
    for r in results:
        resp = r.get("response")
        if isinstance(resp, dict) and resp.get("status") == "drafted":
            return "ordered", ""
    return "no_action", ""


async def _handle(runner, session_service, item):
    """Runs one at-risk SKU through the swarm as its own session."""
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=OPERATOR
    )

    prompt = (
        f"{item['sku']} ({item['product']}) is at {item['risk']} stockout risk: "
        f"{item['on_hand']} units on hand against {item['weekly_sales']} sold "
        f"per week, reorder point {item['reorder_point']}. "
        f"Check the latest message from {item['supplier']} and draft a purchase "
        f"order to bring stock back above the reorder point. Record what is agreed."
    )

    events = []
    async for event in runner.run_async(
        user_id=OPERATOR,
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
    ):
        events.append(event)

    results = _tool_results(events)
    outcome, detail = _classify(results)

    summary = ""
    for event in reversed(events):
        content = getattr(event, "content", None)
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "text", None):
                summary = part.text.strip()
                break
        if summary:
            break

    return {
        "sku": item["sku"],
        "product": item["product"],
        "supplier": item["supplier"],
        "risk": item["risk"],
        "on_hand": item["on_hand"],
        "weeks_of_cover": item["weeks_of_cover"],
        "outcome": outcome,
        "detail": detail,
        "agent_summary": summary[:1200],
        "tools_called": [r["tool"] for r in results],
    }


async def main():
    started = datetime.now(timezone.utc)
    catalogue = scan_catalogue()
    at_risk = [i for i in catalogue if i["risk"] in AT_RISK]

    print(f"Revoyé autonomous run — {started.isoformat()}")
    print(f"Scanned {len(catalogue)} SKUs, {len(at_risk)} at risk\n")

    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
        # Satisfies ADK's after_agent_callback. Durable supplier memory is
        # separate, and lives in Firestore via the negotiator's tools.
        memory_service=InMemoryMemoryService(),
    )

    decisions = []
    for item in at_risk:
        print(f"  → {item['sku']} ({item['risk']}) via {item['supplier']}")
        try:
            decision = await _handle(runner, session_service, item)
        except Exception as exc:  # a failure on one SKU must not stop the run
            decision = {
                "sku": item["sku"],
                "product": item["product"],
                "supplier": item["supplier"],
                "risk": item["risk"],
                "outcome": "error",
                "detail": str(exc)[:400],
            }
        decisions.append(decision)
        print(f"    {decision['outcome']}")

    finished = datetime.now(timezone.utc)
    tally = {}
    for d in decisions:
        tally[d["outcome"]] = tally.get(d["outcome"], 0) + 1

    record = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 1),
        "skus_scanned": len(catalogue),
        "skus_at_risk": len(at_risk),
        "tally": tally,
        "needs_human": [d["sku"] for d in decisions
                        if d["outcome"] in ("held_for_approval", "blocked", "error")],
        "decisions": decisions,
    }

    _db().collection("runs").document(started.strftime("%Y%m%dT%H%M%SZ")).set(record)

    print(f"\nRun complete in {record['duration_seconds']}s")
    print(f"  {tally}")
    if record["needs_human"]:
        print(f"  Needs a human: {', '.join(record['needs_human'])}")

    await runner.close()


if __name__ == "__main__":
    asyncio.run(main())
