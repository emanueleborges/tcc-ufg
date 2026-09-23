# Spec vigente — Deploy Docker (API + frontend React)

**Status:** implemented  
**Módulo:** empacotamento / `docker-compose`  
**Related:** `api-frontend.md`

## Problema

Rodar backend e frontend React localmente exige Python, Node e dependências pesadas (embeddings, Chroma). Falta um caminho reproduzível via containers.

## Objetivo

Disponibilizar a API FastAPI e o frontend React em Docker Compose, com proxy HTTP no frontend para a API e volumes persistentes de dados.

## Fora de escopo

- Imagem do Ollama (continua no host ou serviço externo via `OLLAMA_HOST`)
- Streamlit
- CI/CD / registry remoto

## Requisitos

### R1 — Backend em container
- Dockerfile em `backend/` sobe FastAPI (`uvicorn`) na porta `8000`
- Instala `requirements-api.txt` **somente no Docker** (API + React; sem Streamlit); `requirements.txt` local permanece intacto
- Volumes para `uploads/`, `validacoes/`, `indice_juridico/`, `downloads_peticoes/`
- `OLLAMA_HOST` configurável (padrão: `http://host.docker.internal:11434`)
- Primeiro build é lento por deps ML; builds seguintes usam cache de camada

### R2 — Frontend React em container
- Build multi-stage (Node → nginx)
- Nginx serve o `dist/` e faz proxy de `/v1` e `/health` para o serviço `backend`
- Cliente usa URL relativa (`VITE_API_BASE_URL` vazio no build Docker)

### R3 — Compose na raiz
- `docker compose up --build` sobe backend + frontend
- Frontend exposto em `http://localhost:8080`; API também em `http://localhost:8000`

## Acceptance criteria

- [x] `backend/Dockerfile` e `frontend/Dockerfile` (+ nginx)
- [x] `docker-compose.yml` na raiz do repositório
- [x] `.dockerignore` para contexto enxuto
- [x] Spec e README com instruções `docker compose up --build`
- [x] Frontend acessa a API via proxy nginx (`/v1`, `/health`)
