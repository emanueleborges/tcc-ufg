# Spec vigente — API e frontend

**Status:** implemented  

## API (FastAPI `:8000`)

Principais rotas: `/health`, `/v1/models`, `/v1/chat/completions`, `/v1/uploads`, `/v1/index`, `/v1/index/rebuild[/stream]`, `/v1/scrape[/stream]`, `/v1/validations`.

## Frontend (React `:5173`)

Chat + sidebar (modelo, sliders, rebuild/scrape com %).

## Acceptance criteria

- [x] Monorepo `backend/` + `frontend/`
- [x] Progresso % nos botões rebuild/scrape
- [x] Painéis análise/recriação no chat React
- [ ] Paridade total com Streamlit clássico (PDF viewer / PDF recriado)
