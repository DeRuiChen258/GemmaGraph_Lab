import { useEffect, useState } from 'react'
import { Archive, FileJson2, LoaderCircle, UploadCloud } from 'lucide-react'
import { api } from '@/api/client'
import { errorMessage } from '@/lib/format'
import type { Repository } from '@/api/types'
import { Button, InlineNotice, Modal } from './ui'

type Props = { mode: 'repository' | 'dataset'; open: boolean; onClose: () => void;
  repositories?: Repository[]; onComplete: (value: Repository | { id: string; task_count: number; name: string }) => void }

export function ImportDialog({ mode, open, onClose, repositories = [], onComplete }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [map, setMap] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [repoKeys, setRepoKeys] = useState<string[]>([])
  useEffect(() => {
    let active = true
    setRepoKeys([])
    if (mode !== 'dataset' || !file) return
    void file.text().then(text => {
      const values = new Set<string>()
      for (const [index, line] of text.split(/\r?\n/).entries()) {
        if (!line.trim()) continue
        try { const item = JSON.parse(line); if (!item.repository_id && item.repository_key) values.add(item.repository_key) }
        catch { throw new Error(`第 ${index + 1} 行不是有效 JSON`) }
      }
      if (active) setRepoKeys([...values])
    }).catch(e => { if (active) setError(errorMessage(e)) })
    return () => { active = false }
  }, [file, mode])

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError('')
    if (!file) { setError('请选择一个文件。'); return }
    if (mode === 'dataset' && repoKeys.some(key => !map[key])) { setError('请为每个仓库键选择一个已导入仓库。'); return }
    setBusy(true)
    try {
      const value = mode === 'repository' ? await api.importRepository(name || file.name.replace(/\.zip$/i, ''), file)
        : await api.importDataset(file, map)
      onComplete(value as Repository | { id: string; task_count: number; name: string })
      setFile(null); setName(''); setMap({}); setRepoKeys([]); onClose()
    } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  return <Modal open={open} onClose={() => !busy && onClose()} title={mode === 'repository' ? '导入代码仓库' : '导入任务清单'}>
    <form className="form-grid" onSubmit={submit}>
      <div className="upload-drop"><label htmlFor="import-file"><span className="upload-icon">{mode === 'repository' ? <Archive size={19} /> : <FileJson2 size={19} />}</span>
        <strong>{file?.name || (mode === 'repository' ? '选择仓库 ZIP 文件' : '选择任务 JSONL 文件')}</strong>
        <span>{file ? `${(file.size / 1048576).toFixed(1)} MB` : (mode === 'repository' ? 'Python 源码 ZIP，最大 50 MB' : 'UTF-8 JSONL，最大 5 MB')}</span></label>
        <input id="import-file" type="file" accept={mode === 'repository' ? '.zip,application/zip' : '.jsonl,.txt,application/json'}
          onChange={e => { setFile(e.target.files?.[0] || null); setMap({}); setError('') }} /></div>
      {mode === 'repository' ? <div className="form-field"><label htmlFor="repo-name">仓库名称</label>
        <input id="repo-name" className="field-control" value={name} placeholder="使用文件名" onChange={e => setName(e.target.value)} /></div>
        : <>{repoKeys.length > 0 && <div className="repo-mappings"><div className="form-label">仓库键映射</div>
          {repoKeys.map(key => <div key={key} className="mapping-row"><code className="mono">{key}</code>
            <select className="field-control" aria-label={`${key} 对应的仓库`} value={map[key] || ''} onChange={e => setMap({ ...map, [key]: e.target.value })}>
              <option value="">选择本地仓库</option>{repositories.map(repo => <option value={repo.id} key={repo.id}>{repo.name}</option>)}
            </select></div>)}</div>}
          {repositories.length === 0 && <InlineNotice kind="warning">请先导入一个仓库，再导入任务清单。</InlineNotice>}</>}
      {error && <InlineNotice kind="danger" title="导入未完成">{error}</InlineNotice>}
      <div className="modal-footer"><Button type="button" variant="ghost" onClick={onClose} disabled={busy}>取消</Button>
        <Button type="submit" variant="primary" disabled={busy || !file || (mode === 'dataset' && repositories.length === 0)}>
          {busy ? <><LoaderCircle className="spin" size={15} /> 正在上传</> : <><UploadCloud size={15} />{mode === 'repository' ? '上传并索引' : '校验并导入'}</>}
        </Button></div>
    </form>
  </Modal>
}
