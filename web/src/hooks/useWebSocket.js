/**
 * ME2 WebSocket hook — auto-reconnect, parse JSON messages.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL || `ws://${window.location.host}/ws/live`
const RECONNECT_DELAY = 3000
const MAX_RECONNECT_ATTEMPTS = 10

export default function useWebSocket(onMessage) {
  const wsRef = useRef(null)
  const reconnectCount = useRef(0)
  const reconnectTimer = useRef(null)
  const [connected, setConnected] = useState(false)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        reconnectCount.current = 0
        console.log('[ME2 WS] Conectado')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.(data)
        } catch (err) {
          console.warn('[ME2 WS] Mensagem inválida:', event.data)
        }
      }

      ws.onclose = (event) => {
        setConnected(false)
        console.log('[ME2 WS] Desconectado:', event.code)

        if (reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectCount.current += 1
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY)
        }
      }

      ws.onerror = (error) => {
        console.error('[ME2 WS] Erro:', error)
      }
    } catch (err) {
      console.error('[ME2 WS] Falha ao conectar:', err)
    }
  }, [onMessage])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return { connected, send }
}
