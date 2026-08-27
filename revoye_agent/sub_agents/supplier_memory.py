"""Persistent supplier memory, backed by Cloud Firestore.

ADK's --memory_service_uri only accepts rag://, agentengine:// and memory://,
and the two persistent options both require Vertex AI. Rather than fight the
service layer, the swarm reaches Firestore through ordinary tools. The agent
decides when to recall and when to record; the data outlives the process
either way.

What is stored here is judgement, not facts: agreed terms, lead times,
reliability notes. Live stock levels and delivery status stay in the systems
that own them and are queried fresh each time.
"""

import os
import threading
from datetime import datetime, timezone

from google.cloud import firestore

COLLECTION = "supplier_memory"
KEY_PATH = os.environ.get("FIRESTORE_KEY_PATH", "firebase-key.json")

_client = None
_lock = threading.Lock()


def _db():
    global _client
    with _lock:
        if _client is None:
            _client = firestore.Client.from_service_account_json(KEY_PATH)
        return _client


def recall_supplier_history(supplier: str) -> dict:
    """Recalls what was agreed with a supplier in earlier sessions.

    Args:
        supplier: The supplier or carrier name to look up.

    Returns:
        A dict with any prior notes on record for that supplier.
    """
    docs = list(
        _db()
        .collection(COLLECTION)
        .where(filter=firestore.FieldFilter("supplier", "==", supplier))
        .stream()
    )

    if not docs:
        return {
            "supplier": supplier,
            "found": False,
            "notes": [],
            "summary": f"No prior negotiation history on record for {supplier}.",
        }

    notes = []
    for doc in docs:
        data = doc.to_dict() or {}
        notes.append(
            {
                "recorded_at": data.get("recorded_at"),
                "note": data.get("note"),
            }
        )
    notes.sort(key=lambda n: n.get("recorded_at") or "")

    return {
        "supplier": supplier,
        "found": True,
        "count": len(notes),
        "notes": notes,
        "summary": f"{len(notes)} prior note(s) on record for {supplier}.",
    }


def record_supplier_note(supplier: str, note: str) -> dict:
    """Records a durable note about a supplier for future sessions.

    Use this for agreed terms, lead times, pricing or reliability
    observations. Do not use it for live stock or delivery status.

    Args:
        supplier: The supplier or carrier the note concerns.
        note: The detail worth remembering, in one or two sentences.

    Returns:
        A dict confirming what was stored.
    """
    recorded_at = datetime.now(timezone.utc).isoformat()
    _db().collection(COLLECTION).add(
        {
            "supplier": supplier,
            "note": note,
            "recorded_at": recorded_at,
        }
    )
    return {
        "supplier": supplier,
        "note": note,
        "recorded_at": recorded_at,
        "status": "recorded",
    }
