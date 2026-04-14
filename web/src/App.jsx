/**
 * ME2 App — Auth + routing + layout.
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './lib/store'
import Layout from './components/Layout'
import Login from './views/Login'
import LiveMonitor from './views/LiveMonitor'
import OEEAnalytics from './views/OEEAnalytics'
import Alerts from './views/Alerts'
import Reports from './views/Reports'

function ProtectedRoute({ children }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <Layout>{children}</Layout>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route
          path="/"
          element={
            <ProtectedRoute>
              <LiveMonitor />
            </ProtectedRoute>
          }
        />
        <Route
          path="/oee"
          element={
            <ProtectedRoute>
              <OEEAnalytics />
            </ProtectedRoute>
          }
        />
        <Route
          path="/alerts"
          element={
            <ProtectedRoute>
              <Alerts />
            </ProtectedRoute>
          }
        />
        <Route
          path="/reports"
          element={
            <ProtectedRoute>
              <Reports />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
