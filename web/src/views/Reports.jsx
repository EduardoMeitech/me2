/**
 * Reports — Relatório de turno / diário.
 */

import { useState } from 'react'
import { colors, typography } from '../styles/theme'
import { useEquipment } from '../hooks/useME2Data'
import { useUIStore } from '../lib/store'
import Card from '../components/Card'
import Button from '../components/Button'
import ShiftSelector from '../components/ShiftSelector'
import api from '../lib/api'

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function Reports() {
  const { equipment } = useEquipment()
  const [selectedEquipment, setSelectedEquipment] = useState(null)
  const [date, setDate] = useState(todayStr())
  const selectedShift = useUIStore((s) => s.selectedShift)
  const setShift = useUIStore((s) => s.setShift)
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchReport = async () => {
    if (!selectedEquipment) return
    setLoading(true)
    try {
      const params = { equipment_id: selectedEquipment, date }
      if (selectedShift) params.shift = selectedShift
      const res = await api.get('/api/v1/reports/shift', { params })
      setReport(res.data?.data ?? null)
    } catch (err) {
      console.error('Erro ao buscar relatório:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 style={{ ...typography.headlineMedium, color: colors.onSurface, marginBottom: '24px' }}>
        Relatórios
      </h1>

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', marginBottom: '24px', alignItems: 'center' }}>
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

        <ShiftSelector selected={selectedShift} onChange={setShift} />

        <Button onClick={fetchReport} disabled={!selectedEquipment || loading}>
          {loading ? 'Gerando...' : 'Gerar Relatório'}
        </Button>
      </div>

      {/* Report content */}
      {report && (
        <Card>
          <h2 style={{ ...typography.titleLarge, color: colors.onSurface, marginBottom: '16px' }}>
            Relatório de Turno
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px' }}>
            <div>
              <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>Total Peças</p>
              <p style={{ ...typography.headlineSmall }}>{report.total_parts ?? 0}</p>
            </div>
            <div>
              <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>OEE</p>
              <p style={{ ...typography.headlineSmall }}>
                {report.oee_pct != null ? `${(report.oee_pct * 100).toFixed(1)}%` : '—'}
              </p>
            </div>
            <div>
              <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>Disponibilidade</p>
              <p style={{ ...typography.headlineSmall }}>
                {report.availability_pct != null ? `${(report.availability_pct * 100).toFixed(1)}%` : '—'}
              </p>
            </div>
            <div>
              <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>Performance</p>
              <p style={{ ...typography.headlineSmall }}>
                {report.performance_pct != null ? `${(report.performance_pct * 100).toFixed(1)}%` : '—'}
              </p>
            </div>
            <div>
              <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>Qualidade</p>
              <p style={{ ...typography.headlineSmall }}>
                {report.quality_pct != null ? `${(report.quality_pct * 100).toFixed(1)}%` : '—'}
              </p>
            </div>
            <div>
              <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>Downtime</p>
              <p style={{ ...typography.headlineSmall }}>
                {report.downtime_min != null ? `${report.downtime_min.toFixed(0)} min` : '—'}
              </p>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
