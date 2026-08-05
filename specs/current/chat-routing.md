# Spec vigente — Chat e roteamento

**Status:** implemented  
**Módulo:** `backend/src/services/chat`, `frontend` chat

## Objetivo

Responder em português com roteamento automático e fontes rastreáveis.

## Intents

| Intent | Quando |
|---|---|
| `analyze_petition` | PDF + verbo analisar |
| `recreate_petition` | PDF + verbo recriar/melhorar |
| `ask_internet` | sinais web/temporal ou keywords |
| `ask_rag` | sinais jurídicos / base |
| `ask_ollama` | default / saudação |

## Acceptance criteria

- [x] Badge de fonte na UI
- [x] Painel **Referências** (não “Trechos usados”)
- [x] RAG não ecoa blocos `[N] Arquivo:` na bolha (prompt + strip)
- [x] Upload PDF + análise/recriação via API
- [x] Análise: bolha curta; scores/sugestões só no painel (sem dump de texto)

## Fora desta spec

- Streaming de tokens do chat
