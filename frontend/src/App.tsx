import { useState, useEffect, useRef } from 'react'
import AuditForm from './components/AuditForm'
import ManualLinksForm from './components/ManualLinksForm'
import AuditResult from './components/AuditResult'
import './App.css'

interface ScanState {
  loading: boolean
  result: any | null
  error: string | null
  progress?: number
  progressMessage?: string
}

function App() {
  const [auditMethod, setAuditMethod] = useState<'auto' | 'manual'>('auto')
  const [scanState, setScanState] = useState<ScanState>({
    loading: false,
    result: null,
    error: null,
  })
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Stop polling on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
      }
    }
  }, [])

  const pollScanStatus = async (scanId: string): Promise<void> => {
    try {
      const response = await fetch(`/api/scans/${scanId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })

      if (!response.ok) {
        throw new Error(`Failed to get scan status: ${response.statusText}`)
      }

      const jobData = await response.json()

      if (jobData.status === 'completed' && jobData.result) {
        // Scan completed successfully
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
          pollingIntervalRef.current = null
        }
        setScanState({
          loading: false,
          result: jobData.result,
          error: null,
        })
      } else if (jobData.status === 'failed') {
        // Scan failed
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
          pollingIntervalRef.current = null
        }
        setScanState({
          loading: false,
          result: null,
          error: jobData.error || 'Auditoría fallida',
        })
      } else {
        // Still processing: update progress
        const stageMessages: Record<string, string> = {
          queued: 'Preparando auditoría...',
          fetching_master: 'Consultando publicaciones principales...',
          fetching_targets: 'Consultando publicaciones regionales...',
          downloading_media: 'Descargando recursos visuales...',
          matching: 'Comparando contenido...',
          exporting: 'Generando Excel...',
        }
        setScanState((prev) => ({
          ...prev,
          progress: jobData.progress || 0,
          progressMessage: stageMessages[jobData.status] || jobData.message || 'Procesando...',
        }))
      }
    } catch (err) {
      console.warn(`Polling error (will retry): ${err}`)
      // Continue polling on transient errors
    }
  }

  const handleScanSubmit = async (formData: any) => {
    setScanState({
      loading: true,
      result: null,
      error: null,
      progress: 0,
      progressMessage: 'Iniciando auditoría...',
    })

    try {
      const endpoint = auditMethod === 'manual' ? '/api/scans/manual' : '/api/scans'
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })

      if (!response.ok) {
        let errorMessage = 'Error en la auditoría'
        try {
          const errorData = await response.json()
          if (errorData.detail) {
            errorMessage = errorData.detail
          } else if (errorData.errors) {
            // FastAPI validation errors
            const errors = Array.isArray(errorData.errors)
              ? errorData.errors.map((e: any) => e.msg || e.toString()).join(', ')
              : JSON.stringify(errorData.errors)
            errorMessage = `Validación: ${errors}`
          }
        } catch {
          errorMessage = response.statusText || errorMessage
        }
        throw new Error(errorMessage)
      }

      const startResponse = await response.json()
      const scanId = startResponse.scan_id

      if (!scanId) {
        throw new Error('No scan_id received from server')
      }

      // Start polling
      pollingIntervalRef.current = setInterval(() => {
        pollScanStatus(scanId)
      }, 2000) // Poll every 2 seconds

      // Initial poll immediately
      await pollScanStatus(scanId)
    } catch (err) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
      setScanState({
        loading: false,
        result: null,
        error: err instanceof Error ? err.message : 'Error desconocido',
      })
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="container">
          <h1>Auditor de Contenido</h1>
          <p>Compara publicaciones de una cuenta principal con otras cuentas de Instagram y detecta contenido faltante.</p>
        </div>
      </header>

      <main className="container">
        {!scanState.result && (
          <>
            {/* Method Selector */}
            <div style={{
              display: 'flex',
              gap: '12px',
              marginBottom: '30px',
              justifyContent: 'center',
            }}>
              <button
                onClick={() => setAuditMethod('auto')}
                disabled={scanState.loading}
                style={{
                  padding: '10px 20px',
                  backgroundColor: auditMethod === 'auto' ? '#2563eb' : '#e5e7eb',
                  color: auditMethod === 'auto' ? 'white' : '#333',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '14px',
                  fontWeight: '500',
                  cursor: scanState.loading ? 'not-allowed' : 'pointer',
                  opacity: scanState.loading ? 0.6 : 1,
                }}
              >
                Escanear cuentas
              </button>
              <button
                onClick={() => setAuditMethod('manual')}
                disabled={scanState.loading}
                style={{
                  padding: '10px 20px',
                  backgroundColor: auditMethod === 'manual' ? '#2563eb' : '#e5e7eb',
                  color: auditMethod === 'manual' ? 'white' : '#333',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '14px',
                  fontWeight: '500',
                  cursor: scanState.loading ? 'not-allowed' : 'pointer',
                  opacity: scanState.loading ? 0.6 : 1,
                }}
              >
                Importar enlaces
              </button>
            </div>

            {/* Progress Display */}
            {scanState.loading && (
              <div style={{
                marginBottom: '30px',
                padding: '20px',
                backgroundColor: '#f0f9ff',
                border: '1px solid #0284c7',
                borderRadius: '4px',
              }}>
                <p style={{ margin: '0 0 12px 0', fontSize: '16px', fontWeight: '500', color: '#0284c7' }}>
                  {scanState.progressMessage || 'Auditoría en progreso...'}
                </p>
                {scanState.progress !== undefined && (
                  <div style={{
                    width: '100%',
                    height: '8px',
                    backgroundColor: '#e0e7ff',
                    borderRadius: '4px',
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      width: `${scanState.progress}%`,
                      height: '100%',
                      backgroundColor: '#0284c7',
                      transition: 'width 0.3s ease',
                    }} />
                  </div>
                )}
                <p style={{ margin: '12px 0 0 0', fontSize: '12px', color: '#666' }}>
                  {scanState.progress !== undefined ? `${scanState.progress}%` : 'Iniciando...'}
                </p>
              </div>
            )}

            {/* Form */}
            {!scanState.loading && (
              <>
                {auditMethod === 'auto' && (
                  <AuditForm onSubmit={handleScanSubmit} loading={scanState.loading} error={scanState.error} />
                )}
                {auditMethod === 'manual' && (
                  <ManualLinksForm onSubmit={handleScanSubmit} loading={scanState.loading} error={scanState.error} />
                )}
              </>
            )}
          </>
        )}
        {scanState.result && <AuditResult result={scanState.result} onNewScan={() => {
          setScanState({ loading: false, result: null, error: null })
          setAuditMethod('auto')
        }} />}
      </main>

      <footer className="app-footer">
        <p>Backend: <span className="status-ok">Conectado</span></p>
      </footer>
    </div>
  )
}

export default App
