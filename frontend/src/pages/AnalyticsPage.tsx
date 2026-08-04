import type { LogEntry, Metrics } from '../types'

type AnalyticsPageProps = {
  metrics: Metrics | null
  visibleLogs: LogEntry[]
  logLevel: string
  logQuery: string
  onLogLevelChange: (value: string) => void
  onLogQueryChange: (value: string) => void
  onRefresh: () => void
}

function formatUptime(seconds?: number) {
  if (seconds === undefined) return '—'
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

export function AnalyticsPage({
  metrics,
  visibleLogs,
  logLevel,
  logQuery,
  onLogLevelChange,
  onLogQueryChange,
  onRefresh,
}: AnalyticsPageProps) {
  const latestLog = visibleLogs.length ? visibleLogs[visibleLogs.length - 1] : null

  return (
    <section className="analytics-grid">
      <article className="stat-card">
        <p className="eyebrow">PROVEDOR</p>
        <strong>{metrics?.provider || '—'}</strong>
        <span>ativo</span>
      </article>
      <article className="stat-card">
        <p className="eyebrow">REQUISIÇÕES</p>
        <strong>{metrics?.total_requests ?? 0}</strong>
        <span>desde o início</span>
      </article>
      <article className="stat-card">
        <p className="eyebrow">ERROS</p>
        <strong>{metrics?.total_errors ?? 0}</strong>
        <span>registrados</span>
      </article>
      <article className="stat-card">
        <p className="eyebrow">UPTIME</p>
        <strong>{formatUptime(metrics?.uptime_seconds)}</strong>
        <span>servidor local</span>
      </article>
      <article className="stat-card">
        <p className="eyebrow">CPU</p>
        <strong>{metrics?.cpu !== undefined ? `${Math.round(metrics.cpu)}%` : '—'}</strong>
        <div className="metric-bar">
          <div className="metric-bar-fill" style={{ width: `${Math.min(100, metrics?.cpu ?? 0)}%` }} />
        </div>
      </article>
      <article className="stat-card">
        <p className="eyebrow">RAM</p>
        <strong>
          {metrics?.ram_used !== undefined && metrics?.ram_total !== undefined
            ? `${metrics.ram_used} / ${metrics.ram_total} GB`
            : metrics?.ram_percent !== undefined
              ? `${Math.round(metrics.ram_percent)}%`
              : '—'}
        </strong>
        <div className="metric-bar">
          <div className="metric-bar-fill metric-bar-ram" style={{ width: `${Math.min(100, metrics?.ram_percent ?? 0)}%` }} />
        </div>
      </article>
      <article className="analytics-panel">
        <p className="eyebrow">FERRAMENTAS EXECUTADAS</p>
        {Object.entries(metrics?.tools_executed || {}).length ? (
          Object.entries(metrics?.tools_executed || {}).map(([name, count]) => (
            <p className="tool-row" key={name}>
              {name}
              <b>{count}</b>
            </p>
          ))
        ) : (
          <p className="empty-state">Ainda não há ferramentas registradas.</p>
        )}
      </article>
      <article className="analytics-panel wide">
        <div className="section-heading">
          <p className="eyebrow">LOGS AO VIVO</p>
          <div className="analytics-controls">
            <select aria-label="Nível do log" value={logLevel} onChange={event => onLogLevelChange(event.target.value)}>
              <option value="">Todos</option>
              <option value="DEBUG">Debug</option>
              <option value="INFO">Info</option>
              <option value="WARNING">Avisos</option>
              <option value="ERROR">Erros</option>
            </select>
            <input
              aria-label="Pesquisar logs"
              value={logQuery}
              onChange={event => onLogQueryChange(event.target.value)}
              placeholder="Filtrar logs"
            />
            <button type="button" onClick={onRefresh}>
              Atualizar
            </button>
          </div>
        </div>
        <div className="log-live-region" aria-live="polite" aria-relevant="additions text">
          {latestLog && (
            <span className="sr-only">
              Último log: {latestLog.level || 'INFO'} — {latestLog.message}
            </span>
          )}
          {visibleLogs.length ? (
            visibleLogs
              .slice(-50)
              .reverse()
              .map((log, index) => (
                <p className="log-row" key={`${log.timestamp}-${index}`}>
                  <span className={`log-${(log.level || 'info').toLowerCase()}`}>{log.level || 'INFO'}</span>
                  <b>{log.component || 'Jarvis'}</b>
                  {log.message}
                </p>
              ))
          ) : (
            <p className="empty-state">Nenhum log disponível.</p>
          )}
        </div>
      </article>
    </section>
  )
}
