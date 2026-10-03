import { useState } from 'react'
import AuditForm from './components/AuditForm'
import AuditResult from './components/AuditResult'
import './App.css'

interface ScanState {
  loading: boolean
  result: any | null
  error: string | null
}

function App() {
  const [scanState, setScanState] = useState<ScanState>({
    loading: false,
    result: null,
    error: null,
  })

  const handleScanSubmit = async (formData: any) => {
    setScanState({ loading: true, result: null, error: null })

    try {
      const response = await fetch('/api/scans', {
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
        {!scanState.result && <AuditForm onSubmit={handleScanSubmit} loading={scanState.loading} error={scanState.error} />}
        {scanState.result && <AuditResult result={scanState.result} onNewScan={() => setScanState({ loading: false, result: null, error: null })} />}
      </main>

      <footer className="app-footer">
        <p>Backend: <span className="status-ok">Conectado</span></p>
      </footer>
    </div>
  )
}

export default App
