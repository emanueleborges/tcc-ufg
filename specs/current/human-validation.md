# Spec vigente — Análise e validação humana

**Status:** implemented
**Módulo:** scoring, analyze petition, API `/v1/validations`, dashboard React

## Objetivo

Analisar petição nas 6 dimensões do fluxograma Intelligent, registrar validação humana (lawyer-in-the-loop) e apresentar um **dashboard de métricas** comparando avaliação do protótipo × avaliação humana, com médias das avaliações humanas para a apresentação do TCC.

## Dimensões de score

1. estrutura  
2. clareza  
3. coerencia  
4. fundamentacao  
5. consistencia  
6. elementos_essenciais  

## Requisitos

### R7 — Persistência em SQLite
- Validações humanas armazenadas em **SQLite** (`backend/validacoes/validacoes.db`, tabela `validations`)
- Importação automática e única dos JSON legados de `validacoes/` (sem perda de dados)
- Repositório atrás de port (`ValidationRepositoryPort`), na linha da Clean Architecture

### R8 — Endpoint de métricas agregadas
`GET /v1/validations/metrics` retorna:
- `count`, petições distintas, avaliadores distintos
- `mean_mae`, `mean_agreement_rate`, `mean_final_quality` (média da qualidade final atribuída pelo humano, 1–5)
- `dimensions`: por dimensão, média do protótipo × média humana × gap médio
- `problems`: totais de problemas confirmados/parciais/rejeitados

### R9 — Dashboard no frontend (simplificado)
- View separada, alternável com o chat (botão no header)
- **CRUD simples de tempo de leitura humana:** formulário com apenas **nome do advogado + tempo gasto lendo a petição** (hh:mm); edição e exclusão de registros na lista
- Lista dos registros (advogado — tempo) e **tempo médio** de leitura, para comparação com o tempo do protótipo no TCC
- **Gráfico de linhas** dos tempos por advogado (eixo Y hh:mm), com linha da média humana e referência da média do protótipo
- **Tempo real da aplicação:** cada análise de petição grava a duração em SQLite (`analysis_times`); a média alimenta o gráfico de linhas e a pizza (humano × aplicação)
- Botão no dashboard **"Medir tempo da aplicação"** para executar medições sob demanda e atualizar a média
- API própria: `POST/GET /v1/reading-times`, `PUT/DELETE /v1/reading-times/{id}`, persistida no mesmo SQLite (`validacoes/validacoes.db`, tabela `reading_times`)
- (O formulário completo de validação com scores/checklist foi removido da UI; a API `/v1/validations` segue disponível.)

## Acceptance criteria

- [x] Scores das 6 dimensões + geral
- [x] API `POST/GET /v1/validations` com comparação MAE/acordo
- [x] Validações persistidas em SQLite; legado JSON importado automaticamente
- [x] `GET /v1/validations/metrics` retorna agregados (inclui média humana por dimensão e qualidade final média)
- [x] Dashboard acessível na UI com formulário simples (advogado + tempo), lista de registros e tempo médio
- [x] `POST/GET /v1/reading-times` persiste no SQLite e retorna média dos tempos
- [x] CRUD completo: `PUT/DELETE /v1/reading-times/{id}` e editar/excluir na UI
- [x] Exportação CSV dos registros e PNG do gráfico de linhas
- [x] Gráfico de pizza humano × aplicação + linhas de média no gráfico de linhas
- [x] Tempo real da aplicação gravado em SQLite; botão "Medir tempo da aplicação" atualiza a média dos gráficos
