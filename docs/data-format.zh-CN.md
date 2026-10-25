# 任务集、指标与导出

## JSONL 任务输入

每行一个 JSON 对象，UTF-8 编码。支持的字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `instance_id` | 是 | 清单内唯一任务 ID |
| `issue` | 是 | 至少 5 个字符的错误描述与期望行为 |
| `repository_key` | 条件必填 | 导入时映射到本地仓库 ID |
| `repository_id` | 条件必填 | 已存在的本地仓库 ID，可免映射 |
| `source_snapshot_hash` | 否 | 提供时必须与本地仓库树哈希相同 |
| `test_profile_id` | 否 | 目前仅支持 `python-pytest` |
| `split`, `language` | 否 | 任务来源元数据；首期仅执行 Python 静态解析 |

示例：

```jsonl
{"instance_id":"bug-001","repository_key":"calculator","issue":"normalize_items 在空列表输入时会抛出 IndexError，应返回空列表。"}
```

导入时必须将 `repository_key` 映射到已导入的仓库。平台会保存清单原始 SHA-256，并把任务指向仓库的固定树哈希。

## 实验维度

默认三种方法为：

- `lexical`：词法相关符号排序。
- `lexical_graph`：词法种子加静态图邻居，按距离与稳定顺序打包。
- `lexical_graph_budget`：图候选按相关性、距离、失败线索和片段长度排序，并受证据预算限制。

每个任务、方法和 seed 组合生成独立 run。模型配置、预算、任务集哈希、检索方法、测试 Profile 和提示词哈希写入运行快照。UI 显示的成功率为 `verified` 任务数除以计划任务数；只有基线能复现测试失败、修改后的测试通过且测试环境正常时，任务才记为 verified。

供应商没有返回的 token 数不会推算。字符数估算的检索片段标记 `token_count_mode=estimated`，不用于伪装为供应商实测。

## 导出包

实验完成后下载 ZIP，包含：

- `tasks.jsonl`：导入后的任务数据与仓库快照哈希。
- `results.jsonl`：逐项方法、seed、状态、验证、用量与错误。
- `metrics.json`：方法级计划/完成/修复数量、修复率、环境错误、token 和活动时长。
- `config.json`：方法、seed、预算与数据集哈希。
- `manifest.json`：各导出文件 SHA-256。
- `report.md`、`reproduce.md`：指标摘要和人工复现步骤。

环境错误、取消和无法确定的 token 计量会保留为数据，不会剔除或填入估计值。批量实验使用 deferred 审查；需要人工判断的结果仍应回到逐项运行记录审阅。
