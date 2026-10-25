import json

from gemmagraph.agent.budgets import record_model_reply, remaining
from gemmagraph.agent.model_outputs import FixPlan, parse_json_output
from gemmagraph.errors import AppError
from gemmagraph.prompts import render


async def plan_fix(state, deps):
    if not all(remaining(state).values()):
        return {"error": {"code": "budget_exhausted", "message": "模型调用预算已用完"},
                "outcome": "unverified"}
    provider = deps.provider_factory()
    prompt = render("planner", issue=state["issue"],
                    baseline=json.dumps(state.get("baseline_result_ref"), ensure_ascii=False),
                    evidence=json.dumps(state.get("evidence", []), ensure_ascii=False))
    reply = await provider.generate(prompt, seed=state["config_snapshot"].get("seed"))
    try:
        data = FixPlan.model_validate(parse_json_output(reply["text"]))
    except Exception as e:
        raise AppError("invalid_model_output", f"修复计划格式无效：{type(e).__name__}", 502) from e
    evidence_ids = {e["id"] for e in state.get("evidence", [])}
    files = {e["path"] for e in state.get("evidence", [])}
    if not set(data.evidence_ids) <= evidence_ids or not set(data.files) <= files:
        raise AppError("invalid_model_output", "修复计划引用了未检索的证据或文件", 502)
    usage = record_model_reply(state.get("usage", {}), reply)
    await deps.events.append(state["run_id"], "plan.created", data.model_dump(), node="plan_fix",
                             source_key=f"plan:{state.get('attempt',0)}")
    return {"plan": data.model_dump(), "usage": usage}
