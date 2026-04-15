/**
 * OEEGauge — Gauge circular MD3 com 3 arcos (Disponibilidade, Performance, Qualidade).
 * Supports configurable size and a compact mode (no legend).
 */

import { colors, typography } from '../styles/theme'

function Arc({ value, color, radius, stroke, cx, cy }) {
  const circ = 2 * Math.PI * radius
  const dashArray = `${circ * value} ${circ * (1 - value)}`

  return (
    <circle
      cx={cx}
      cy={cy}
      r={radius}
      fill="none"
      stroke={color}
      strokeWidth={stroke}
      strokeDasharray={dashArray}
      strokeLinecap="round"
      transform={`rotate(-90 ${cx} ${cy})`}
      style={{ transition: 'stroke-dasharray 0.8s ease' }}
    />
  )
}

export default function OEEGauge({
  availability = 0,
  performance = 0,
  quality = 0,
  size = 200,
  compact = false,
}) {
  const oee = availability * performance * quality
  const stroke = Math.round(size * 0.05)
  const gap = Math.round(stroke * 0.25)
  const cx = size / 2
  const cy = size / 2
  const outerR = (size - stroke) / 2

  const arcs = [
    { value: availability, color: colors.success, label: 'Disponibilidade', radius: outerR },
    { value: performance, color: colors.primary, label: 'Performance', radius: outerR - stroke - gap },
    { value: quality, color: colors.outline, label: 'Qualidade', radius: outerR - (stroke + gap) * 2 },
  ]

  const oeeColor = oee >= 0.85 ? colors.success : oee >= 0.60 ? '#F9A825' : colors.error

  // Font sizes proportional to gauge size
  const valueFontSize = Math.round(size * 0.22)
  const labelFontSize = Math.round(size * 0.065)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
        {/* Background arcs */}
        {arcs.map((arc, i) => (
          <circle
            key={`bg-${i}`}
            cx={cx} cy={cy} r={arc.radius}
            fill="none" stroke={colors.surfaceVariant} strokeWidth={stroke}
          />
        ))}

        {/* Value arcs */}
        {arcs.map((arc, i) => (
          <Arc key={i} value={arc.value} color={arc.color} radius={arc.radius} stroke={stroke} cx={cx} cy={cy} />
        ))}

        {/* Center value only — vertically centered */}
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central"
          style={{ fontSize: valueFontSize, fontWeight: 700, fill: oeeColor }}
        >
          {(oee * 100).toFixed(1)}%
        </text>
      </svg>

      {/* Legend (hidden in compact mode) */}
      {!compact && (
        <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
          {arcs.map((arc, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: arc.color }} />
              <span style={{ ...typography.labelSmall, color: colors.onSurfaceVariant }}>
                {arc.label}: {(arc.value * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
