# Produto — Visão geral

## Problema

Advogados precisam analisar petições à luz de peças semelhantes com desfechos conhecidos (deferimento vs indeferimento), com apoio de LLM local e rastreabilidade das fontes.

## Solução

**Crítico Jurídico Inteligente**: chatbot que roteia entre RAG, Ollama, Internet, análise e recriação de petição; corpus com casos favoráveis e desfavoráveis.

## Personas

- Estudante/pesquisador (TCC)
- Operador jurídico (validação humana opcional via API)

## Capacidades principais

1. Chat com roteamento automático de intenção
2. Upload de petição PDF
3. Análise multi-dimensional (6 critérios do fluxograma Intelligent)
4. Recriação com comentários inline
5. Scrape + índice RAG (aceitas + rejeitadas)
6. API HTTP para o frontend React

## Fora de escopo (por enquanto)

- Viewer PDF completo no React (existe no Streamlit clássico)
- Streaming token-a-token do chat
- Dataset gold estatístico formal de comparação humano×máquina (API de validação existe; UI de card de comparação foi removida)
