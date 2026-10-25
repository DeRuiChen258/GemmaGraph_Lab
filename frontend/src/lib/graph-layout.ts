import type { Edge, Node } from '@xyflow/react'

export interface GraphDatum { id: string; name: string; path: string; kind: string; start_line: number; end_line: number }

const colors: Record<string, { color: string; background: string }> = {
  file: { color: '#26766c', background: '#f1faf7' },
  class: { color: '#536eaa', background: '#f5f7fc' },
  function: { color: '#546c98', background: '#f7f8fc' },
  unresolved: { color: '#8992a0', background: '#fafafa' },
}

export function codeGraphLayout(values: GraphDatum[], relations: Array<{ source: string; target: string; kind: string }>) {
  const ids = new Set(values.map(v => v.id))
  const parents = new Map<string, string[]>()
  for (const edge of relations) if (ids.has(edge.source) && ids.has(edge.target)) {
    parents.set(edge.target, [...(parents.get(edge.target) || []), edge.source])
  }
  const levels = new Map<string, number>()
  const getLevel = (id: string, chain = new Set<string>()): number => {
    if (levels.has(id)) return levels.get(id)!
    if (chain.has(id)) return 0
    chain.add(id)
    const above = parents.get(id) || []
    const level = above.length ? Math.min(3, Math.max(...above.map(p => getLevel(p, new Set(chain)))) + 1) : 0
    levels.set(id, level); return level
  }
  for (const value of values) getLevel(value.id)
  const slots: number[] = [0, 0, 0, 0]
  const nodes: Node[] = values.map(value => {
    const level = levels.get(value.id) ?? 0, slot = slots[level]++
    const tone = colors[value.kind] || colors.function
    return { id: value.id, type: 'default', position: { x: level * 250, y: slot * 96 },
      data: { label: `${value.kind === 'unresolved' ? '未解析' : value.kind}  ·  ${value.name || value.path}`,
        detail: value.path ? `${value.path}:${value.start_line}` : '动态引用未能解析' },
      style: { width: 200, color: tone.color, borderColor: value.kind === 'unresolved' ? '#e5e7eb' : '#dfe8e5',
        background: tone.background, borderRadius: 9, padding: 10, fontSize: 10, lineHeight: 1.5,
        opacity: value.kind === 'unresolved' ? .76 : 1 },
    }
  })
  const edges: Edge[] = relations.filter(edge => ids.has(edge.source) && ids.has(edge.target)
    && edge.source !== edge.target).map((edge, i) => ({ id: `e-${i}-${edge.source}-${edge.target}`,
      source: edge.source, target: edge.target, label: edge.kind, type: 'smoothstep',
      animated: false, style: { stroke: '#b9cec8', strokeWidth: 1.2 },
      labelStyle: { fill: '#829088', fontSize: 8 }, labelBgStyle: { fill: '#fff', fillOpacity: .94 } }))
  return { nodes, edges }
}
