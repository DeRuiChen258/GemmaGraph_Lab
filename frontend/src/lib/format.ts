export function dateTime(value?: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  return Number.isNaN(+d) ? '—' : new Intl.DateTimeFormat('zh-CN', {
    month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(d)
}

export function elapsed(start?: string | null, end: string | Date = new Date()) {
  if (!start) return '—'
  const seconds = Math.max(0, Math.round((+new Date(end) - +new Date(start)) / 1000))
  if (!Number.isFinite(seconds)) return '—'
  return seconds >= 3600 ? `${Math.floor(seconds / 3600)}小时 ${Math.floor((seconds % 3600) / 60)}分`
    : seconds >= 60 ? `${Math.floor(seconds / 60)}分 ${seconds % 60}秒` : `${seconds}秒`
}

export function compact(value: number | null | undefined, locale = 'zh-CN') {
  if (value === null || value === undefined || !Number.isFinite(value)) return '未采集'
  return new Intl.NumberFormat(locale, { notation: value >= 10000 ? 'compact' : 'standard', maximumFractionDigits: 1 }).format(value)
}

export function percent(value: number | null | undefined) {
  return value === null || value === undefined || !Number.isFinite(value) ? '—' : `${(value * 100).toFixed(1)}%`
}

export function bytes(value?: number | null) {
  if (value === undefined || value === null) return '—'
  return value < 1024 ? `${value} B` : value < 1048576 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1048576).toFixed(1)} MB`
}

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '发生未知错误，请稍后重试。'
}
