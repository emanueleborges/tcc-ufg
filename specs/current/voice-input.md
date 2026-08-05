# Feature spec — Input por voz (microfone)

**Status:** implemented  
**Owner:** frontend  
**Related:** `specs/current/api-frontend.md`

## Problema

Digitação longa no chat é inconveniente; o usuário quer ditar a pergunta e ver o texto no campo de mensagem antes de enviar.

## Objetivo

Incluir um botão de microfone no composer (antes de Enviar) que transcreve áudio do navegador para texto no input.

## Fora de escopo

- Envio de áudio bruto ao backend
- Armazenamento de gravações
- Tradução automática
- Suporte obrigatório em navegadores sem Web Speech API

## Requisitos

### R1 — Posição e controle

Botão de microfone no `ChatInput`, imediatamente antes do botão Enviar. Alterna iniciar/parar escuta.

### R2 — Transcrição no input

Texto reconhecido (interim + final) aparece/atualiza no `textarea` do composer; o usuário pode editar antes de enviar. Resultados finais são acumulados no texto base (não substituem digitação prévia).

### R3 — Idioma

Reconhecimento em `pt-BR`.

### R4 — Feedback e falhas

Estado “ouvindo” visível no botão. Se a API não existir ou a permissão de microfone falhar, exibir mensagem curta (hint/toast no composer) sem quebrar o chat.

### R5 — Sem backend

Transcrição 100% no cliente via Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`). Nenhuma rota nova.

## Cenários

### Cenário A — feliz

**Dado** navegador com Web Speech API e permissão de microfone  
**Quando** o usuário clica no microfone e fala  
**Então** o texto transcrito aparece no input e pode ser enviado normalmente

### Cenário B — parar

**Dado** escuta ativa  
**Quando** o usuário clica novamente no microfone  
**Então** a escuta para e o texto já reconhecido permanece no input

### Cenário C — não suportado

**Dado** navegador sem Speech Recognition  
**Quando** o usuário clica no microfone  
**Então** vê aviso de indisponibilidade e o input continua usável por teclado

## Acceptance criteria

- [x] Botão de microfone visível antes de Enviar no composer React
- [x] Clique inicia/para reconhecimento de voz
- [x] Texto transcrito preenche/atualiza o `textarea` (editável)
- [x] Idioma `pt-BR`
- [x] Feedback visual de “ouvindo”
- [x] Fallback amigável se API/permissão indisponível
- [x] Nenhuma alteração de API backend

## Impacto técnico (rascunho)

- Backend: nenhum
- Frontend: `ChatInput.tsx`, `App.css`, `types/speech.d.ts`
- Dados: nenhum
