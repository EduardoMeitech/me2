/**
 * OEEAnalytics — OEE histórico com filtros (turno, data, equipamento).
 */

import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { colors, typography } from '../styles/theme'
import { useEquipment, useOEE, useProduction } from '../hooks/useME2Data'
import { useUIStore } from '../lib/store'
import Card from '../components/Card'
import OEEGauge from '../components/OEEGauge'
import ProductionBar from '../components/ProductionBar'
import StatusTimeline from '../components/StatusTimeline'
import ShiftSelector from '../components/ShiftSelector'

function todayStr() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export default function OEEAnalytics() {
  const [searchParams] = useSearchParams()
  const equipmentId = searchParams.get('equipment')
  const { equipment } = useEquipment()
  const [selectedEquipment, setSelectedEquipment] = useState(equipmentId || null)
  const [date, setDate] = useState(todayStr())
  const selectedShift = useUIStore((s) => s.selectedShift)
  const setShift = useUIStore((s) => s.setShift)

  const { oee, loading: oeeLoading } = useOEE(selectedEquipment, date, selectedShift)
  const { production, loading: prodLoading } = useProduction(selectedEquipment, date, selectedShift)

  const currentEquipment = equipment.find((e) => e.id === selectedEquipment)

  return (
    <div>
      {/* Header */}
      <h1 style={{ ...typography.headlineMedium, color: colors.onSurface, marginBottom: '24px' }}>
        OEE Analytics
      </h1>

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', marginBottom: '24px', alignItems: 'center' }}>
        {/* Equipment selector */}
        <select
          value={selectedEquipment || ''}
          onChange={(e) => setSelectedEquipment(e.target.value || null)}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: `1px solid ${colors.outlineVariant}`,
            background: '#FFFFFF',
            ...typography.bodyMedium,
          }}
        >
          <option value="">Selecione um equipamento</option>
          {equipment.map((eq) => (
            <option key={eq.id} value={eq.id}>
              {eq.name} ({eq.serial_number})
            </option>
          ))}
        </select>

        {/* Date picker */}
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={{
            padding: '8px 16px',
            borderRadius: '8px',
            border: `1px solid ${colors.outlineVariant}`,
            background: '#FFFFFF',
            ...typography.bodyMedium,
          }}
        />

        {/* Shift selector */}
        <ShiftSelector selected={selectedShift} onChange={setShift} />
      </div>

      {!selectedEquipment ? (
        <div style={{ textAlign: 'center', padding: '64px' }}>
          <p style={{ ...typography.bodyLarge, color: colors.onSurfaceVariant }}>
            Selecione um equipamento para ver os dados de OEE.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px' }}>
          {/* OEE Gauge */}
          <Card>
            <p style={{ ...typography.titleMedium, color: colors.onSurface, marginBottom: '16px' }}>
              {currentEquipment?.name ?? 'Equipamento'}
            </p>
            <OEEGauge
              availability={oee?.availability_pct ?? 0}
              performance={oee?.performance_pct ?? 0}
              quality={oee?.quality_pct ?? 1}
            />
            <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: '16px' }}>
              <div style={{ textAlign: 'center' }}>
                <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>Peças OK</p>
                <p style={{ ...typography.titleLarge }}>{oee?.parts_good ?? 0}</p>
              </div>
              <div style={{ textAlign: 'center' }}>
                <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>Downtime</p>
                <p style={{ ...typography.titleLarge }}>{(oee?.downtime_min ?? 0).toFixed(0)} min</p>
              </div>
            </div>
          </Card>

          {/* Production + Timeline */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Card>
              <ProductionBar
                data={production}
                targetPerHour={currentEquipment?.standard_cycle_time_s ? Math.floor(3600 / currentEquipment.standard_cycle_time_s) : 0}
              />
            </Card>

            <Card>
              <p style={{ ...typography.titleSmall, color: colors.onSurface, marginBottom: '8px' }}>
                Status ao Longo do Dia
              </p>
              <StatusTimeline events={[]} />
            </Card>
          </div>
        </div>
      )}
    </div>
  )
}
