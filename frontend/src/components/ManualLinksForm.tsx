import { useState } from 'react'
import '../styles/form.css'

interface LinksData {
  [account: string]: string
}

interface ManualLinksFormProps {
  onSubmit: (data: any) => void
  loading: boolean
  error: string | null
}

const ACCOUNTS = [
  { username: 'newbodycol', label: 'Colombia' },
  { username: 'newbodyclubmedellin', label: 'Medellín' },
  { username: 'newbodyclubantienvejecimientoc', label: 'Antienvejecimiento' },
  { username: 'newbodybaq', label: 'Barranquilla' },
]

function parseLinks(text: string): string[] {
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0 && (line.includes('/p/') || line.includes('/reel/')))
}

function countValidLinks(text: string): number {
  return parseLinks(text).length
}

export default function ManualLinksForm({ onSubmit, loading, error }: ManualLinksFormProps) {
  const [linksData, setLinksData] = useState<LinksData>(
    ACCOUNTS.reduce((acc, acc_info) => {
      acc[acc_info.username] = ''
      return acc
    }, {} as LinksData)
  )
  const [validationError, setValidationError] = useState<string | null>(null)

  const handleLinksChange = (username: string, value: string) => {
    setLinksData(prev => ({
      ...prev,
      [username]: value,
    }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const masterUsername = ACCOUNTS[0].username
    const masterLinks = parseLinks(linksData[masterUsername])

    if (masterLinks.length === 0) {
      setValidationError('Debes proporcionar al menos un enlace para la cuenta principal (Colombia).')
      return
    }

    setValidationError(null)

    const targetAccounts = ACCOUNTS.slice(1)
    const data = {
      master: {
        username: masterUsername,
        label: ACCOUNTS[0].label,
        links: masterLinks,
      },
      targets: targetAccounts.map(account => ({
        username: account.username,
        label: account.label,
        links: parseLinks(linksData[account.username]),
      })),
    }

    onSubmit(data)
  }

  return (
    <form onSubmit={handleSubmit} className="audit-form">
      <h2>Importar Enlaces</h2>
      <p style={{ color: '#666', fontSize: '14px', marginBottom: '20px' }}>
        Pega URLs de Instagram, una por línea. Soporta /p/ y /reel/.
      </p>

      {validationError && (
        <div style={{
          backgroundColor: '#fee',
          border: '1px solid #f99',
          color: '#933',
          padding: '12px',
          borderRadius: '4px',
          marginBottom: '20px',
        }}>
          {validationError}
        </div>
      )}

      {error && (
        <div style={{
          backgroundColor: '#fee',
          border: '1px solid #f99',
          color: '#933',
          padding: '12px',
          borderRadius: '4px',
          marginBottom: '20px',
        }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
        {ACCOUNTS.map((account, idx) => {
          const isMaster = idx === 0
          const linkCount = countValidLinks(linksData[account.username])

          return (
            <div key={account.username} style={{
              border: isMaster ? '2px solid #2563eb' : '1px solid #ddd',
              borderRadius: '8px',
              padding: '16px',
              backgroundColor: isMaster ? '#f0f7ff' : '#fafafa',
            }}>
              <h3 style={{ margin: '0 0 4px 0', fontSize: '16px' }}>
                {account.label}
              </h3>
              <p style={{ margin: '0 0 12px 0', color: '#666', fontSize: '14px' }}>
                @{account.username}
              </p>

              <textarea
                value={linksData[account.username]}
                onChange={(e) => handleLinksChange(account.username, e.target.value)}
                placeholder="https://www.instagram.com/p/ABC123/&#10;https://www.instagram.com/reel/XYZ789/"
                style={{
                  width: '100%',
                  height: '150px',
                  padding: '10px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  resize: 'vertical',
                }}
                disabled={loading}
              />

              <p style={{
                margin: '8px 0 0 0',
                fontSize: '13px',
                color: '#666',
              }}>
                {linkCount} enlace{linkCount !== 1 ? 's' : ''} válido{linkCount !== 1 ? 's' : ''}
              </p>

              {isMaster && (
                <p style={{
                  margin: '4px 0 0 0',
                  fontSize: '12px',
                  color: '#2563eb',
                  fontWeight: '500',
                }}>
                  Requerido
                </p>
              )}
            </div>
          )
        })}
      </div>

      <button
        type="submit"
        disabled={loading}
        style={{
          width: '100%',
          padding: '12px',
          backgroundColor: loading ? '#ccc' : '#2563eb',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          fontSize: '16px',
          fontWeight: '500',
          cursor: loading ? 'not-allowed' : 'pointer',
        }}
      >
        {loading ? 'Procesando publicaciones...' : 'Procesar y auditar enlaces'}
      </button>
    </form>
  )
}
