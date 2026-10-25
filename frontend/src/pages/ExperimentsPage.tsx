import { useEffect, useState } from 'react'
import { BarChart3, Download, FlaskConical, Plus, Square, Upload } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { keys } from '@/api/query'
import type { Method, Metric } from '@/api/types'
import { compact, dateTime, errorMessage, percent } from '@/lib/format'
import { ImportDialog } from '@/components/ImportDialog'
import { Badge, Button, EmptyState, InlineNotice, Loading, PageHeading, Panel } from '@/components/ui'

const availableMethods: Array<{ id: Method; label: string }> = [
  { id: 'lexical', label: '词法检索' }, { id: 'lexical_graph', label: '词法 + 图' }, { id: 'lexical_graph_budget', label: '图检索 + 预算' },
]

export default function ExperimentsPage() {
  const qc = useQueryClient()
  const datasets = useQuery({ queryKey: keys.datasets, queryFn: api.datasets })
  const repositories = useQuery({ queryKey: keys.repositories, queryFn: api.repositories })
  const experiments = useQuery({ queryKey: keys.experiments, queryFn: api.experiments, refetchInterval: 5000 })
  const [selectedId, setSelectedId] = useState('')
  const [importing, setImporting] = useState(false)
  const [name, setName] = useState('')
  const [datasetId, setDatasetId] = useState('')
  const [arms, setArms] = useState<Method[]>(['lexical', 'lexical_graph', 'lexical_graph_budget'])
  const [seedText, setSeedText] = useState('42')
  const [error, setError] = useState('')
  const detail = useQuery({ queryKey: keys.experiment(selectedId), queryFn: () => api.experiment(selectedId), enabled: !!selectedId, refetchInterval: 3000 })
  const create = useMutation({ mutationFn: api.createExperiment, onSuccess: async value => {
    setSelectedId(value.id); setError(''); await Promise.all([qc.invalidateQueries({ queryKey: keys.experiments }), qc.invalidateQueries({ queryKey: keys.overview })])
  }, onError: e => setError(errorMessage(e)) })
  const cancel = useMutation({ mutationFn: api.cancelExperiment, onSuccess: async () => {
    await qc.invalidateQueries({ queryKey: keys.experiment(selectedId) }); await qc.invalidateQueries({ queryKey: keys.experiments })
  }, onError: e => setError(errorMessage(e)) })
  const exportFile = useMutation({ mutationFn: api.exportExperiment, onSuccess: blob => {
    const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `${selectedId}.zip`
    link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }, onError: e => setError(errorMessage(e)) })
  useEffect(() => { if (!datasetId && datasets.data?.items.length) setDatasetId(datasets.data.items[0].id) }, [datasetId, datasets.data])
  const selected = detail.data
  const plannedRuns = Number(selected?.config.planned_runs ?? selected?.run_ids?.length ?? 0)
  if (datasets.isLoading || experiments.isLoading) return <Loading label="正在读取研究数据" />
  return <>
    <PageHeading eyebrow="CONTROLLED EVALUATION" title="研究实验" description="对固定任务清单运行多个检索方法与随机种子。每一项都会保存独立运行记录，汇总修复率、模型用量与环境错误。"
      actions={<Button variant="secondary" onClick={() => setImporting(true)}><Upload size={14} /> 导入 JSONL</Button>} />
    {error && <InlineNotice kind="danger" title="操作未完成">{error}</InlineNotice>}
    {(datasets.isError || experiments.isError) && <InlineNotice kind="danger" title="无法读取实验数据">{errorMessage(datasets.error || experiments.error)}</InlineNotice>}
    {detail.isError && <InlineNotice kind="danger" title="无法读取实验详情">{errorMessage(detail.error)}</InlineNotice>}
    <div className="experiment-grid">
      <div className="experiment-list">
        <Panel><div className="panel-heading"><div><h2>创建实验</h2><div className="panel-subtitle">每个任务 × 方法 × seed 创建一条运行记录</div></div><Badge>最多 300 项</Badge></div>
          <form className="panel-body form-grid" onSubmit={e => {
            e.preventDefault(); setError('')
            const tokens = seedText.trim().split(/[\s,]+/).filter(Boolean)
            const seeds = [...new Set(tokens.map(Number))]
            if (!seeds.length || seeds.some(seed => !Number.isSafeInteger(seed) || seed < 0 || seed > 2147483647) || seeds.length > 10 || !arms.length) {
              setError('请选择至少一个方法，并填写 1–10 个 0 到 2147483647 之间的整数 seed。'); return
            }
            create.mutate({ name: name.trim() || `实验 ${new Date().toLocaleDateString('zh-CN')}`, dataset_id: datasetId, arms, seeds })
          }}>
            <div className="setting-form"><div className="form-field"><label htmlFor="exp-name">实验名称</label><input id="exp-name" className="field-control" value={name} onChange={e => setName(e.target.value)} placeholder="例如：图检索消融 · v1" /></div>
              <div className="form-field"><label htmlFor="exp-dataset">任务清单</label><select id="exp-dataset" className="field-control" required value={datasetId} onChange={e => setDatasetId(e.target.value)}>
                <option value="">选择已导入清单</option>{datasets.data?.items.map(ds => <option key={ds.id} value={ds.id}>{ds.name} · {ds.task_count} tasks</option>)}</select></div></div>
            <fieldset className="arm-picker"><legend>比较方法</legend>{availableMethods.map(item => <label className="arm-option" key={item.id}>
              <input type="checkbox" checked={arms.includes(item.id)} onChange={e => setArms(old => e.target.checked ? [...old, item.id] : old.filter(value => value !== item.id))} />{item.label}</label>)}</fieldset>
            <div className="form-field"><label htmlFor="exp-seeds">随机种子</label><input id="exp-seeds" className="field-control" value={seedText} onChange={e => setSeedText(e.target.value)} placeholder="42, 43, 44" />
              <span className="form-help">以逗号或空格分隔。本地 llama.cpp 会使用此 seed；不同设备的结果仍可能不同。</span></div>
            {datasets.data?.items.length === 0 && <InlineNotice kind="warning">请先导入 JSONL 任务清单。每行需要 instance_id、issue 和 repository_key。</InlineNotice>}
            <Button variant="primary" type="submit" disabled={create.isPending || !datasetId || !arms.length}><Plus size={14} />{create.isPending ? '正在创建…' : '开始实验'}</Button>
          </form></Panel>
        <Panel><div className="panel-heading"><div><h2>实验记录</h2><div className="panel-subtitle">数据集和运行配置在创建时固定</div></div></div>
          {experiments.data?.items.length ? <div className="experiment-table">{experiments.data.items.map(item => <button className={`experiment-item ${selectedId === item.id ? 'experiment-item-selected' : ''}`} key={item.id} onClick={() => setSelectedId(item.id)}>
            <span className="experiment-mark"><FlaskConical size={16} /></span><span className="experiment-item-copy"><strong>{item.name}</strong><small>{item.id} · {dateTime(item.created_at)}</small></span>
            <Badge tone={item.status === 'completed' ? 'success' : 'info'} dot>{item.status === 'completed' ? '已完成' : item.status === 'queued' ? '排队中' : '运行中'}</Badge>
          </button>)}</div> : <EmptyState icon={FlaskConical} title="还没有研究实验" description="导入任务 JSONL，选择比较方法与 seed 后开始受控评估。" />}
        </Panel>
      </div>
      <aside className="experiment-detail section-stack">{selectedId && selected ? <Panel>
        <div className="panel-heading"><div><h2>{selected.name}</h2><div className="panel-subtitle">{selected.id} · {plannedRuns} 个计划运行</div></div>
          <div className="toolbar">{selected.status !== 'completed' && <Button size="sm" onClick={() => cancel.mutate(selected.id)} disabled={cancel.isPending}><Square size={12} />停止</Button>}
            {selected.status === 'completed' && <Button size="sm" variant="primary" onClick={() => exportFile.mutate(selected.id)} disabled={exportFile.isPending}><Download size={13} />导出包</Button>}</div></div>
        {detail.isLoading ? <Loading label="正在汇总运行指标" /> : <>
          <div className="metric-bars">{selected.metrics?.map(metric => <div className="metric-bar-row" key={metric.method}>
            <div className="metric-bar-label"><strong>{methodName(metric.method)}</strong><span>{metric.solved}/{metric.planned} · {percent(metric.solve_rate)}</span></div>
            <div className="metric-bar-track"><div className="metric-bar-fill" style={{ width: `${Math.min(100, (metric.solve_rate || 0) * 100)}%` }} /></div>
            <div className="metric-detail"><div className="metric-detail-card"><span>完成</span><strong>{metric.completed}/{metric.planned}</strong></div>
              <div className="metric-detail-card"><span>环境错误</span><strong>{metric.environment_errors}</strong></div>
              <div className="metric-detail-card"><span>模型 tokens</span><strong>{compact(totalTokens(metric))}</strong></div></div>
          </div>)}</div>
          {selected.runs?.length ? <div className="table-wrap"><table><thead><tr><th>任务</th><th>方法</th><th>Seed</th><th>状态</th><th>结果</th></tr></thead><tbody>{selected.runs.map(item => <tr key={item.run_id}>
            <td className="mono">{item.instance_id}</td><td>{methodName(item.method)}</td><td>{item.seed}</td><td>{item.status}</td><td>{item.outcome}</td></tr>)}</tbody></table></div> : null}
          {selected.status === 'completed' && <InlineNotice kind="info" title="指标口径">成功率按通过基线复现与候选测试的任务数计算。未报告的 token 与时间指标保持原样，不做估算。</InlineNotice>}
        </>}
      </Panel> : <Panel><EmptyState icon={BarChart3} title="选择一个实验" description="创建实验后可以查看各方法的修复率、逐任务状态和可复现导出包。" /></Panel>}</aside>
    </div>
    <ImportDialog mode="dataset" open={importing} onClose={() => setImporting(false)} repositories={repositories.data?.items || []}
      onComplete={() => { void qc.invalidateQueries({ queryKey: keys.datasets }) }} />
  </>
}

function methodName(method: Method) { return availableMethods.find(item => item.id === method)?.label || method }

function totalTokens(metric: Metric) {
  if (metric.input_tokens == null || metric.output_tokens == null || metric.thought_tokens == null) return null
  return metric.input_tokens + metric.output_tokens + metric.thought_tokens
}
