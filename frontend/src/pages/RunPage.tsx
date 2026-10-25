import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Ban, Check, CircleAlert, Download, FileDiff, LoaderCircle, RefreshCw, X } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, artifactUrl } from '@/api/client'
import { keys } from '@/api/query'
import { useRunEvents } from '@/hooks/useRunEvents'
import { dateTime, elapsed, errorMessage } from '@/lib/format'
import { WorkflowGraph } from '@/components/WorkflowGraph'
import { MonacoDiffViewer } from '@/components/MonacoEditor'
import type { RunEvent } from '@/api/types'
import { Badge, Button, InlineNotice, Loading, PageHeading, Panel } from '@/components/ui'

const statusNames: Record<string, [string, 'neutral'|'success'|'warning'|'danger'|'info']> = {
  queued: ['排队中','neutral'], running: ['执行中','info'], awaiting_review: ['待人工审查','warning'], completed: ['已完成','success'],
  blocked: ['执行受阻','warning'], failed: ['执行失败','danger'], cancelled: ['已取消','neutral'],
}
const eventNames: Record<string, string> = { 'run.queued': '加入任务队列', 'run.started': '开始执行', 'run.resumed': '从人工审查恢复',
  'run.cancel_requested': '请求取消', 'run.cancelled': '已取消', 'run.completed': '流程完成', 'run.blocked': '执行前置条件不足',
  'run.failed': '运行失败', 'run.recovered': '从检查点恢复', 'node.started': '节点开始', 'node.completed': '节点完成', 'node.failed': '节点失败',
  'evidence.selected': '选择检索证据', 'plan.created': '生成修复计划', 'patch.generated': '生成补丁',
  'verification.completed': '测试完成', 'review.required': '等待人工审查' }

