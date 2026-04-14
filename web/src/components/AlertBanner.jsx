/**
 * AlertBanner — Banner persistente para máquina parada > threshold.
 */

import { colors, typography, shape } from '../styles/theme'
import Button from './Button'

export default function AlertBanner({ alert, onAcknowledge }) {
  if (!alert) return null

  const isL2 = alert.level >= 2
  const bgColor = isL2 ? colors.errorDark : colors.error

  const minutesAgo = alert.started_at
    ? Math.round((Date.now() - new Date(alert.started_at).getTime()) / 60000)
    : 0

  return (
    <div
      style={{
        background: bgColor,
        color: colors.onError,
        padding: '12px 20px',
        borderRadius: shape.medium,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '20px' }}>&#9888;</span>
        <div>
          <p style={{ ...typography.titleSmall, color: colors.onError }}>
            {alert.message ?? `Equipamento parado há ${minutesAgo} min`}
          </p>
          <p style={{ ...typography.bodySmall, color: 'rgba(255,255,255,0.8)' }}>
            Nível {alert.level} — Iniciado às{' '}
            {alert.started_at ? new Date(alert.started_at).toLocaleTimeString('pt-BR') : '—'}
          </p>
        </div>
      </div>

      {!alert.acknowledged_at && (
        <Button
          variant="outlined"
          style={{ color: colors.onError, borderColor: 'rgba(255,255,255,0.5)' }}
          onClick={() => onAcknowledge?.(alert.id)}
        >
          Reconhecer
        </Button>
      )}
    </div>
  )
}
