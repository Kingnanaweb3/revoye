# Revoyé

A retail supply chain agent swarm that scans live inventory on a schedule,
decides what to reorder, and raises purchase orders on its own — behind
guardrails that stop it acting on poisoned supplier email.

Built on Google ADK and Gemini 3.6 Flash. Submitted to the All Things Agentic
Hackathon, **Fortified Enterprise Fleet** track.

**Live:** https://revoye-900638801452.us-central1.run.app

---

## The problem

Bellworth Home is a mid-sized kitchen and homeware retailer: around 2,400
products, eleven suppliers, and one buyer doing all of it by hand. Watching which
items are running low, emailing suppliers, comparing what was quoted last time,
drafting purchase orders, chasing deliveries.

The most valuable part of that job — remembering that one supplier was late twice
and another came back with better terms — lives only in that person's head.

## What it does

**On a schedule, unattended.** Every interval, a Cloud Run Job scans the live
inventory, finds every SKU at risk of stockout, and hands each one to the swarm.
Nobody types anything. A typical run:

```
Scanned 5 SKUs, 3 at risk
  → SKU-9902 (critical) via Northwind Ceramics    blocked
  → SKU-3390 (critical) via Kettleworth Foundry   ordered
  → SKU-4471 (high)     via Kettleworth Foundry   ordered

{'blocked': 1, 'ordered': 2}
Needs a human: SKU-9902
```

Two purchase orders raised, one supplier refused because its inbound
correspondence failed security screening, and one item surfaced for a person to
look at. The operator reads the exception queue, not the whole catalogue.

**Interactively, when asked.** The same swarm answers direct questions through
the deployed web interface, with a full reasoning trace for every decision.

## The agents

An orchestrator routes each request to a specialist using ADK's built-in
`transfer_to_agent`:

| Agent | Responsibility |
|---|---|
| `demand_forecaster` | Reads live stock and flags stockout risk from weeks of cover |
| `supplier_negotiator` | Reads supplier correspondence, recalls prior terms, raises POs |
| `logistics_tracker` | Tracks shipment status and carrier correspondence |

## Governance layer

Every guardrail is an ADK callback, which is what makes them impossible to talk
around.

| Component | Hook | What it does |
|---|---|---|
| Model Armor | `after_tool_callback` | Quarantines prompt injection and redacts PII in untrusted inbound messages |
| Agent Gateway | `before_tool_callback` | Blocks POs from quarantined suppliers or above a value threshold |
| Agent Identity | `before_tool_callback` | Per-agent tool and data scoping, default-deny for anything unregistered |
| Memory Bank | Firestore-backed tools | Negotiation history that survives sessions, processes and redeploys |
| Resilience | `on_model_error_callback` | Retries with backoff, then degrades explicitly rather than fabricating |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the diagram and request path.

## Stack

- **Gemini 3.6 Flash** on **Vertex AI** — all four agents
- **Google ADK 2.6.2** — agents, delegation, and the callback surface the
  governance layer is built on
- **Cloud Run** — the deployed swarm and its web interface
- **Cloud Run Jobs** + **Cloud Scheduler** — autonomous interval runs
- **Firestore** — inventory, supplier memory, purchase orders, run summaries

## Firestore collections

| Collection | Contents |
|---|---|
| `inventory` | Product master with stock on hand, weekly sales, reorder points |
| `supplier_memory` | Agreed terms and reliability notes, written by the agents |
| `purchase_orders` | POs the swarm has raised, with reference, value and status |
| `runs` | One document per autonomous run: tally, decisions, exception list |

## Running it yourself

Requires Python 3.10+, a Google Cloud project with billing, and the `gcloud` CLI.

```bash
git clone https://github.com/Kingnanaweb3/revoye.git
cd revoye
pip install -r requirements.txt
```

**Authenticate and configure.** The swarm runs on Vertex AI, so it uses
application default credentials rather than an API key:

```bash
gcloud auth application-default login
gcloud services enable run.googleapis.com aiplatform.googleapis.com firestore.googleapis.com
```

Create `revoye_agent/.env`:

```
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
```

> `GOOGLE_CLOUD_LOCATION` must be `global`. On Vertex, Gemini 3.x models are
> served only from the global endpoint; regional endpoints return 404.

**Firestore access.** Locally, download a service account key to
`firebase-key.json` in the project root (it is gitignored). On Cloud Run the
service identity is used instead and no key file is needed — grant it
`roles/datastore.user`.

