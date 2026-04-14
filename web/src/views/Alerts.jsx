/**
 * Alerts — Alertas ativos e histórico.
 */

import { colors, typography } from '../styles/theme'
import { useActiveAlerts } from '../hooks/useME2Data'
import Card from '../components/Card'
import AlertBanner from '../components/AlertBanner'
import api from '../lib/api'

export default function Alerts() {
  const { alerts, loading, refetch } = useActiveAlerts()

  const handleAcknowledge = async (alertId) => {
    try {
      await api.post(`/api/v1/alerts/${alertId}/acknowledge`)
      refetch()
    } catch (err) {
      console.error('Erro ao reconhecer alerta:', err)
    }
  }

  return (
    <div>
      <h1 style={{ ...typography.headlineMedium, color: colors.onSurface, marginBottom: '24px' }}>
        Alertas
      </h1>

      {loading ? (
        <p style={{ ...typography.bodyLarge, color: colors.onSurfaceVariant }}>
          Carregando alertas...
        </p>
      ) : alerts.length === 0 ? (
        <Card>
          <div style={{ textAlign: 'center', padding: '32px' }}>
            <p style={{ fontSize: '48px', marginBottom: '8px' }}>&#10003;</p>
            <p style={{ ...typography.titleMedium, color: colors.success }}>
              Nenhum alerta ativo
            </p>
            <p style={{ ...typography.bodyMedium, color: colors.onSurfaceVariant }}>
              Todos os equipamentos operando normalmente.
            </p>
          </div>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {alerts.map((alert) => (
            <AlertBanner key={alert.id} alert={alert} onAcknowledge={handleAcknowledge} />
          ))}
        </div>
      )}
    </div>
  )
}
