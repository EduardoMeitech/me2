/**
 * ME2 data hooks — fetch equipment, OEE, production from API.
 */

import { useCallback, useEffect, useState } from 'react'
import api from '../lib/api'

/**
 * Fetch all equipment for the current tenant.
 */
export function useEquipment() {
  const [equipment, setEquipment] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function fetch() {
      try {
        setLoading(true)
        const res = await api.get('/api/v1/equipment')
        if (!cancelled) setEquipment(res.data?.data ?? [])
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => { cancelled = true }
  }, [])

  return { equipment, loading, error }
}

/**
 * Fetch OEE data for a specific equipment.
 */
export function useOEE(equipmentId, date, shift) {
  const [oee, setOEE] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!equipmentId) return
    let cancelled = false

    async function fetch() {
      try {
        setLoading(true)
        const params = {}
        if (date) params.date = date
        if (shift) params.shift = shift
        const res = await api.get(`/api/v1/equipment/${equipmentId}/oee`, { params })
        if (!cancelled) setOEE(res.data?.data ?? null)
      } catch (err) {
        console.error('Erro ao buscar OEE:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => { cancelled = true }
  }, [equipmentId, date, shift])

  return { oee, loading }
}

/**
 * Fetch hourly production for a specific equipment.
 */
export function useProduction(equipmentId, date, shift) {
  const [production, setProduction] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!equipmentId) return
    let cancelled = false

    async function fetch() {
      try {
        setLoading(true)
        const params = {}
        if (date) params.date = date
        if (shift) params.shift = shift
        const res = await api.get(`/api/v1/equipment/${equipmentId}/production`, { params })
        if (!cancelled) setProduction(res.data?.data ?? [])
      } catch (err) {
        console.error('Erro ao buscar produção:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => { cancelled = true }
  }, [equipmentId, date, shift])

  return { production, loading }
}

/**
 * Fetch status events for a specific equipment (for StatusTimeline + StatusPareto).
 */
export function useStatusEvents(equipmentId, date, shift) {
  const [statusEvents, setStatusEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!equipmentId) return
    let cancelled = false

    async function fetch() {
      try {
        setLoading(true)
        const params = {}
        if (date) params.date = date
        if (shift) params.shift = shift
        const res = await api.get(`/api/v1/equipment/${equipmentId}/status`, { params })
        if (!cancelled) setStatusEvents(res.data?.data ?? [])
      } catch (err) {
        console.error('Erro ao buscar status events:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => { cancelled = true }
  }, [equipmentId, date, shift])

  return { statusEvents, loading }
}

/**
 * Fetch active alerts.
 */
export function useActiveAlerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  const refetch = useCallback(async () => {
    try {
      const res = await api.get('/api/v1/alerts/active')
      setAlerts(res.data?.data ?? [])
    } catch (err) {
      console.error('Erro ao buscar alertas:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
    const interval = setInterval(refetch, 30000)
    return () => clearInterval(interval)
  }, [refetch])

  return { alerts, loading, refetch }
}

/**
 * Fetch alert summary (counts).
 */
export function useAlertSummary() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  const refetch = useCallback(async () => {
    try {
      const res = await api.get('/api/v1/alerts/summary')
      setSummary(res.data?.data ?? null)
    } catch (err) {
      console.error('Erro ao buscar resumo de alertas:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refetch()
    const interval = setInterval(refetch, 30000)
    return () => clearInterval(interval)
  }, [refetch])

  return { summary, loading, refetch }
}

/**
 * Fetch alert history (resolved).
 */
export function useAlertHistory(days = 7, equipmentId = null) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  const refetch = useCallback(async () => {
    try {
      const params = { days }
      if (equipmentId) params.equipment_id = equipmentId
      const res = await api.get('/api/v1/alerts/history', { params })
      setHistory(res.data?.data ?? [])
    } catch (err) {
      console.error('Erro ao buscar histórico de alertas:', err)
    } finally {
      setLoading(false)
    }
  }, [days, equipmentId])

  useEffect(() => {
    refetch()
  }, [refetch])

  return { history, loading, refetch }
}
