import { useCallback, useEffect, useRef, useState } from 'react'
import {
  checkHealth,
  getIndexStatus,
  listModels,
  listPersonas,
  rebuildIndex,
  scrapePetitions,
} from './api/client'
import type { IndexStatusResponse, ModelOut, PersonaOut } from './api/types'
import { ChatBubble } from './components/ChatBubble'
import { ChatInput } from './components/ChatInput'
import { DashboardView } from './components/DashboardView'
import { Sidebar } from './components/Sidebar'
import { ThemeToggle } from './components/ThemeToggle'
import { useChat } from './hooks/useChat'
import { useTheme } from './hooks/useTheme'
import './App.css'

export default function App() {
  const chat = useChat()
  const { theme, toggleTheme } = useTheme()
  const [apiOnline, setApiOnline] = useState<boolean | null>(null)
  const [models, setModels] = useState<ModelOut[]>([])
  const [personas, setPersonas] = useState<PersonaOut[]>([])
  const [indexStatus, setIndexStatus] = useState<IndexStatusResponse | null>(null)
  const [busyAction, setBusyAction] = useState<'rebuild' | 'scrape' | null>(null)
  const [busyPercent, setBusyPercent] = useState<number | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [view, setView] = useState<'chat' | 'dashboard'>('chat')
  const bottomRef = useRef<HTMLDivElement>(null)

  const refreshIndexStatus = useCallback(async () => {
    try {
      const status = await getIndexStatus()
      setIndexStatus(status)
    } catch {
      setIndexStatus(null)
    }
  }, [])

  useEffect(() => {
    checkHealth()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false))

    listModels()
      .then((res) => {
        setModels(res.data)
        const ollamaModels = res.data.filter((m) => m.owned_by === 'ollama')
        const preferred =
          ollamaModels.find((m) => m.id === 'llama3.1:8b') ?? ollamaModels[0]
        if (preferred) chat.setModel(preferred.id)
      })
      .catch(() => setModels([]))

    listPersonas()
      .then((res) => {
        setPersonas(res.data)
        if (res.default_id) {
          chat.updateSettings({ personaId: res.default_id })
        }
      })
      .catch(() => setPersonas([]))

    refreshIndexStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- só no mount
  }, [refreshIndexStatus])

  useEffect(() => {
    if (view !== 'chat') return
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.messages, chat.isLoading, view])

  useEffect(() => {
    if (!sidebarOpen) return

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setSidebarOpen(false)
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [sidebarOpen])

  async function handleRebuildIndex() {
    setBusyAction('rebuild')
    setBusyPercent(0)
    setActionMessage(null)
    try {
      const result = await rebuildIndex((percent, message) => {
        setBusyPercent(percent)
        if (message) setActionMessage(message)
      })
      setBusyPercent(100)
      setActionMessage(
        `Índice atualizado: ${result.documents} docs · ${result.chunks} chunks.`,
      )
      await refreshIndexStatus()
    } catch (err) {
      setActionMessage(
        err instanceof Error ? err.message : 'Falha ao recriar índice.',
      )
    } finally {
      setBusyAction(null)
      setBusyPercent(null)
    }
  }

  async function handleScrape() {
    setBusyAction('scrape')
    setBusyPercent(0)
    setActionMessage(null)
    try {
      const result = await scrapePetitions((percent, message) => {
        setBusyPercent(percent)
        if (message) setActionMessage(message)
      })
      setBusyPercent(100)
      setActionMessage(result.message)
    } catch (err) {
      setActionMessage(
        err instanceof Error ? err.message : 'Falha ao baixar PDFs.',
      )
    } finally {
      setBusyAction(null)
      setBusyPercent(null)
    }
  }

  return (
    <div className={`app-shell${sidebarOpen ? ' is-sidebar-open' : ''}`}>
      <button
        type="button"
        className="sidebar-backdrop"
        aria-label="Fechar menu"
        tabIndex={sidebarOpen ? 0 : -1}
        onClick={() => setSidebarOpen(false)}
      />
      <Sidebar
        model={chat.model}
        onModelChange={chat.setModel}
        models={models}
        settings={chat.settings}
        onSettingsChange={chat.updateSettings}
        petitionName={chat.petitionName}
        onClearPetition={chat.clearPetition}
        apiOnline={apiOnline}
        indexStatus={indexStatus}
        busyAction={busyAction}
        busyPercent={busyPercent}
        actionMessage={actionMessage}
        onRebuildIndex={handleRebuildIndex}
        onScrape={handleScrape}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="chat-main">
        <header className="chat-header">
          <button
            type="button"
            className="sidebar-toggle"
            aria-label="Abrir configurações"
            aria-expanded={sidebarOpen}
            aria-controls="app-sidebar"
            onClick={() => setSidebarOpen(true)}
          >
            ☰
          </button>
          <div className="chat-header-copy">
            <h1 className="chat-title">
              {view === 'chat' ? 'Chat IA' : 'Tempo de leitura'}
            </h1>
            <p>
              {view === 'chat'
                ? 'Roteamento automático entre RAG, Ollama e Internet'
                : 'Registro do tempo humano de leitura × protótipo (TCC)'}
            </p>
          </div>
          <div className="chat-header-actions">
            <button
              type="button"
              className="new-chat-btn"
              onClick={() =>
                setView((current) =>
                  current === 'chat' ? 'dashboard' : 'chat',
                )
              }
            >
              {view === 'chat' ? 'Tempo de leitura' : 'Chat'}
            </button>
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
            {view === 'chat' && (
              <button
                type="button"
                className="new-chat-btn"
                onClick={chat.clearChat}
              >
                Nova conversa
              </button>
            )}
          </div>
        </header>

        {view === 'dashboard' ? (
          <section className="dashboard-scroll">
            <DashboardView />
          </section>
        ) : (
          <>
            {chat.petitionName && (
              <div className="petition-banner">
                <span>
                  📎 Petição ativa: <strong>{chat.petitionName}</strong>
                </span>
                <button
                  type="button"
                  className="link-btn"
                  onClick={chat.clearPetition}
                >
                  Remover
                </button>
              </div>
            )}

            <section className="message-list" aria-live="polite">
              {chat.messages.map((message) => (
                <ChatBubble key={message.id} message={message} />
              ))}
              {chat.isLoading && (
                <div className="typing">
                  <span />
                  <span />
                  <span />
                </div>
              )}
              <div ref={bottomRef} />
            </section>

            {chat.error && <div className="error-banner">{chat.error}</div>}

            <ChatInput
              disabled={chat.isLoading}
              pendingFile={chat.pendingFile}
              onFileChange={chat.setPendingFile}
              onSend={chat.sendMessage}
              personas={personas}
              personaId={chat.settings.personaId}
              onPersonaChange={(personaId) => chat.updateSettings({ personaId })}
            />
          </>
        )}
      </main>
    </div>
  )
}
