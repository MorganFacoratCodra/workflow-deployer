import { useEffect } from 'react'

type ExecutionSocketMessage = {
  type: 'node' | 'execution'
  node_id?: string
  status: string
  logs?: string
  duration_ms?: number
}

export function useExecutionSocket(
  executionId: number | null,
  onMessage: (message: ExecutionSocketMessage) => void,
) {
  useEffect(() => {
    if (!executionId) {
      return
    }

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
    const wsBase = apiUrl.replace(/^http/, 'ws').replace(/\/api\/?$/, '')
    const socket = new WebSocket(`${wsBase}/ws/executions/${executionId}`)

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data) as ExecutionSocketMessage
      onMessage(data)
    }

    const ping = window.setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send('ping')
      }
    }, 5000)

    return () => {
      window.clearInterval(ping)
      socket.close()
    }
  }, [executionId, onMessage])
}
