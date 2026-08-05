# Crítico Jurídico Inteligente — TCC UFG

Projeto de TCC da Universidade Federal de Goiás (UFG): **chatbot jurídico** baseado em RAG (Retrieval-Augmented Generation) que conversa em linguagem natural, analisa petições iniciais em PDF, compara com um corpus de petições de referência e sugere melhorias com auxílio de um LLM local. Cada resposta indica claramente sua origem (base RAG, Ollama local ou DuckDuckGo).

## Funcionalidades

- **Chatbot com roteamento inteligente** entre 3 fontes: 📚 RAG interno, 🤖 Ollama local, 🌐 DuckDuckGo — cada resposta exibe sua fonte
- Orquestração com **LangChain** (`ChatOllama` + prompts especializados por fonte)
- Anexar uma petição no chat e pedir _"analise"_ ou _"recrie esta petição"_ aciona automaticamente os use cases de análise/recriação
- Indexação de petições jurídicas em PDF, com OCR automático quando o PDF é escaneado
- Análise crítica: scores multi-dimensionais, features jurídicas, pontos fracos e sugestões
- Busca semântica em uma base curada de petições com sentenças procedentes
- Recriação da petição preservando o original e anotando melhorias *inline* via LLM
- Geração de relatórios em Markdown e PDF
- Modo **clássico** (formulário tradicional) também disponível no mesmo Streamlit
- CLI para indexação e scraping

## Arquitetura

O projeto segue **Clean Architecture**, com camadas isoladas por responsabilidade, e **Spec-Driven Development (SDD)** — veja `AGENTS.md` e `specs/`.

```
tcc-ufg/
├── frontend/                       # React (Vite) — chat estilo ChatGPT
├── backend/                        # API FastAPI + Streamlit + CLI
│   ├── app.py                      # Ponto de entrada (UI + API + CLI)
│   ├── requirements.txt
│   ├── .streamlit/                 # Config Streamlit
│   ├── downloads_peticoes/         # PDFs baixados / aceitos
│   ├── indice_juridico/            # Índice RAG em disco
│   ├── relatorios/                 # Relatórios gerados
│   ├── uploads/                    # Uploads de petições
│   └── src/
│       ├── domain/                 # Entidades puras e padrões linguísticos jurídicos
│       │   ├── entities.py
│       │   └── patterns.py
│       ├── application/            # Regras de aplicação (ports + use cases)
│       │   ├── ports.py
│       │   └── use_cases/
│       │       ├── build_index.py
│       │       ├── analyze_petition.py
│       │       ├── recreate_petition.py
│       │       ├── download_petitions.py
│       │       ├── generate_corpus_report.py
│       │       └── chat_with_assistant.py
│       ├── infrastructure/         # Adapters concretos
│       │   ├── pdf/                # leitura, OCR, geração de PDF
│       │   ├── nlp/                # chunking, features, sections, embeddings
│       │   ├── persistence/        # índice RAG em disco
│       │   ├── llm/                # cliente Ollama (não-conversacional)
│       │   ├── langchain/          # chat conversacional (ChatOllama)
│       │   ├── search/             # busca web (DuckDuckGo)
│       │   └── scraping/           # baixador de PDFs públicos
│       ├── services/               # Orquestração entre use cases e infra
│       │   ├── chunk_factory.py
│       │   ├── semantic_search.py
│       │   ├── scoring.py
│       │   ├── benchmarks.py
│       │   ├── inline_comments.py
│       │   ├── report_renderer.py
│       │   └── chat/               # Estratégias e orquestrador do chatbot
│       │       ├── intent_classifier.py
│       │       ├── orchestrator.py
│       │       ├── prompts.py
│       │       ├── ollama_answerer.py
│       │       ├── rag_answerer.py
│       │       ├── internet_answerer.py
│       │       └── petition_answerers.py
│       ├── presentation/           # UI Streamlit + API FastAPI + CLI
│       │   ├── streamlit/          # app.py (roteador) + chat_view + classic_view
│       │   ├── api/                # FastAPI (endpoints para frontend ChatGPT-like)
│       │   └── cli/
│       ├── config/                 # Configurações (env-aware)
│       │   └── settings.py
│       └── container.py            # Composition root (injeção de dependências)
└── README.md
```

