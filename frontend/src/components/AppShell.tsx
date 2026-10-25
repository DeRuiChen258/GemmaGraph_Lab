import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Activity, Blocks, BookOpenText, Boxes, CircleHelp, FlaskConical, LayoutDashboard, Settings2, Workflow } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import { keys } from '@/api/query'
import { Badge, Button } from './ui'

const nav = [
  { to: '/overview', label: '概览', icon: LayoutDashboard },
  { to: '/repositories', label: '仓库', icon: Blocks },
  { to: '/runs/new', label: '新建修复', icon: Workflow },
  { to: '/experiments', label: '实验', icon: FlaskConical },
  { to: '/settings', label: '设置', icon: Settings2 },
]

function SystemStatus() {
  const { data: settings } = useQuery({ queryKey: keys.settings, queryFn: api.settings, refetchInterval: 8000 })
  const modelReady = settings?.model.configured === true
  const sandboxReady = settings?.sandbox.available === true
  return <div className="status-strip">
    <div className="status-strip-title"><span className="status-indicator" /><span>本地运行环境</span></div>
    <div className="status-pills">
      <Badge tone={modelReady ? 'success' : 'warning'} dot>Gemma {modelReady ? '已配置' : '待配置'}</Badge>
      <Badge tone={sandboxReady ? 'success' : 'warning'} dot>Docker {sandboxReady ? '就绪' : '不可用'}</Badge>
    </div>
    {settings && (!modelReady || !sandboxReady) && <div className="status-help">任务启动前需要本地模型与测试容器都就绪。</div>}
  </div>
}

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const pageName = nav.find(item => location.pathname.startsWith(item.to))?.label || '工作台'
  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
      <NavLink className="brand" to="/overview" onClick={() => setMenuOpen(false)}>
        <img width="38" height="38" src="/mark.svg" alt="" />
        <span className="brand-copy"><strong>GemmaGraph</strong><span>RESEARCH LAB</span></span>
      </NavLink>
      <div className="nav-caption">工作区</div>
      <nav className="main-nav" aria-label="主导航">
        {nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to}
          className={({ isActive }) => `nav-item ${isActive ? 'nav-active' : ''}`}
          onClick={() => setMenuOpen(false)}>
          <Icon size={18} strokeWidth={1.8} /><span>{label}</span>
        </NavLink>)}
      </nav>
      <div className="sidebar-bottom"><SystemStatus />
        <a className="docs-link" href="https://docs.langchain.com/oss/python/langgraph/overview" target="_blank" rel="noreferrer">
          <BookOpenText size={15} /><span>LangGraph 文档</span><CircleHelp className="docs-question" size={15} />
        </a>
        <div className="local-label"><span className="local-dot" />所有数据保存在本机</div>
      </div>
    </aside>
    {menuOpen && <button className="mobile-scrim" aria-label="关闭导航" onClick={() => setMenuOpen(false)} />}
    <main className="main-area">
      <header className="topbar">
        <div className="topbar-left"><Button variant="ghost" size="sm" className="mobile-menu"
          aria-label="打开导航" onClick={() => setMenuOpen(true)}><Boxes size={19} /></Button>
          <span className="breadcrumb-muted">工作区</span><span className="breadcrumb-divider">/</span>
          <span className="breadcrumb-current">{pageName}</span></div>
        <div className="topbar-right"><span className="run-mode"><Activity size={14} />研究模式</span>
          <span className="topbar-version">v0.1</span></div>
      </header>
      <div className="page-content"><Outlet /></div>
    </main>
  </div>
}
