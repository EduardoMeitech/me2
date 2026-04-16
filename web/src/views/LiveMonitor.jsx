/**
 * LiveMonitor — Grid de máquinas em tempo real.
 * Vista principal do dashboard ME2.
 */

import { useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { colors, typography } from '../styles/theme'
import { useEquipment, useActiveAlerts } from '../hooks/useME2Data'
import useWebSocket from '../hooks/useWebSocket'
import { useEquipmentStore } from '../lib/store'
import MachineCard from '../components/MachineCard'
import AlertBanner from '../components/AlertBanner'
import Card from '../components/Card'
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

  // Status summary: count machines per status
  const statusSummary = useMemo(() => {
    const counts = { running: 0, stopped: 0, noData: 0 }
    for (const eq of equipment) {
      const live = liveData[eq.id]
      if (!live || live.word_status == null) {
        counts.noData++
      } else if (live.word_status === 18 || live.word_status === 19) {
        counts.running++
      } else {
        counts.stopped++
      }
    }
    return counts
  }, [equipment, liveData])

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h1 style={{ ...typography.headlineMedium, color: colors.onSurface }}>
            Monitor ao Vivo
          </h1>
          <p style={{ ...typography.bodyMedium, color: colors.onSurfaceVariant }}>
            {equipment.length} equipamento{equipment.length !== 1 ? 's' : ''} cadastrado{equipment.length !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Connection indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: connected ? colors.success : colors.error,
          }} />
          <span style={{ ...typography.labelMedium, color: colors.onSurfaceVariant }}>
            {connected ? 'Conectado' : 'Desconectado'}
          </span>
        </div>
      </div>

      {/* Status summary pills */}
      {equipment.length > 0 && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
          <StatusPill
            label="Produzindo"
            count={statusSummary.running}
            color={colors.success}
          />
          <StatusPill
            label="Parado"
            count={statusSummary.stopped}
            color={colors.error}
          />
          <StatusPill
            label="Sem dados"
            count={statusSummary.noData}
            color={colors.outline}
          />
        </div>
      )}

      {/* Active alerts */}
      {alerts.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
          {alerts.map((alert) => (
            <AlertBanner key={alert.id} alert={alert} onAcknowledge={handleAcknowledge} />
          ))}
        </div>
      )}

      {/* Equipment grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: 16,
      }}>
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
        <Card>
          <div style={{ textAlign: 'center', padding: 48 }}>
            <p style={{ ...typography.titleMedium, color: colors.onSurfaceVariant, marginBottom: 8 }}>
              Nenhum equipamento cadastrado
            </p>
            <p style={{ ...typography.bodyMedium, color: colors.onSurfaceVariant }}>
              Configure os equipamentos em equipment.json e reinicie o coletor.
            </p>
          </div>
        </Card>
      )}
    </div>
  )
}


function StatusPill({ label, count, color }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '6px 16px', borderRadius: '9999px',
      background: `${color}14`,
    }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
      <span style={{ ...typography.labelMedium, color }}>
        {count} {label}
      </span>
    </div>
  )
}
