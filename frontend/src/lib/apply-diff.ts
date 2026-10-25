export function parseUnifiedDiff(diff: string): Array<{ path: string; original: string[]; modified: string[] }> {
  const files = diff.split(/^diff --git .*$/m).filter(chunk => chunk.trim())
  return files.flatMap(chunk => {
    const header = chunk.match(/^\+\+\+ b\/(.+)$/m)
    if (!header) return []
    const original: string[] = [], modified: string[] = []
    for (const line of chunk.split('\n').slice(chunk.split('\n').findIndex(v => /^@@ /.test(v)))) {
      if (/^@@ /.test(line) || line === '\ No newline at end of file' || line === '') continue
      if (line.startsWith(' ')) { original.push(line.slice(1)); modified.push(line.slice(1)) }
      else if (line.startsWith('-')) original.push(line.slice(1))
      else if (line.startsWith('+') && !line.startsWith('+++')) modified.push(line.slice(1))
    }
    return [{ path: header[1], original, modified }]
  })
}

export function applyUnifiedDiff(source: string, diff: string) {
  const hunks = diff.split(/^diff --git .*$/m).filter(chunk => chunk.trim())
  let output = source.split('\n'), failed = false
  for (const chunk of hunks) {
    const rows = chunk.split('\n')
    const file = rows.findIndex(row => /^\+\+\+ b\//.test(row))
    if (file < 0) { failed = true; continue }
    const next: string[] = []
    let cursor = 0
    const hunkIndices = rows.map((row, index) => /^@@ -/.test(row) ? index : -1).filter(i => i >= 0)
    for (const index of hunkIndices) {
      const heading = rows[index].match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/)
      if (!heading) { failed = true; continue }
      const start = Math.max(0, Number(heading[1]) - 1)
      next.push(...output.slice(cursor, start)); cursor = start
      for (const row of rows.slice(index + 1)) {
        if (/^@@ /.test(row) || /^diff --git /.test(row)) break
        if (row === '' || row === '\ No newline at end of file') continue
        if (row.startsWith(' ')) {
          const line = row.slice(1)
          if (output[cursor] !== line) failed = true
          next.push(line); cursor++
        } else if (row.startsWith('-') && !row.startsWith('---')) {
          if (output[cursor] !== row.slice(1)) failed = true
          cursor++
        } else if (row.startsWith('+') && !row.startsWith('+++')) next.push(row.slice(1))
      }
    }
    output = [...next, ...output.slice(cursor)]
  }
  return failed ? null : output.join('\n')
}
