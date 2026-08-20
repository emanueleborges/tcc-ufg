# Análise técnica — o que é usado no projeto

Documento de referência do TCC: stack, funções e classes principais por funcionalidade.
Gerado a partir da leitura do código em `backend/` (Clean Architecture: `presentation → application → domain`; `infrastructure` implementa as ports de `application/ports.py`).

---

## 1. Web scraping — `requests` + `BeautifulSoup4` (+ `ddgs` opcional)

**Classe principal:** `PdfScraper` — `backend/src/infrastructure/scraping/pdf_scraper.py`

| Função | Papel |
|---|---|
| `run(on_progress)` | Orquestra todo o scraping; retorna `ScrapingResult` |
| `_search_candidates(...)` | Monta candidatos a partir de seeds (`BUILTIN_PDF_URLS` + `seed_urls.txt`) e buscas |
| `_search_duckduckgo_html` / `_search_brave_html` | Buscas HTML (DuckDuckGo POST → fallback Brave GET) |
| `_search_web` / `_expand_candidates` | Expande páginas HTML em links PDF (hints jurídicos, hosts `.jus.br`, ConJur) |
| `_discover_download_links(candidate)` | Descobre URLs de PDF dentro de uma página |
| `_download_pdf_bytes(url)` | Download com `requests.get` (stream, limite 30 MB) |
| `_classify_for_corpus` | Classifica em `aceitas/` (deferido), `rejeitadas/` (indeferido), `parcial/` |
| `_reclassify_existing_library` | Re-classifica PDFs já baixados |

**Backfill:** `hf_corpus_backfill.backfill_from_open_datasets()` busca datasets abertos no Hugging Face (`stadv/modelos_peticoes`, `mrhewbuc/brazilian_court_civil_decisions`) e gera PDFs com ReportLab se o corpus for insuficiente.

**Use case que dispara:** `DownloadPetitionsUseCase.execute()` → `application/use_cases/download_petitions.py` → chamado pela rota `POST /v1/scrape` e pela CLI (`python app.py scrape`).

Metadados persistidos em `downloads_peticoes/metadata.json` + `.csv`.

---

## 2. Roteamento de modelos — LangChain (`langchain-ollama`) + heurística própria

O roteamento **não é um LLM router**: é um classificador heurístico por palavras-chave/sinais, seguido de estratégias por canal.

| Peça | Arquivo | Papel |
|---|---|---|
| `classify_intent(message, *, has_petition)` | `services/chat/intent_classifier.py` | Decide a intenção: `ANALYZE_PETITION`, `ASK_INTERNET`, `ASK_RAG`, `ASK_OLLAMA` (ordem de prioridade fixa) |
| `ChatOrchestrator.respond(user_message, history, context)` | `services/chat/orchestrator.py` | Recebe a intenção e despacha para a estratégia certa; retorna `ChatAnswer` |
| `OllamaAnswerer` | `services/chat/ollama_answerer.py` | Chat geral (Ollama puro) |
| `RagAnswerer` | `services/chat/rag_answerer.py` | RAG: retrieval → montagem de prompt → resposta com citações |
| `InternetAnswerer` | `services/chat/internet_answerer.py` | Busca web + síntese via Ollama |
| `AnalyzePetitionAnswerer` | `services/chat/petition_answerers.py` | Análise de petição via chat |
| `ChatWithAssistantUseCase.execute(...)` | `application/use_cases/chat_with_assistant.py` | Ponto de entrada único do chat (usado pela API e pelo Streamlit) |

**Uso real do LangChain:** apenas `langchain_ollama.ChatOllama` + `langchain_core.messages` (`SystemMessage`, `HumanMessage`, `AIMessage`), encapsulados em:

- `LangChainOllamaChat` — `infrastructure/langchain/ollama_chat.py` — chama `chat_model.invoke(lc_messages)`.

Não há chains, LCEL, agents nem `langchain_community` em runtime.

**Personas:** `personas.py` — dataclass `LegalPersona` + catálogo `PERSONAS` (15 personas); funções `list_personas()`, `get_persona(id)`, `compose_system_prompt(channel_prompt, persona_id)`, `steer_user_message(msg, persona_id)`.

**Prompts por canal:** `services/chat/prompts.py` — `SYSTEM_GENERAL`, `SYSTEM_RAG`, `SYSTEM_INTERNET` e templates.

---

## 3. Banco vetorial — **ChromaDB** (persistente, local)

O índice RAG usa ChromaDB (`chromadb.PersistentClient`) em `backend/indice_juridico/`:

