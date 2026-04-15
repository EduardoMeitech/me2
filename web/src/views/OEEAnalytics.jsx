/**
 * OEEAnalytics — OEE dashboard inspired by E2 layout.
 *
 * Layout (top to bottom):
 *   1. Filters (equipment, date, shift)
 *   2. OEE header card: Gauge + Cycle Time + Availability + Performance + Quality (horizontal)
 *   3. Middle row: Production bar chart (left) + Status Pareto (right)
 *   4. Status Timeline bar (full width)
 *   5. KPI cards row: Standard CycleTime | Lost Time | Production Target | Scrap
 */

import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { colors, typography, elevation, shape } from '../styles/theme'
import { useEquipment, useOEE, useProduction } from '../hooks/useME2Data'
import { useUIStore } from '../lib/store'
import Card from '../components/Card'
import OEEGauge from '../components/OEEGauge'
import ProductionBar from '../components/ProductionBar'
import StatusTimeline from '../components/StatusTimeline'
import StatusPareto from '../components/StatusPareto'
import ShiftSelector from '../components/ShiftSelector'

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Mock status data until the API endpoint is wired
function mockStatusData(oee) {
  if (!oee) return []
  const uptimeMin = (oee.planned_min ?? 0) - (oee.downtime_min ?? 0)
  const downtimeMin = oee.downtime_min ?? 0
  const items = []
  if (uptimeMin > 0) items.push({ word_status: 18, duration_min: uptimeMin })
  if (downtimeMin > 0) {
    // Distribute downtime across typical statuses
    items.push({ word_status: 20, duration_min: downtimeMin * 0.35 })
    items.push({ word_status: 24, duration_min: downtimeMin * 0.25 })
    items.push({ word_status: 32, duration_min: downtimeMin * 0.30 })
    items.push({ word_status: 16, duration_min: downtimeMin * 0.10 })
  }
  return items
}

