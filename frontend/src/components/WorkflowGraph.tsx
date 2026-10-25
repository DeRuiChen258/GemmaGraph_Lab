import { Background, Controls, Handle, Position, ReactFlow, type Node, type NodeProps } from '@xyflow/react'
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { Run, RunEvent } from '@/api/types'
import { Loading } from './ui'

type WorkflowNodeData = Node<{ label: string; detail: string }, 'workflow'>

function WorkflowNode({ data }: NodeProps<WorkflowNodeData>) {
  return <div className={`workflow-node ${data.detail === '当前步骤' ? 'workflow-node-active' : data.detail === '已完成' ? 'workflow-node-done' : ''}`}>
    <Handle type="target" position={Position.Left} isConnectable={false} />
    <strong>{data.label}</strong><small>{data.detail}</small>
    <Handle type="source" position={Position.Right} isConnectable={false} /></div>
}
const nodeTypes = { workflow: WorkflowNode }

export function WorkflowGraph({ run, events }: { run: Run; events: RunEvent[] }) {
  const query = useQuery({ queryKey: ['workflow'], queryFn: api.workflow, staleTime: Infinity })
  const graph = useMemo(() => {
    if (!query.data) return { nodes: [] as WorkflowNodeData[], edges: [] }
    const completed = new Set(events.filter(e => e.type === 'node.completed').map(e => e.node))
    const active = run.status === 'running' ? events.filter(e => e.type === 'node.started').at(-1)?.node || run.current_node
      : run.status === 'awaiting_review' ? 'human_review' : null
    const nodes: WorkflowNodeData[] = query.data.nodes.map((item: { id: string; label: string }, index: number) => ({
      id: item.id, type: 'workflow', position: { x: (index % 5) * 175, y: Math.floor(index / 5) * 92 },
      data: { label: item.label, detail: item.id === active ? '当前步骤' : completed.has(item.id) ? '已完成' : '等待执行' },
    }))
    const ids = new Set(nodes.map(node => node.id))
    const edges = query.data.edges.filter((item: { source: string; target: string }) => ids.has(item.source) && ids.has(item.target)).map((item: { source: string; target: string }, i: number) => ({
      id: `work-${i}`, source: item.source, target: item.target, type: 'smoothstep' as const,
      style: { stroke: completed.has(item.source) ? '#6bb4a5' : '#dce2e6', strokeWidth: 1.2 },
      animated: item.source === active,
    }))
    return { nodes, edges }
  }, [query.data, run.current_node, events])
  if (query.isLoading) return <Loading label="正在加载后端执行图" />
  return <div className="workflow-canvas" role="img" aria-label="LangGraph 执行状态图">
    <ReactFlow nodes={graph.nodes} edges={graph.edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: .2 }}
      nodesDraggable={false} nodesConnectable={false} elementsSelectable zoomOnDoubleClick={false} proOptions={{ hideAttribution: true }}>
      <Background color="#e5ebed" gap={17} size={1} /><Controls showInteractive={false} />
    </ReactFlow></div>
}
