# Spec vigente — Corpus RAG e scraping

**Status:** implemented  
**Módulo:** `backend/src/infrastructure/scraping`, `build_index`, NLP `case_outcome`

## Objetivo

Manter base documental **trinária** para o RAG: petições/decisões **aceitas (deferidas)**, **rejeitadas (indeferidas)** e **parciais**, sem duplicar downloads, com metadados de resultado na indexação.

## Requisitos

### R1 — Pastas (3 classes)
- `downloads_peticoes/aceitas/` → outcome `deferido` | `indefinido` (com sinal jurídico)
- `downloads_peticoes/rejeitadas/` → outcome `indeferido`
- `downloads_peticoes/parcial/` → outcome `parcial`
- Índice RAG lê **as três** pastas

### R2 — Volume e dedupe
- Meta: corpus com **pelo menos 100 PDFs** no total (`aceitas` + `rejeitadas` + `parcial`)
- Contraste: manter volume mínimo em cada classe (alvo ~25% rejeitadas e ~15% parciais, ou mínimos configuráveis via backfill)
- Por execução, tenta baixar até `SCRAPING_DOWNLOAD_LIMIT` (default 100) **novos**, ou o necessário para atingir 100 no acervo
- Dedupe por URL normalizada + SHA-256 (+ hashes já em disco)

### R3 — Busca (resiliência)
- **Primário:** HTML DuckDuckGo + HTML Brave
- DDGS opcional via `SCRAPING_USE_DDGS=1`
- Queries de procedente, improcedente e parcialmente procedente
- Seeds: `seed_urls.txt` + `builtin_seeds.py`
- **Backfill HF** se meta/contraste não fechar

### R4 — Indexação
- Extrair features + `resultado` ∈ {deferido, indeferido, parcial, indefinido}
- Retrieval diversifica as três classes
- UI: painel **Referências**

## Acceptance criteria

- [x] Scrape grava em `aceitas/`, `rejeitadas/` e `parcial/` conforme outcome
- [x] Build index inclui PDFs das três pastas
- [x] Dedupe por hash/URL
- [x] Meta default ≥ 100 no acervo
- [x] Mensagem de scrape reporta `aceitas=` / `rejeitadas=` / `parcial=`
- [x] Backfill HF cobre as três classes
- [x] Reclassificação move parciais que estavam em `aceitas/`

## Notas

`parcial` = parcialmente procedente / provimento parcial (não misturar com aceitas plenas).
