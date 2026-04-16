/**
 * MachineCard — Card de máquina com status colorido, métricas e última atualização.
 */

import { useState, useEffect } from 'react'
import Card from './Card'
import { colors, typography, shape, getStatusColor, getStatusLabel } from '../styles/theme'

export default function MachineCard({ equipment, liveData, onClick }) {
  const hasData = liveData && (liveData.word_status != null || liveData.parts_ok != null)
  const status = liveData?.word_status ?? null
  const statusColor = status != null ? getStatusColor(status) : colors.outline
  const statusLabel = status != null ? getStatusLabel(status) : 'Sem dados'
  const isRunning = status === 18
  const partsOk = liveData?.parts_ok ?? 0
  const cycleTime = liveData?.cycle_time_s ?? 0
  const lastTs = liveData?.ts ?? null

  // Tick every 30s to update "time ago"
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(interval)
  }, [])

  const timeAgo = lastTs ? formatTimeAgo(now - new Date(lastTs).getTime()) : null

  return (
    <Card
      variant="elevated"
      onClick={onClick}
      style={{
        position: 'relative',
        overflow: 'hidden',
        minWidth: '280px',
        cursor: 'pointer',
      }}
    >
      {/* Status indicator bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: '4px',
        background: statusColor,
      }} />

      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginTop: 4 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ ...typography.titleMedium, color: colors.onSurface, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {equipment?.name ?? 'Equipamento'}
          </p>
          <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>
            {equipment?.serial_number ?? '\u2014'}
          </p>
        </div>

        {/* Status badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '4px 12px', borderRadius: shape.full,
          background: `${statusColor}14`,
        }}>
          <div
            className={isRunning ? 'status-pulse' : undefined}
            style={{
              width: 8, height: 8, borderRadius: '50%',
              background: statusColor,
            }}
          />
          <span style={{ ...typography.labelSmall, color: statusColor, whiteSpace: 'nowrap' }}>
            {statusLabel}
          </span>
        </div>
      </div>

      {/* Metrics */}
      {hasData ? (
        <div style={{ display: 'flex', gap: 24, marginTop: 16 }}>
          <Metric label="Pe\u00e7as" value={partsOk} />
          <Metric label="Ciclo" value={cycleTime > 0 ? `${cycleTime.toFixed(1)}s` : '\u2014'} />
          {equipment?.standard_cycle_time_s > 0 && (
            <Metric label="Meta/h" value={Math.floor(3600 / equipment.standard_cycle_time_s)} />
          )}
        </div>
      ) : (
        <div style={{ marginTop: 16, padding: '12px 0' }}>
          <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>
            Aguardando dados do coletor...
          </p>
        </div>
      )}

      {/* Last update footer */}
      <div style={{
        marginTop: 12, paddingTop: 8,
        borderTop: `1px solid ${colors.outlineVariant}`,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>
          {timeAgo ? `Atualizado ${timeAgo}` : 'Sem comunica\u00e7\u00e3o'}
        </span>
        {equipment?.model && (
          <span style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>
            {equipment.model}
          </span>
        )}
      </div>
    </Card>
  )
}


function Metric({ label, value }) {
  return (
    <div>
      <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>{label}</p>
      <p style={{ ...typography.titleLarge, color: colors.onSurface }}>{value}</p>
    </div>
  )
}


function formatTimeAgo(ms) {
  if (ms < 0) return 'agora'
  const sec = Math.floor(ms / 1000)
  if (sec < 60) return 'agora'
  const min = Math.floor(sec / 60)
  if (min < 60) return `h\u00e1 ${min} min`
  const hours = Math.floor(min / 60)
  if (hours < 24) return `h\u00e1 ${hours}h`
  return `h\u00e1 ${Math.floor(hours / 24)}d`
}
