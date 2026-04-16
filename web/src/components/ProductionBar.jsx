/**
 * ProductionBar — Recharts bar chart for production per hour.
 * Fills all hours of the selected shift so X-axis is always complete.
 */

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from 'recharts'
import { colors, typography } from '../styles/theme'

function timeToHour(hhmm) {
  return parseInt(hhmm.split(':')[0], 10)
}

function buildFullHourData(data, startTime, endTime) {
  const startH = timeToHour(startTime)
  let endH = timeToHour(endTime)
  if (endH <= startH) endH += 24

  // API returns hours in UTC; convert to BRT (UTC-3)
  const UTC_OFFSET = -3
  const dataMap = {}
  for (const d of data) {
    const utcH = parseInt(String(d.hour).split(':')[0], 10)
    const localH = ((utcH + UTC_OFFSET) % 24 + 24) % 24
    dataMap[localH] = (dataMap[localH] ?? 0) + (d.parts_ok ?? 0)
  }

  const result = []
  for (let h = startH; h <= endH; h++) {
    const realH = ((h % 24) + 24) % 24
    result.push({
      hour: `${String(realH).padStart(2, '0')}h`,
      parts_ok: dataMap[realH] ?? 0,
    })
  }
  return result
}

export default function ProductionBar({ data = [], targetPerHour = 0, startTime = '05:00', endTime = '22:00' }) {
  const fullData = buildFullHourData(data, startTime, endTime)

  return (
    <div>
      <p style={{ ...typography.titleSmall, color: colors.onSurface, marginBottom: 8 }}>
        Peças / Hora
      </p>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={fullData} margin={{ top: 5, right: 0, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.outlineVariant} />
          <XAxis
            dataKey="hour"
            tick={{ fontSize: 11, fill: colors.onSurfaceVariant }}
            tickLine={false}
            axisLine={{ stroke: colors.outline }}
            padding={{ left: 0, right: 0 }}
          />
          <YAxis
            tick={false}
            tickLine={false}
            axisLine={{ stroke: colors.outline }}
            width={1}
          />
          <Tooltip
            contentStyle={{
              background: '#FFFFFF',
              border: `1px solid ${colors.outlineVariant}`,
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value) => [value.toLocaleString('pt-BR'), 'Peças']}
          />
          <Bar dataKey="parts_ok" radius={[4, 4, 0, 0]} maxBarSize={36}>
            {fullData.map((entry, i) => (
              <Cell
                key={i}
                fill={
                  entry.parts_ok === 0
                    ? 'transparent'
                    : targetPerHour > 0 && entry.parts_ok >= targetPerHour
                    ? colors.success
                    : colors.warning
                }
              />
            ))}
          </Bar>
          {targetPerHour > 0 && (
            <ReferenceLine
              y={targetPerHour}
              stroke={colors.primary}
              strokeDasharray="5 5"
              label={{
                value: `Meta: ${targetPerHour}`,
                position: 'insideTopRight',
                fill: colors.primary,
                fontSize: 11,
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
