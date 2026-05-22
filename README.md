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

O projeto segue **Clean Architecture**, com camadas isoladas por responsabilidade:

```
tcc-ufg/
├── app.py                          # Ponto de entrada (UI + CLI)
├── requirements.txt
├── README.md
└── src/
    ├── domain/                     # Entidades puras e padrões linguísticos jurídicos
    │   ├── entities.py
    │   └── patterns.py
    ├── application/                # Regras de aplicação (ports + use cases)
    │   ├── ports.py
    │   └── use_cases/
    │       ├── build_index.py
    │       ├── analyze_petition.py
    │       ├── recreate_petition.py
    │       ├── download_petitions.py
    │       ├── generate_corpus_report.py
    │       └── chat_with_assistant.py
    ├── infrastructure/             # Adapters concretos
    │   ├── pdf/                    # leitura, OCR, geração de PDF
    │   ├── nlp/                    # chunking, features, sections, embeddings
    │   ├── persistence/            # índice RAG em disco
    │   ├── llm/                    # cliente Ollama (não-conversacional)
    │   ├── langchain/              # chat conversacional (ChatOllama)
    │   ├── search/                 # busca web (DuckDuckGo)
    │   └── scraping/               # baixador de PDFs públicos
    ├── services/                   # Orquestração entre use cases e infra
    │   ├── chunk_factory.py
    │   ├── semantic_search.py
    │   ├── scoring.py
    │   ├── benchmarks.py
    │   ├── inline_comments.py
    │   ├── report_renderer.py
    │   └── chat/                   # Estratégias e orquestrador do chatbot
    │       ├── intent_classifier.py
    │       ├── orchestrator.py
    │       ├── prompts.py
    │       ├── ollama_answerer.py
    │       ├── rag_answerer.py
    │       ├── internet_answerer.py
    │       └── petition_answerers.py
    ├── presentation/               # UI Streamlit + CLI
    │   ├── streamlit/              # app.py (roteador) + chat_view + classic_view
    │   └── cli/
    ├── config/                     # Configurações (env-aware)
    │   └── settings.py
    └── container.py                # Composition root (injeção de dependências)
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

pip install -r requirements.txt
```

## Como usar

O `app.py` é o ponto de entrada único, com modo UI e modo CLI.

### Interface web (recomendado)

```bash
streamlit run app.py
# ou
python app.py
python app.py ui
```

Acesse `http://localhost:8501` no navegador.

### CLI

Indexar PDFs aceitos em `downloads_peticoes/aceitas/`:

```bash
python app.py index
```

Baixar PDFs públicos para alimentar a base:

```bash
python app.py scrape
```

## Fluxo recomendado

1. `python app.py scrape` → baixa PDFs jurídicos públicos
2. `python app.py index` → cria o índice RAG e o relatório do corpus
3. `streamlit run app.py` → abre o chatbot
4. (Opcional) Anexe sua petição em PDF na barra lateral e digite no chat: _"analise minha petição"_ ou _"recrie esta petição"_

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

Todas as configurações ficam em `src/config/settings.py`, com valores padrão sensatos. É possível sobrepor via variáveis de ambiente, por exemplo:

| Variável | Padrão | Descrição |
|---|---|---|
| `RAG_EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Modelo de embeddings |
| `RAG_TOP_K` | `8` | Quantos chunks similares retornar |
| `RAG_ANONYMIZE` | `true` | Anonimiza CPF/CNPJ/processo/email/telefone |
| `OLLAMA_HOST` | `http://localhost:11434` | Endpoint do Ollama |
| `OLLAMA_MODEL` | `llama3:latest` | Modelo padrão do Ollama |
| `SCRAPING_DOWNLOAD_LIMIT` | `30` | Máximo de PDFs novos por execução |
| `SCRAPING_MAX_RUNTIME_SECONDS` | `900` | Tempo máximo do scraping |

## Troubleshooting

### Spam de `ModuleNotFoundError: torchvision` no terminal

São avisos inofensivos do watcher do Streamlit ao inspecionar módulos lazy do `transformers`. A aplicação continua funcionando normalmente. Já tratado neste repositório via `.streamlit/config.toml` com `fileWatcherType = "none"` — para recarregar após alterar código, use o botão **Rerun** da UI ou pressione `R`.

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
pip install -r requirements.txt

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
