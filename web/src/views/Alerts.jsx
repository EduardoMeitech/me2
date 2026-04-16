/**
 * Alerts — Alertas ativos, resumo e histórico.
 */

import { useState, useEffect } from 'react'
import { colors, typography, shape } from '../styles/theme'
import { useActiveAlerts, useAlertSummary, useAlertHistory, useEquipment } from '../hooks/useME2Data'
import Card from '../components/Card'
import Button from '../components/Button'
import api from '../lib/api'

export default function Alerts() {
  const { alerts, loading, refetch } = useActiveAlerts()
  const { summary } = useAlertSummary()
  const { equipment } = useEquipment()
  const [filterEquipment, setFilterEquipment] = useState(null)
  const { history } = useAlertHistory(7, filterEquipment)
  const [now, setNow] = useState(Date.now())

  // Tick every 30s to update "time ago" values
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(interval)
  }, [])

  const handleAcknowledge = async (alertId) => {
    try {
      await api.post(`/api/v1/alerts/${alertId}/acknowledge`)
      refetch()
    } catch (err) {
      console.error('Erro ao reconhecer alerta:', err)
    }
  }

  const selectStyle = {
    padding: '8px 16px',
    borderRadius: shape.small,
    border: `1px solid ${colors.outlineVariant}`,
    background: '#FFFFFF',
    ...typography.bodyMedium,
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 20, alignItems: 'center' }}>
        <h1 style={{ ...typography.headlineMedium, color: colors.onSurface, marginRight: 'auto' }}>
          Alertas
        </h1>
        <select
          value={filterEquipment || ''}
          onChange={(e) => setFilterEquipment(e.target.value || null)}
          style={selectStyle}
        >
          <option value="">Todos os equipamentos</option>
          {equipment.map((eq) => (
            <option key={eq.id} value={eq.id}>{eq.name} ({eq.serial_number})</option>
          ))}
        </select>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 24 }}>
        <SummaryCard
          label="Ativos"
          value={summary?.active_total ?? 0}
          color={summary?.active_total > 0 ? colors.error : colors.success}
          icon="&#9888;"
        />
        <SummaryCard
          label="N\u00edvel 1"
          value={summary?.active_l1 ?? 0}
          color={summary?.active_l1 > 0 ? colors.warning : colors.onSurfaceVariant}
          icon="&#9679;"
        />
        <SummaryCard
          label="N\u00edvel 2"
          value={summary?.active_l2 ?? 0}
          color={summary?.active_l2 > 0 ? colors.error : colors.onSurfaceVariant}
          icon="&#9679;"
        />
        <SummaryCard
          label="Resolvidos hoje"
          value={summary?.resolved_today ?? 0}
          color={colors.success}
          icon="&#10003;"
        />
      </div>

      {/* Active alerts */}
      <SectionTitle>Alertas Ativos</SectionTitle>

      {loading ? (
        <p style={{ ...typography.bodyLarge, color: colors.onSurfaceVariant, padding: '16px 0' }}>
          Carregando alertas...
        </p>
      ) : alerts.length === 0 ? (
        <Card style={{ marginBottom: 32 }}>
          <div style={{ textAlign: 'center', padding: '32px' }}>
            <p style={{ fontSize: '40px', marginBottom: '8px', lineHeight: 1 }}>&#10003;</p>
            <p style={{ ...typography.titleMedium, color: colors.success }}>
              Nenhum alerta ativo
            </p>
            <p style={{ ...typography.bodyMedium, color: colors.onSurfaceVariant }}>
              Todos os equipamentos operando normalmente.
            </p>
          </div>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 32 }}>
          {alerts
            .filter((a) => !filterEquipment || a.equipment_id === filterEquipment)
            .map((alert) => (
              <ActiveAlertRow
                key={alert.id}
                alert={alert}
                now={now}
                onAcknowledge={handleAcknowledge}
              />
            ))}
        </div>
      )}

      {/* History */}
      <SectionTitle>Hist\u00f3rico (7 dias)</SectionTitle>

      {history.length === 0 ? (
        <Card>
          <p style={{ ...typography.bodyMedium, color: colors.onSurfaceVariant, textAlign: 'center', padding: '24px' }}>
            Nenhum alerta resolvido nos \u00faltimos 7 dias.
          </p>
        </Card>
      ) : (
        <Card style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', ...typography.bodyMedium }}>
              <thead>
                <tr style={{ background: colors.surfaceVariant }}>
                  <Th>Equipamento</Th>
                  <Th>N\u00edvel</Th>
                  <Th>In\u00edcio</Th>
                  <Th>Resolvido</Th>
                  <Th>Dura\u00e7\u00e3o</Th>
                  <Th>Reconhecido</Th>
                </tr>
              </thead>
              <tbody>
                {history.map((alert) => (
                  <HistoryRow key={alert.id} alert={alert} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}


// ── Summary card ──────────────────────────────────────────────────────────────

function SummaryCard({ label, value, color, icon }) {
  return (
    <Card style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <div style={{
        width: 44, height: 44, borderRadius: shape.medium,
        background: `${color}14`, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 20, color, flexShrink: 0,
      }}>
        <span dangerouslySetInnerHTML={{ __html: icon }} />
      </div>
      <div>
        <p style={{ ...typography.headlineSmall, color, lineHeight: 1 }}>{value}</p>
        <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>{label}</p>
      </div>
    </Card>
  )
}


// ── Section title ─────────────────────────────────────────────────────────────

function SectionTitle({ children }) {
  return (
    <p style={{ ...typography.titleMedium, color: colors.onSurface, marginBottom: 12 }}>
      {children}
    </p>
  )
}


// ── Active alert row ──────────────────────────────────────────────────────────

function ActiveAlertRow({ alert, now, onAcknowledge }) {
  const isL2 = alert.level >= 2
  const accentColor = isL2 ? colors.errorDark : colors.error

  const minutesAgo = alert.started_at
    ? Math.round((now - new Date(alert.started_at).getTime()) / 60000)
    : 0

  const equipLabel = alert.equipment_name
    ? `${alert.equipment_name} (${alert.serial_number})`
    : alert.equipment_id

  return (
    <Card
      variant="outlined"
      style={{
        borderLeft: `4px solid ${accentColor}`,
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        flexWrap: 'wrap',
      }}
    >
      {/* Level badge */}
      <div style={{
        width: 36, height: 36, borderRadius: shape.full,
        background: accentColor, color: '#FFFFFF',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        ...typography.labelLarge, flexShrink: 0,
      }}>
        L{alert.level}
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 200 }}>
        <p style={{ ...typography.titleSmall, color: colors.onSurface }}>
          {equipLabel}
        </p>
        <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>
          {alert.message ?? `Equipamento parado h\u00e1 ${minutesAgo} min`}
        </p>
      </div>

      {/* Duration */}
      <div style={{ textAlign: 'center', minWidth: 80 }}>
        <p style={{ ...typography.headlineSmall, color: accentColor, lineHeight: 1 }}>
          {minutesAgo}
        </p>
        <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>min parado</p>
      </div>

      {/* Time */}
      <div style={{ textAlign: 'center', minWidth: 80 }}>
        <p style={{ ...typography.bodyMedium, color: colors.onSurface }}>
          {alert.started_at ? new Date(alert.started_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '\u2014'}
        </p>
        <p style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>in\u00edcio</p>
      </div>

      {/* Ack status / button */}
      {alert.acknowledged_at ? (
        <div style={{
          padding: '6px 16px', borderRadius: shape.full,
          background: colors.surfaceVariant,
          ...typography.labelMedium, color: colors.onSurfaceVariant,
        }}>
          Reconhecido
        </div>
      ) : (
        <Button variant="error" onClick={() => onAcknowledge?.(alert.id)}>
          Reconhecer
        </Button>
      )}
    </Card>
  )
}


// ── Table helpers ─────────────────────────────────────────────────────────────

function Th({ children }) {
  return (
    <th style={{
      ...typography.labelMedium,
      color: colors.onSurfaceVariant,
      padding: '10px 16px',
      textAlign: 'left',
      whiteSpace: 'nowrap',
    }}>
      {children}
    </th>
  )
}

function HistoryRow({ alert }) {
  const startDate = alert.started_at ? new Date(alert.started_at) : null
  const resolvedDate = alert.resolved_at ? new Date(alert.resolved_at) : null
  const durationMin = startDate && resolvedDate
    ? Math.round((resolvedDate - startDate) / 60000)
    : null

  const equipLabel = alert.equipment_name
    ? `${alert.equipment_name}`
    : alert.equipment_id?.slice(0, 8)

  const levelColor = alert.level >= 2 ? colors.errorDark : colors.error

  const cellStyle = {
    padding: '10px 16px',
    borderBottom: `1px solid ${colors.outlineVariant}`,
    whiteSpace: 'nowrap',
  }

  return (
    <tr>
      <td style={cellStyle}>
        <span style={{ ...typography.bodyMedium, color: colors.onSurface }}>{equipLabel}</span>
        {alert.serial_number && (
          <span style={{ ...typography.bodySmall, color: colors.onSurfaceVariant, marginLeft: 8 }}>
            {alert.serial_number}
          </span>
        )}
      </td>
      <td style={cellStyle}>
        <span style={{
          display: 'inline-block', padding: '2px 10px',
          borderRadius: shape.full, background: `${levelColor}14`,
          color: levelColor, ...typography.labelSmall,
        }}>
          L{alert.level}
        </span>
      </td>
      <td style={{ ...cellStyle, ...typography.bodySmall, color: colors.onSurfaceVariant }}>
        {startDate ? formatDateTime(startDate) : '\u2014'}
      </td>
      <td style={{ ...cellStyle, ...typography.bodySmall, color: colors.onSurfaceVariant }}>
        {resolvedDate ? formatDateTime(resolvedDate) : '\u2014'}
      </td>
      <td style={cellStyle}>
        <span style={{ ...typography.bodyMedium, color: colors.onSurface }}>
          {durationMin != null ? `${durationMin} min` : '\u2014'}
        </span>
      </td>
      <td style={cellStyle}>
        {alert.acknowledged_at ? (
          <span style={{ ...typography.bodySmall, color: colors.success }}>Sim</span>
        ) : (
          <span style={{ ...typography.bodySmall, color: colors.onSurfaceVariant }}>N\u00e3o</span>
        )}
      </td>
    </tr>
  )
}


function formatDateTime(date) {
  const d = String(date.getDate()).padStart(2, '0')
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const min = String(date.getMinutes()).padStart(2, '0')
  return `${d}/${m} ${h}:${min}`
}
