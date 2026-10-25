import { ArrowRight, ArrowUpRight, Blocks, Clock3, Code2, Database, FileSearch2,
  FolderKanban, FlaskConical, History, Plus, ShieldCheck, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { keys } from '@/api/query'
import { compact, dateTime } from '@/lib/format'
import type { Run } from '@/api/types'
import { Badge, EmptyState, InlineNotice, Loading, PageHeading, Panel } from '@/components/ui'

function statusFor(run: Run) {
  const map: Record<string, { label: string; tone: 'neutral' | 'success' | 'warning' | 'danger' | 'info' }> = {
    queued: { label: '排队中', tone: 'neutral' }, running: { label: '执行中', tone: 'info' },
    awaiting_review: { label: '待审查', tone: 'warning' }, completed: { label: run.outcome === 'verified' ? '验证通过' : '流程结束', tone: run.outcome === 'verified' ? 'success' : 'neutral' },
    blocked: { label: '已阻塞', tone: 'warning' }, failed: { label: '失败', tone: 'danger' }, cancelled: { label: '已取消', tone: 'neutral' },
  }
  return map[run.status] || map.queued
}

function RecentRuns({ runs }: { runs: Run[] }) {
  return <Panel className="overview-recent"><div className="panel-heading"><div><h2>近期运行</h2>
    <div className="panel-subtitle">本机保存的修复任务</div></div><Link className="button button-ghost button-sm" to="/repositories">仓库列表 <ArrowRight size={14} /></Link></div>
    {runs.length ? <div className="table-wrap"><table><thead><tr><th>问题描述</th><th>仓库</th><th>方法</th><th>状态</th><th>创建时间</th><th /></tr></thead>
      <tbody>{runs.map(run => { const state = statusFor(run); return <tr key={run.id}>
        <td><Link className="table-primary truncate" to={`/runs/${run.id}`}>{run.issue}</Link></td>
        <td><span className="truncate">{run.repository_name}</span></td><td><code className="mono">{run.method}</code></td>
        <td><Badge tone={state.tone} dot>{state.label}</Badge></td><td>{dateTime(run.created_at)}</td>
        <td><Link className="icon-link" aria-label="打开任务" to={`/runs/${run.id}`}><ArrowUpRight size={15} /></Link></td>
      </tr>})}</tbody></table></div>
      : <EmptyState icon={History} title="还没有修复运行" description="导入一个 Python 仓库并创建任务，Agent 会在这里显示真实执行记录。"
        action={<Link to="/runs/new" className="button button-secondary button-sm">创建修复任务</Link>} />}
  </Panel>
}

export default function OverviewPage() {
  const { data, isLoading, error } = useQuery({ queryKey: keys.overview, queryFn: api.overview, refetchInterval: 5000 })
  if (isLoading) return <Loading label="正在读取本地工作区" />
  if (!data) return <><PageHeading eyebrow="GemmaGraph Lab" title="概览" />
    <InlineNotice kind="danger" title="无法读取本地后端">{error instanceof Error ? error.message : '请确认后端 API 已启动。'}</InlineNotice></>

  return <>
    <PageHeading eyebrow="GEMMAGRAPH LAB · CODE REPAIR RESEARCH" title="研究工作台" />
    {(!data.model.configured || !data.sandbox.available) && <div className="model-notice">
      <InlineNotice kind="warning" title="运行前需要完成环境配置">
        Gemma：{data.model.configured ? `${data.model.model_id} 已配置` : '本地权重或推理程序尚未就绪'}；
        Docker：{data.sandbox.available ? `已连接 ${data.sandbox.engine_version}` : '不可用'}。
        <Link to="/settings" className="inline-link">查看环境状态与配置说明 <ArrowRight size={12} /></Link>
      </InlineNotice></div>}
    <Panel className="hero-panel"><div className="hero-copy">
      <div className="eyebrow">LOCAL SOFTWARE ENGINEERING AGENT</div>
      <h2>让每一步修复都有据可查</h2>
      <p>将代码关系图检索、LangGraph 执行轨迹与隔离测试放在同一工作台，记录每次 Agent 运行与研究实验。</p>
      <div className="toolbar"><Link to="/runs/new" className="button button-primary button-md"><Plus size={15} /> 新建修复任务</Link>
        <Link to="/repositories" className="button button-secondary button-md"><Blocks size={15} /> 浏览仓库</Link></div>
      <div className="hero-meta"><span><ShieldCheck size={13} /> 数据保存在本机</span><span><Sparkles size={13} /> Python AST 代码图</span></div>
    </div><div className="hero-figure"><img src="/mark.svg" alt="GemmaGraph Lab 图标" /></div></Panel>

    <section className="metric-grid" aria-label="工作区统计">
      {[{ label: '已导入仓库', value: data.repositories, icon: Blocks, tone: '' },
        { label: '修复运行', value: data.runs, icon: Code2, tone: 'blue' },
        { label: '等待审查', value: data.by_status.awaiting_review || 0, icon: Clock3, tone: 'orange' },
        { label: '研究实验', value: data.experiments, icon: FlaskConical, tone: 'gray' }].map(item =>
          <Panel key={item.label} className="metric-card"><div className={`metric-icon ${item.tone}`}><item.icon size={18} /></div>
            <div className="metric-text"><span className="metric-label">{item.label}</span><strong className="metric-number">{compact(item.value)}</strong></div></Panel>)}
    </section>

    <div className="overview-grid"><RecentRuns runs={data.recent_runs} />
      <Panel><div className="panel-heading"><div><h2>开始使用</h2><div className="panel-subtitle">三步开始一个可追踪的实验</div></div></div>
        <div className="panel-body quick-links">
          {[{ to: '/repositories', icon: FolderKanban, title: '导入 Python 仓库', desc: '上传源码 ZIP，构建符号与依赖图' },
            { to: '/settings', icon: Database, title: '检查本地 Gemma 4', desc: '确认 GGUF 权重与官方 llama.cpp 已就绪' },
            { to: '/runs/new', icon: FileSearch2, title: '提出一个修复问题', desc: '选择检索策略，查看证据与测试结果' }].map(item =>
            <Link key={item.title} to={item.to} className="quick-link"><span className="quick-link-icon"><item.icon size={17} /></span>
              <span className="quick-link-copy"><strong>{item.title}</strong><p>{item.desc}</p></span><ArrowUpRight className="quick-arrow" size={15} /></Link>)}
        </div></Panel></div>
  </>
}
