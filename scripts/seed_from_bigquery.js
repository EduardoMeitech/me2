#!/usr/bin/env node
/**
 * ME2 seed_from_bigquery.js — Generate realistic seed data from E2/BigQuery exports.
 *
 * Reads machinesStation.json and machinesProduction.json (exported from BigQuery),
 * maps them to ME2 domain (serial_number, word_status, equipment names), shifts
 * timestamps to recent weeks, and outputs a SQL file for psql import.
 *
 * Usage:
 *   node scripts/seed_from_bigquery.js > scripts/seed_bigquery.sql
 *   psql -U me2 -d me2 -f scripts/seed_bigquery.sql
 *
 * Or pipe directly:
 *   node scripts/seed_from_bigquery.js | psql -U me2 -d me2
 */

const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const TABLES_DIR = path.join(__dirname, '..', 'tables')
const TENANT_NAME = 'Meitech Industrial'
const PLANT_NAME = 'Meitech Sede — Linha Frango'

// Map StationSAP → ME2 equipment
const EQUIPMENT_MAP = {
  '28321': { serial: 'MEI-2024-28321', name: 'Desossadora 01',      model: 'M241',  manufacturer: 'Schneider Electric', cycleTime: 8.8 },
  '28322': { serial: 'MEI-2024-28322', name: 'Desossadora 02',      model: 'M241',  manufacturer: 'Schneider Electric', cycleTime: 8.7 },
  '29072': { serial: 'MEI-2024-29072', name: 'Transportadora 01',   model: 'M340',  manufacturer: 'Schneider Electric', cycleTime: 7.8 },
  '29073': { serial: 'MEI-2024-29073', name: 'Transportadora 02',   model: 'M340',  manufacturer: 'Schneider Electric', cycleTime: 8.8 },
  '29075': { serial: 'MEI-2024-29075', name: 'Balança Aérea 01',    model: 'S7-1200', manufacturer: 'Siemens',          cycleTime: 31.6 },
  '29076': { serial: 'MEI-2024-29076', name: 'Balança Aérea 02',    model: 'S7-1200', manufacturer: 'Siemens',          cycleTime: 8.2 },
  '29078': { serial: 'MEI-2024-29078', name: 'Transferidora 01',    model: 'M251',  manufacturer: 'Schneider Electric', cycleTime: 17.5 },
  '29657': { serial: 'MEI-2024-29657', name: 'Embaladora 01',       model: 'M241',  manufacturer: 'Schneider Electric', cycleTime: 7.7 },
  '34513': { serial: 'MEI-2024-34513', name: 'Classificadora 01',   model: 'M580',  manufacturer: 'Schneider Electric', cycleTime: 7.7 },
  '34514': { serial: 'MEI-2024-34514', name: 'Classificadora 02',   model: 'M580',  manufacturer: 'Schneider Electric', cycleTime: 7.7 },
  '9999':  { serial: 'MEI-2024-09999', name: 'Escaldadeira 01',     model: 'M221',  manufacturer: 'Schneider Electric', cycleTime: 8.2 },
}

// Product number mapping (E2 codes → ME2-friendly names)
const PRODUCT_MAP = {
  '118041021': 'Coxa c/ Sobrecoxa',
  '118041022': 'Coxa s/ Sobrecoxa',
  '118141013': 'Peito Inteiro',
  '118141015': 'Filé de Peito',
  '118141016': 'Sassami',
  '118141017': 'Meio Peito',
  '218022005': 'Frango Inteiro',
}

// WordStatus bitmask mapping (E2 → ME2 standard)
// Priority: Emergency(128) > Failure(32) > Setup(64) > Blocked(8) > Starving(4) > Running(2) > Ready(16)
function mapWordStatus(ws) {
  const v = parseInt(ws) || 0
  if (v & 128) return 128  // Emergency
  if (v & 32)  return 32   // Failure
  if (v & 64)  return 64   // Setup
  if (v & 8)   return 24   // Blocked (Ready + Blocked)
  if ((v & 2) && (v & 4))  return 20  // Running + Starving → Starving
  if ((v & 2) && (v & 16)) return 18  // Running + Ready → Uptime
  if (v & 4)   return 20   // Starving
  if (v & 16)  return 16   // Ready/Idle
  if (v & 1)   return 17   // Planned Stop
  if (v === 0) return 16   // Off → Idle
  return 16                 // Fallback
}

// ---------------------------------------------------------------------------
// Timestamp shifting
// ---------------------------------------------------------------------------

// Calculate offset to shift original data to recent dates
// Original latest: 2025-03-17 ~16:44 UTC
// Target latest: today (2026-04-16) minus a few hours
function calcTimestampOffset(records) {
  let maxTs = 0
  for (const r of records) {
    const t = new Date(r.TimeStamp.replace(' UTC', 'Z')).getTime()
    if (t > maxTs) maxTs = t
  }
  const now = Date.now() - 2 * 3600_000 // 2h ago
  return now - maxTs
}

