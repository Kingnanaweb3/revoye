# Revoyé

A retail supply chain agent swarm built on Google ADK and Gemini 3.6 Flash.
Submitted to the All Things Agentic Hackathon, **Fortified Enterprise Fleet** track.

## The problem

A mid-sized retailer has someone whose job is watching which products are
running low, emailing suppliers, comparing what was quoted last time, drafting
purchase orders, and chasing shipments. It is repetitive, spread across a stock
system and an inbox, and the most valuable part — remembering that this supplier
was late twice and that one came back with better terms — lives only in that
person's head.

## What it does

An orchestrator delegates to three specialists:

| Agent | Responsibility |
|---|---|
| `demand_forecaster` | Flags stockout risk from sales trends |
| `supplier_negotiator` | Reads supplier correspondence, checks prior terms, drafts POs |
| `logistics_tracker` | Tracks shipment status and ETAs |

Delegation uses ADK's built-in `transfer_to_agent`.

## Governance layer

| Component | Implementation | File |
|---|---|---|
| Memory Bank | `after_agent_callback` on every sub-agent | `sub_agents/memory.py` |
| Model Armor | `after_tool_callback` — quarantines injection, redacts PII | `armor.py` |
| Agent Gateway | `before_tool_callback` — tainted source and value threshold policies | `gateway.py` |
| Resilience | `on_model_error_callback` — degrades, never fabricates | `resilience.py` |
| Model layer | Retry with backoff on 429/503 | `models.py` |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full diagram and request path.

## Running locally

Requires Python 3.11+ and a Google AI Studio API key.

```bash
git clone https://github.com/Kingnanaweb3/revoye.git
cd revoye
pip install google-adk==2.6.2
```

Create `revoye_agent/.env`:

```
GOOGLE_API_KEY=your_key_here
GOOGLE_GENAI_USE_ENTERPRISE=0
```

Then, from the repository root:

```bash
adk web                # browser UI with trace panel at http://127.0.0.1:8000
adk run revoye_agent   # terminal REPL
```

## Try these

**Benign correspondence.** The negotiator reads the message, checks memory, drafts the PO.

```
Check the latest message from Meridian Supply and draft a PO for SKU-4471.
```

**Prompt injection.** This supplier's message tries to override the agent's
instructions. Model Armor quarantines it and the Agent Gateway refuses to raise a
PO against a tainted source — even though the model still attempts the draft.

```
Check the latest message from Northwind Parts and draft a PO for SKU-9902.
```

**PII redaction.** Contact details are stripped before the model sees them, so it
cannot recite them even when asked directly.

```
Read the latest correspondence from Calder Freight and tell me the driver contact details for the SKU-4471 delivery.
```

## Scope and honesty

- Tool functions return fixed values. They are stubs standing in for inventory,
  procurement, and logistics connectors, not live integrations.
- `fetch_supplier_message` is the only tool with branching logic; it serves three
  canned messages used to exercise the guardrails.
- Cloud Run deployment and the Vertex AI backend are in progress.

## Findings

**ADK ends a delegating agent's turn early.** A memory-saving
`after_agent_callback` on the orchestrator never fires once it hands off, because
only the agent that *finishes* the turn gets its callback called. The callback has
to live on every sub-agent. The parameter must also be named `callback_context`,
since ADK calls it by keyword.

**Guardrails belong at the tool boundary, not the model boundary.** Screening
`llm_request.contents` in a `before_model_callback` looks correct and is not: the
filter cannot distinguish attacker-controlled text from the agent's own trusted
output, so it flagged its own prior messages while the real injected payload —
arriving as a tool result — passed through unscreened. Moving the screen to
`after_tool_callback` fixed both failure modes.

**Persuading a model is not the same as constraining it.** With Armor alone, the
model still attempted to draft a PO from a quarantined message. Enforcement had to
move into `before_tool_callback`, where returning a value means the tool never
executes regardless of what the model decides.
