import { useState } from 'react'
import '../styles/result.css'

interface PostResult {
  original: {
    shortcode: string
    permalink: string
    published_at: string
    caption: string
    type: string
  }
  accounts: Array<{
    username: string
    label: string
    status: string
    similarity: number
    visual_similarity: number
    caption_similarity: number
    candidate_permalink: string | null
  }>
}

interface AuditResultProps {
  result: {
    scan_id: string
    status: string
    master_account: string
    master_posts: number
    regional_posts: { [key: string]: number }
    found_everywhere: number
    with_missing: number
    with_review: number
    missing_by_account: { [key: string]: number }
    review_by_account: { [key: string]: number }
    export_url: string
    posts: PostResult[]
    scan_mode?: string
    scan_period?: string
    warnings?: string[] | null
    unavailable_accounts?: string[]
    extraction_summary?: { [key: string]: any }
  }
  onNewScan: () => void
}

export default function AuditResult({ result, onNewScan }: AuditResultProps) {
  const [expandedPost, setExpandedPost] = useState<string | null>(null)

  const handleDownload = async () => {
    try {
      const response = await fetch(result.export_url)
      if (!response.ok) throw new Error('Error descargando archivo')

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `NewBody_Auditoria_${new Date().toISOString().split('T')[0]}.xlsx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      alert('Error al descargar el archivo')
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'found':
        return { icon: '✓', text: 'Match confirmado', color: '#2E7D32' }
      case 'review':
        return { icon: '⚠', text: 'Revisar candidato', color: '#E65100' }
      case 'missing':
        return { icon: '✕', text: 'No encontrado', color: '#C62828' }
      default:
        return { icon: '?', text: status, color: '#666' }
    }
  }

  const hasWarnings = result.warnings && result.warnings.length > 0

  return (
    <div className="audit-result">
      <div className="result-header">
        <h2>{hasWarnings ? '⚠ Auditoría Parcial' : 'Auditoría Completada'}</h2>
        {hasWarnings && result.warnings && (
          <div className="warning-box">
            <p><strong>Aviso:</strong> Instagram limitó el acceso a algunos datos durante el escaneo.</p>
            {result.warnings.map((warning: string, idx: number) => (
              <p key={idx} className="warning-item">• {warning}</p>
            ))}
          </div>
        )}
        {result.scan_period && (
          <p className="scan-period">
            <strong>Período auditado:</strong> {result.scan_period}
          </p>
        )}
        <button onClick={onNewScan} className="btn-secondary">
          Nueva auditoría
        </button>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-value">{result.master_posts}</div>
          <div className="metric-label">Publicaciones revisadas</div>
        </div>
        <div className="metric-card">
          <div className="metric-value" style={{ color: '#2E7D32' }}>{result.found_everywhere}</div>
          <div className="metric-label">Encontradas en todas</div>
        </div>
        <div className="metric-card">
          <div className="metric-value" style={{ color: '#C62828' }}>{result.with_missing}</div>
          <div className="metric-label">Con faltantes</div>
        </div>
        <div className="metric-card">
          <div className="metric-value" style={{ color: '#E65100' }}>{result.with_review}</div>
          <div className="metric-label">Para revisar</div>
        </div>
      </div>

      <div className="account-details">
        <h3>Desglose por cuenta</h3>
        {Object.entries(result.missing_by_account || {}).map(([account, missing]: [string, any]) => {
          // Use provided label or fallback to account
          const accountLabels: Record<string, string> = {
            "newbodyclubmedellin": "Medellín",
            "newbodyclubantienvejecimientoc": "Antienvejecimiento",
            "newbodybaq": "Barranquilla"
          }
          const displayLabel = accountLabels[account] || account
          const isUnavailable = result.unavailable_accounts?.includes(account)

          return (
            <div key={account} className="account-item">
              <strong>{displayLabel}</strong>
              <span className="account-stats">
                {isUnavailable
                  ? <span style={{ color: '#f59e0b' }}>Sin cobertura · No concluyente</span>
                  : <>Faltantes: {missing} · Revisar: {result.review_by_account[account] || 0}</>
                }
              </span>
            </div>
          )
        })}
      </div>

      {result.posts && result.posts.length > 0 && (
        <div className="posts-section">
          <h3>Detalle por publicación</h3>
          {(result.posts as PostResult[]).map((post) => (
            <div key={post.original.shortcode} className="post-card">
              <div className="post-header" onClick={() => setExpandedPost(expandedPost === post.original.shortcode ? null : post.original.shortcode)}>
                <div className="post-date">{new Date(post.original.published_at).toLocaleDateString()}</div>
                <div className="post-caption">{post.original.caption.substring(0, 80)}...</div>
                <span className="post-type">{post.original.type}</span>
              </div>

              {expandedPost === post.original.shortcode && (
                <div className="post-details">
                  <div className="post-action">
                    <a href={post.original.permalink} target="_blank" rel="noopener noreferrer" className="link-button">
                      Ver original
                    </a>
                  </div>

                  <div className="accounts-list">
                    {post.accounts.map((account) => {
                      const badge = getStatusBadge(account.status)
                      return (
                        <div key={account.username} className="account-match">
                          <div className="match-header">
                            <span className="account-label">{account.label}</span>
                            <span className="status-badge" style={{ color: badge.color }}>
                              {badge.icon} {badge.text}
                            </span>
                            <span className="similarity">Similitud: {account.similarity}%</span>
                          </div>

                          {account.status !== 'missing' && (
                            <div className="match-details">
                              <small>Visual: {account.visual_similarity}% | Caption: {account.caption_similarity}%</small>
                            </div>
                          )}

                          <div className="match-action">
                            {account.status === 'found' && account.candidate_permalink && (
                              <a href={account.candidate_permalink} target="_blank" rel="noopener noreferrer" className="link-button">
                                Ver match
                              </a>
                            )}
                            {account.status === 'review' && account.candidate_permalink && (
                              <a href={account.candidate_permalink} target="_blank" rel="noopener noreferrer" className="link-button">
                                Ver candidato
                              </a>
                            )}
                            {account.status === 'missing' && (
                              <a href={post.original.permalink} target="_blank" rel="noopener noreferrer" className="link-button">
                                Ver original para publicar
                              </a>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <button onClick={handleDownload} className="btn-primary btn-large">
        Descargar Excel
      </button>
    </div>
  )
}
