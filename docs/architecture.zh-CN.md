# 架构与 API

## 进程与职责

| 部件 | 职责 | 持久化 |
| --- | --- | --- |
| React/Vite | 仓库、代码图、任务、事件流、审查、实验与设置界面 | 浏览器查询缓存；不保存密钥 |
| FastAPI | REST、上传校验、任务入队、事件和产物读取 | 业务 SQLite、受控文件系统 |
| Worker | 单实例租约队列；执行索引与修复任务，处理取消和恢复 | 业务 SQLite |
| LangGraph | 显式 StateGraph、条件路由、人工 interrupt 与状态恢复 | 单独的 checkpoint SQLite |
| Model Provider | 启动官方 llama.cpp `llama-completion` 子进程，读取本地 Gemma 4 GGUF | 每次调用单独加载；模型和运行时来源写入运行配置 |
| Docker Runner | 对固定测试 Profile 启动无网络受限容器 | 临时容器；每个 run 专属 workspace |

SQLite 业务事务与 checkpoint 事务不跨库原子提交。持久事件有来源键去重，队列有租约和幂等键；Worker 在生成完成但 checkpoint 尚未提交时退出，恢复后仍可能重复执行本地推理。因此复现时需同时保留业务事件和 checkpoint。

## LangGraph 路径

`validate_task → prepare_workspace → index_repository → collect_baseline → retrieve_context → plan_fix → generate_patch → validate_patch → apply_patch → verify_patch → human_review → finalize`

补丁无效或验证未通过时，`reflect` 依据失败摘要和剩余预算选择再次检索、重规划、生成补丁或转人工审查。预算只能由服务端确定性路由执行。人工审查保存 `review_id` 和补丁哈希，以同一 `thread_id` 通过 checkpoint 恢复。

## REST 路由

所有路由以 `/api/v1` 为前缀。

| 路由 | 用途 |
| --- | --- |
| `GET /health`, `GET /overview`, `GET /workflow`, `GET/PATCH /settings` | 健康、统计、流程图和非敏感默认预算 |
| `GET /providers/status`, `POST /providers/check` | 本地模型、运行时及来源记录状态；检查时不生成内容 |
| `POST/GET /repositories`，`GET /repositories/{id}` | 上传 ZIP 与仓库列表/详情 |
| `GET /repositories/{id}/tree`, `/file`, `/graph` | 目录、只读源码和 AST 子图 |
| `POST/GET /runs`，`GET /runs/{id}` | 创建修复任务、查看运行记录 |
| `GET /runs/{id}/events/history`, `/events` | 按序事件历史和 SSE |
| `POST /runs/{id}/cancel`, `/resume` | 请求取消或恢复人工审查 |
| `GET /runs/{id}/artifacts`, `GET /artifacts/{artifact_id}` | 列出或下载运行产物 |
| `POST /datasets/import`, `GET /datasets`, `GET /datasets/{id}` | 导入与查看 JSONL 任务集 |
| `POST/GET /experiments`, `GET /experiments/{id}` | 创建、列出和查看成组实验 |
| `POST /experiments/{id}/cancel`, `/export` | 请求停止实验或下载复现 ZIP |

创建 run、审查恢复和创建实验都需要 `Idempotency-Key`。浏览器请求附带 `X-Request-ID`；上传使用 multipart。

## 事件与终态

事件按 run 使用严格递增的 `seq`，当前类型包含 `run.*`、`node.*`、`plan.created`、`patch.generated`、`verification.completed` 和 `review.required`。SSE 断线后可用 `Last-Event-ID` 从指定序号继续读取。

`outcome` 表示技术验证结果；`review_status` 表示人工决策，两者分别保留。接受或拒绝候选补丁不会伪造测试通过结果。实验批处理采用 deferred 审查策略，逐项数据不代表人工接受。

## 本地 Gemma 4 推理

当前默认 provider 为 `llama_cpp_local`；Gemma 4 GGUF 的绝对路径通过 `.env` 中的 `MODEL_PATH` 配置。权重由官方上游 [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) 执行。工作台通过子进程传入 prompt，使用 GGUF 内置聊天模板与 Jinja，执行一次生成后回收进程。推理不启动 HTTP 服务，不依赖云端 API key。

默认构建 CUDA 13.4 版本，并以 `MODEL_GPU_LAYERS=999` 请求卸载所有可卸载层；不自动回退到 CPU。每次调用包含模型加载耗时。官方版本固定为 `v0.7.0`，构建脚本记录源码 commit、二进制 SHA-256、CUDA 编译器、Toolkit 版本和目标架构。完整流程见 [本地推理与调试](local-inference.zh-CN.md)；运行方式参考 [Google 官方 llama.cpp 指南](https://ai.google.dev/gemma/docs/integrations/llamacpp)。