| Artefato | Conteúdo |
|---|---|
| `chroma/` | Banco ChromaDB; coleção `peticoes_chunks` (id = `chunk_id`, document = texto, embedding, metadados com features em JSON + `row_index`) |
| `documentos.json` | Sumário dos documentos (`DocumentSummary`, sem vetor) |

**Classe principal:** `ChromaIndexRepository` — `infrastructure/persistence/chroma_index_repository.py`

| Função | Papel |
|---|---|
| `exists()` | Diz se o índice existe (status em `GET /v1/index`) |
| `save(chunks, documents, embeddings)` | Recria a coleção do zero e grava em lotes |
| `load()` | Carrega chunks + documentos + matriz `np.ndarray` (alinhada por `row_index`) |
| `_migrate_legacy_if_needed()` | Migração única do formato antigo (`chunks.jsonl` + `embeddings.npy`) sem rebuild |

**Legado:** `FileSystemIndexRepository` — `infrastructure/persistence/index_repository.py` — mantido apenas como fonte da migração automática.

**Embeddings:** `SentenceTransformerEmbeddingEngine` — `infrastructure/nlp/embedding_engine.py`, modelo `intfloat/multilingual-e5-small` (sentence-transformers), prefixos E5 (`passage:`/`query:`), vetores L2-normalizados.

**Rebuild:** `BuildIndexUseCase.execute(on_progress)` (PDFs das três pastas → chunks → encode → save) e `LoadOrBuildIndexUseCase.execute()` (carrega se existe, senão constrói) — `application/use_cases/build_index.py`. Na API: `POST /v1/index/rebuild[/stream]`.

---

## 4. Busca semântica (retrieval RAG) — NumPy (cosine)

**Classe:** `SemanticSearchService` — `services/semantic_search.py`

- `search(query_text, chunks, embeddings, top_k, exclude_document_id=None) -> list[SimilarChunk]`
- Cosine similarity via `np.dot` (vetores já normalizados)
- `top_k` default 8 (`RAG_TOP_K`), boost +0.02 por preferência de outcome na query
- Diversificação: garante ≥1 deferido, ≥1 indeferido, ≥1 parcial

O `RagAnswerer` usa esse resultado para montar o contexto (`_format_chunks`) e chama o `ChatOllama`. Citações vão para o painel (não no texto); `_strip_echoed_chunks` remove eco de PDFs da resposta.

---

## 5. Busca na internet — `ddgs` (DuckDuckGo)

**Classe:** `DuckDuckGoWebSearch` — `infrastructure/search/duckduckgo_search.py`

- `search_references(review, max_results) -> list[WebReference]`
- `search_text(query, max_results) -> list[WebReference]`

Região default `br-pt`, `max_results=5`. Usado por `InternetAnswerer`.

---

## 6. Leitura e geração de PDFs — `pypdf` + `PyMuPDF` + `rapidocr` + `reportlab`

| Classe/função | Arquivo | Papel |
|---|---|---|
| `PdfReader.read_pages` / `read_text` | `infrastructure/pdf/pdf_reader.py` | Extrai texto nativo (pypdf); páginas sem texto passam por OCR (`rapidocr` via `ocr_missing_pages`, com PyMuPDF) |
| `ReportlabPdfWriter` | `infrastructure/pdf/pdf_writer.py` | Markdown → PDF |

---

## 7. Análise de petição — use case próprio + segurança OWASP LLM01

**`AnalyzePetitionUseCase.execute(petition_path, chunks, documents, embeddings) -> ReviewResult`** — `application/use_cases/analyze_petition.py`

Pipeline:
1. `ChunkFactory.build_for_pdf` (`services/chunk_factory.py`) — PDF → chunks + features (`extract_features` + `enrich_case_features`)
2. `PromptInjectionAnalyzer.analyze_petition` — varredura de injeção
3. `score_review` (`services/scoring.py`) — scores multidimensionais: estrutura, clareza, coerência, fundamentação, consistência, elementos essenciais
4. `SemanticSearchService.search` — petições similares do corpus
5. Heurísticas `_detect_problems_and_suggestions`
6. `render_review_markdown` (`services/report_renderer.py`) — relatório em Markdown

**Detecção de prompt injection:** `PromptInjectionAnalyzer` — `services/security/prompt_injection_analyzer.py`

- `analyze(text)` / `analyze_petition(text, pdf_path)` → `PromptInjectionReport`
- Padrões regex (jailbreaks EN/PT, overrides, Base64, zero-width) + spans invisíveis no PDF (fonte branca/minúscula, via PyMuPDF)
- Risco `high`/`critical` ⇒ alerta de segurança em destaque no painel e no chat

