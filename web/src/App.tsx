import { Routes, Route, Navigate } from 'react-router-dom'
import { isLoggedIn } from '@/lib/api'
import { AuthPage } from '@/pages/AuthPage'
import { DashboardLayout } from '@/layouts/DashboardLayout'
import { OverviewPage } from '@/pages/OverviewPage'
import { ConnectionsPage } from '@/pages/ConnectionsPage'
import { ActionsPage } from '@/pages/ActionsPage'
import { TriggersPage } from '@/pages/TriggersPage'
import { LogsPage } from '@/pages/LogsPage'
import { KeysPage } from '@/pages/KeysPage'
import { QuickstartPage } from '@/pages/QuickstartPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!isLoggedIn()) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AuthPage />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="connections" element={<ConnectionsPage />} />
        <Route path="actions" element={<ActionsPage />} />
        <Route path="triggers" element={<TriggersPage />} />
        <Route path="logs" element={<LogsPage />} />
        <Route path="keys" element={<KeysPage />} />
        <Route path="quickstart" element={<QuickstartPage />} />
      </Route>
    </Routes>
  )
}