export default function RunPage() {
  const { runId = '' } = useParams()
  const qc = useQueryClient()
  const query = useQuery({ queryKey: keys.run(runId), queryFn: () => api.run(runId), refetchInterval: data =>
    data?.state.data?.status === 'queued' || data?.state.data?.status === 'running' ? 2000 : 5000 })
  const { events, connected, historyError } = useRunEvents(runId)
  const [feedback, setFeedback] = useState('')
  const [activeTab, setActiveTab] = useState<'diff'|'verification'|'events'>('diff')
  const [diff, setDiff] = useState('')
  const [reviewError, setReviewError] = useState('')
  const run = query.data
  const artifacts = useQuery({ queryKey: ['artifacts', runId], queryFn: () => api.artifacts(runId), enabled: !!run && !!run.patch })
  const patchId = run?.patch?.id
  useEffect(() => {
    let active = true
    if (!patchId) { setDiff(''); return }
    void api.artifact(patchId).then(blob => blob.text()).then(text => { if (active) setDiff(text) })
      .catch(e => { if (active) setDiff(`无法读取补丁：${errorMessage(e)}`) })
    return () => { active = false }
  }, [patchId])
  const reviewMutation = useMutation({ mutationFn: (decision: 'accept'|'reject'|'revise') => api.resumeRun(runId, {
    review_id: run?.review?.review_id || '', patch_hash: run?.review?.patch_hash || '', decision, feedback: feedback.trim() }),
    onSuccess: async () => { setReviewError(''); setFeedback(''); await qc.invalidateQueries({ queryKey: keys.run(runId) }) },
    onError: e => setReviewError(errorMessage(e)) })
  const cancelMutation = useMutation({ mutationFn: () => api.cancelRun(runId), onSuccess: () => qc.invalidateQueries({ queryKey: keys.run(runId) }) })
  const status = statusNames[run?.status || ''] || statusNames.queued
  const timeline = useMemo(() => events.slice().reverse(), [events])
  if (query.isLoading) return <Loading label="正在读取运行状态" />
  if (!run) return <><PageHeading title="运行不可用" /><InlineNotice kind="danger">{query.error instanceof Error ? query.error.message : '没有找到此运行。'}</InlineNotice></>
  const canCancel = ['queued','running'].includes(run.status)
  return <>
    <PageHeading eyebrow="REPAIR RUN" title="修复运行" description={run.issue} actions={<Link to="/overview" className="button button-secondary button-md"><ArrowLeft size={14} /> 返回概览</Link>} />
    <Panel className="run-head-panel"><div className="run-head-main"><div className="run-head-row"><strong>{run.repository_name}</strong><Badge tone={status[1]} dot>{status[0]}</Badge><Badge>{run.method}</Badge>
      <span className="subtle mono">{run.id}</span></div><div className="run-head-sub">创建于 {dateTime(run.created_at)} · 当前节点：{run.current_node || '已结束'} · 尝试 {run.attempt}</div></div>
      <div className="toolbar run-head-actions">{canCancel && <Button variant="danger" size="sm" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}><Ban size={13} /><span className="button-label">取消运行</span></Button>}
        <span className={`connection-label ${connected ? 'connected' : ''}`}><i />{connected ? '事件实时连接' : '正在重连事件流'}</span></div></Panel>
    {historyError && <InlineNotice kind="warning" title="事件历史不可用">{historyError}</InlineNotice>}
    {cancelMutation.isError && <InlineNotice kind="danger" title="取消运行失败">{errorMessage(cancelMutation.error)}</InlineNotice>}
    {run.error && <InlineNotice kind={run.status === 'blocked' ? 'warning' : 'danger'} title={run.error.code}>{run.error.message}</InlineNotice>}
    <div className="run-workbench">
      <div className="run-column"><Panel className="workbench-panel"><div className="panel-heading"><div><h2>LangGraph 流程</h2><div className="panel-subtitle">运行时节点与路径</div></div></div>
        <div className="workflow-side"><WorkflowGraph run={run} events={events} /></div></Panel></div>
      <div className="run-column run-main"><Panel className="workbench-panel"><div className="panel-heading"><div><h2>执行记录</h2><div className="panel-subtitle">{run.summary || '节点事件与修复产物'}</div></div>
        {run.patch && <a className="button button-secondary button-sm" href={artifactUrl(run.patch.id)} download={run.patch.name}><Download size={13} /> 下载 Diff</a>}</div>
        <div className="tabs"><button className={`tab ${activeTab === 'diff' ? 'tab-active' : ''}`} onClick={() => setActiveTab('diff')}><FileDiff size={13} /> 补丁与证据</button>
          <button className={`tab ${activeTab === 'verification' ? 'tab-active' : ''}`} onClick={() => setActiveTab('verification')}><Check size={13} /> 测试结果</button>
          <button className={`tab ${activeTab === 'events' ? 'tab-active' : ''}`} onClick={() => setActiveTab('events')}><RefreshCw size={13} /> 事件时间线 <span>{events.length}</span></button></div>
        {activeTab === 'diff' && <div className="run-tab-body">
          {run.plan && <div className="run-summary"><strong>修复计划</strong><pre>{JSON.stringify(run.plan, null, 2)}</pre></div>}
          {run.patch ? diff ? <MonacoDiffViewer diff={diff} /> : <div className="repository-placeholder"><FileDiff size={22} /><span>正在读取补丁…</span></div>
            : <div className="repository-placeholder"><FileDiff size={22} /><span>补丁生成后会显示在这里</span></div>}
          {!!run.evidence.length && <div className="evidence-list">{run.evidence.map((item, i) => <article className="evidence-card" key={`${item.id}-${i}`}>
            <div className="evidence-path">{item.path}:{item.start_line}–{item.end_line}</div><div className="evidence-meta">相关度 {item.score.toFixed(3)} · 关系距离 {item.relation_distance} · {item.tokens} tokens</div>
            <pre className="evidence-excerpt">{item.text}</pre></article>)}</div>}
        </div>}
        {activeTab === 'verification' && <div className="run-tab-body verification-pane">{(['baseline','verification'] as const).map(key => <Panel className="log-panel" key={key}>
          <div className="panel-heading"><div><h2>{key === 'baseline' ? '基线测试' : '候选补丁测试'}</h2><div className="panel-subtitle">{run[key] ? `退出码 ${run[key]?.exit_code ?? '未知'} · 收集 ${run[key]?.collected ?? 0} 项` : '尚无结果'}</div></div>
          {run[key]?.tests_passed !== undefined && <Badge tone={run[key]?.tests_passed ? 'success' : 'danger'}>{run[key]?.tests_passed ? '通过' : '未通过'}</Badge>}</div>
          {run[key] ? <pre className="log-box">{[run[key]?.stdout, run[key]?.stderr].filter(Boolean).join('\n\nSTDERR\n') || '测试未产生标准输出。'}</pre> : <div className="panel-body subtle">等待测试完成。</div>}
        </Panel>)}</div>}
        {activeTab === 'events' && <div className="timeline">{timeline.length ? timeline.map(event => <TimelineItem key={event.seq} event={event} />)
          : <div className="repository-placeholder">正在等待第一个事件…</div>}</div>}
      </Panel></div>
      <aside className="run-column run-side"><Panel className="workbench-panel"><div className="panel-heading"><div><h2>运行摘要</h2><div className="panel-subtitle">固定配置与可复现信息</div></div></div>
        <div className="result-table"><ResultRow label="结果" value={run.outcome} /><ResultRow label="模型" value={String(run.config_snapshot.model.model_id || '未配置')} />
          <ResultRow label="提示词版本" value={String(run.config_snapshot.prompt_version || '—').slice(0, 16)} /><ResultRow label="模型调用" value={String(run.usage.model_calls ?? 0)} />
          <ResultRow label="输入 tokens" value={String(run.usage.input_tokens ?? '未采集')} /><ResultRow label="输出 tokens" value={String(run.usage.output_tokens ?? '未采集')} />
          <ResultRow label="思考 tokens" value={String(run.usage.thought_tokens ?? '未采集')} />
          <ResultRow label="运行时长" value={elapsed(run.created_at, run.updated_at)} /></div>
        {!!artifacts.data?.items.length && <div className="artifact-list">{artifacts.data.items.map(file => <a className="artifact-row" key={file.id} href={artifactUrl(file.id)} download={file.name}>
          <Download size={13} /><span>{file.name}</span></a>)}</div>}</Panel>
        {run.status === 'awaiting_review' && <Panel className="review-card"><h3><CircleAlert size={14} /> 人工审查</h3>
          <p>请检查 Diff 和验证日志，再决定接受、拒绝或要求修改。提交后会通过 LangGraph checkpoint 恢复流程。</p>
          <textarea className="field-control" aria-label="审查意见" value={feedback} onChange={e => setFeedback(e.target.value)} placeholder="修改意见（选择“要求修改”时必填）" />
          {reviewError && <InlineNotice kind="danger">{reviewError}</InlineNotice>}
          <div className="review-actions"><Button variant="primary" size="sm" onClick={() => reviewMutation.mutate('accept')} disabled={reviewMutation.isPending}><Check size={13} /> 接受</Button>
            <Button variant="secondary" size="sm" onClick={() => reviewMutation.mutate('reject')} disabled={reviewMutation.isPending}><X size={13} /> 拒绝</Button>
            <Button variant="secondary" size="sm" onClick={() => reviewMutation.mutate('revise')} disabled={reviewMutation.isPending || feedback.trim().length < 3}><RefreshCw size={13} /> 修改</Button></div>
          {reviewMutation.isPending && <span className="form-help"><LoaderCircle className="spin" size={12} /> 正在恢复流程…</span>}
        </Panel>}
        {run.review?.status && run.review.status !== 'pending' && <InlineNotice kind={run.review.status === 'accept' ? 'success' : 'info'} title={`审查状态：${run.review.status}`}>
          {run.review.feedback || '审查决策已保存。'}</InlineNotice>}
      </aside>
    </div>
  </>
}

function ResultRow({ label, value }: { label: string; value: string }) { return <div className="result-row"><span>{label}</span><strong>{value}</strong></div> }
function TimelineItem({ event }: { event: RunEvent }) {
  const detail = [event.node && `节点 ${event.node}`, event.attempt ? `第 ${event.attempt} 轮` : '', event.payload?.error && String(event.payload.error)].filter(Boolean).join(' · ')
  return <div className="timeline-item"><span className={`timeline-dot ${event.type.endsWith('failed') ? 'error' : event.type.endsWith('started') ? 'working' : ''}`} />
    <div className="timeline-copy"><div className="timeline-top"><strong>{eventNames[event.type] || event.type}</strong><span className="timeline-time">#{event.seq} · {new Date(event.timestamp).toLocaleTimeString('zh-CN')}</span></div>
      {detail && <p>{detail}</p>}</div></div>
}
