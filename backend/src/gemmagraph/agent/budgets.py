def remaining(state):
    config, usage = state["config_snapshot"], state.get("usage", {})
    budget = config["budget"]
    return {
        "calls": max(0, budget["max_model_calls"] - usage.get("model_calls", 0)),
        "attempts": max(0, budget["max_attempts"] - state.get("attempt", 0)),
        "seconds": max(0, budget["active_timeout_seconds"] - usage.get("active_seconds", 0)),
    }


def record_model_reply(previous, reply):
    """Preserve missing runtime counts as unknown instead of reporting zero."""
    usage = dict(previous)
    prior_calls = usage.get("model_calls", 0)
    usage["model_calls"] = prior_calls + 1
    for field in ("input_tokens", "output_tokens", "thought_tokens"):
        incoming, prior = reply.get(field), usage.get(field)
        if incoming is None or (prior_calls and prior is None):
            usage[field] = None
        else:
            usage[field] = (prior or 0) + incoming
    usage["token_count_mode"] = ("runtime_usage_or_unknown" if reply.get("provider") == "llama_cpp_local"
                                  else "provider_usage_or_unknown")
    return usage


def allowed_next(state, suggestion):
    r = remaining(state)
    if r["calls"] <= 0 or r["attempts"] <= 0 or r["seconds"] <= 0:
        return "human_review"
    return {"retrieve": "retrieve_context", "replan": "plan_fix",
            "regenerate": "generate_patch", "stop": "human_review"}.get(suggestion, "human_review")
