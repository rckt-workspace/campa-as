import { useState } from 'react'
import AuditForm from './components/AuditForm'
import ManualLinksForm from './components/ManualLinksForm'
import AuditResult from './components/AuditResult'
import './App.css'

interface ScanState {
  loading: boolean
  result: any | null
  error: string | null
}

function App() {
  const [auditMethod, setAuditMethod] = useState<'auto' | 'manual'>('auto')
  const [scanState, setScanState] = useState<ScanState>({
    loading: false,
    result: null,
    error: null,
  })

  const handleScanSubmit = async (formData: any) => {
    setScanState({ loading: true, result: null, error: null })

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
          // If JSON parsing fails, use status text
          errorMessage = response.statusText || errorMessage
        }
        throw new Error(errorMessage)
      }

      const result = await response.json()
      setScanState({ loading: false, result, error: null })
    } catch (err) {
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
                style={{
                  padding: '10px 20px',
                  backgroundColor: auditMethod === 'auto' ? '#2563eb' : '#e5e7eb',
                  color: auditMethod === 'auto' ? 'white' : '#333',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '14px',
                  fontWeight: '500',
                  cursor: 'pointer',
                }}
              >
                Escanear cuentas
              </button>
              <button
                onClick={() => setAuditMethod('manual')}
                style={{
                  padding: '10px 20px',
                  backgroundColor: auditMethod === 'manual' ? '#2563eb' : '#e5e7eb',
                  color: auditMethod === 'manual' ? 'white' : '#333',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '14px',
                  fontWeight: '500',
                  cursor: 'pointer',
                }}
              >
                Importar enlaces
              </button>
            </div>

            {/* Form */}
            {auditMethod === 'auto' && (
              <AuditForm onSubmit={handleScanSubmit} loading={scanState.loading} error={scanState.error} />
            )}
            {auditMethod === 'manual' && (
              <ManualLinksForm onSubmit={handleScanSubmit} loading={scanState.loading} error={scanState.error} />
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
