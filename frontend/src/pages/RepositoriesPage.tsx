import { useState } from 'react'
import { ArrowUpRight, Blocks, Code2, FolderUp, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { keys } from '@/api/query'
import { dateTime } from '@/lib/format'
import { ImportDialog } from '@/components/ImportDialog'
import { Badge, Button, EmptyState, InlineNotice, Loading, PageHeading, Panel } from '@/components/ui'

export default function RepositoriesPage() {
  const [importing, setImporting] = useState(false)
  const qc = useQueryClient()
  const query = useQuery({ queryKey: keys.repositories, queryFn: api.repositories })
  if (query.isLoading) return <Loading label="正在读取仓库" />
  return <>
    <PageHeading eyebrow="CODE SNAPSHOTS" title="代码仓库" description="导入本机 Python 源码快照。每个快照会构建 AST 符号与调用关系索引，运行时始终在独立工作副本中修改。"
      actions={<Button variant="primary" onClick={() => setImporting(true)}><Plus size={15} /> 导入仓库</Button>} />
    {query.error && <InlineNotice kind="danger" title="仓库列表读取失败">{query.error instanceof Error ? query.error.message : '请确认后端已启动。'}</InlineNotice>}
    {query.data?.items.length ? <div className="repository-list">{query.data.items.map(repo => <Panel className="repository-row" key={repo.id}>
      <div className="repo-main"><span className="repo-icon"><Blocks size={18} /></span><div className="repo-copy">
        <strong>{repo.name}</strong><p>{repo.id} · 导入于 {dateTime(repo.created_at)}</p></div></div>
      <div className="repo-actions"><div className="repo-stats"><span><Code2 size={13} /> {repo.file_count} 文件</span>
        <span>{repo.symbol_count} 符号</span><Badge tone={repo.index_status === 'ready' ? 'success' : repo.index_status === 'failed' ? 'danger' : 'info'} dot>
          {repo.index_status === 'ready' ? '索引就绪' : repo.index_status === 'failed' ? '索引失败' : repo.index_status === 'queued' ? '等待索引' : repo.index_status}</Badge></div>
        <Link className="button button-secondary button-sm" to={`/repositories/${repo.id}`}>查看 <ArrowUpRight size={13} /></Link></div>
    </Panel>)}</div> : <Panel><EmptyState icon={FolderUp} title="还没有导入仓库" description="上传一个包含 Python 源码的 ZIP。文件会先做路径与大小校验，再保存在本机快照目录。"
      action={<Button variant="secondary" onClick={() => setImporting(true)}>选择 ZIP 文件</Button>} /></Panel>}
    <ImportDialog mode="repository" open={importing} onClose={() => setImporting(false)}
      onComplete={() => { void qc.invalidateQueries({ queryKey: keys.repositories }) }} />
  </>
}
