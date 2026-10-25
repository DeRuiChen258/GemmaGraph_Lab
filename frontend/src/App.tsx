import { Component, Suspense, lazy, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { Loading } from './components/ui'

const OverviewPage = lazy(() => import('./pages/OverviewPage'))
const RepositoriesPage = lazy(() => import('./pages/RepositoriesPage'))
const RepositoryPage = lazy(() => import('./pages/RepositoryPage'))
const NewRunPage = lazy(() => import('./pages/NewRunPage'))
const RunPage = lazy(() => import('./pages/RunPage'))
const ExperimentsPage = lazy(() => import('./pages/ExperimentsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

class ApplicationBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(error: Error) { console.error('GemmaGraph page error', error.name) }
  render() {
    if (this.state.error) return <div className="page-content"><section className="panel panel-body">
      <h1>页面遇到问题</h1><p className="page-description">刷新页面后重试。运行结果仍保存在本机。</p>
      <button className="button button-secondary button-md" onClick={() => location.reload()}>刷新页面</button>
    </section></div>
    return this.props.children
  }
}

export default function App() {
  return <ApplicationBoundary><Routes><Route element={<AppShell />}>
    <Route index element={<Navigate to="/overview" replace />} />
    <Route path="overview" element={<Suspense fallback={<Loading />}><OverviewPage /></Suspense>} />
    <Route path="repositories" element={<Suspense fallback={<Loading />}><RepositoriesPage /></Suspense>} />
    <Route path="repositories/:repositoryId" element={<Suspense fallback={<Loading />}><RepositoryPage /></Suspense>} />
    <Route path="runs/new" element={<Suspense fallback={<Loading />}><NewRunPage /></Suspense>} />
    <Route path="runs/:runId" element={<Suspense fallback={<Loading />}><RunPage /></Suspense>} />
    <Route path="experiments" element={<Suspense fallback={<Loading />}><ExperimentsPage /></Suspense>} />
    <Route path="settings" element={<Suspense fallback={<Loading />}><SettingsPage /></Suspense>} />
    <Route path="*" element={<Suspense fallback={<Loading />}><NotFoundPage /></Suspense>} />
  </Route></Routes></ApplicationBoundary>
}
