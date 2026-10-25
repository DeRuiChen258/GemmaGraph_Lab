import { useEffect, useMemo, useRef, useState } from 'react'
import * as monaco from 'monaco-editor'
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker'
import 'monaco-editor/min/vs/editor/editor.main.css'

let workersConfigured = false
function configureWorkers() {
  if (workersConfigured) return
  window.MonacoEnvironment = { getWorker: (_moduleId, _label) => new EditorWorker() }
  workersConfigured = true
}

export function MonacoEditor({ value, language = 'plaintext', className = '' }: {
  value: string; language?: string; className?: string
}) {
  const host = useRef<HTMLDivElement>(null)
  const editor = useRef<monaco.editor.IStandaloneCodeEditor | null>(null)
  useEffect(() => {
    if (!host.current) return
    configureWorkers()
    const instance = monaco.editor.create(host.current, {
      value, language, readOnly: true, automaticLayout: true, minimap: { enabled: false },
      scrollBeyondLastLine: false, renderLineHighlight: 'none', fontSize: 11, lineHeight: 19,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
      lineNumbersMinChars: 3, folding: false, contextmenu: false, wordWrap: 'off',
      padding: { top: 12, bottom: 12 }, overviewRulerBorder: false, hideCursorInOverviewRuler: true,
      scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
    })
    editor.current = instance
    const resize = new ResizeObserver(() => instance.layout())
    resize.observe(host.current)
    return () => {
      resize.disconnect()
      const model = instance.getModel()
      instance.dispose(); model?.dispose(); editor.current = null
    }
  }, [])
  useEffect(() => {
    if (!editor.current) return
    const model = editor.current.getModel()
    if (model && model.getValue() !== value) editor.current.setValue(value)
    if (model && model.getLanguageId() !== language) monaco.editor.setModelLanguage(model, language)
  }, [value, language])
  return <div className={`monaco-container ${className}`} ref={host} aria-label="只读代码编辑器" />
}

type DiffFile = { path: string; original: string[]; modified: string[] }

function parseDiff(diff: string): DiffFile[] {
  const chunks = diff.includes('diff --git ')
    ? diff.split(/^diff --git .*$/m).filter(chunk => chunk.trim())
    : diff.split(/(?=^--- a\/)/m).filter(chunk => chunk.trim())
  return chunks.flatMap(chunk => {
    const header = chunk.match(/^\+\+\+ b\/(.+)$/m)
    const hunk = chunk.split('\n').findIndex(line => /^@@ /.test(line))
    if (!header || hunk < 0) return []
    const original: string[] = [], modified: string[] = []
    for (const line of chunk.split('\n').slice(hunk + 1)) {
      if (/^@@ /.test(line) || /^diff --git /.test(line) || line === '\\ No newline at end of file') continue
      if (line.startsWith(' ')) { original.push(line.slice(1)); modified.push(line.slice(1)) }
      else if (line.startsWith('-')) original.push(line.slice(1))
      else if (line.startsWith('+')) modified.push(line.slice(1))
    }
    return [{ path: header[1], original, modified }]
  })
}

export function MonacoDiffViewer({ diff }: { diff: string }) {
  const host = useRef<HTMLDivElement>(null)
  const diffEditor = useRef<monaco.editor.IStandaloneDiffEditor | null>(null)
  const files = useMemo(() => parseDiff(diff), [diff])
  const [fileIndex, setFileIndex] = useState(0)
  useEffect(() => { setFileIndex(0) }, [diff])
  useEffect(() => {
    if (!host.current || !files.length) return
    configureWorkers()
    const instance = monaco.editor.createDiffEditor(host.current, {
      readOnly: true, originalEditable: false, automaticLayout: true, minimap: { enabled: false },
      renderSideBySide: true, ignoreTrimWhitespace: false, lineNumbers: 'on', fontSize: 10,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
      scrollBeyondLastLine: false, diffWordWrap: 'off', renderOverviewRuler: false,
      scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
    })
    diffEditor.current = instance
    const resize = new ResizeObserver(() => instance.layout())
    resize.observe(host.current)
    return () => { resize.disconnect(); instance.setModel(null); instance.dispose(); diffEditor.current = null }
  }, [files.length])
  useEffect(() => {
    const instance = diffEditor.current, file = files[fileIndex]
    if (!instance || !file) return
    const language = file.path.endsWith('.py') ? 'python' : 'plaintext'
    const original = monaco.editor.createModel(file.original.join('\n'), language)
    const modified = monaco.editor.createModel(file.modified.join('\n'), language)
    instance.setModel({ original, modified })
    return () => { original.dispose(); modified.dispose() }
  }, [files, fileIndex])
  if (!files.length) return <pre className="diff-view">{diff || '补丁生成后会显示在这里'}</pre>
  return <div className="diff-shell">{files.length > 1 && <div className="diff-file-tabs">{files.map((file, index) =>
    <button key={`${file.path}-${index}`} className={fileIndex === index ? 'diff-file-active' : ''} onClick={() => setFileIndex(index)}>{file.path}</button>)}</div>}
    <div className="diff-file-caption">{files[fileIndex]?.path} · 仅展示补丁覆盖的上下文行</div>
    <div className="monaco-diff-container" ref={host} aria-label="补丁并排差异视图" />
  </div>
}