function shiftTimestamp(tsStr, offsetMs) {
  const t = new Date(tsStr.replace(' UTC', 'Z'))
  const shifted = new Date(t.getTime() + offsetMs)
  return shifted.toISOString()
}

// ---------------------------------------------------------------------------
// SQL generation helpers
// ---------------------------------------------------------------------------

function uuid() {
  return crypto.randomUUID()
}

function esc(s) {
  if (s === null || s === undefined) return 'NULL'
  return "'" + String(s).replace(/'/g, "''") + "'"
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  console.error('Reading BigQuery exports...')

  const stationFile = path.join(TABLES_DIR, 'machinesStation.json')
  const productionFile = path.join(TABLES_DIR, 'machinesProduction.json')

  if (!fs.existsSync(stationFile) || !fs.existsSync(productionFile)) {
    console.error('ERROR: tables/machinesStation.json and tables/machinesProduction.json not found')
    process.exit(1)
  }

  const stations = JSON.parse(fs.readFileSync(stationFile, 'utf8'))
  const productions = JSON.parse(fs.readFileSync(productionFile, 'utf8'))

  console.error(`  machinesStation: ${stations.length} records`)
  console.error(`  machinesProduction: ${productions.length} records`)

  // Calculate time offset (shift to recent dates)
  const allRecords = [...stations, ...productions]
  const offsetMs = calcTimestampOffset(allRecords)
  const offsetDays = (offsetMs / 86400_000).toFixed(1)
  console.error(`  Shifting timestamps by ${offsetDays} days to bring data to present`)

  // SQL output
  const sql = []

  sql.push('-- =================================================================')
  sql.push('-- ME2 Seed Data — Generated from E2/BigQuery exports')
  sql.push(`-- Date: ${new Date().toISOString()}`)
  sql.push(`-- Source: tables/machinesStation.json (${stations.length} records)`)
  sql.push(`--         tables/machinesProduction.json (${productions.length} records)`)
  sql.push(`-- Timestamp shift: +${offsetDays} days`)
  sql.push('-- =================================================================')
  sql.push('')
  sql.push('BEGIN;')
  sql.push('')

  // --- Tenant ---
  const tenantId = uuid()
  sql.push('-- Tenant')
  sql.push(`INSERT INTO me2_tenants (id, name, country, timezone)`)
  sql.push(`VALUES (${esc(tenantId)}, ${esc(TENANT_NAME)}, 'BRA', 'America/Sao_Paulo')`)
  sql.push(`ON CONFLICT DO NOTHING;`)
  sql.push('')

  // --- Plant ---
  const plantId = uuid()
  sql.push('-- Plant')
  sql.push(`INSERT INTO me2_plants (id, tenant_id, name, location, timezone)`)
  sql.push(`VALUES (${esc(plantId)}, ${esc(tenantId)}, ${esc(PLANT_NAME)}, 'Caxias do Sul - RS', 'America/Sao_Paulo')`)
  sql.push(`ON CONFLICT DO NOTHING;`)
  sql.push('')

  // --- User ---
  const userId = uuid()
  // bcrypt hash of "me2admin"
  const pwHash = '$2b$12$LJ3mFGy1l8Eo0L/7Nh4ZAO4n6KqFRbBJmN2NROPB9XplFvNpKwPi'
  sql.push('-- User')
  sql.push(`INSERT INTO me2_users (id, tenant_id, name, email, role, password_hash)`)
  sql.push(`VALUES (${esc(userId)}, ${esc(tenantId)}, 'Eduardo Rosa', 'eduardo.rosa@meitech.com.br', 'meitech_admin', ${esc(pwHash)})`)
  sql.push(`ON CONFLICT (email) DO NOTHING;`)
  sql.push('')

  // --- Shifts ---
  const shiftIds = {}
  const shiftDefs = [
    { name: 'Turno 1', code: 'T100', start: '05:00:00', end: '13:29:00' },
    { name: 'Turno 2', code: 'T200', start: '13:30:00', end: '21:59:00' },
    { name: 'Turno 3', code: 'T300', start: '22:00:00', end: '04:59:00' },
  ]
  sql.push('-- Shifts')
  for (const s of shiftDefs) {
    const sid = uuid()
    shiftIds[s.code] = sid
    sql.push(`INSERT INTO me2_shifts (id, plant_id, name, start_time, end_time)`)
    sql.push(`VALUES (${esc(sid)}, ${esc(plantId)}, ${esc(s.name)}, '${s.start}', '${s.end}')`)
    sql.push(`ON CONFLICT DO NOTHING;`)
  }
  sql.push('')

  // --- Equipment ---
  const equipmentIds = {} // StationSAP → UUID
  sql.push('-- Equipment (11 machines from BigQuery E2 data)')
  for (const [sap, eq] of Object.entries(EQUIPMENT_MAP)) {
    const eqId = uuid()
    equipmentIds[sap] = eqId
    sql.push(`INSERT INTO me2_equipment (id, plant_id, serial_number, name, model, manufacturer, standard_cycle_time_s, active)`)
    sql.push(`VALUES (${esc(eqId)}, ${esc(plantId)}, ${esc(eq.serial)}, ${esc(eq.name)}, ${esc(eq.model)}, ${esc(eq.manufacturer)}, ${eq.cycleTime}, true)`)
    sql.push(`ON CONFLICT (serial_number) DO UPDATE SET name = EXCLUDED.name, model = EXCLUDED.model, standard_cycle_time_s = EXCLUDED.standard_cycle_time_s;`)
  }
  sql.push('')

  // --- Status Events ---
  console.error('Generating status_events...')
  sql.push('-- Status Events')
  sql.push(`-- (${stations.length} records, WordStatus mapped to ME2 standard)`)

  let statusCount = 0
  let batchValues = []

  for (const row of stations) {
    const sap = row.StationSAP
    if (!equipmentIds[sap]) continue

    const eqId = equipmentIds[sap]
    const serial = EQUIPMENT_MAP[sap].serial
    const ws = mapWordStatus(row.WordStatus)
    const ts = shiftTimestamp(row.TimeStamp, offsetMs)

    batchValues.push(`(${esc(eqId)}, ${esc(serial)}, ${ws}, ${esc(ts)}::timestamptz)`)
    statusCount++

    // Flush every 500 rows
    if (batchValues.length >= 500) {
      sql.push(`INSERT INTO status_events (equipment_id, serial_number, word_status, ts) VALUES`)
      sql.push(batchValues.join(',\n') + ';')
      batchValues = []
    }
  }
  if (batchValues.length > 0) {
    sql.push(`INSERT INTO status_events (equipment_id, serial_number, word_status, ts) VALUES`)
    sql.push(batchValues.join(',\n') + ';')
    batchValues = []
  }
  sql.push('')
  console.error(`  ${statusCount} status_events generated`)

  // --- Production Events ---
  console.error('Generating production_events...')
  sql.push('-- Production Events')
  sql.push(`-- (${productions.length} records, trigger-on-change preserved)`)

  let prodCount = 0

  for (const row of productions) {
    const sap = row.StationSAP
    if (!equipmentIds[sap]) continue

    const eqId = equipmentIds[sap]
    const serial = EQUIPMENT_MAP[sap].serial
    const partsOk = parseInt(row.PartsOK) || 0
    const productNo = PRODUCT_MAP[row.ProductNumber] || row.ProductNumber
    const cycleTime = parseFloat(EQUIPMENT_MAP[sap]?.cycleTime || 0)
    const ts = shiftTimestamp(row.TimeStamp, offsetMs)

    batchValues.push(`(${esc(eqId)}, ${esc(serial)}, ${esc(productNo)}, ${partsOk}, ${cycleTime}, ${esc(ts)}::timestamptz)`)
    prodCount++

    if (batchValues.length >= 500) {
      sql.push(`INSERT INTO production_events (equipment_id, serial_number, product_no, parts_ok, cycle_time_s, ts) VALUES`)
      sql.push(batchValues.join(',\n') + ';')
      batchValues = []
    }
  }
  if (batchValues.length > 0) {
    sql.push(`INSERT INTO production_events (equipment_id, serial_number, product_no, parts_ok, cycle_time_s, ts) VALUES`)
    sql.push(batchValues.join(',\n') + ';')
  }
  sql.push('')
  console.error(`  ${prodCount} production_events generated`)

  // --- Commit ---
  sql.push('COMMIT;')
  sql.push('')
  sql.push(`-- Summary: ${statusCount} status_events + ${prodCount} production_events`)
  sql.push(`-- for ${Object.keys(EQUIPMENT_MAP).length} equipment across ~2.5 days shifted to present`)

  // Output
  const output = sql.join('\n')
  process.stdout.write(output)

  console.error('')
  console.error('Done! Output SQL to stdout.')
  console.error(`Total: ${statusCount + prodCount} events for ${Object.keys(EQUIPMENT_MAP).length} machines`)
  console.error('')
  console.error('To import:')
  console.error('  node scripts/seed_from_bigquery.js > scripts/seed_bigquery.sql')
  console.error('  psql -U me2 -d me2 -f scripts/seed_bigquery.sql')
}

main()
