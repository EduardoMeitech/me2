/**
 * StatusTimeline — Barra horizontal com segmentos coloridos por estado (tipo Gantt).
 * Accepts startTime/endTime as "HH:MM" strings to match shift boundaries.
 */

import { colors, typography, getStatusColor, getStatusLabel } from '../styles/theme'

function timeToMin(hhmm) {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + (m || 0)
}

function formatHour(totalMin) {
  const h = Math.floor(totalMin / 60) % 24
  const m = totalMin % 60
  if (m === 0) return `${String(h).padStart(2, '0')}h`
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

export default function StatusTimeline({ events = [], startTime = '05:00', endTime = '22:00' }) {
  const startMin = timeToMin(startTime)
  let endMin = timeToMin(endTime)

  // Handle overnight (e.g. T300: 22:00-04:59)
  if (endMin <= startMin) endMin += 24 * 60

  const totalMinutes = endMin - startMin

  if (events.length === 0) {
    return (
      <div>
        <div style={{ height: 32, background: colors.surfaceVariant, borderRadius: 4 }} />
        <HourLabels startMin={startMin} endMin={endMin} />
      </div>
    )
  }

  return (
    <div>
      {/* Timeline bar */}
      <div
        style={{
          display: 'flex',
          height: 32,
          borderRadius: 4,
          overflow: 'hidden',
          background: colors.surfaceVariant,
        }}
      >
        {events.map((event, i) => {
          const durationMin = event.duration_min ?? 1
          const widthPct = Math.max((durationMin / totalMinutes) * 100, 0.3)

          return (
            <div
              key={i}
              title={`${getStatusLabel(event.word_status)} — ${durationMin.toFixed(0)} min`}
              style={{
                width: `${widthPct}%`,
                background: getStatusColor(event.word_status),
                minWidth: 2,
                transition: 'width 0.3s',
              }}
            />
          )
        })}
      </div>

      {/* Hour labels */}
      <HourLabels startMin={startMin} endMin={endMin} />
    </div>
  )
}

function HourLabels({ startMin, endMin }) {
  // Match Recharts categorical distribution:
  // N items spread evenly, each label at center of its slot = (i + 0.5) / N * 100%
  const firstHour = Math.floor(startMin / 60)
  const lastHour = Math.floor(endMin / 60)
  const hours = []
  for (let h = firstHour; h <= lastHour; h++) hours.push(h)
  const N = hours.length
  const labels = hours.map((h, i) => ({
    min: h * 60,
    pct: ((i + 0.5) / N) * 100,
  }))

  return (
    <div style={{ position: 'relative', height: 16, marginTop: 4 }}>
      {labels.map((l) => (
        <span
          key={l.min}
          style={{
            position: 'absolute',
            left: `${l.pct}%`,
            transform: 'translateX(-50%)',
            ...typography.labelSmall,
            color: colors.onSurfaceVariant,
            whiteSpace: 'nowrap',
          }}
        >
          {formatHour(l.min)}
        </span>
      ))}
    </div>
  )
}
