import { useCallback, useState } from 'react'
import { sendChat, uploadPetition } from '../api/client'
import type { ChatMessageIn, ChatSettings, UiMessage } from '../api/types'

const WELCOME: UiMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    'Olá. Sou o **Crítico Jurídico Inteligente**.\n\n' +
    'Pergunte sobre dano moral, petições ou jurisprudência — eu roteio automaticamente entre **RAG**, **Ollama** e **Internet**, e mostro a fonte da resposta.\n\n' +
    'Anexe um PDF e peça *“analise minha petição”* ou *“recrie esta petição”*.',
  source: {
    id: 'system',
    label: 'Sistema',
    icon: 'ℹ️',
  },
}

const DEFAULT_SETTINGS: ChatSettings = {
  ragTopK: 8,
  webMaxResults: 5,
  useInternetOnRecreate: true,
}

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

export function useChat() {
  const [messages, setMessages] = useState<UiMessage[]>([WELCOME])
  const [model, setModel] = useState('llama3:latest')
  const [settings, setSettings] = useState<ChatSettings>(DEFAULT_SETTINGS)
  const [petitionId, setPetitionId] = useState<string | null>(null)
  const [petitionName, setPetitionName] = useState<string | null>(null)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const clearPetition = useCallback(() => {
    setPetitionId(null)
    setPetitionName(null)
    setPendingFile(null)
  }, [])

  const clearChat = useCallback(() => {
    setMessages([WELCOME])
    setError(null)
    setPetitionId(null)
    setPetitionName(null)
    setPendingFile(null)
  }, [])

  const updateSettings = useCallback((patch: Partial<ChatSettings>) => {
    setSettings((prev) => ({ ...prev, ...patch }))
  }, [])

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if ((!trimmed && !pendingFile) || isLoading) return

      setError(null)
      setIsLoading(true)

      let activePetitionId = petitionId
      let attachmentName: string | undefined

      try {
        if (pendingFile) {
          const uploaded = await uploadPetition(pendingFile)
          activePetitionId = uploaded.petition_id
          attachmentName = uploaded.file_name
          setPetitionId(uploaded.petition_id)
          setPetitionName(uploaded.file_name)
          setPendingFile(null)
        }

        const userContent =
          trimmed ||
          (attachmentName
            ? `_Anexei a petição **${attachmentName}**._`
            : '')

        const userMsg: UiMessage = {
          id: uid(),
          role: 'user',
          content: userContent,
          attachmentName,
        }

        const historyForApi: ChatMessageIn[] = [
          ...messages
            .filter((m) => m.id !== 'welcome')
            .map((m) => ({ role: m.role, content: m.content })),
          { role: 'user', content: userContent },
        ]

        setMessages((prev) => [...prev, userMsg])

        const response = await sendChat({
          messages: historyForApi,
          model,
          petitionId: activePetitionId,
          settings,
        })

        const assistantMsg: UiMessage = {
          id: response.id || uid(),
          role: 'assistant',
          content: response.choices[0]?.message.content ?? '',
          source: response.source,
          routing: response.routing,
          citations: response.citations,
          model: response.model,
          analysis: response.analysis,
          recreation: response.recreation,
        }
        setMessages((prev) => [...prev, assistantMsg])
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Falha ao falar com a API.'
        setError(message)
      } finally {
        setIsLoading(false)
      }
    },
    [isLoading, messages, model, pendingFile, petitionId, settings],
  )

  return {
    messages,
    model,
    setModel,
    settings,
    updateSettings,
    petitionId,
    petitionName,
    pendingFile,
    setPendingFile,
    isLoading,
    error,
    setError,
    sendMessage,
    clearChat,
    clearPetition,
  }
}
