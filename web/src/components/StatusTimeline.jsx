/**
 * StatusTimeline — Barra horizontal com segmentos coloridos por estado (tipo Gantt).
 */

import { colors, typography, getStatusColor, getStatusLabel } from '../styles/theme'

export default function StatusTimeline({ events = [], startHour = 5, endHour = 22 }) {
  const totalMinutes = (endHour - startHour) * 60

  if (events.length === 0) {
    return (
      <div style={{ height: '32px', background: colors.surfaceVariant, borderRadius: '4px' }} />
    )
  }

  return (
    <div>
      {/* Timeline bar */}
      <div
        style={{
          display: 'flex',
          height: '32px',
          borderRadius: '4px',
          overflow: 'hidden',
          background: colors.surfaceVariant,
        }}
      >
        {events.map((event, i) => {
          const durationMin = event.duration_min ?? 5
          const widthPct = Math.max((durationMin / totalMinutes) * 100, 0.5)

          return (
            <div
              key={i}
              title={`${getStatusLabel(event.word_status)} — ${durationMin.toFixed(0)} min`}
              style={{
                width: `${widthPct}%`,
                background: getStatusColor(event.word_status),
                minWidth: '2px',
                transition: 'width 0.3s',
              }}
            />
          )
        })}
      </div>

      {/* Hour labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
        {Array.from({ length: endHour - startHour + 1 }, (_, i) => {
          const h = startHour + i
          return (
            <span key={h} style={{ ...typography.labelSmall, color: colors.onSurfaceVariant }}>
              {h < 10 ? `0${h}` : h}
            </span>
          )
        })}
      </div>
    </div>
  )
}
