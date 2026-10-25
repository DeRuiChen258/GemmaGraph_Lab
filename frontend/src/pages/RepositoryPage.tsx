import { useMemo, useState } from 'react'
import { ArrowLeft, ChevronRight, FileCode2, Folder, GitBranch, Search } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Background, Controls, ReactFlow } from '@xyflow/react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import { keys } from '@/api/query'
import { codeGraphLayout } from '@/lib/graph-layout'
import { bytes, percent } from '@/lib/format'
import { MonacoEditor } from '@/components/MonacoEditor'
import { Badge, Button, InlineNotice, Loading, PageHeading, Panel } from '@/components/ui'

export default function RepositoryPage() {
  const { repositoryId = '' } = useParams()
  const [directory, setDirectory] = useState('')
  const [selectedFile, setSelectedFile] = useState('')
  const [graphQuery, setGraphQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const repoQuery = useQuery({ queryKey: keys.repo(repositoryId), queryFn: () => api.repository(repositoryId), enabled: !!repositoryId })
  const treeQuery = useQuery({ queryKey: keys.tree(repositoryId, directory), queryFn: () => api.tree(repositoryId, directory), enabled: !!repositoryId })
  const fileQuery = useQuery({ queryKey: ['repository-file', repositoryId, selectedFile], queryFn: () => api.file(repositoryId, selectedFile), enabled: !!selectedFile })
  const graph = useQuery({ queryKey: ['graph', repositoryId, submittedQuery], queryFn: () => api.graph(repositoryId, submittedQuery), enabled: !!repositoryId })
  const layout = useMemo(() => graph.data ? codeGraphLayout(graph.data.nodes, graph.data.edges) : { nodes: [], edges: [] }, [graph.data])
  if (repoQuery.isLoading) return <Loading label="正在读取仓库快照" />
  const repo = repoQuery.data
  if (!repo) return <><PageHeading title="仓库不可用" /><InlineNotice kind="danger">{repoQuery.error instanceof Error ? repoQuery.error.message : '没有找到这个仓库。'}</InlineNotice></>
  const parts = directory ? directory.split('/') : []
  const breadcrumb = parts.map((part, i) => ({ name: part, path: parts.slice(0, i + 1).join('/') }))
  return <>
    <PageHeading eyebrow="REPOSITORY SNAPSHOT" title={repo.name} description={`${repo.file_count} 个文件 · ${repo.symbol_count} 个符号 · AST 覆盖率 ${percent(repo.parse_coverage)}`}
      actions={<Link className="button button-secondary button-md" to="/repositories"><ArrowLeft size={14} /> 返回仓库</Link>} />
    {repo.diagnostics?.length > 0 && <InlineNotice kind="warning" title="索引诊断">有 {repo.diagnostics.length} 条解析诊断；未解析的动态引用不会计入静态关系。</InlineNotice>}
    <div className="repo-detail-grid section-stack">
      <Panel><div className="panel-heading"><div><h2>源码文件</h2><div className="panel-subtitle">只读快照 · {repo.id}</div></div>
        <Badge tone={repo.index_status === 'ready' ? 'success' : 'info'}>{repo.index_status}</Badge></div>
        <div className="panel-body">
          <div className="file-breadcrumb"><button className="tree-item" onClick={() => setDirectory('')}><Folder size={13} /> 项目根目录</button>
            {breadcrumb.map(item => <span className="crumb-piece" key={item.path}><ChevronRight size={12} /><button className="tree-item" onClick={() => setDirectory(item.path)}>{item.name}</button></span>)}</div>
          {treeQuery.isError && <InlineNotice kind="danger">{treeQuery.error instanceof Error ? treeQuery.error.message : '读取文件失败'}</InlineNotice>}
          <div className="tree-list tree-scroll">{treeQuery.data?.items.map(item => <button className={`tree-item ${selectedFile === item.path ? 'tree-selected' : ''}`} key={item.path}
            onClick={() => item.type === 'directory' ? setDirectory(item.path) : setSelectedFile(item.path)}>
            {item.type === 'directory' ? <Folder size={13} /> : <FileCode2 size={13} />}<span>{item.name}</span>
            {item.type === 'file' && <small className="tree-size">{bytes(item.size)}</small>}</button>)}</div>
          {!treeQuery.data?.items.length && <p className="subtle">此目录中没有可显示文件。</p>}
        </div></Panel>
      <Panel><div className="panel-heading"><div><h2>{selectedFile || '源码预览'}</h2><div className="panel-subtitle">单文件最多显示 1 MB</div></div></div>
        {selectedFile ? fileQuery.isLoading ? <Loading label="正在读取文件" /> : fileQuery.data ? <MonacoEditor className="source-preview" language={selectedFile.endsWith('.py') ? 'python' : 'plaintext'} value={fileQuery.data.content} />
          : <InlineNotice kind="danger">{fileQuery.error instanceof Error ? fileQuery.error.message : '无法读取文件'}</InlineNotice>
          : <div className="repository-placeholder"><FileCode2 size={23} /><span>从左侧选择一个文件</span></div>}</Panel>
    </div>
    <Panel className="graph-panel"><div className="panel-heading"><div><h2><GitBranch size={15} /> 代码关系图</h2><div className="panel-subtitle">Python AST 符号、定义与静态调用关系</div></div>
      <form className="graph-search" onSubmit={e => { e.preventDefault(); setSubmittedQuery(graphQuery.trim()) }}>
        <Search size={14} /><input aria-label="搜索符号" value={graphQuery} onChange={e => setGraphQuery(e.target.value)} placeholder="搜索函数或文件" />
        <Button size="sm" type="submit">搜索</Button></form></div>
      {graph.isLoading ? <Loading label="正在构建代码关系图" /> : graph.error ? <div className="panel-body"><InlineNotice kind="danger">{graph.error instanceof Error ? graph.error.message : '关系图读取失败'}</InlineNotice></div>
        : layout.nodes.length ? <><div className="codegraph-area"><ReactFlow nodes={layout.nodes} edges={layout.edges} fitView fitViewOptions={{ padding: .16 }}
            nodesDraggable={false} nodesConnectable={false} elementsSelectable proOptions={{ hideAttribution: true }}>
            <Background color="#e5ebed" gap={17} size={1} /><Controls showInteractive={false} /></ReactFlow></div>
          <div className="graph-label"><span>{graph.data?.nodes.length} 个节点</span><span>{graph.data?.edges.length} 条关系</span>
            <span>解析覆盖率 {percent(graph.data?.coverage)}</span>{graph.data?.truncated && <span>显示结果已截断</span>}</div></>
          : <div className="panel-body"><InlineNotice>此快照暂未解析出匹配符号。</InlineNotice></div>}
    </Panel>
  </>
}
