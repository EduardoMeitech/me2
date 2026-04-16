/**
 * Reports — Relatório de turno com OEE, produção e breakdown de status.
 */

import { useState } from 'react'
import { colors, typography, shape } from '../styles/theme'
import { getStatusColor, getStatusLabel } from '../styles/theme'
import { useEquipment } from '../hooks/useME2Data'
import { useUIStore } from '../lib/store'
import Card from '../components/Card'
import Button from '../components/Button'
import OEEGauge from '../components/OEEGauge'
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
  const [error, setError] = useState(null)

  const fetchReport = async () => {
    if (!selectedEquipment || !selectedShift) return
    setLoading(true)
    setError(null)
    try {
      const params = { equipment_id: selectedEquipment, date, shift: selectedShift }
      const res = await api.get('/api/v1/reports/shift', { params })
      setReport(res.data?.data ?? null)
    } catch (err) {
      console.error('Erro ao buscar relatório:', err)
      setError('Erro ao gerar relatório. Verifique os filtros.')
      setReport(null)
    } finally {
      setLoading(false)
    }
  }

  const selectStyle = {
    padding: '8px 16px',
    borderRadius: shape.small,
    border: `1px solid ${colors.outlineVariant}`,
    background: '#FFFFFF',
    ...typography.bodyMedium,
  }

  const oee = report?.oee
  const availability = oee?.availability_pct ?? 0
  const performance = oee?.performance_pct ?? 0
  const quality = oee?.quality_pct ?? 1

  return (
    <div>
      {/* Header + Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 20, alignItems: 'center' }}>
        <h1 style={{ ...typography.headlineMedium, color: colors.onSurface, marginRight: 'auto' }}>
          Relatórios
        </h1>
        <select
          value={selectedEquipment || ''}
          onChange={(e) => { setSelectedEquipment(e.target.value || null); setReport(null) }}
          style={selectStyle}
        >
          <option value="">Selecione um equipamento</option>
          {equipment.map((eq) => (
            <option key={eq.id} value={eq.id}>{eq.name} ({eq.serial_number})</option>
          ))}
        </select>
        <input type="date" value={date} onChange={(e) => { setDate(e.target.value); setReport(null) }} style={selectStyle} />
        <ShiftSelector selected={selectedShift} onChange={(s) => { setShift(s); setReport(null) }} />
        <Button
          onClick={fetchReport}
          disabled={!selectedEquipment || !selectedShift || loading}
        >
          {loading ? 'Gerando...' : 'Gerar Relatório'}
        </Button>
      </div>

      {/* Prompt */}
      {!report && !error && (
        <div style={{ textAlign: 'center', padding: 64 }}>
          <p style={{ ...typography.bodyLarge, color: colors.onSurfaceVariant }}>
            {!selectedEquipment
              ? 'Selecione um equipamento, data e turno para gerar o relatório.'
              : !selectedShift
                ? 'Selecione um turno para gerar o relatório.'
                : 'Clique em "Gerar Relatório" para visualizar.'}
          </p>
        </div>
      )}

      {error && (
        <Card style={{ borderLeft: `4px solid ${colors.error}`, marginBottom: 16 }}>
          <p style={{ ...typography.bodyMedium, color: colors.error }}>{error}</p>
        </Card>
      )}

      {/* Report content */}
      {report && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* ── Row 1: Equipment info + OEE Gauge ── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: 16 }}>

            {/* Card: Equipment + shift info */}
            <Card style={{ padding: '16px 20px' }}>
              <p style={{ ...typography.titleLarge, color: colors.onSurface, marginBottom: 4 }}>
                {report.equipment_name}
              </p>
              <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant, marginBottom: 16 }}>
                {report.serial_number} — {report.shift_label} — {formatDateBR(report.date)}
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px 32px' }}>
                <KPI label="Total Peças" value={report.total_parts} />
                <KPI label="Downtime" value={`${report.downtime_min} min`} color={report.downtime_min > 0 ? colors.error : undefined} />
                <KPI label="Tempo Planejado" value={`${report.planned_min} min`} />
                <KPI label="Cycle Time" value={report.cycle_time_s > 0 ? `${report.cycle_time_s.toFixed(1)}s` : '—'} />
              </div>
            </Card>

            {/* Card: OEE Gauge + A/P/Q */}
            <Card style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 24 }}>
              <OEEGauge
                availability={availability}
                performance={performance}
                quality={quality}
                size={120}
              />
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
                <p style={{ ...typography.titleMedium, color: colors.onSurface }}>
                  OEE: {(availability * performance * quality * 100).toFixed(1)}%
                </p>
                <OEEBar label="Disponibilidade" value={availability} color={colors.success} />
                <OEEBar label="Performance" value={performance} color={colors.primary} />
                <OEEBar label="Qualidade" value={quality} color={colors.outline} />
              </div>
            </Card>
          </div>

          {/* ── Row 2: Status breakdown ── */}
          <Card>
            <p style={{ ...typography.titleMedium, color: colors.onSurface, marginBottom: 16 }}>
              Distribuição de Status
            </p>
            {report.status_breakdown && report.status_breakdown.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {report.status_breakdown.map((s) => {
                  const totalMin = report.status_breakdown.reduce((sum, x) => sum + x.duration_min, 0)
                  const pct = totalMin > 0 ? (s.duration_min / totalMin) : 0
                  return (
                    <StatusRow
                      key={s.word_status}
                      wordStatus={s.word_status}
                      durationMin={s.duration_min}
                      pct={pct}
                    />
                  )
                })}
              </div>
            ) : (
              <p style={{ ...typography.bodyMedium, color: colors.onSurfaceVariant }}>
                Sem dados de status para este turno.
              </p>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}


