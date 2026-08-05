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
}: Props) {
  const ollamaModels = models.filter((m) => m.owned_by === 'ollama')

  return (
    <aside className="sidebar">
      <div className="brand">
        <p className="brand-mark">Crítico Jurídico</p>
        <p className="brand-sub">Assistente RAG · Ollama · Web</p>
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
        <p
          className={`api-status ${apiOnline === true ? 'ok' : apiOnline === false ? 'bad' : ''}`}
        >
          API {apiOnline === true ? 'online' : apiOnline === false ? 'offline' : '…'}
        </p>
      </div>
    </aside>
  )
}
