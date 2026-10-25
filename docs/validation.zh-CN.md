# 构建与调试记录

记录日期：2026-10-25。默认模型为本地 `Gemma-4-E4B-QAT-Q4`，推理程序来自官方上游 `ggml-org/llama.cpp` 固定版本 `v0.7.0`，使用 NVIDIA CUDA Toolkit 13.4、目标架构 `sm_120`。运行配置默认请求全部可卸载层使用 GPU，不启动模型 HTTP 服务。

## 已实际完成

| 检查 | 结果 |
| --- | --- |
| GGUF 元数据 | v3、gemma4、666 tensors、42 层、131072 声明上下文；有内置 Google 聊天模板 |
| 完整权重 SHA256 | `676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee`；与本地 Hugging Face 下载 metadata 一致 |
| NVIDIA 编译器 | `/usr/local/cuda-13.4/bin/nvcc` 报告 release 13.4、V13.4.92 |
| CUDA 诊断程序编译 | 使用上述 nvcc 和 `-arch=sm_120` 编译成功 |
| CUDA 诊断内核运行 | 用户宿主终端已实际通过：`ok=true`、RTX 5070 Laptop、compute capability 12.0、`kernel_result=42` |
| 工程回归 | 36 项通过，26.61 秒；另新增的 3 项真实 API 回归通过，1.00 秒；共 39 项 |
| FastAPI schema | app 导入及 OpenAPI 生成通过，27 条路径 |
| Python 与脚本 | Ruff、compileall、Shell 语法检查通过 |
| 前端本地源码 | esbuild 入口解析通过，第三方依赖 external；25 个源码文件、59 条本地导入路径检查通过 |

工程回归实际使用 LangGraph、官方 InMemorySaver、SQLite、AST 索引、git apply 和 FastAPI ASGI 调用，覆盖补丁路径保护、审查与崩溃恢复、失败后重试、缺失 token 用量、本地子进程取消和超时、CUDA 构建版本约束、API 幂等性及上传路径保护。模型回复、容器测试输出及本地进程生命周期测试中的可执行文件是明确的协议夹具，不代表 Gemma 4 真实推理或 Docker 测试已通过。

本次回归通过临时 `PYTHONPATH` 使用本机已缓存的官方 aiosqlite 和 FastAPI 包，未替换项目依赖声明。当前沙箱禁止向 asyncio 自唤醒 socket 写入，因此测试启用了 `GEMMAGRAPH_TEST_POLL_LOOP=1` 的测试专用轮询事件循环；生产运行不启用此机制。

## 尚未完成

| 项目 | 实际阻塞 |
| --- | --- |
| 官方 llama.cpp 下载与构建 | 最新宿主验证在前端依赖安装处停止，尚未执行官方源码 clone 和编译 |
| 真实本地模型生成 | 官方 runtime 尚未构建，尚未执行实际 Gemma 4 生成 |
| 完整验证脚本 | pnpm 之前报告忽略 esbuild build script；已在 `frontend/pnpm-workspace.yaml` 明确批准 `esbuild`，需重新运行脚本继续 |
| 前端 TypeScript 与生产构建 | 前端 Agent 报告 `pnpm typecheck` 和 `pnpm build` 均通过，Vite 构建生成 `frontend/dist` |
| Docker 与端到端修复 | 最新宿主验证未到 Docker 步骤；尚未进行浏览器联调或完整修复实验 |

用户提供的宿主机 `nvidia-smi` 成功输出显示：RTX 5070 Laptop、驱动 615.71.10、CUDA UMD 13.4、8151 MiB 显存。之后宿主执行 `make verify-local` 的 CUDA 诊断程序也实际完成 kernel 并返回 `42`；这证明宿主 CUDA 可用。此前代码执行会话中的设备探测失败不代表宿主 GPU 不可用。

## 在宿主机继续

在能运行 `nvidia-smi` 的宿主终端执行：

```bash
cd GemmaGraph_Lab
make verify-local
```

脚本遇到失败即停止，记录位于 `.data/validation/<UTC时间>/`，包括检查日志、模型检查 JSON 与实际生成 JSON。全部通过后执行 `./scripts/dev.sh`，再从工作台导入任务，验证实际代码修复和人工审查闭环。
