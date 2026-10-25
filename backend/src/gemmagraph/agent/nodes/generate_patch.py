import re

from gemmagraph.agent.budgets import record_model_reply, remaining
from gemmagraph.errors import AppError
from gemmagraph.prompts import render


async def generate_patch(state, deps):
    if not all(remaining(state).values()):
        return {"error": {"code": "budget_exhausted", "message": "模型调用预算已用完"},
                "outcome": "unverified"}
    attempt = state.get("attempt", 0) + 1
    provider = deps.provider_factory()
    evidence = "\n\n".join(f"--- {e['path']}:{e['start_line']} id={e['id']} ---\n{e['text']}"
                           for e in state.get("evidence", []))
    run = await deps.db.get("run", state["run_id"])
    allowed = run.get("config_snapshot", {}).get("allowed_paths", ["src/"])
    reply = await provider.generate(render(
        "patcher", issue=state["issue"], plan=state.get("plan"), evidence=evidence,
        allowed_paths=allowed, feedback=(state.get("reflection") or {}).get("summary", "")),
        seed=state["config_snapshot"].get("seed"))
    diff = reply["text"].strip()
    fenced = re.fullmatch(r"```(?:diff)?\s*\n(.*?)\n```", diff, flags=re.DOTALL)
    if fenced:
        diff = fenced[1].strip()
    if not diff:
        raise AppError("empty_patch", "模型没有生成可审查的补丁", 422)
    # git apply requires the patch's final line to end in a newline.
    diff += "\n"
    artifact = await deps.artifacts.write(state["run_id"], f"patch-{attempt}.diff", diff,
                                          "text/x-diff")
    usage = record_model_reply(state.get("usage", {}), reply)
    await deps.events.append(state["run_id"], "patch.generated", artifact,
                             node="generate_patch", attempt=attempt,
                             source_key=f"patch:{attempt}:{artifact['sha256']}")
    return {"attempt": attempt, "patch_ref": artifact, "patch_hash": artifact["sha256"],
            "patch_text": diff, "usage": usage, "outcome": "pending", "verification_ref": None}