A regra de dependência aponta sempre para dentro: `presentation → application → domain`, e adapters (`infrastructure`) implementam as **ports** definidas em `application/ports.py`.

## Pré-requisitos

- Python 3.10+
- (Opcional) [Ollama](https://ollama.com) rodando localmente em `http://localhost:11434`, com um modelo baixado, por exemplo:
  ```bash
  ollama pull llama3:latest
  ```

## Instalação

```bash
git clone https://github.com/<seu-usuario>/tcc-ufg.git
cd tcc-ufg

python3 -m venv .venv
source .venv/bin/activate

pip install -r backend/requirements.txt
```

## Como usar

O `backend/app.py` é o ponto de entrada único, com modo UI, API e CLI.

### API HTTP (frontend estilo ChatGPT)

Antes **não havia endpoints HTTP** — só Streamlit. Agora existe uma API FastAPI:

```bash
cd backend
pip install -r requirements.txt
python app.py api
# docs: http://localhost:8000/docs
```

#### Endpoints

| Método | Endpoint | Uso no frontend |
|---|---|---|
| `GET` | `/health` | Healthcheck |
| `GET` | `/v1/models` | Seletor de modelo / fontes |
| `POST` | `/v1/chat/completions` | **Chat principal** (estilo OpenAI/ChatGPT) |
| `POST` | `/v1/uploads` | Upload do PDF da petição |
| `GET` | `/v1/uploads/{petition_id}` | Metadados do PDF enviado |
| `GET` | `/v1/index` | Status do índice RAG |
| `POST` | `/v1/index/rebuild` | Recriar índice RAG |
| `POST` | `/v1/scrape` | Baixar PDFs públicos |

#### Chat — request

```json
{
  "model": "llama3:latest",
  "messages": [
    { "role": "user", "content": "O que é dano moral?" }
  ],
  "petition_id": null
}
```

Com petição (após `POST /v1/uploads`):

```json
{
  "model": "llama3:latest",
  "messages": [
    { "role": "user", "content": "analise minha petição" }
  ],
  "petition_id": "a1b2c3d4e5f6"
}
```

#### Chat — response (para UI ChatGPT-like)

Use no frontend:
- `choices[0].message.content` → texto do assistente
- `source` → badge da fonte (RAG / Ollama / Internet)
- `routing` → caption do roteamento
- `citations` → referências

```json
{
  "id": "chatcmpl-...",
  "model": "llama3:latest",
  "choices": [
    { "message": { "role": "assistant", "content": "..." } }
  ],
  "source": { "id": "rag", "label": "Base RAG jurídica", "icon": "📚" },
  "routing": { "intent": "ask_rag", "mode": "automatic", "reason": "..." },
  "citations": [{ "title": "peticao.pdf", "detail": "...", "url": "" }]
}
```

#### Upload

```bash
curl -F "file=@peticao.pdf" http://localhost:8000/v1/uploads
```

Guarde o `petition_id` e envie em `/v1/chat/completions`.

#### Exemplo mínimo (fetch)

```js
const res = await fetch("http://localhost:8000/v1/chat/completions", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "llama3:latest",
    messages: [{ role: "user", content: text }],
    petition_id: petitionId ?? null,
  }),
});
const data = await res.json();
const reply = data.choices[0].message.content;
const source = data.source;
```

### Frontend React (estilo ChatGPT)

```bash
# terminal 1 — API
cd backend
python app.py api

# terminal 2 — UI
cd frontend
npm install
npm run dev
```

Abra `http://localhost:5173`. A interface inclui:

- layout de chat (sidebar + mensagens + composer)
- upload de PDF no campo de mensagem
- badge de fonte / modelo / roteamento
- painel de citações

### Interface web Streamlit

```bash
cd backend
streamlit run app.py
# ou
python app.py ui
```

Acesse `http://localhost:8501` no navegador.

### CLI

```bash
cd backend
python app.py index    # cria/atualiza o índice RAG
python app.py scrape   # baixa PDFs públicos
python app.py api      # sobe a API em :8000
```

## Fluxo recomendado

1. `cd backend && python app.py scrape` → baixa PDFs jurídicos públicos
2. `cd backend && python app.py index` → cria o índice RAG e o relatório do corpus
3. `cd backend && python app.py api` + `cd frontend && npm run dev` → abre o chat React
4. (Opcional) Anexe uma petição em PDF e digite: _"analise minha petição"_ ou _"recrie esta petição"_

## Como o chatbot decide a fonte

A mensagem do usuário passa por um classificador heurístico de intenção. A fonte da resposta é mostrada como badge colorido acima de cada mensagem do assistente, e o roteamento é exibido como caption.

| Sinais na mensagem | Fonte usada | Badge |
|---|---|---|
| "analise", "avalie", "critique" + PDF anexado | use case `AnalyzePetition` | ⚖️ Análise crítica |
| "recrie", "melhore", "reescreva" + PDF anexado | use case `RecreatePetition` | ✍️ Recriação |
| "internet", "pesquise", "online", "duckduckgo" | DuckDuckGo + Ollama | 🌐 Internet |
| "base", "corpus", "rag", "similar", "anteriores" | RAG (busca semântica) + Ollama | 📚 RAG |
| qualquer outra | Ollama puro (chat geral) | 🤖 Ollama |

Cada resposta de RAG/Internet vem com um expansor de citações (trechos da base ou links da web) para auditoria.

## Configuração

Todas as configurações ficam em `backend/src/config/settings.py`, com valores padrão sensatos. É possível sobrepor via variáveis de ambiente, por exemplo:

| Variável | Padrão | Descrição |
|---|---|---|
| `RAG_EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Modelo de embeddings |
| `RAG_TOP_K` | `8` | Quantos chunks similares retornar |
| `RAG_ANONYMIZE` | `true` | Anonimiza CPF/CNPJ/processo/email/telefone |
| `OLLAMA_HOST` | `http://localhost:11434` | Endpoint do Ollama |
| `OLLAMA_MODEL` | `llama3:latest` | Modelo padrão do Ollama |
| `SCRAPING_DOWNLOAD_LIMIT` | `100` | Mínimo de PDFs novos por execução (aceitas + rejeitadas) |
| `SCRAPING_KEEP_REJECTED` | `true` | Sempre salvar também as rejeitadas |
| `SCRAPING_MAX_RUNTIME_SECONDS` | `2700` | Tempo máximo do scraping |

## Troubleshooting

### Spam de `ModuleNotFoundError: torchvision` no terminal

São avisos inofensivos do watcher do Streamlit ao inspecionar módulos lazy do `transformers`. A aplicação continua funcionando normalmente. Já tratado neste repositório via `backend/.streamlit/config.toml` com `fileWatcherType = "none"` — para recarregar após alterar código, use o botão **Rerun** da UI ou pressione `R`.

Se quiser hot-reload completo de volta, instale `torchvision` opcionalmente:

```bash
pip install torchvision
```

e remova/comente a linha `fileWatcherType` no config.

## Tecnologias

- **Python 3.10+** + `streamlit` (UI)
- `langchain` + `langchain-ollama` (orquestração do chatbot)
- `sentence-transformers` (E5) + `numpy` (embeddings/busca semântica)
- `pypdf` + `PyMuPDF` + `rapidocr` (leitura/OCR de PDFs)
- `reportlab` (geração de PDF a partir de Markdown)
- `ddgs` (busca web)
- `requests` + `beautifulsoup4` (scraping)
- `Ollama` (LLM local, opcional)


python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
streamlit run app.py        # ou: python app.py
python app.py scrape        # baixa PDFs
python app.py index         # cria índice RAG
python app.py --help        # lista comandos

estes de roteamento (16/16 ok)
Você digita	Fonte escolhida	Modo
"Oi, tudo bem?"
🤖 Ollama
automático (casual)
"O que é dano moral?"
📚 RAG
automático (jurídico)
"Como redigir uma petição inicial?"
📚 RAG
automático (jurídico)
"Me explique o art. 186 do código civil"
📚 RAG
automático (artigo de lei)
"Quais as últimas decisões do STJ?"
🌐 Internet
automático (temporal)
"Jurisprudência atual sobre indenização"
🌐 Internet
automático (temporal + jurídico)
"Qual o entendimento do STJ em 2024?"
🌐 Internet
automático (ano)
"Pesquise na internet sobre o STF"
🌐 Internet
explícito
"Compare com a base RAG"
📚 RAG
explícito
"Quanto é 2+2?"
🤖 Ollama
padrão
"analise minha petição" (com PDF)
⚖️ Análise
explícito
"recrie esta petição" (com PDF)
✍️ Recriação
explícito
