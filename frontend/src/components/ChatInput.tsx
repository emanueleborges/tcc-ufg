import { useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

interface Props {
  disabled: boolean
  pendingFile: File | null
  onFileChange: (file: File | null) => void
  onSend: (text: string) => void
}

export function ChatInput({
  disabled,
  pendingFile,
  onFileChange,
  onSend,
}: Props) {
  const [text, setText] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

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
        Enter envia · Shift+Enter quebra linha · PDF via botão +
      </p>
    </form>
  )
}
