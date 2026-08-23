"""Graceful degradation when model retries are exhausted.

HttpRetryOptions in models.py absorbs transient 429/503 with backoff. This
callback is the last line of defence: if retries still run out, it returns a
response explicitly marked as an error rather than letting one upstream
hiccup abort the whole orchestration.

The response never resembles a normal answer. In a procurement swarm a
plausible-looking fallback is how you get a phantom purchase order nobody
placed, so error_code and error_message are always populated and the body
states that no action was taken.
"""

from google.adk.models.llm_response import LlmResponse
from google.genai.types import Content, Part

TRANSIENT_MARKERS = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")


def degrade_on_model_error(*, callback_context, llm_request, error):
    detail = str(error)
    if not any(m in detail for m in TRANSIENT_MARKERS):
        return None
    agent = getattr(callback_context, "agent_name", "agent")
    text = (
        f"[{agent}] Upstream model unavailable after retries. "
        "NO ACTION WAS TAKEN: no purchase order was drafted, no record "
        "was written. Retry this request later."
    )
    return LlmResponse(
        error_code="UPSTREAM_UNAVAILABLE",
        error_message=detail[:500],
        turn_complete=True,
        content=Content(role="model", parts=[Part(text=text)]),
    )
