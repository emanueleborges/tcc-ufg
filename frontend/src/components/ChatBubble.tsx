import ReactMarkdown from 'react-markdown'
import type { UiMessage } from '../api/types'
import { CitationPanel } from './CitationPanel'
import { AnalysisPanel } from './ResultPanels'
import { SourceBadge } from './SourceBadge'

interface Props {
  message: UiMessage
}

export function ChatBubble({ message }: Props) {
  const isUser = message.role === 'user'

  return (
    <article className={`bubble-row ${isUser ? 'is-user' : 'is-assistant'}`}>
      <div className="bubble-avatar" aria-hidden>
        {isUser ? 'Você' : message.source?.icon || '⚖️'}
      </div>
      <div className="bubble-body">
        {!isUser && message.source && (
          <SourceBadge
            source={message.source}
            model={message.model}
            personaLabel={message.persona?.label}
            routingMode={
              message.routing?.mode === 'automatic'
                ? 'automático'
                : message.routing?.mode === 'explicit'
                  ? 'explícito'
                  : message.routing?.mode === 'default'
                    ? 'padrão'
                    : message.routing?.mode
            }
          />
        )}
        {message.attachmentName && (
          <p className="attachment-chip">📎 {message.attachmentName}</p>
        )}
        <div className="bubble-content">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
        {!isUser && message.analysis && (
          <AnalysisPanel analysis={message.analysis} />
        )}
        {!isUser && message.citations && (
          <CitationPanel
            citations={message.citations}
            sourceId={message.source?.id}
          />
        )}
        {!isUser && message.routing?.reason && (
          <p className="routing-reason">Roteamento: {message.routing.reason}</p>
        )}
      </div>
    </article>
  )
}