**Seed the inventory** so the forecaster has something to read:

```bash
python3 seed_inventory.py
```

**Run it:**

```bash
adk web                # browser UI with the reasoning trace
adk run revoye_agent   # terminal
python3 autorun.py     # one autonomous pass over the whole catalogue
```

## Deploying

```bash
adk deploy cloud_run --project=YOUR_PROJECT --region=us-central1 \
  --service_name=revoye --with_ui revoye_agent \
  -- --set-env-vars=GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT,GOOGLE_CLOUD_LOCATION=global \
     --timeout=600
```

For the autonomous runs:

```bash
gcloud run jobs deploy revoye-autorun --source . --region=us-central1 \
  --task-timeout=900 --max-retries=1 \
  --set-env-vars=GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT,GOOGLE_CLOUD_LOCATION=global

gcloud scheduler jobs create http revoye-autorun-schedule --location=us-central1 \
  --schedule="0 */5 * * *" \
  --uri="https://run.googleapis.com/v2/projects/YOUR_PROJECT/locations/us-central1/jobs/revoye-autorun:run" \
  --http-method=POST --oauth-service-account-email=YOUR_COMPUTE_SA
```

> ADK reads `requirements.txt` from **inside the agent folder**
> (`revoye_agent/requirements.txt`), not the repository root. A copy lives in
> both places for that reason.

## Try these

**Normal path.** Benign correspondence; the negotiator reads it, checks memory,
raises the order.

```
Check the latest message from Kettleworth Foundry and draft a PO for 200 units of SKU-4471.
```

**Prompt injection.** This supplier's message tries to override the agent's
instructions. Armor quarantines it and the Gateway refuses to raise a PO against
a tainted source — even though the model still attempts the draft.

```
Check the latest message from Northwind Ceramics and draft a PO for SKU-9902.
```

**PII redaction.** Contact details are stripped before the model sees them, so it
cannot recite them even when asked directly.

```
Read the latest correspondence from Calder Freight and tell me the driver contact details for the SKU-4471 delivery.
```

**Persistent memory.** Start a new session and ask this. It answers from
Firestore, not conversation history.

```
What have we previously agreed with Kettleworth Foundry?
```

> Name the supplier explicitly in each prompt, and use a fresh session per
> scenario. Vague follow-ups inherit the previous supplier's context.

## Scope and honesty

- The inventory is a seeded product master rather than a live ERP sync. Stock
  levels, purchase orders and supplier memory are all real Firestore documents
  that the agents read and write; what is missing is the connector that would
  populate inventory from a retailer's own system.
- `check_delivery_status` still returns fixed values. It stands in for a
  logistics provider integration.
- Injection and PII detection are pattern-based, not classifier-based. Effective
  on the demonstrated attacks; not a claim of completeness.
- Suppliers, products and correspondence are fictional, written to exercise the
  guardrails.

## Findings

**A delegating agent's turn ends early, so its callbacks never fire.** The Memory
Bank silently recalled nothing for a long time. `load_memory` ran without error
and always came back empty. The save callback sat on the orchestrator, but ADK
ends a delegating agent's turn early on handoff, so only the agent that *finishes*
the turn gets its callback invoked. It has to live on every sub-agent, and the
parameter must be named `callback_context`.

**Guardrails belong at the tool boundary, not the model boundary.** The first
Model Armor screened `llm_request.contents` in a `before_model_callback`, which
sounds like the safest possible place. It failed both ways at once: the injected
message passed through because it arrived as a *tool result* rather than
conversation history, while a benign message got blocked because the filter
matched its own earlier quarantine notice. Screening at the model boundary cannot
distinguish attacker-controlled text from the agent's own trusted output.

**Persuading a model is not the same as constraining it.** Even with the message
quarantined, the model attempted the purchase order anyway. Enforcement moved
into `before_tool_callback`, where returning a value means the tool never
executes at all.

**Default-deny needs a complete allow-list.** Agent Identity initially blocked the
orchestrator's own `transfer_to_agent`. Delegation failed silently and the model
wrote a convincing purchase order in prose instead of reporting that it could not
act. Guardrails constrain actions, not claims.

**The dev harness hides its dependencies.** Running the swarm outside `adk web`
surfaced two implicit ones in a row: `.env` is loaded by the ADK CLI but not by a
bare Python process, and `Runner` needs an explicit `memory_service` or the
memory callback raises. Neither is visible until you leave the harness.
