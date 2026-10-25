import { useEffect, useRef, useState } from 'react'
import { CircleAlert, Database, ExternalLink, HardDrive, RefreshCw, Save, Server, ShieldCheck } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { keys } from '@/api/query'
import { errorMessage } from '@/lib/format'
import { Badge, Button, InlineNotice, Loading, PageHeading, Panel } from '@/components/ui'

const budgetFields: Array<{ key: string; label: string; min: number; max: number; help: string }> = [
  { key: 'max_attempts', label: '最大修复轮数', min: 1, max: 10, help: '每次反思后最多重新检索与生成补丁的次数。' },
  { key: 'max_model_calls', label: '模型调用上限', min: 2, max: 50, help: '限制单次运行最多请求模型的次数。' },
  { key: 'active_timeout_seconds', label: '总运行超时（秒）', min: 10, max: 7200, help: '不含 worker 排队等待时间。' },
  { key: 'test_timeout_seconds', label: '单次测试超时（秒）', min: 1, max: 600, help: '到时后沙箱进程会被终止。' },
  { key: 'evidence_tokens', label: '证据预算（tokens）', min: 128, max: 65536, help: '发送给模型的代码片段估算上限。' },
  { key: 'max_changed_files', label: '最大变更文件数', min: 1, max: 20, help: '补丁校验会拒绝超出此值的修改。' },
  { key: 'graph_hops', label: '代码图扩展跳数', min: 1, max: 2, help: '沿静态定义与引用关系扩展候选。' },
  { key: 'max_candidates', label: '最大检索候选数', min: 1, max: 500, help: '排序前的候选符号上限。' },
]