// ── KPI display ───────────────────────────────────────────────────────────────

function KPI({ label, value, color }) {
  return (
    <div>
      <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant, marginBottom: 4 }}>{label}</p>
      <p style={{ ...typography.headlineSmall, color: color ?? colors.onSurface }}>{value}</p>
    </div>
  )
}


// ── OEE horizontal bar ────────────────────────────────────────────────────────

function OEEBar({ label, value, color }) {
  const pct = Math.round(value * 100)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>{label}</span>
        <span style={{ ...typography.labelMedium, color }}>{pct}%</span>
      </div>
      <div style={{ height: 6, borderRadius: 3, background: colors.surfaceVariant }}>
        <div style={{ height: '100%', borderRadius: 3, background: color, width: `${pct}%`, transition: 'width 0.3s' }} />
      </div>
    </div>
  )
}


// ── Status row (horizontal bar) ───────────────────────────────────────────────

function StatusRow({ wordStatus, durationMin, pct }) {
  const barColor = getStatusColor(wordStatus)
  const label = getStatusLabel(wordStatus)

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{
        width: 10, height: 10, borderRadius: '50%',
        background: barColor, flexShrink: 0,
      }} />
      <span style={{ ...typography.bodyMedium, color: colors.onSurface, width: 120, flexShrink: 0 }}>
        {label}
      </span>
      <div style={{ flex: 1, height: 20, borderRadius: 4, background: colors.surfaceVariant, position: 'relative', overflow: 'hidden' }}>
        <div style={{
          height: '100%', borderRadius: 4, background: barColor,
          width: `${Math.max(pct * 100, 1)}%`, transition: 'width 0.3s',
          opacity: 0.8,
        }} />
      </div>
      <span style={{ ...typography.labelMedium, color: colors.onSurface, width: 70, textAlign: 'right', flexShrink: 0 }}>
        {durationMin} min
      </span>
      <span style={{ ...typography.bodySmall, color: colors.onSurfaceVariant, width: 45, textAlign: 'right', flexShrink: 0 }}>
        {(pct * 100).toFixed(0)}%
      </span>
    </div>
  )
}


// ── Date formatter (YYYY-MM-DD → DD/MM/YYYY) ─────────────────────────────────

function formatDateBR(dateStr) {
  if (!dateStr) return '—'
  const parts = dateStr.split('-')
  if (parts.length !== 3) return dateStr
  return `${parts[2]}/${parts[1]}/${parts[0]}`
}