---

## 8. Validação humana (lawyer-in-the-loop) — **SQLite** + dashboard

| Peça | Arquivo |
|---|---|
| `SubmitHumanValidationUseCase` / `ListHumanValidationsUseCase` / `GetHumanValidationUseCase` | `application/use_cases/submit_human_validation.py` |
| `GetValidationMetricsUseCase` (agregados: médias por dimensão, MAE médio, acordo médio, qualidade final média) | `application/use_cases/validation_metrics.py` |
| `SQLiteValidationRepository` (tabela `validations` em `validacoes/validacoes.db`; importa JSONs legados na 1ª execução) | `infrastructure/persistence/validation_repository_sqlite.py` |
| `ValidationRepositoryPort` (port) | `application/ports.py` |
| `build_validation` / `compute_comparison` (aderência humano×protótipo) | `services/human_comparison.py` |

Rotas: `POST /v1/validations`, `GET /v1/validations[/{id}]`, `GET /v1/validations/metrics`.

**Tempos de leitura humana:** `ReadingTimeEntry` (domínio) + `SQLiteReadingTimeRepository` (`infrastructure/persistence/reading_time_repository_sqlite.py`, tabela `reading_times` no mesmo `validacoes.db`) + `SubmitReadingTimeUseCase` / `ListReadingTimesUseCase` (`application/use_cases/reading_times.py`). Rotas: `POST/GET /v1/reading-times` (com média dos tempos) + `PUT/DELETE /v1/reading-times/{id}` (CRUD completo).

**Dashboard (React):** view “Tempo de leitura” alternável no header do chat — formulário simples (nome do advogado + tempo hh:mm), tempo médio e lista de registros, para comparação humano × protótipo no TCC.

---

## 9. API e apresentação

**FastAPI:** `create_app()` / `app` — `presentation/api/app.py`; rotas em `routes.py`; dependências via `get_container()`.

| Método | Rota | Chama |
|---|---|---|
| GET | `/health` | healthcheck |
| GET | `/v1/models` | Ollama `/api/tags` + modelos lógicos (rag/internet/petition) |
| GET | `/v1/personas` | `list_personas()` |
| POST | `/v1/chat/completions` | `ChatWithAssistantUseCase.execute` |
| POST | `/v1/uploads` | grava PDF em `uploads/` |
| GET | `/v1/uploads/{petition_id}` | metadados |
| GET | `/v1/index` | `index_repository.exists/load` |
| POST | `/v1/index/rebuild[/stream]` | `build_index` + relatório do corpus |
| POST | `/v1/scrape[/stream]` | `DownloadPetitionsUseCase` |
| POST/GET | `/v1/validations[/{id}]` | use cases de validação |
| GET | `/v1/validations/metrics` | `GetValidationMetricsUseCase` |

**Outros entrypoints:** Streamlit (`presentation/streamlit/{app,chat_view,classic_view}.py`), CLI (`presentation/cli/commands.py` — `ui` | `api` | `index` | `scrape`).

**Frontend:** React + Vite (TypeScript), estilo ChatGPT; sem libs de UI — CSS próprio com variáveis de tema.

---

## 10. Composition root e configuração

- `AppContainer` — `src/container.py` — único ponto de injeção de dependências (wiring de ports → adapters → use cases → presentation).
- `Settings` / `get_settings()` — `src/config/settings.py` — `PathsSettings`, `ScrapingSettings`, `RagSettings`, `OllamaSettings`, `WebSearchSettings` (sobreponíveis por env).

## Resumo da stack

| Funcionalidade | Tecnologia |
|---|---|
| Web scraping | `requests` + `beautifulsoup4` (+ `ddgs` e Hugging Face Datasets p/ backfill) |
| Orquestração do chat | `langchain` + `langchain-ollama` (`ChatOllama`) |
| Roteamento de intenções | heurística própria (`classify_intent`) — sem LLM router |
| Banco vetorial | ChromaDB (`PersistentClient`, coleção `peticoes_chunks`) |
| Embeddings | `sentence-transformers` (E5 multilingual) |
| Busca web | `ddgs` (DuckDuckGo) |
| PDF | `pypdf`, `PyMuPDF`, `rapidocr` (OCR), `reportlab` |
| LLM | Ollama local (`llama3` por padrão) |
| API | FastAPI + Uvicorn |
| UI extra | Streamlit |
| Frontend | React 19 + Vite + TypeScript |
