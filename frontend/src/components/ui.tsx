import { forwardRef, type ButtonHTMLAttributes, type PropsWithChildren } from 'react'
import { X } from 'lucide-react'

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md'
}>(({ variant = 'secondary', size = 'md', className = '', ...props }, ref) =>
  <button ref={ref} className={`button button-${variant} button-${size} ${className}`} {...props} />)
Button.displayName = 'Button'

export function Badge({ children, tone = 'neutral', dot = false }: PropsWithChildren<{
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info'; dot?: boolean
}>) {
  return <span className={`badge badge-${tone}`}>{dot && <i aria-hidden="true" />}{children}</span>
}

export function Panel({ children, className = '', ...props }: PropsWithChildren<{
  className?: string; [key: string]: unknown
}>) {
  return <section className={`panel ${className}`} {...props}>{children}</section>
}

export function PageHeading({ eyebrow, title, description, actions }: {
  eyebrow?: string; title: string; description?: string; actions?: React.ReactNode
}) {
  return <div className="page-heading">
    <div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>
      {description && <p className="page-description">{description}</p>}</div>
    {actions && <div className="heading-actions">{actions}</div>}
  </div>
}

export function EmptyState({ icon: Icon, title, description, action }: {
  icon: React.ComponentType<{ size?: number }>; title: string; description: string; action?: React.ReactNode
}) {
  return <div className="empty-state"><div className="empty-icon"><Icon size={22} /></div>
    <strong>{title}</strong><p>{description}</p>{action}</div>
}

export function InlineNotice({ kind = 'info', title, children }: PropsWithChildren<{
  kind?: 'info' | 'warning' | 'danger' | 'success'; title?: string
}>) {
  return <div className={`notice notice-${kind}`} role={kind === 'danger' ? 'alert' : 'status'}>
    {title && <strong>{title}</strong>}<div>{children}</div></div>
}

export function Loading({ label = '正在加载' }: { label?: string }) {
  return <div className="loading-state"><span className="spinner" aria-hidden="true" /><span>{label}</span></div>
}

export function Modal({ open, onClose, title, children, className = '' }: {
  open: boolean; onClose: () => void; title: string; children: React.ReactNode; className?: string
}) {
  return <dialog open={open} className={`modal ${className}`} aria-label={title} onClick={e => {
    if (e.target === e.currentTarget) onClose()
  }} onKeyDown={e => { if (e.key === 'Escape') onClose() }}>
    <div className="modal-panel"><div className="modal-heading"><div><div className="eyebrow">GemmaGraph Lab</div><h2>{title}</h2></div>
      <Button variant="ghost" size="sm" aria-label="关闭" onClick={onClose}><X size={17} /></Button></div>
      {children}</div>
  </dialog>
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden="true" className={`skeleton ${className}`} />
}
