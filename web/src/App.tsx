import { Routes, Route, Navigate } from 'react-router-dom'
import { isLoggedIn } from '@/lib/api'
import { AuthPage } from '@/pages/AuthPage'
import { DashboardLayout } from '@/layouts/DashboardLayout'
import { OverviewPage } from '@/pages/OverviewPage'
import { AuthConfigsPage } from '@/pages/AuthConfigsPage'
import { ConnectionsPage } from '@/pages/ConnectionsPage'
import { EntitiesPage } from '@/pages/EntitiesPage'
import { ActionsPage } from '@/pages/ActionsPage'
import { TriggersPage } from '@/pages/TriggersPage'
import { LogsPage } from '@/pages/LogsPage'
import { KeysPage } from '@/pages/KeysPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { QuickstartPage } from '@/pages/QuickstartPage'
import { WebhookLogsPage } from '@/pages/WebhookLogsPage'
import { ApiDocsPage } from '@/pages/ApiDocsPage'

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
        <Route path="auth-configs" element={<AuthConfigsPage />} />
        <Route path="connections" element={<ConnectionsPage />} />
        <Route path="entities" element={<EntitiesPage />} />
        <Route path="actions" element={<ActionsPage />} />
        <Route path="triggers" element={<TriggersPage />} />
        <Route path="logs" element={<LogsPage />} />
        <Route path="keys" element={<KeysPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="quickstart" element={<QuickstartPage />} />
        <Route path="webhook-logs" element={<WebhookLogsPage />} />
        <Route path="api-docs" element={<ApiDocsPage />} />
      </Route>
    </Routes>
  )
}
