"""Firestore-backed Memory Bank.

Implements ADK's BaseMemoryService against Cloud Firestore, so negotiation
history survives process restarts and is visible in the Google Cloud console.

The swarm was built against the abstract BaseMemoryService from the start,
which is what makes this a new class rather than a rewrite: nothing in the
agents changes.

Each memory is stored as its own document so the collection is legible in the
console during a demo. Search is keyword matching, mirroring what
InMemoryMemoryService does — a production deployment would use vector search.
"""

import os
import threading

from google.adk.memory.base_memory_service import BaseMemoryService
from google.adk.memory.base_memory_service import SearchMemoryResponse
from google.adk.memory.memory_entry import MemoryEntry
from google.cloud import firestore
from google.genai import types

COLLECTION = "revoye_memory"
KEY_PATH = os.environ.get("FIRESTORE_KEY_PATH", "firebase-key.json")

_client = None
_client_lock = threading.Lock()


def _db():
    """Lazily builds a shared Firestore client."""
    global _client
    with _client_lock:
        if _client is None:
            _client = firestore.Client.from_service_account_json(KEY_PATH)
        return _client


def _text_of(content) -> str:
    """Flattens a Content object to searchable plain text."""
    if content is None or not getattr(content, "parts", None):
        return ""
    return " ".join(p.text for p in content.parts if getattr(p, "text", None))


def _doc_id(session_id: str, event_id: str) -> str:
    return f"{session_id}__{event_id}"


class FirestoreMemoryService(BaseMemoryService):
    """Persists session history to Firestore."""

    def _write(self, app_name, user_id, session_id, event):
        text = _text_of(event.content)
        if not text.strip():
            return
        _db().collection(COLLECTION).document(
            _doc_id(session_id, event.id or "noid")
        ).set(
            {
                "app_name": app_name,
                "user_id": user_id,
                "session_id": session_id,
                "author": getattr(event, "author", None),
                "text": text,
                "content": event.content.model_dump(exclude_none=True),
                "stored_at": firestore.SERVER_TIMESTAMP,
            }
        )

    async def add_session_to_memory(self, session) -> None:
        for event in session.events:
            if event.content and event.content.parts:
                self._write(session.app_name, session.user_id, session.id, event)

    async def add_events_to_memory(
        self, *, app_name, user_id, events, session_id=None, custom_metadata=None
    ) -> None:
        for event in events:
            if event.content and event.content.parts:
                self._write(app_name, user_id, session_id or "unknown", event)

    async def add_memory(
        self, *, app_name, user_id, memories, custom_metadata=None
    ) -> None:
        for i, memory in enumerate(memories):
            text = _text_of(memory.content)
            if not text.strip():
                continue
            _db().collection(COLLECTION).document(
                _doc_id("explicit", memory.id or str(i))
            ).set(
                {
                    "app_name": app_name,
                    "user_id": user_id,
                    "session_id": "explicit",
                    "author": memory.author,
                    "text": text,
                    "content": memory.content.model_dump(exclude_none=True),
                    "stored_at": firestore.SERVER_TIMESTAMP,
                }
            )

    async def search_memory(self, *, app_name, user_id, query) -> SearchMemoryResponse:
        docs = (
            _db()
            .collection(COLLECTION)
            .where("app_name", "==", app_name)
            .where("user_id", "==", user_id)
            .stream()
        )

        words = {w.lower() for w in query.split() if len(w) > 2}
        memories = []
        for doc in docs:
            data = doc.to_dict() or {}
            text = (data.get("text") or "").lower()
            if words and not any(w in text for w in words):
                continue
            memories.append(
                MemoryEntry(
                    content=types.Content.model_validate(data["content"]),
                    author=data.get("author"),
                    id=doc.id,
                    custom_metadata={"session_id": data.get("session_id")},
                )
            )
        return SearchMemoryResponse(memories=memories)
