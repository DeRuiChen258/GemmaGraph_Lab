from gemmagraph.errors import AppError


def validate_profile(profile, image):
    if not image:
        raise AppError("sandbox_image_missing", "未配置容器镜像", 503)
    command = profile.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(v, str) for v in command):
        raise AppError("invalid_test_profile", "测试命令必须是非空参数数组")
    if command[0] not in {"python", "python3", "pytest"}:
        raise AppError("invalid_test_profile", "测试 profile 只能启动 Python 测试入口")
