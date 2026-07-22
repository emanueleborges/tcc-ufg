import { useCallback, useEffect, useRef, useState } from 'react'
import {
  checkHealth,
  getIndexStatus,
  listModels,
  rebuildIndex,
  scrapePetitions,
} from './api/client'
import type { IndexStatusResponse, ModelOut } from './api/types'
import { ChatBubble } from './components/ChatBubble'
import { ChatInput } from './components/ChatInput'
import { Sidebar } from './components/Sidebar'
import { useChat } from './hooks/useChat'
import './App.css'

export default function App() {
  const chat = useChat()
  const [apiOnline, setApiOnline] = useState<boolean | null>(null)
  const [models, setModels] = useState<ModelOut[]>([])
  const [indexStatus, setIndexStatus] = useState<IndexStatusResponse | null>(null)
  const [busyAction, setBusyAction] = useState<'rebuild' | 'scrape' | null>(null)
  const [busyPercent, setBusyPercent] = useState<number | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
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
        const ollama = res.data.find((m) => m.owned_by === 'ollama')
        if (ollama) chat.setModel(ollama.id)
      })
      .catch(() => setModels([]))

    refreshIndexStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- só no mount
  }, [refreshIndexStatus])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.messages, chat.isLoading])

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
      setActionMessage(
        `${result.message} Total: ${result.total_documents} documentos.`,
      )
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
    <div className="app-shell">
      <Sidebar
        model={chat.model}
        onModelChange={chat.setModel}
        models={models}
        settings={chat.settings}
        onSettingsChange={chat.updateSettings}
        petitionName={chat.petitionName}
        onClearPetition={chat.clearPetition}
        onClearChat={chat.clearChat}
        apiOnline={apiOnline}
        indexStatus={indexStatus}
        busyAction={busyAction}
        busyPercent={busyPercent}
        actionMessage={actionMessage}
        onRebuildIndex={handleRebuildIndex}
        onScrape={handleScrape}
      />

      <main className="chat-main">
        <header className="chat-header">
          <h1>Conversa</h1>
          <p>Roteamento automático entre RAG, Ollama e Internet</p>
        </header>

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
        />
      </main>
    </div>
  )
}
