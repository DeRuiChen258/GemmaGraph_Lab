import { useState } from 'react'
import { ArrowRight, Blocks, ShieldCheck, Sparkles } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { keys } from '@/api/query'
import type { Method } from '@/api/types'
import { errorMessage } from '@/lib/format'
import { Badge, Button, InlineNotice, PageHeading, Panel } from '@/components/ui'

const methods: Array<{ id: Method; title: string; description: string }> = [
  { id: 'lexical', title: '词法检索', description: '只按问题文本与源码符号匹配，作为轻量基线。' },
  { id: 'lexical_graph', title: '词法 + 代码图', description: '在词法候选上扩展静态关系邻居。' },
  { id: 'lexical_graph_budget', title: '图检索 + 预算', description: '按失败类型迭代检索，并限制模型调用和变更文件。' },
]

export default function NewRunPage() {
  const navigate = useNavigate()
  const repos = useQuery({ queryKey: keys.repositories, queryFn: api.repositories })
  const settings = useQuery({ queryKey: keys.settings, queryFn: api.settings })
  const [repositoryId, setRepositoryId] = useState('')
  const [issue, setIssue] = useState('')
  const [method, setMethod] = useState<Method>('lexical_graph_budget')
  const [error, setError] = useState('')
  const create = useMutation({ mutationFn: api.createRun, onSuccess: run => navigate(`/runs/${run.id}`) })
  const selectedRepo = repos.data?.items.find(item => item.id === repositoryId)
  return <>
    <PageHeading eyebrow="NEW REPAIR RUN" title="创建修复任务" description="描述要修复的问题，Agent 将读取固定仓库快照、生成可审查补丁，并在隔离容器中运行仓库测试。" />
    {settings.data && (!settings.data.model.configured || !settings.data.sandbox.available) && <InlineNotice kind="warning" title="当前环境无法完成模型修复验证">
      本地模型或 Docker 尚未就绪。任务可以保存到队列，但 worker 会在执行前记录阻塞状态。先到 <Link className="inline-link" to="/settings">设置</Link> 查看环境状态。
    </InlineNotice>}
    <div className="new-run-layout">
      <Panel><div className="panel-heading"><div><h2>任务输入</h2><div className="panel-subtitle">运行时会记录模型、代码快照、预算与提示词版本</div></div><Badge>本机队列</Badge></div>
        <form className="panel-body form-grid" onSubmit={e => { e.preventDefault(); setError(''); create.mutate({ repository_id: repositoryId, issue, method, test_profile_id: 'python-pytest' }, { onError: e => setError(errorMessage(e)) }) }}>
          <div className="form-field"><label htmlFor="repository">目标仓库</label>
            <select id="repository" className="field-control" required value={repositoryId} onChange={e => setRepositoryId(e.target.value)}>
              <option value="">选择已导入的仓库</option>{repos.data?.items.map(repo => <option key={repo.id} value={repo.id}>{repo.name} · {repo.file_count} 文件</option>)}
            </select>
            {repos.isError ? <InlineNotice kind="danger">{errorMessage(repos.error)}</InlineNotice>
              : !repos.data?.items.length && !repos.isLoading && <span className="form-help">先<Link className="inline-link" to="/repositories">导入一个仓库</Link>再创建修复任务。</span>}
          </div>
          <div className="form-field"><label htmlFor="issue">问题描述</label><textarea id="issue" className="field-control issue-input" required minLength={5} maxLength={30000}
            value={issue} onChange={e => setIssue(e.target.value)} placeholder="例如：空列表传入 normalize_items 时会抛出 IndexError。请修复边界处理，并保留现有排序语义。" />
            <span className="form-help">提供可复现的输入、实际行为和期望行为。Agent 会先验证原测试能复现失败。</span></div>
          <fieldset className="method-picker"><legend>检索方法</legend>{methods.map(item => <label key={item.id} className={`method-option ${method === item.id ? 'method-selected' : ''}`}>
            <input type="radio" name="method" value={item.id} checked={method === item.id} onChange={() => setMethod(item.id)} />
            <span className="method-copy"><strong>{item.title}</strong><small>{item.description}</small></span>
          </label>)}</fieldset>
          <div className="run-config-summary"><span><Blocks size={14} /> {selectedRepo ? `${selectedRepo.name} · ${selectedRepo.tree_hash.slice(0, 12)}` : '尚未选择仓库'}</span>
            <span><ShieldCheck size={14} /> 审查策略：验证通过后等待人工决策</span>
            <span><Sparkles size={14} /> 默认预算：最多 {settings.data?.defaults.max_attempts ?? 3} 轮 / {settings.data?.defaults.max_model_calls ?? 12} 次模型调用</span></div>
          {error && <InlineNotice kind="danger" title="任务创建失败">{error}</InlineNotice>}
          {create.isError && !error && <InlineNotice kind="danger">{errorMessage(create.error)}</InlineNotice>}
          <div className="toolbar"><Button variant="primary" type="submit" disabled={!repositoryId || issue.trim().length < 5 || create.isPending}>
            {create.isPending ? '正在加入队列…' : '创建修复任务'} <ArrowRight size={14} /></Button><Link className="button button-ghost button-md" to="/overview">取消</Link></div>
        </form>
      </Panel>
      <aside className="new-run-aside section-stack"><Panel><div className="panel-heading"><div><h2>执行顺序</h2><div className="panel-subtitle">LangGraph 有状态流程</div></div></div>
        <div className="node-flow">{['校验任务与配置','准备隔离副本','构建 AST 代码图','基线测试','检索相关证据','规划与生成补丁','校验 diff','应用到工作副本','沙箱测试','人工审查'].map((label, i) => <div className="flow-node" key={label}><span className="flow-icon">{String(i + 1).padStart(2, '0')}</span>{label}</div>)}</div></Panel>
        <InlineNotice kind="info" title="可追溯与可复现">每次运行保留预算快照、检索证据、模型用量、测试标准输出、Diff 与事件时间线。</InlineNotice>
      </aside>
    </div>
  </>
}
