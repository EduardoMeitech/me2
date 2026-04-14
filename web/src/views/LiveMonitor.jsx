/**
 * LiveMonitor — Grid de máquinas em tempo real.
 * Vista principal do dashboard ME2.
 */

import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { colors, typography } from '../styles/theme'
import { useEquipment, useActiveAlerts } from '../hooks/useME2Data'
import useWebSocket from '../hooks/useWebSocket'
import { useEquipmentStore } from '../lib/store'
import MachineCard from '../components/MachineCard'
import AlertBanner from '../components/AlertBanner'
import api from '../lib/api'

export default function LiveMonitor() {
  const navigate = useNavigate()
  const { equipment, loading } = useEquipment()
  const { alerts } = useActiveAlerts()
  const liveData = useEquipmentStore((s) => s.liveData)
  const updateLiveData = useEquipmentStore((s) => s.updateLiveData)

  // WebSocket — recebe atualizações em tempo real
  const onMessage = useCallback(
    (data) => {
      if (data.equipment_id) {
        updateLiveData(data.equipment_id, data)
      }
    },
    [updateLiveData]
  )

  const { connected } = useWebSocket(onMessage)

  const handleAcknowledge = async (alertId) => {
    try {
      await api.post(`/api/v1/alerts/${alertId}/acknowledge`)
    } catch (err) {
      console.error('Erro ao reconhecer alerta:', err)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '64px' }}>
        <p style={{ ...typography.bodyLarge, color: colors.onSurfaceVariant }}>
          Carregando equipamentos...
        </p>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ ...typography.headlineMedium, color: colors.onSurface }}>
            Monitor ao Vivo
          </h1>
          <p style={{ ...typography.bodyMedium, color: colors.onSurfaceVariant }}>
            {equipment.length} equipamento{equipment.length !== 1 ? 's' : ''} conectado{equipment.length !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Connection indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: connected ? colors.success : colors.error,
            }}
          />
          <span style={{ ...typography.labelMedium, color: colors.onSurfaceVariant }}>
            {connected ? 'Conectado' : 'Desconectado'}
          </span>
        </div>
      </div>

      {/* Active alerts */}
      {alerts.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '24px' }}>
          {alerts.map((alert) => (
            <AlertBanner key={alert.id} alert={alert} onAcknowledge={handleAcknowledge} />
          ))}
        </div>
      )}

      {/* Equipment grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: '16px',
        }}
      >
        {equipment.map((eq) => (
          <MachineCard
            key={eq.id}
            equipment={eq}
            liveData={liveData[eq.id]}
            onClick={() => navigate(`/oee?equipment=${eq.id}`)}
          />
        ))}
      </div>

      {equipment.length === 0 && (
        <div style={{ textAlign: 'center', padding: '64px' }}>
          <p style={{ ...typography.bodyLarge, color: colors.onSurfaceVariant }}>
            Nenhum equipamento cadastrado. Configure em equipment.json.
          </p>
        </div>
      )}
    </div>
  )
}
