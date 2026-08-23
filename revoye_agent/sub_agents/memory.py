async def save_to_memory(callback_context):
    """Persists this session's conversation into long-term memory.

    Attached to every agent in the swarm, not just the orchestrator: when
    the orchestrator delegates via transfer_to_agent, ADK's scheduler ends
    the orchestrator's own turn early and its after_agent_callback never
    fires. Only whichever agent actually finishes the turn gets its
    callback called, so each sub-agent needs its own copy of this.
    """
    await callback_context.add_session_to_memory()
