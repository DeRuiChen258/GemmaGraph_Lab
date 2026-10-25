from langgraph.types import interrupt

from gemmagraph.agent.budgets import remaining


async def human_review(state, deps):
    patch = state.get("patch_ref")
    if state.get("review_policy") == "deferred":
        return {"review": {"status": "not_requested", "patch_hash": state.get("patch_hash")}}
    payload = {
        "review_id": f"review_{state['run_id']}_{state.get('attempt', 0)}_{(state.get('patch_hash') or 'none')[:12]}",
        "patch_hash": state.get("patch_hash"), "patch": patch,
        "verification": state.get("verification_ref"), "outcome": state.get("outcome"),
        "plan": state.get("plan"), "baseline": state.get("baseline_result_ref"),
        "actions": ["accept", "reject", "revise"],
    }
    if (state.get("error") or {}).get("code") == "preflight_blocked":
        return {"review": {"status": "not_requested"}}
    decision = interrupt(payload)
    if decision.get("review_id") != payload["review_id"] or decision.get("patch_hash") != payload["patch_hash"]:
        return {"review": {"status": "stale", "patch_hash": payload["patch_hash"]}}
    feedback = decision.get("feedback", "")
    updates = {"review": {**payload, "status": decision["decision"], "feedback": feedback}}
    if decision["decision"] == "revise" and all(remaining(state).values()):
        updates["reflection"] = {"next_step": "retrieve", "evidence_gap": feedback,
                                 "summary": feedback, "failure_type": "human_feedback"}
        updates["outcome"] = "pending"
    elif decision["decision"] == "reject":
        updates["outcome"] = "rejected"
    return updates


def route_review(state):
    review = state.get("review") or {}
    if review.get("status") == "revise" and state.get("outcome") == "pending" and all(remaining(state).values()):
        return "retrieve_context"
    return "finalize"
