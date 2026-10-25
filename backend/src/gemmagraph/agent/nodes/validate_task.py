async def validate_task(state, deps):
    settings = deps.settings
    reasons = []
    try:
        await deps.provider_factory().check()
    except Exception as error:
        reasons.append(f"模型预检失败：{error}")
    try:
        await deps.sandbox.available()
    except Exception:
        reasons.append("Docker 沙箱不可用；修复任务不会在宿主机运行仓库代码。")
    profile = settings.profiles().get(state["config_snapshot"]["test_profile_id"])
    if not profile:
        reasons.append("测试 profile 未配置。")
    if reasons:
        return {"error": {"code": "preflight_blocked", "message": " ".join(reasons)},
                "outcome": "blocked"}
    return {"error": None, "outcome": "pending"}


def route_validated(state):
    return "finalize" if state.get("outcome") == "blocked" else "prepare_workspace"
