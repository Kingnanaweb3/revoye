"""Central model construction for the swarm.

Every agent builds its model here so retry policy is defined once. Using
Gemini(...) objects instead of bare model-name strings is what makes
retry_options attachable at all.
"""

from google.adk.models.google_llm import Gemini
from google.genai.types import HttpRetryOptions

DEFAULT_MODEL = "gemini-3.6-flash"

# 429 = free-tier quota exhausted, 503 = upstream capacity spike.
# Both are transient, so back off and retry rather than failing the run.
RETRY = HttpRetryOptions(
    attempts=6,
    initial_delay=2.0,
    max_delay=45.0,
    exp_base=2.0,
    jitter=0.3,
    http_status_codes=[429, 503],
)


def build_model(name: str = DEFAULT_MODEL) -> Gemini:
    return Gemini(model=name, retry_options=RETRY)
