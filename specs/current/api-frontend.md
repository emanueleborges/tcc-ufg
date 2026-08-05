# Spec vigente — API e frontend

**Status:** implemented  

## API (FastAPI `:8000`)

Principais rotas: `/health`, `/v1/models`, `/v1/chat/completions`, `/v1/uploads`, `/v1/index`, `/v1/index/rebuild[/stream]`, `/v1/scrape[/stream]`, `/v1/validations`.

## Frontend (React `:5173`)

Chat + sidebar (modelo, sliders, rebuild/scrape com %).

### Responsividade

Layout fixo em `100dvh` (sem scroll da página). Breakpoints:

| Largura | Comportamento |
|---|---|
| ≥ 1100px | Sidebar fixa 260px + chat |
| 901–1099px | Sidebar compacta 220px; fontes/listas densas |
| ≤ 900px | Sidebar em drawer (overlay); chat em tela cheia; botão menu no header |
| ≤ 640px | Composer/toolbar e bolhas adaptados ao telefone |

Altura ≤ 820px: sidebar ainda mais compacta (sem scrollbar da página).

## Acceptance criteria

- [x] Monorepo `backend/` + `frontend/`
- [x] Progresso % nos botões rebuild/scrape
- [x] Painéis análise/recriação no chat React
- [ ] Paridade total com Streamlit clássico (PDF viewer / PDF recriado)
- [x] Desktop (≥1100): sidebar + chat lado a lado, viewport sem scroll externo
- [x] Tablet (901–1099): sidebar estreita, conteúdo legível
- [x] Mobile (≤900): drawer de configurações + chat full-width
- [x] Phone (≤640): composer e mensagens usáveis sem overflow horizontal
