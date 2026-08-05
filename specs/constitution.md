# Constituição — Crítico Jurídico Inteligente (TCC UFG)

## Missão

Chatbot jurídico documental (RAG + LLM local + busca web) para analisar e melhorar petições iniciais, com base contrastiva de casos deferidos e indeferidos.

## Não negociáveis

1. Spec antes de código (SDD).
2. Clean Architecture no backend.
3. Separação `backend/` e `frontend/`.
4. Corpus RAG: pastas `aceitas/`, `rejeitadas/` e `parcial/`; metadados de resultado (`deferido` / `indeferido` / `parcial`).
5. UI de chat: texto sintético + painel **Referências** (sem ecoar trechos/PDFs na bolha).
6. APIs documentadas em specs/contratos; sem endpoint “surpresa”.
7. Dados gerados (uploads, índice, PDFs baixados, validações) fora do versionamento pesado (ver `.gitignore`).

## Stack

- Backend: Python, FastAPI, Streamlit, LangChain/Ollama, sentence-transformers, RapidOCR
- Frontend: React + Vite + TypeScript

## Qualidade

- Mudanças pequenas e focadas.
- Preferir estender ports/use cases a acoplar infra na presentation.
- Testar mentalmente contra os **acceptance criteria** da spec ativa.