export default function OEEAnalytics() {
  const [searchParams] = useSearchParams()
  const equipmentId = searchParams.get('equipment')
  const { equipment } = useEquipment()
  const [selectedEquipment, setSelectedEquipment] = useState(equipmentId || null)
  const [date, setDate] = useState(todayStr())
  const selectedShift = useUIStore((s) => s.selectedShift)
  const setShift = useUIStore((s) => s.setShift)

  const { oee } = useOEE(selectedEquipment, date, selectedShift)
  const { production } = useProduction(selectedEquipment, date, selectedShift)

  const currentEquipment = equipment.find((e) => e.id === selectedEquipment)

  // Aggregate OEE from hourly snapshots (oee is an array)
  const agg = Array.isArray(oee) && oee.length > 0
    ? {
        availability_pct: oee.reduce((s, h) => s + h.availability_pct, 0) / oee.length,
        performance_pct: oee.reduce((s, h) => s + h.performance_pct, 0) / oee.length,
        quality_pct: oee.reduce((s, h) => s + h.quality_pct, 0) / oee.length,
        parts_good: oee.reduce((s, h) => s + h.parts_good, 0),
        downtime_min: oee.reduce((s, h) => s + h.downtime_min, 0),
        planned_min: oee.reduce((s, h) => s + h.planned_min, 0),
      }
    : oee

  const availability = agg?.availability_pct ?? 0
  const performance = agg?.performance_pct ?? 0
  const quality = agg?.quality_pct ?? 1
  const cycleTimeAvg = currentEquipment?.standard_cycle_time_s ?? 0

  const targetPerHour = cycleTimeAvg > 0 ? Math.floor(3600 / cycleTimeAvg) : 0
  const lostTimeMin = agg?.downtime_min ?? 0
  const statusData = mockStatusData(agg)

  const selectStyle = {
    padding: '8px 16px', borderRadius: shape.small,
    border: `1px solid ${colors.outlineVariant}`,
    background: '#FFFFFF', ...typography.bodyMedium,
  }

  return (
    <div>
      {/* Header + Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 20, alignItems: 'center' }}>
        <h1 style={{ ...typography.headlineMedium, color: colors.onSurface, marginRight: 'auto' }}>
          OEE Analytics
        </h1>
        <select
          value={selectedEquipment || ''}
          onChange={(e) => setSelectedEquipment(e.target.value || null)}
          style={selectStyle}
        >
          <option value="">Selecione um equipamento</option>
          {equipment.map((eq) => (
            <option key={eq.id} value={eq.id}>{eq.name} ({eq.serial_number})</option>
          ))}
        </select>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={selectStyle} />
        <ShiftSelector selected={selectedShift} onChange={setShift} />
      </div>

      {!selectedEquipment ? (
        <div style={{ textAlign: 'center', padding: 64 }}>
          <p style={{ ...typography.bodyLarge, color: colors.onSurfaceVariant }}>
            Selecione um equipamento para ver os dados de OEE.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* ── Row 1: Two cards with aligned title (30px) + KPI rows ── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 16 }}>

            {/* Card left: Equipment + KPIs */}
            <Card style={{ padding: '10px 20px', display: 'grid', gridTemplateRows: '30px 1fr', minHeight: 126 }}>
              <div>
                <p style={{ fontSize: 18, fontWeight: 600, color: colors.onSurface, lineHeight: 1.2 }}>
                  {currentEquipment?.name ?? 'Equipamento'}
                </p>
                <p style={{ fontSize: 11, color: colors.onSurfaceVariant }}>
                  {currentEquipment?.serial_number}
                </p>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-evenly', alignItems: 'center', flexWrap: 'wrap', gap: '8px 4px' }}>
                <MetricPill label="Cycle Time Avg(s)" value={cycleTimeAvg.toFixed(2)} />
                <MetricPill label="Standard CycleTime(s)" value={cycleTimeAvg.toFixed(1)} />
                <MetricPill label="Lost Time (min)" value={lostTimeMin.toFixed(2)} color={lostTimeMin > 0 ? colors.error : undefined} />
                <MetricPill label="Production Target" value={targetPerHour > 0 ? `${targetPerHour}/h` : '—'} />
              </div>
            </Card>

            {/* Card right: OEE Deployment + A/P/Q + Gauge */}
            <Card style={{ padding: '10px 10px 10px 20px', display: 'grid', gridTemplateRows: '30px 1fr', gridTemplateColumns: '1fr auto', minHeight: 126 }}>
              <p style={{ fontSize: 18, fontWeight: 600, color: colors.onSurface, lineHeight: 1.2 }}>
                OEE Deployment
              </p>
              <div style={{ gridColumn: '2', gridRow: '1 / 3', display: 'flex', alignItems: 'center', position: 'relative' }}>
                <span style={{ position: 'absolute', top: 0, right: 0, fontSize: 10, fontWeight: 500, color: colors.onSurfaceVariant }}>OEE</span>
                <OEEGauge
                  availability={availability}
                  performance={performance}
                  quality={quality}
                  size={100}
                  compact
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-evenly', alignItems: 'center', flexWrap: 'wrap', gap: '8px 4px' }}>
                <MetricPill label="Availability" value={`${(availability * 100).toFixed(2)}%`} color={colors.success} />
                <MetricPill label="Performance" value={`${(performance * 100).toFixed(2)}%`} color={colors.primary} />
                <MetricPill label="Quality" value={`${(quality * 100).toFixed(2)}%`} color={colors.outline} />
              </div>
            </Card>

          </div>

          {/* ── Row 2: Production chart (left) + Status Pareto (right) ── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr minmax(240px, 280px)', gap: 16 }}>
            <Card>
              <ProductionBar data={production} targetPerHour={targetPerHour} />
            </Card>
            <Card>
              <StatusPareto statusData={statusData} />
            </Card>
          </div>

          {/* ── Row 3: Status Timeline ── */}
          <Card>
            <p style={{ ...typography.titleSmall, color: colors.onSurface, marginBottom: 8 }}>
              Status Changes
            </p>
            <StatusTimeline events={[]} />
          </Card>


        </div>
      )}
    </div>
  )
}

// ── Metric pill (header row) ───────────────────────────────────────────────
function MetricPill({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center', minWidth: 0 }}>
      <p style={{ fontSize: 11, fontWeight: 500, color: colors.onSurfaceVariant, marginBottom: 4, letterSpacing: '0.3px', whiteSpace: 'nowrap' }}>
        {label}
      </p>
      <p style={{ fontSize: 'clamp(18px, 2vw, 26px)', fontWeight: 700, color: color ?? colors.onSurface, lineHeight: 1, whiteSpace: 'nowrap' }}>
        {value}
      </p>
    </div>
  )
}

