# Spec vigente — Personas jurídicas no chat

**Status:** implemented  
**Módulo:** `backend/src/services/chat/personas.py`, API chat, frontend header

## Objetivo

Permitir que o usuário selecione uma **persona jurídica** (especialista por ramo + persona **Geral** orquestradora) via dropdown no chat. A persona condiciona o system prompt do LLM (Ollama, RAG e Internet).

## Personas

| ID | Label |
|---|---|
| `geral` | Geral (Orquestrador) — padrão |
| `constitucional` | Direito Constitucional |
| `penal` | Direito Penal |
| `civil` | Direito Civil |
| `processual_civil` | Direito Processual Civil |
| `trabalho` | Direito do Trabalho |
| `tributario` | Direito Tributário |
| `administrativo` | Direito Administrativo |
| `empresarial` | Direito Empresarial |
| `previdenciario` | Direito Previdenciário |
| `consumidor` | Direito do Consumidor |
| `ambiental` | Direito Ambiental |
| `digital_lgpd` | Direito Digital e LGPD |
| `redacao` | Redação Jurídica |
| `jurisprudencia_rag` | Pesquisa de Jurisprudência (RAG) |

## Requisitos

### R1 — Backend
- Catálogo versionado com `id`, `label`, `description`, `system_prompt`
- Regras comuns: PT-BR, não inventar jurisprudência, declarar lacunas
- `persona_id` em `POST /v1/chat/completions` (default `geral`)
- `GET /v1/personas` lista opções para a UI
- Answerers Ollama/RAG/Internet:
  - system prompt = cabeçalho obrigatório + persona + canal
  - steering da persona também no turno do usuário (aderência em modelos pequenos)
  - persona especializada no Ollama: não reaproveitar respostas anteriores do assistente no histórico
  - âncoras jurídicas (`legal_anchors.py`) para institutos clássicos; em modelos 1b–3b a resposta pode ser grounding direto
- Resposta da API inclui `persona` (`id`, `label`, `description`) efetivamente aplicada

### R2 — Frontend
- Ícone no composer (ao lado do anexar) abre menu de personas
- Chip no input exibe o nome da persona selecionada
- Seleção enviada a cada mensagem
- Badge da resposta exibe a persona aplicada
- Default: Geral

## Acceptance criteria

- [x] Persona Geral existe e é o default
- [x] 14 especialidades + Geral no catálogo
- [x] Dropdown no chat
- [x] Prompt da persona chega ao LLM (system + steering no user)
- [x] Endpoint `/v1/personas`
- [x] UI mostra persona usada na resposta
