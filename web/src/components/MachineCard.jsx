/**
 * MachineCard — Card de máquina com status colorido, OEE badge e sparkline.
 */

import Card from './Card'
import { colors, typography, getStatusColor, getStatusLabel } from '../styles/theme'

export default function MachineCard({ equipment, liveData, onClick }) {
  const status = liveData?.word_status ?? 0
  const statusColor = getStatusColor(status)
  const statusLabel = getStatusLabel(status)
  const partsOk = liveData?.parts_ok ?? 0
  const cycleTime = liveData?.cycle_time_s ?? 0
  const oee = liveData?.oee_pct

  return (
    <Card
      variant="elevated"
      onClick={onClick}
      style={{ position: 'relative', overflow: 'hidden', minWidth: '280px' }}
    >
      {/* Status indicator bar */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '4px',
          background: statusColor,
        }}
      />

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginTop: '4px' }}>
        <div>
          <p style={{ ...typography.titleMedium, color: colors.onSurface }}>
            {equipment?.name ?? 'Equipamento'}
          </p>
          <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>
            {equipment?.serial_number ?? '—'}
          </p>
        </div>

        {/* OEE Badge */}
        {oee != null && (
          <div
            style={{
              background: oee >= 85 ? colors.success : oee >= 60 ? colors.warning : colors.error,
              color: '#FFFFFF',
              padding: '4px 10px',
              borderRadius: '12px',
              ...typography.labelMedium,
            }}
          >
            {(oee * 100).toFixed(1)}%
          </div>
        )}
      </div>

      {/* Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px' }}>
        <div
          className={status === 18 ? 'status-pulse' : undefined}
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            background: statusColor,
          }}
        />
        <span style={{ ...typography.labelMedium, color: statusColor }}>
          {statusLabel}
        </span>
      </div>

      {/* Metrics */}
      <div style={{ display: 'flex', gap: '24px', marginTop: '12px' }}>
        <div>
          <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>Peças</p>
          <p style={{ ...typography.titleLarge, color: colors.onSurface }}>{partsOk}</p>
        </div>
        <div>
          <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>Ciclo</p>
          <p style={{ ...typography.titleLarge, color: colors.onSurface }}>
            {cycleTime > 0 ? `${cycleTime.toFixed(1)}s` : '—'}
          </p>
        </div>
      </div>
    </Card>
  )
}
