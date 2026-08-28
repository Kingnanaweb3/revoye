"""Live inventory reads, backed by Cloud Firestore.

Stock levels are facts, not judgement: they change constantly and are queried
fresh every time rather than cached into agent memory where they would go
stale. This is the read side of Bellworth Home's stock system.
"""

import os
import threading

from google.cloud import firestore

COLLECTION = "inventory"
KEY_PATH = os.environ.get("FIRESTORE_KEY_PATH", "firebase-key.json")

_client = None
_lock = threading.Lock()


def _db():
    global _client
    with _lock:
        if _client is None:
            if os.path.exists(KEY_PATH):
                _client = firestore.Client.from_service_account_json(KEY_PATH)
            else:
                _client = firestore.Client()
        return _client


def _assess(sku: str, data: dict) -> dict:
    on_hand = data.get("on_hand", 0)
    weekly = data.get("weekly_sales", 0) or 1
    reorder_point = data.get("reorder_point", 0)
    weeks_cover = round(on_hand / weekly, 1)

    if on_hand < reorder_point * 0.25:
        risk = "critical"
    elif on_hand < reorder_point:
        risk = "high"
    elif on_hand < reorder_point * 1.5:
        risk = "moderate"
    else:
        risk = "low"

    return {
        "sku": sku,
        "product": data.get("name"),
        "supplier": data.get("supplier"),
        "on_hand": on_hand,
        "weekly_sales": weekly,
        "reorder_point": reorder_point,
        "weeks_of_cover": weeks_cover,
        "trend": "declining" if on_hand < reorder_point else "stable",
        "risk": risk,
        "unit_cost": data.get("unit_cost"),
    }


def stock_position(sku: str) -> dict:
    """Returns the live stock position and risk level for one SKU."""
    doc = _db().collection(COLLECTION).document(sku).get()
    if not doc.exists:
        return {"sku": sku, "found": False,
                "detail": f"{sku} is not in the product catalogue."}
    return _assess(sku, doc.to_dict() or {})


def scan_catalogue() -> list:
    """Returns the live position for every SKU, worst risk first."""
    order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
    rows = [_assess(d.id, d.to_dict() or {})
            for d in _db().collection(COLLECTION).stream()]
    rows.sort(key=lambda r: (order.get(r["risk"], 9), -r["weekly_sales"]))
    return rows
