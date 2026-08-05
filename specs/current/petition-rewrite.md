# Feature spec — Reescrita completa da petição

**Status:** implemented  
**Owner:** TCC UFG  
**Related:** análise crítica; recriação anotada; Ollama

## Problema

A “recriação” atual apenas anota o PDF original. O usuário precisa de uma **nova redação** da petição, com base na análise (problemas/sugestões), em arquivos baixáveis (PDF e DOCX).

## Objetivo

Após analisar a petição anexada e pedir recriação/reescrita:
1. O LLM (Ollama) gera a **petição reescrita completa** (preservando fatos; aplicando melhorias de estrutura/clareza/fundamentação).
2. O sistema monta **PDF** (reportlab) e **DOCX** (python-docx).
3. O painel oferece downloads. O PDF anotado do original (grifo azul) permanece como artefato complementar.

## Fora de escopo

- Editor WYSIWYG no frontend
- Assinatura digital / protocolo eletrônico
- Garantia de layout tipográfico idêntico ao escritório do autor

## Requisitos

### R1 — Reescrita via LLM
`LLMClientPort.rewrite_petition(...)` usa análise (`problems`, `suggestions`, scores) + texto original + (opcional) RAG/web.

### R2 — Documentos gerados
- PDF: `peticao_reescrita_*.pdf`
- DOCX: `peticao_reescrita_*.docx`
- (Complementar) PDF anotado: `peticao_recriada_*.pdf` (layout original)

### R3 — Downloads na API/UI
Endpoints `GET /v1/recreations/{file}` para `.pdf` e `.docx`. Painel com botões de download.

### R4 — Segurança
Respeitar bloqueio por injeção de prompt (risco high/critical).

## Acceptance criteria

- [x] Spec vigente
- [x] Método de reescrita no Ollama client
- [x] PDF + DOCX gerados na recriação
- [x] Download no frontend
- [x] `python-docx` em requirements

## Impacto técnico

- Backend: `ollama_client`, `recreate_petition`, writers PDF/DOCX, API
- Frontend: `RecreationPanel`
- Deps: `python-docx`
