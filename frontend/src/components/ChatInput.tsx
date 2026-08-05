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
  const fileRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const options = personas.length > 0 ? personas : FALLBACK_PERSONAS
  const selected = options.find((item) => item.id === personaId) ?? options[0]

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

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (disabled) return
    if (!text.trim() && !pendingFile) return
    onSend(text)
    setText('')
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

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Pergunte algo ou anexe uma petição em PDF…"
          rows={1}
          disabled={disabled}
        />
        <button
          type="submit"
          className="send-btn"
          disabled={disabled || (!text.trim() && !pendingFile)}
        >
          Enviar
        </button>
      </div>
      <p className="composer-hint">
        Enter envia · Shift+Enter quebra linha · + anexa PDF · chip troca a persona
      </p>
    </form>
  )
}
