import { useState, useEffect } from 'react'
import { api } from '../services/api'
import './HealthCheck.css'

interface HealthStatus {
  status: string
  service: string
}

export default function HealthCheck() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await api.checkHealth()
        setHealth(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
        setHealth(null)
      } finally {
        setLoading(false)
      }
    }

    checkHealth()
  }, [])

  return (
    <div className="health-check">
      <h2>Backend Status</h2>
      {loading && <p className="status-loading">Checking...</p>}
      {error && <p className="status-error">Error: {error}</p>}
      {health && (
        <div className="status-info">
          <p className="status-ok">✓ Service: {health.service}</p>
          <p className="status-ok">✓ Status: {health.status}</p>
        </div>
      )}
    </div>
  )
}
