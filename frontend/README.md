# Frontend — Crítico Jurídico

Interface React estilo ChatGPT para o backend FastAPI.

## Pré-requisitos

1. API rodando em `http://localhost:8000`:
   ```bash
   cd backend
   python app.py api
   ```
2. (Opcional) Ollama local com o modelo configurado.

## Desenvolvimento

```bash
cd frontend
npm install
npm run dev
```

Abra `http://localhost:5173`.

A URL da API vem de `VITE_API_BASE_URL` (padrão: `http://localhost:8000`). O Vite também faz proxy de `/v1` e `/health`.

## Build

```bash
npm run build
npm run preview
```

## Funcionalidades

- Chat com histórico
- Badge de fonte (RAG / Ollama / Internet / Análise)
- Upload de PDF no composer (+)
- Seletor de modelo Ollama na sidebar
- Citações expansíveis
- Status online/offline da API
