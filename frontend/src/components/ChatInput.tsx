import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'
import type { PersonaOut } from '../api/types'

interface Props {
  disabled: boolean
  pendingFile: File | null
  onFileChange: (file: File | null) => void
  onSend: (text: string) => void
  personas: PersonaOut[]
  personaId: string
  onPersonaChange: (personaId: string) => void
}

const FALLBACK_PERSONAS: PersonaOut[] = [
  {
    id: 'geral',
    label: 'Geral (Orquestrador)',
    description: 'Visão transversal dos ramos do Direito.',
  },
]

function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

function PersonaIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M12 3v3M12 18v3M5.6 6.2l2.1 2.1M16.3 15.7l2.1 2.1M3 12h3M18 12h3M5.6 17.8l2.1-2.1M16.3 8.3l2.1-2.1"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  )
}

function MicIcon() {
  return (
    <svg
      width="30"
      height="30"
      viewBox="2 0 17 17"
      fill="none"
      aria-hidden="true"
    >
      <rect
        x="9"
        y="3"
        width="6"
        height="11"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.8"
      />
      <path
        d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"
        stroke="currentColor"
        strokeWidth="2.0"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function ChatInput({
  disabled,
  pendingFile,
  onFileChange,
  onSend,
  personas,
  personaId,
  onPersonaChange,
}: Props) {
  const [text, setText] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [listening, setListening] = useState(false)
  const [voiceHint, setVoiceHint] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const baseTextRef = useRef('')
  const textRef = useRef(text)
  const options = personas.length > 0 ? personas : FALLBACK_PERSONAS
  const selected = options.find((item) => item.id === personaId) ?? options[0]

  function resizeTextarea() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const styles = window.getComputedStyle(el)
    const lineHeight = Number.parseFloat(styles.lineHeight) || 20
    const paddingY =
      Number.parseFloat(styles.paddingTop) + Number.parseFloat(styles.paddingBottom)
    const maxHeight = lineHeight * 2 + paddingY
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
  }

  useEffect(() => {
    textRef.current = text
    resizeTextarea()
  }, [text])

  useEffect(() => {
    if (!menuOpen) return

    function onPointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }

    function onEscape(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false)
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onEscape)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onEscape)
    }
  }, [menuOpen])

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort()
      recognitionRef.current = null
    }
  }, [])

  function stopListening() {
    recognitionRef.current?.stop()
  }

  function startListening() {
    const SpeechRecognitionCtor = getSpeechRecognition()
    if (!SpeechRecognitionCtor) {
      setVoiceHint(
        'Reconhecimento de voz indisponível neste navegador. Use Chrome ou Edge.',
      )
      return
    }

    setVoiceHint(null)
    const current = textRef.current
    baseTextRef.current = current && !/\s$/.test(current) ? `${current} ` : current

    const recognition = new SpeechRecognitionCtor()
    recognition.lang = 'pt-BR'
    recognition.continuous = true
    recognition.interimResults = true

    recognition.onresult = (event) => {
      let interim = ''
      let finalized = baseTextRef.current

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        const chunk = result[0]?.transcript ?? ''
        if (result.isFinal) {
          finalized += chunk
          if (chunk && !/\s$/.test(chunk)) finalized += ' '
          baseTextRef.current = finalized
        } else {
          interim += chunk
        }
      }

      setText(`${finalized}${interim}`)
    }

    recognition.onerror = (event) => {
      if (event.error === 'aborted') return
      if (event.error === 'not-allowed') {
        setVoiceHint('Permissão de microfone negada. Libere o acesso nas configurações do navegador.')
      } else if (event.error === 'no-speech') {
        setVoiceHint('Nenhuma fala detectada. Tente novamente.')
      } else {
        setVoiceHint('Não foi possível transcrever o áudio. Tente novamente.')
      }
      setListening(false)
      recognitionRef.current = null
    }

    recognition.onend = () => {
      setListening(false)
      recognitionRef.current = null
    }

    try {
      recognition.start()
      recognitionRef.current = recognition
      setListening(true)
    } catch {
      setVoiceHint('Não foi possível iniciar o microfone.')
      setListening(false)
      recognitionRef.current = null
    }
  }

  function toggleListening() {
    if (disabled) return
    if (listening) {
      stopListening()
      return
    }
    startListening()
  }

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (disabled) return
    if (!text.trim() && !pendingFile) return
    if (listening) stopListening()
    onSend(text)
    setText('')
    baseTextRef.current = ''
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      {pendingFile && (
        <div className="composer-file">
          <span>📎 {pendingFile.name}</span>
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              onFileChange(null)
              if (fileRef.current) fileRef.current.value = ''
            }}
          >
            Remover
          </button>
        </div>
      )}
      <div className="composer-box">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            if (listening) baseTextRef.current = e.target.value
          }}
          onKeyDown={onKeyDown}
          placeholder="Pergunte algo ou anexe uma petição em PDF…"
          rows={1}
          disabled={disabled}
        />

        <div className="composer-toolbar">
          <div className="persona-menu" ref={menuRef}>
            <button
              type="button"
              className={`persona-chip${menuOpen ? ' is-open' : ''}`}
              title={`Persona: ${selected.label}`}
              aria-label={`Persona jurídica: ${selected.label}`}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              disabled={disabled}
              onClick={() => setMenuOpen((open) => !open)}
            >
              <PersonaIcon />
              <span className="persona-chip-text">
                <span className="persona-chip-kicker">Persona</span>
                <span className="persona-chip-label">{selected.label}</span>
              </span>
              <span className="persona-chip-caret" aria-hidden>
                ▾
              </span>
            </button>
            {menuOpen && (
              <div className="persona-menu-panel" role="menu" aria-label="Personas jurídicas">
                <p className="persona-menu-title">Persona jurídica</p>
                <ul className="persona-menu-list">
                  {options.map((persona) => {
                    const active = persona.id === personaId
                    return (
                      <li key={persona.id}>
                        <button
                          type="button"
                          role="menuitemradio"
                          aria-checked={active}
                          className={`persona-menu-item${active ? ' is-active' : ''}`}
                          onClick={() => {
                            onPersonaChange(persona.id)
                            setMenuOpen(false)
                          }}
                        >
                          <span className="persona-menu-item-label">{persona.label}</span>
                          <span className="persona-menu-item-desc">{persona.description}</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              </div>
            )}
          </div>

          <button
            type="button"
            className="icon-btn"
            title="Anexar petição PDF"
            disabled={disabled}
            onClick={() => fileRef.current?.click()}
          >
            +
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf,.pdf"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null
              onFileChange(file)
            }}
          />

          <div className="composer-toolbar-actions">
            <button
              type="button"
              className={`mic-btn${listening ? ' is-listening' : ''}`}
              title={listening ? 'Parar ditado' : 'Ditar por voz'}
              aria-label={listening ? 'Parar ditado por voz' : 'Ditar por voz'}
              aria-pressed={listening}
              disabled={disabled}
              onClick={toggleListening}
            >
              <MicIcon />
            </button>
            <button
              type="submit"
              className="send-btn"
              disabled={disabled || (!text.trim() && !pendingFile)}
            >
              Enviar
            </button>
          </div>
        </div>
      </div>
      {voiceHint && <p className="composer-voice-hint">{voiceHint}</p>}
      <p className="composer-hint">
        Enter envia · Shift+Enter quebra linha · + anexa PDF · microfone dita · chip troca a persona
      </p>
    </form>
  )
}
