import json

from gemmagraph.agent.budgets import allowed_next, record_model_reply, remaining
from gemmagraph.agent.model_outputs import Reflection, parse_json_output
from gemmagraph.errors import AppError
from gemmagraph.prompts import render


async def reflect(state, deps):
    budget = remaining(state)
    verification = state.get("verification_ref") or state.get("patch_validation") or state.get("error")
    if not all(budget.values()) or (verification or {}).get("environment_error"):
        return {"reflection": {"next_step": "stop", "summary": "达到调用预算或验证未能证明修复成功。"}}
    reply = await deps.provider_factory().generate(render(
        "reflector", verification=json.dumps(verification, ensure_ascii=False),
        patch=(state.get("patch_ref") or {}).get("sha256", ""), budget=remaining(state)))
    try:
        reflection = Reflection.model_validate(parse_json_output(reply["text"])).model_dump()
    except Exception as e:
        raise AppError("invalid_model_output", f"反思结果格式无效：{type(e).__name__}", 502) from e
    usage = record_model_reply(state.get("usage", {}), reply)
    return {"reflection": reflection, "usage": usage}


def route_reflection(state):
    return allowed_next(state, (state.get("reflection") or {}).get("next_step", "stop"))
