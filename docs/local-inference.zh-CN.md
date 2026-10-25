# 本地 Gemma 4 推理与调试

## 模型与运行时

本工程需要一个本地 Gemma 4 E4B QAT Q4 GGUF 文件，并通过根目录 `.env` 的 `MODEL_PATH` 指向它，例如：

```text
MODEL_PATH=/path/to/gemma-4-E4B_q4_0-it.gguf
```

已读取的文件头信息为 GGUF v3、`gemma4` 架构、666 个 tensor、42 层，声明上下文长度为 131072，文件大小为 5154941280 字节。GGUF 内置 Google Gemma 4 Canonical Chat Template。以上信息说明文件格式及声明属性，不能证明权重无损或真实推理成功。

采用 [Google 官方文档介绍的 llama.cpp 方案](https://ai.google.dev/gemma/docs/integrations/llamacpp)，运行时从 [ggml-org/llama.cpp 的 v0.7.0](https://github.com/ggml-org/llama.cpp/releases/tag/v0.7.0) 编译。llama.cpp 是官方文档支持的开源推理框架；它并非 Google 自有框架。工程不选用机器上已有的 Prism 分支。

若模型发布目录同时提供 `gemma-4-E4B-it-mmproj.gguf`，该文件用于多模态。当前代码修复任务只使用文本权重，不加载 projector。模型权重不随本工程源码发布。

## 安装与检查

在工程根目录执行：

```bash
make cuda-check
./install.sh
./scripts/install-llama-cpp.sh --cuda
uv run --project backend python scripts/model-smoke.py --check-only
uv run --project backend python scripts/model-smoke.py --max-tokens 64
```

安装脚本需要 Git、CMake、C++ 编译器、官方 CUDA Toolkit 13.4 和能够访问官方 GitHub 源码的网络。默认 `--cuda`，显式使用 `/usr/local/cuda-13.4/bin/nvcc`。通过 `CUDA_TOOLKIT_ROOT` 可指定其他安装目录，但该目录的 nvcc 必须报告 release 13.4。脚本固定源码版本，只接受官方 origin；已有 checkout 若版本不符、来源不同或存在 tracked 修改，会停止并保留原文件，不自动切换或覆盖。构建目标为 `llama-completion`。

产物位置：

```text
.runtime/llama.cpp/build/bin/llama-completion
.runtime/llama.cpp/build/gemmagraph-runtime.json
```

来源记录包含 `repository`、`ref`、完整 `commit`、`binary_sha256`、`device`、`binary_path`、`built_at`、`cuda_toolkit_version`、`cuda_compiler` 和 `cuda_architectures`。它记录构建来源，不能替代实际生成测试。`.runtime/` 不提交到版本控制。

`--check-only` 不生成内容。去掉该参数后，smoke 命令会真正加载模型，完成一次短文本生成；只有取得实际回复才能记录为生成通过。`--sha256` 可额外计算本地权重摘要，用于后续复现时比较文件。当前实测 SHA256 为 `676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee`，与模型目录的 Hugging Face 下载 metadata 一致；本次未联网核对发布方文件。

## 配置

根目录 `.env` 的主要字段：

| 字段 | 用途 |
| --- | --- |
| `MODEL_PROVIDER=llama_cpp_local` | 直接启动本地 llama.cpp 子进程 |
| `MODEL_PATH` | 上述文本 GGUF 的绝对路径 |
| `LLAMA_CPP_DIR=.runtime/llama.cpp` | 官方源码和 build 所在目录 |
| `MODEL_ID=gemma-4-E4B-QAT-Q4` | 运行记录中的模型名称 |
| `MODEL_GPU_LAYERS=999` | 请求将所有可卸载层放到 GPU，超出实际层数的部分不会创建额外层 |
| `MODEL_THREADS=8` | CPU 侧推理线程数 |
| `MODEL_CONTEXT_WINDOW` | 实际为本次运行分配的上下文窗口 |
| `MODEL_MAX_OUTPUT_TOKENS` | 单次生成 token 上限 |
| `MODEL_TIMEOUT_SECONDS` | 加载与生成的总超时 |

`MODEL_CONTEXT_WINDOW` 是运行配置，不会因文件声明 128K 就自动分配 128K。代码证据、任务说明、模板与输出共同占用窗口。更大的窗口和输出上限会增加内存与耗时。

推理使用官方 completion 的单轮会话模式、Jinja 和权重内置模板，关闭 thinking 以便计划 JSON 与补丁输出进入确定的后续解析。prompt 由后端传给本地进程；不启动模型 HTTP 服务。前端和工作台后端之间仍使用本机 REST/SSE，以呈现任务和事件。

## CUDA

机器安装了 CUDA Toolkit 13.4，编译器路径为 `/usr/local/cuda-13.4/bin/nvcc`。构建时显式设置 `CUDAToolkit_ROOT`、`CMAKE_CUDA_COMPILER` 和 `CMAKE_CUDA_ARCHITECTURES`；目标架构默认 `120`，不依赖 CMake 在当前会话探测 GPU。可使用以下方式覆盖 Toolkit 安装目录或架构：

```bash
CUDA_TOOLKIT_ROOT=/usr/local/cuda-13.4 CUDA_ARCHITECTURES=120 ./scripts/install-llama-cpp.sh --cuda
```

当前 `.env` 使用 `MODEL_GPU_LAYERS=999`。更改配置后重启工作台，再运行 smoke。构建为 CUDA 不代表 GPU 推理已验证；需要保留实际 GPU 加载日志及生成结果。默认流程在 CUDA 不可用时报告错误，不自动回退。仅当明确需要 CPU 诊断时才使用 `make llama-cpp-cpu` 并显式设置 `MODEL_GPU_LAYERS=0`。

## 调试顺序

1. 用 `--check-only` 确认 GGUF 文件、官方二进制和来源记录齐备。
2. 用短生成确认实际模型能加载并返回文本，必要时增加超时。
3. 执行 `make test` 检查工程回归，再执行 `make build` 检查前端构建。
4. 构建 `infra/sandbox` 镜像，启动 API、Worker、前端后导入小型 Python 仓库，检查基线测试、补丁、复测和人工审查恢复。

协议或路由测试中的模型夹具仅验证工程行为。它们不能替代第 2 步的真实本地推理。仓库测试仍通过受限 Docker 容器运行，不在宿主机执行上传代码。

## 当前环境限制

39 项工程回归、CUDA 13.4 / `sm_120` 编译和宿主机 GPU kernel 测试见 [验证记录](validation.zh-CN.md)。用户提供的宿主机执行结果显示 `kernel_result=42`。最新完整构建已推进到依赖安装；pnpm 11 会执行已明确批准的 esbuild 安装脚本，之后继续运行该脚本验证官方 runtime 和模型生成。

官方源码 clone 已实际尝试，网络 socket 操作返回 `Operation not permitted`；依赖下载和官方运行时下载受阻，尚未编译 llama.cpp。当前会话没有暴露 `/dev/nvidia*`，`nvidia-smi` 无法访问 GPU；这表示本会话缺少 GPU 访问条件，不能据此推断宿主驱动损坏。真实本地生成尚未执行；完整前端构建、浏览器联调和 Docker 端到端结果也需单独验证。待网络、依赖、GPU 设备访问和 Docker 条件就绪后，使用以上命令继续；不将文件头检查或夹具测试计作推理成功。
