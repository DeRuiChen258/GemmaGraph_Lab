async def finalize(state, deps):
    outcome = state.get("outcome", "unverified")
    review = state.get("review") or {"status": "not_requested"}
    if outcome == "pending":
        outcome = "unverified"
    summaries = {
        "verified": "基线复现了失败，候选补丁通过固定测试；结果已进入人工审查。",
        "unverified": "当前运行未能证明修复成功；请查看基线、补丁与测试报告。",
        "blocked": (state.get("error") or {}).get("message", "执行前置条件尚未满足。"),
    }
    if review.get("status") == "reject":
        outcome = "rejected"
        summary = "人工审查已拒绝候选补丁。"
    elif review.get("status") == "accept":
        summary = "人工审查已接受候选补丁；技术验证结果保留在运行记录中。"
    elif review.get("status") == "revise":
        summary = "人工审查要求修改候选补丁。"
    else:
        summary = summaries.get(outcome, "本次修复流程已结束。")
    await deps.artifacts.write(state["run_id"], "run-summary.json", {
        "outcome": outcome, "summary": summary, "review": review,
        "attempt": state.get("attempt", 0), "config": state["config_snapshot"],
        "usage": state.get("usage", {}), "verification": state.get("verification_ref"),
        "patch": state.get("patch_ref"),
    }, "application/json")
    return {"outcome": outcome, "summary": summary, "review": review}
