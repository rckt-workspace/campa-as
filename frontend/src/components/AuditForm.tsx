import { useState } from 'react'
import '../styles/form.css'

function formatLocalDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

interface TargetAccount {
  username: string
  label: string
}

interface AuditFormProps {
  onSubmit: (data: any) => void
  loading: boolean
  error: string | null
}

export default function AuditForm({ onSubmit, loading, error }: AuditFormProps) {
  const today = formatLocalDate(new Date())

  const [master, setMaster] = useState({ username: '@newbodycol', label: 'Colombia' })
  const [targets, setTargets] = useState<TargetAccount[]>([
    { username: '@newbodyclubmedellin', label: 'Medellín' },
    { username: '@newbodyclubantienvejecimientoc', label: 'Antienvejecimiento' },
    { username: '@newbodybaq', label: 'Barranquilla' },
  ])
  const [scanMode, setScanMode] = useState<'date' | 'count'>('date')
  const [limit, setLimit] = useState(20)
  const [fromDate, setFromDate] = useState('2025-01-01')
  const [toDate, setToDate] = useState(today)
  const [validationError, setValidationError] = useState<string | null>(null)

  const handleAddTarget = () => {
    setTargets([...targets, { username: '', label: '' }])
  }

  const handleRemoveTarget = (idx: number) => {
    setTargets(targets.filter((_, i) => i !== idx))
  }

  const handleTargetChange = (idx: number, field: string, value: string) => {
    const newTargets = [...targets]
    newTargets[idx] = { ...newTargets[idx], [field]: value }
    setTargets(newTargets)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // Validate date mode
    if (scanMode === 'date') {
      if (toDate > today) {
        setValidationError('La fecha final no puede ser posterior a hoy.')
        return
      }
      if (fromDate > toDate) {
        setValidationError('La fecha inicial no puede ser posterior a la fecha final.')
        return
      }
    }

    setValidationError(null)

    const normalizeUsername = (user: string) => user.replace(/^@/, '').trim()

    const data: any = {
      master_username: normalizeUsername(master.username),
      master_label: master.label || 'Principal',
      targets: targets.map(t => ({
        username: normalizeUsername(t.username),
        label: t.label || normalizeUsername(t.username),
      })),
      scan_mode: scanMode,
    }

    if (scanMode === 'count') {
      data.limit = limit
    } else {
      data.from_date = fromDate
      data.to_date = toDate
    }

    onSubmit(data)
  }

  return (
    <form onSubmit={handleSubmit} className="audit-form">
      {error && <div className="error-card">{error}</div>}
      {validationError && <div className="error-card">{validationError}</div>}

      <section className="form-section">
        <h2>Cuenta Principal</h2>

        <div className="form-group">
          <label>Nombre</label>
          <input type="text" value={master.label} onChange={e => setMaster({ ...master, label: e.target.value })} placeholder="Colombia" />
        </div>

        <div className="form-group">
          <label>Usuario de Instagram</label>
          <input type="text" value={master.username} onChange={e => setMaster({ ...master, username: e.target.value })} placeholder="@newbodycol" />
        </div>
      </section>

      <section className="form-section">
        <h2>Cuentas a Comparar</h2>

        {targets.map((target, idx) => (
          <div key={idx} className="target-row">
            <input type="text" value={target.label} onChange={e => handleTargetChange(idx, 'label', e.target.value)} placeholder="Nombre" className="target-label" />
            <input type="text" value={target.username} onChange={e => handleTargetChange(idx, 'username', e.target.value)} placeholder="@usuario" className="target-username" />
            <button type="button" onClick={() => handleRemoveTarget(idx)} className="btn-remove">
              ✕
            </button>
          </div>
        ))}

        <button type="button" onClick={handleAddTarget} className="btn-secondary">
          + Agregar cuenta
        </button>
      </section>

      <section className="form-section">
        <h2>¿Cómo quieres realizar el escaneo?</h2>

        <div className="scan-mode-selector">
          <label className="scan-mode-option">
            <input
              type="radio"
              name="scanMode"
              value="date"
              checked={scanMode === 'date'}
              onChange={() => setScanMode('date')}
            />
            <span>📅 Por rango de fechas</span>
          </label>
          <label className="scan-mode-option">
            <input
              type="radio"
              name="scanMode"
              value="count"
              checked={scanMode === 'count'}
              onChange={() => setScanMode('count')}
            />
            <span># Por cantidad</span>
          </label>
        </div>

        {scanMode === 'count' ? (
          <div className="form-group">
            <label>Cantidad de publicaciones</label>
            <input
              type="number"
              value={limit}
              onChange={e => setLimit(Math.min(100, Math.max(1, parseInt(e.target.value) || 1)))}
              min="1"
              max="100"
            />
            <p className="help-text">Se revisarán las publicaciones más recientes de la cuenta principal.</p>
          </div>
        ) : (
          <div className="form-group">
            <div className="date-range">
              <div>
                <label>Desde</label>
                <input
                  type="date"
                  value={fromDate}
                  onChange={e => setFromDate(e.target.value)}
                />
              </div>
              <div>
                <label>Hasta</label>
                <input
                  type="date"
                  value={toDate}
                  max={today}
                  onChange={e => setToDate(e.target.value)}
                />
              </div>
            </div>
            <p className="help-text">Se analizarán las publicaciones de la cuenta principal dentro del período seleccionado.</p>
            {Math.abs(new Date(toDate).getTime() - new Date(fromDate).getTime()) > 90 * 24 * 60 * 60 * 1000 && (
              <p className="help-text warning">Este proceso puede tardar varios minutos dependiendo de la cantidad de publicaciones.</p>
            )}
          </div>
        )}
      </section>

      <button type="submit" disabled={loading} className="btn-primary btn-large">
        {loading ? (
          <>
            <span className="spinner"></span>Analizando Instagram...
          </>
        ) : (
          'Escanear contenido'
        )}
      </button>

      {loading && <p className="loading-message">Este proceso puede tardar cerca de un minuto.</p>}
    </form>
  )
}
