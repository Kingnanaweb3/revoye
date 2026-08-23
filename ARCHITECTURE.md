# Revoyé — Architecture

```mermaid
flowchart TB
    User([Operator]) --> ORCH

    subgraph SWARM["Agent Swarm — Google ADK"]
        ORCH["revoye_orchestrator<br/>routes by intent"]
        ORCH -->|transfer_to_agent| FC["demand_forecaster"]
        ORCH -->|transfer_to_agent| NG["supplier_negotiator"]
        ORCH -->|transfer_to_agent| TR["logistics_tracker"]
    end

    subgraph TOOLS["Tools — stubs for enterprise connectors"]
        T1["check_stock_trend<br/><i>inventory / sales</i>"]
        T2["draft_purchase_order<br/><i>procurement / ERP</i>"]
        T3["check_delivery_status<br/><i>logistics</i>"]
        T4["fetch_supplier_message<br/><i>UNTRUSTED inbound</i>"]
        T5["load_memory"]
    end

    FC --> T1
    NG --> T2
    NG --> T5
    NG --> T4
    TR --> T3
    TR --> T4

    subgraph GOV["Governance Layer — ADK callbacks"]
        ARMOR["Model Armor<br/>after_tool_callback<br/>quarantine injection · redact PII"]
        GATE["Agent Gateway<br/>before_tool_callback<br/>tainted source · value threshold"]
        MEM["Memory Bank<br/>after_agent_callback<br/>on every sub-agent"]
        RES["Resilience<br/>on_model_error_callback<br/>degrade, never fabricate"]
    end

    T4 -.screened by.-> ARMOR
    ARMOR -.writes verdict to session state.-> GATE
    GATE -.gates.-> T2
    SWARM -.-> MEM
    SWARM -.-> RES

    subgraph MODEL["Model Layer — models.py"]
        GEM["Gemini 3.6 Flash<br/>HttpRetryOptions<br/>6 attempts · backoff 2s→45s · 429/503"]
    end

    SWARM --> GEM
    MEM --> MBS[("InMemoryMemoryService<br/>→ VertexAiMemoryBankService")]

    subgraph GCP["Google Cloud — planned"]
        CR["Cloud Run"]
        VX["Vertex AI"]
    end

    GEM -.migrating to.-> VX
    SWARM -.deploys to.-> CR

    classDef planned stroke-dasharray: 5 5
    class GCP,CR,VX planned
```

## Request path

1. Operator states a goal. The orchestrator picks a specialist and delegates.
2. The specialist calls its tools. Anything arriving from outside the system
   (`fetch_supplier_message`) is screened by Model Armor at the tool boundary
   before the model ever sees it.
3. Armor records a per-supplier verdict in session state.
4. The Agent Gateway reads that verdict before `draft_purchase_order` runs.
   A quarantined source or an over-threshold value means the tool never
   executes — enforcement does not depend on the model cooperating.
5. Whichever agent finishes the turn writes the session to the Memory Bank,
   so negotiation history survives into later sessions.
6. If the model provider fails, retry backs off; if retries exhaust, the turn
   degrades to an explicit "no action taken" rather than a fabricated result.

## Notes

- Tools return fixed values. They are stubs standing in for inventory,
  procurement, and logistics connectors, not live integrations.
- Dashed nodes are planned, not yet built.