export default function SettingsPage() {
  const qc = useQueryClient()
  const query = useQuery({ queryKey: keys.settings, queryFn: api.settings, refetchInterval: 10000 })
  const [values, setValues] = useState<Record<string, number>>({})
  const initialized = useRef(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const save = useMutation({ mutationFn: () => api.updateSettings(values), onSuccess: async () => {
    setError(''); setMessage('默认预算已保存。新建任务会读取这些值。')
    await qc.invalidateQueries({ queryKey: keys.settings })
  }, onError: e => { setMessage(''); setError(errorMessage(e)) } })
  const check = useMutation({ mutationFn: api.checkProvider, onSuccess: result => {
    setError(''); setMessage(`本地环境检查完成：${JSON.stringify(result)}`)
  }, onError: e => { setMessage(''); setError(errorMessage(e)) } })
  useEffect(() => { if (query.data && !initialized.current) { setValues(query.data.defaults); initialized.current = true } }, [query.data])
  if (query.isLoading) return <Loading label="正在读取环境设置" />
  const settings = query.data
  if (!settings) return <><PageHeading title="环境设置" /><InlineNotice kind="danger">{query.error instanceof Error ? query.error.message : '设置读取失败。'}</InlineNotice></>
  return <>
    <PageHeading eyebrow="LOCAL ENVIRONMENT" title="环境与预算" description="使用本机 Gemma 4 权重执行修复。检查推理环境与隔离测试状态，并调整新任务的默认预算。" />
    <div className="setting-grid">
      <div className="section-stack">
        <Panel><div className="panel-heading"><div><h2><Server size={15} /> 本地 Gemma 4</h2><div className="panel-subtitle">Google 官方 GGUF 权重 · llama.cpp 上游推理框架</div></div>
          <Badge tone={settings.model.configured ? 'success' : 'warning'} dot>{settings.model.configured ? '配置就绪' : '待配置'}</Badge></div>
          <div className="panel-body form-grid"><div className="connection-summary">
            <div><span>模型</span><strong>{settings.model.model_id || '未配置'}</strong></div>
            <div><span>权重文件</span><strong>{settings.model.model_path || '未配置'}</strong></div>
            <div><span>权重状态</span><strong>{settings.model.model_file_exists ? '文件已找到' : '尚未找到权重文件'}</strong></div>
            <div><span>推理程序</span><strong>{settings.model.runtime_path || '未配置'}</strong></div>
            <div><span>程序状态</span><strong>{settings.model.runtime_exists ? '文件已找到' : '尚未构建官方 llama.cpp'}</strong></div>
            <div><span>计算设备</span><strong>{settings.model.device === 'gpu' ? 'GPU' : settings.model.device === 'cpu' ? 'CPU' : '未配置'}</strong></div>
            {settings.model.device === 'gpu' && <div><span>CUDA Toolkit</span><strong>{settings.model.cuda_toolkit_version || '未报告版本'}</strong></div>}
            <div><span>上下文 / 输出上限</span><strong>{settings.model.context_window?.toLocaleString() || '—'} / {settings.model.max_output_tokens?.toLocaleString() || '—'} tokens</strong></div>
          </div>
          {!settings.model.configured && <InlineNotice kind="warning" title="本地推理环境尚未就绪">根据项目 README 构建官方 llama.cpp，在工程根目录 .env 中设置 MODEL_PATH 与 LLAMA_CPP_DIR，然后重启 API 与 worker。</InlineNotice>}
          <div className="toolbar"><Button variant="secondary" onClick={() => check.mutate()} disabled={check.isPending}><RefreshCw size={13} />{check.isPending ? '正在检查…' : '检查本地环境'}</Button>
            <span className="form-help">文件存在仅代表配置就绪；生成结果以实际模型测试为准。</span></div>
        </div></Panel>
        <Panel><div className="panel-heading"><div><h2><ShieldCheck size={15} /> 隔离测试沙箱</h2><div className="panel-subtitle">容器网络关闭、只读根文件系统、资源受限</div></div>
          <Badge tone={settings.sandbox.available ? 'success' : 'warning'} dot>{settings.sandbox.available ? '可用' : '不可用'}</Badge></div>
          <div className="panel-body form-grid">{settings.sandbox.available ? <InlineNotice kind="success">Docker 服务已连接：{settings.sandbox.engine_version}</InlineNotice>
            : <InlineNotice kind="warning" title="运行修复前需要 Docker"><span className="mono">{settings.sandbox.reason || 'Docker daemon 不可用'}</span><br />启动 Docker，并构建项目沙箱镜像后重启 worker。</InlineNotice>}
            <div className="container-facts"><span><HardDrive size={14} /> workspace 独立副本</span><span><Database size={14} /> 测试超时可配置</span><span><CircleAlert size={14} /> 测试容器无外网</span></div>
          </div></Panel>
        <Panel><div className="panel-heading"><div><h2>测试 Profile</h2><div className="panel-subtitle">容器内固定运行命令</div></div></div>
          <div className="table-wrap"><table><thead><tr><th>PROFILE</th><th>命令</th><th>内存</th><th>超时</th></tr></thead><tbody>{settings.profiles.map(profile => <tr key={profile.id}>
            <td><code className="mono">{profile.id}</code></td><td><code className="mono">{profile.command.join(' ')}</code></td><td>{profile.memory_mb} MB</td><td>{profile.timeout_seconds}s</td></tr>)}</tbody></table></div>
        </Panel>
      </div>
      <aside className="section-stack"><Panel><div className="panel-heading"><div><h2>默认运行预算</h2><div className="panel-subtitle">只影响之后创建的任务</div></div><Badge>安全范围校验</Badge></div>
        <form className="panel-body form-grid" onSubmit={e => { e.preventDefault(); setMessage(''); setError(''); save.mutate() }}>
          <div className="setting-form">{budgetFields.map(field => <div className="form-field" key={field.key}><label htmlFor={`setting-${field.key}`}>{field.label}</label>
            <input className="field-control" id={`setting-${field.key}`} type="number" min={field.min} max={field.max}
              value={values[field.key] ?? ''} onChange={e => setValues(old => ({ ...old, [field.key]: Number(e.target.value) }))} />
            <span className="form-help">{field.help}</span></div>)}</div>
          <Button variant="primary" type="submit" disabled={save.isPending}><Save size={14} />{save.isPending ? '正在保存…' : '保存默认预算'}</Button>
        </form></Panel>
        {error && <InlineNotice kind="danger" title="操作失败">{error}</InlineNotice>}
        {message && <InlineNotice kind="success" title="状态">{message}</InlineNotice>}
        <InlineNotice kind="info" title="配置文件位置">服务端从工程根目录的 <code>.env</code> 读取本地模型路径和运行参数。可按设备配置调整 GPU 层数、超时与输出上限。</InlineNotice>
        <a className="external-doc-link" href="https://ai.google.dev/gemma/docs/integrations/llamacpp" target="_blank" rel="noreferrer">
          <ExternalLink size={13} /> Google 官方 llama.cpp 运行说明</a>
      </aside>
    </div>
  </>
}
