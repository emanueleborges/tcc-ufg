import type { ChatSettings, IndexStatusResponse, ModelOut } from '../api/types'

interface Props {
  model: string
  onModelChange: (value: string) => void
  models: ModelOut[]
  settings: ChatSettings
  onSettingsChange: (patch: Partial<ChatSettings>) => void
  petitionName: string | null
  onClearPetition: () => void
  apiOnline: boolean | null
  indexStatus: IndexStatusResponse | null
  busyAction: 'rebuild' | 'scrape' | null
  busyPercent: number | null
  actionMessage: string | null
  onRebuildIndex: () => void
  onScrape: () => void
  onClose?: () => void
}

export function Sidebar({
  model,
  onModelChange,
  models,
  settings,
  onSettingsChange,
  petitionName,
  onClearPetition,
  apiOnline,
  indexStatus,
  busyAction,
  busyPercent,
  actionMessage,
  onRebuildIndex,
  onScrape,
  onClose,
}: Props) {
  const ollamaModels = models.filter((m) => m.owned_by === 'ollama')

  return (
    <aside className="sidebar" id="app-sidebar">
      <div className="sidebar-top">
        <div className="brand">
          <p className="brand-mark">Crítico Jurídico</p>
          <p className="brand-sub">Assistente RAG · Ollama · Web</p>
        </div>
        {onClose && (
          <button
            type="button"
            className="sidebar-close"
            onClick={onClose}
            aria-label="Fechar menu"
          >
            ✕
          </button>
        )}
      </div>

      <div className="sidebar-block">
        <label htmlFor="model">Modelo Ollama</label>
        <input
          id="model"
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          placeholder="llama3.1:8b"
          list="model-suggestions"
        />
        <datalist id="model-suggestions">
          {ollamaModels.map((m) => (
            <option key={m.id} value={m.id} />
          ))}
        </datalist>
      </div>

      <div className="sidebar-block">
        <p className="sidebar-label">Configurações do chat</p>

        <label className="range-label" htmlFor="ragTopK">
          Trechos do RAG: <strong>{settings.ragTopK}</strong>
        </label>
        <input
          id="ragTopK"
          type="range"
          min={2}
          max={12}
          value={settings.ragTopK}
          onChange={(e) => onSettingsChange({ ragTopK: Number(e.target.value) })}
        />

        <label className="range-label" htmlFor="webMaxResults">
          Resultados da internet: <strong>{settings.webMaxResults}</strong>
        </label>
        <input
          id="webMaxResults"
          type="range"
          min={2}
          max={10}
          value={settings.webMaxResults}
          onChange={(e) =>
            onSettingsChange({ webMaxResults: Number(e.target.value) })
          }
        />

        <label className="check-label">
          <input
            type="checkbox"
            checked={settings.useInternetOnRecreate}
            onChange={(e) =>
              onSettingsChange({ useInternetOnRecreate: e.target.checked })
            }
          />
          Usar internet ao recriar petição
        </label>
      </div>

      <div className="sidebar-block">
        <p className="sidebar-label">Petição anexada</p>
        {petitionName ? (
          <div className="petition-card">
            <p>{petitionName}</p>
            <button type="button" className="link-btn" onClick={onClearPetition}>
              Remover
            </button>
          </div>
        ) : (
          <p className="muted">Nenhuma. Use o botão + no chat.</p>
        )}
      </div>

      <div className="sidebar-block">
        <p className="sidebar-label">Base RAG</p>
        <div className="index-status">
          {indexStatus == null ? (
            <p className="muted">Carregando status…</p>
          ) : indexStatus.exists ? (
            <p>
              Índice ativo
              {indexStatus.documents != null && (
                <>
                  : <strong>{indexStatus.documents}</strong> docs
                </>
              )}
              {indexStatus.chunks != null && (
                <>
                  {' '}
                  · <strong>{indexStatus.chunks}</strong> chunks
                </>
              )}
            </p>
          ) : (
            <p className="muted">Índice ainda não criado.</p>
          )}
        </div>
        <div className="sidebar-actions">
          <button
            type="button"
            className="ghost-btn"
            disabled={busyAction !== null}
            onClick={onRebuildIndex}
          >
            {busyAction === 'rebuild'
              ? `Recriando… ${busyPercent ?? 0}%`
              : 'Recriar índice RAG'}
          </button>
          <button
            type="button"
            className="ghost-btn"
            disabled={busyAction !== null}
            onClick={onScrape}
          >
            {busyAction === 'scrape'
              ? `Baixando… ${busyPercent ?? 0}%`
              : 'Baixar Petições Públicas'}
          </button>
        </div>
        {busyAction && busyPercent != null && (
          <div className="progress-track" aria-hidden>
            <div className="progress-fill" style={{ width: `${busyPercent}%` }} />
          </div>
        )}
        {actionMessage && <p className="action-message">{actionMessage}</p>}
      </div>

      <div className="sidebar-block sources-block">
        <p className="sidebar-label">Fontes</p>
        <ul className="source-list">
          <li>📚 Base RAG</li>
          <li>🤖 Ollama local</li>
          <li>🌐 DuckDuckGo</li>
          <li>⚖️ Análise de petição</li>
        </ul>
      </div>

      <div className="sidebar-footer">
        <div className="api-brand" aria-hidden="true">
          <svg
            className="api-brand-icon"
            viewBox="0 0 72 72"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient
                id="api-brand-grad"
                className="api-brand-grad"
                x1="0"
                y1="0"
                x2="72"
                y2="72"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stopColor="var(--composer-border-1)" />
                <stop offset="25%" stopColor="var(--composer-border-3)" />
                <stop offset="50%" stopColor="var(--composer-border-2)" />
                <stop offset="75%" stopColor="var(--composer-border-4)" />
                <stop offset="100%" stopColor="var(--composer-border-1)" />
                <animateTransform
                  attributeName="gradientTransform"
                  type="rotate"
                  from="0 36 36"
                  to="360 36 36"
                  dur="5s"
                  repeatCount="indefinite"
                />
              </linearGradient>
              <filter
                id="api-brand-glow"
                x="-20%"
                y="-20%"
                width="140%"
                height="140%"
              >
                <feGaussianBlur stdDeviation="1.1" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <g fill="url(#api-brand-grad)" filter="url(#api-brand-glow)">
              <rect x="4" y="26" width="64" height="3.2" />
              <path
                d="M8 29.2 L16 46 M8 29.2 L0 46"
                fill="none"
                stroke="url(#api-brand-grad)"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path d="M0 46 A8 7.5 0 0 0 16 46 Z" />
              <path
                d="M64 29.2 L72 46 M64 29.2 L56 46"
                fill="none"
                stroke="url(#api-brand-grad)"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path d="M56 46 A8 7.5 0 0 0 72 46 Z" />
              <rect x="26" y="16" width="20" height="20" />
              <rect x="29" y="12.2" width="3.2" height="3.8" />
              <rect x="34.4" y="12.2" width="3.2" height="3.8" />
              <rect x="39.8" y="12.2" width="3.2" height="3.8" />
              <rect x="22.2" y="19.5" width="3.8" height="3.2" />
              <rect x="22.2" y="26" width="3.8" height="3.2" />
              <rect x="46" y="19.5" width="3.8" height="3.2" />
              <rect x="46" y="26" width="3.8" height="3.2" />
              <rect x="29" y="36" width="3.2" height="3.8" />
              <rect x="39.8" y="36" width="3.2" height="3.8" />
              <rect x="33.4" y="36" width="5.2" height="18" />
              <path d="M27 54 L45 54 L42.2 58.2 L29.8 58.2 Z" />
              <rect x="20" y="58.2" width="32" height="3.6" />
            </g>
            <text
              x="36"
              y="30.2"
              textAnchor="middle"
              fill="var(--sidebar)"
              fontSize="11.5"
              fontWeight="700"
              fontFamily="var(--font-body), system-ui, sans-serif"
              letterSpacing="0.02em"
            >
              AI
            </text>
          </svg>
        </div>
        <p
          className={`api-status ${apiOnline === true ? 'ok' : apiOnline === false ? 'bad' : ''}`}
        >
          API {apiOnline === true ? 'online' : apiOnline === false ? 'offline' : '…'}
        </p>
      </div>
    </aside>
  )
}
