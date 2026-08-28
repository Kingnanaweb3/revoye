"""Purchase order records, backed by Cloud Firestore.

A purchase order the swarm raises has to outlive the session that raised it.
Orders land in the purchase_orders collection with a reference, a value and a
status, which is what makes the exception queue reviewable by a human.
"""

import os
import threading
from datetime import datetime, timezone

from google.cloud import firestore

COLLECTION = "purchase_orders"
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


def write_order(*, sku: str, quantity: int, supplier: str) -> dict:
    """Persists a drafted purchase order and returns its reference."""
    from .inventory import stock_position

    position = stock_position(sku)
    unit_cost = position.get("unit_cost") or 0
    value = quantity * unit_cost

    raised_at = datetime.now(timezone.utc)
    ref = f"PO-{raised_at.strftime('%Y%m%d')}-{sku.split('-')[-1]}-{raised_at.strftime('%H%M%S')}"

    record = {
        "po_ref": ref,
        "sku": sku,
        "product": position.get("product"),
        "supplier": supplier,
        "quantity": quantity,
        "unit_cost": unit_cost,
        "order_value": value,
        "status": "drafted",
        "raised_at": raised_at.isoformat(),
        "raised_by": "revoye_swarm",
    }
    _db().collection(COLLECTION).document(ref).set(record)

    return {
        "po_ref": ref,
        "sku": sku,
        "supplier": supplier,
        "quantity": quantity,
        "order_value": value,
        "status": "drafted",
    }
