# Spec vigente — Análise e validação humana

**Status:** implemented
**Módulo:** scoring, analyze petition, API `/v1/validations`, dashboard React

## Objetivo

Analisar petição nas 6 dimensões do fluxograma Intelligent, registrar validação humana (lawyer-in-the-loop) **por petição** e apresentar um **dashboard de métricas** comparando avaliação do protótipo × avaliação humana, com campanha de **exatamente 30 avaliadores fixos** por petição analisada.

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
- Cadastro fixo de **30 avaliadores** na tabela `evaluators`
- Snapshots da aplicação em `application_evaluations` com `petition_id` (um snapshot atual por petição)
- Importação automática e única dos JSON legados de `validacoes/` (sem perda de dados)
- Registros legados sem vínculo explícito permanecem consultáveis, mas **não entram** nas métricas oficiais por petição
- Repositório atrás de port (`ValidationRepositoryPort`), na linha da Clean Architecture

### R8 — Endpoint de métricas agregadas
`GET /v1/validations/metrics` e métricas filtradas por `petition_id` retornam:
- `count`, petições distintas, avaliadores distintos
- progresso da campanha: `required_evaluations=30`, `completed`, `remaining`, `is_complete`
- `mean_mae`, `mean_agreement_rate`, `mean_general_score`, `mean_application_use_score`
- `dimensions`: por dimensão, média do protótipo × média humana × gap médio (seis dimensões + nota Geral)
- Visão global oficial considera somente petições com campanha **30/30**

### R11 — Campanha de 30 avaliadores por petição
- Cada petição analisada pela IA inicia campanha com **exatamente 30** vagas
- Os mesmos 30 avaliadores cadastrados avaliam **cada** petição (uma resposta por avaliador por petição)
- Unicidade: `(petition_id, evaluator_id)` — duplicata retorna HTTP 409
- Bloqueio da 31ª avaliação: HTTP 409 quando `completed == 30`
- Exclusão de uma avaliação reabre a vaga (`completed` volta a 29)
- Reanálise da mesma petição pela IA **atualiza apenas o snapshot da aplicação**; as avaliações humanas permanecem
- Submissão humana recebe `petition_id` + `evaluator_id`; `prototype_scores` e `petition_name` vêm do snapshot no servidor

### Métricas para apresentação dos resultados

Os resultados do trabalho devem apresentar, no mínimo, os seguintes indicadores:

| Grupo | Métrica | Definição | Interpretação |
|---|---|---|---|
| Aderência | MAE dos scores | Média de `\|score_protótipo - confiança_humana\|` nas seis dimensões, em escala 0–100% | Quanto menor, maior a proximidade entre o protótipo e a confiança humana |
| Aderência | Gap por dimensão | Média de `confiança_humana - score_protótipo` (0–100%) para as seis dimensões | Valores próximos de zero indicam menor viés sistemático |
| Aderência | Gap da nota geral | `geral_humano - geral_aplicação`, em escala 0–100% | Compara a confiança global do avaliador com a nota geral da aplicação |
| Aderência | Taxa de concordância | `(confirmados + 0,5 × parciais) / total de problemas avaliados` | Quanto maior, maior a concordância sobre os problemas identificados |
| Qualidade | Confiança geral média | Média da confiança geral (0–100%) atribuída pelos avaliadores | Resume a confiança global na avaliação da aplicação |
| Aceitação | Intenção média de uso | Percentual de avaliadores que responderam **SIM** a “utilizaria esta aplicação?” | Indica a aceitação binária (SIM/NÃO) da aplicação |
| Eficiência | Tempo médio humano | Média **global** dos tempos registrados pelos avaliadores (todas as petições) | Representa o custo temporal da avaliação manual |
| Eficiência | Tempo médio da aplicação | Média **global** das durações em `analysis_times` | Representa o tempo de processamento do protótipo |
| Eficiência | Ganho de tempo | `tempo_humano / tempo_aplicação` | Quantas vezes a aplicação é mais rápida que a avaliação manual |
| Eficiência | Redução de tempo | `1 - (tempo_aplicação / tempo_humano)` | Percentual de tempo poupado pelo uso do protótipo |
| Campanha | Progresso por petição | `completed / 30` avaliadores distintos | Indica se a coorte da petição está completa |

Também devem ser informados o número de petições avaliadas, o número de avaliações,
o número de avaliadores e a distribuição dos problemas confirmados, parciais e
rejeitados. A análise deve reportar os valores observados, sem afirmar validade
estatística ou generalização para a prática jurídica quando a amostra não for
probabilística.

### R9 — Dashboard no frontend
- View separada, alternável com o chat (botão no header)
- **Seletor de petição analisada** + progresso **N de 30** e vagas restantes
- **CRUD de avaliação humana (notas)** com: **seletor dos 30 avaliadores**, **notas (0–100%)** nas 6 dimensões + geral, e **SIM/NÃO** em “utilizaria esta aplicação” (sem campo de tempo)
- **CRUD de tempo** separado: um registro por avaliador (máx. 30), só para métricas de eficiência
- Avaliadores que já responderam a petição aparecem marcados; é possível editar a resposta existente
- Em 30/30, novas inclusões de notas ficam bloqueadas
- Tabela e médias de **notas** filtrados pela petição selecionada
- Gráficos e cards de **tempo** (eficiência) são **globais**: no máximo 30 registros (um por avaliador)
- Gráfico de barras **Aplicação × Avaliação humana** + card de aceitação (% SIM), filtrados pela petição
- API: `/v1/evaluators`, `/v1/application-evaluations`, `/v1/validations` (com `petition_id`/`evaluator_id`)

### R10 — Persistência da avaliação da aplicação
- Cada análise de petição grava/atualiza snapshot das **notas da aplicação** (6 dimensões + geral) em `application_evaluations` (0–100%), com `petition_id`
- Também persiste pontos de melhoria (`problems`) e resumo de injeção de prompt (risco/score)
- `GET /v1/application-evaluations` lista snapshots e progresso da campanha humana

### R13 — Tempo de avaliação humana (eficiência, independente das notas)
- O campo **Tempo de avaliação humana** serve **somente** às métricas de eficiência (gráficos/cards de tempo)
- **Não** faz parte das notas do avaliador (Estrutura, Clareza, Coerência, Fundamentação, Consistência, Elementos essenciais, Geral, Utilizaria)
- Há no máximo **30 registros** de tempo — **um por avaliador** do cadastro fixo (`evaluator_id` único)
- Registro único: criar uma vez; edição atualiza o mesmo registro; nova inclusão do mesmo avaliador → HTTP 409 (ou upsert na edição)
- Tempos globais: não dependem da petição selecionada
- Formulário de notas por petição **não** inclui nem exige tempo

### R12 — Exclusão de petição analisada
- `DELETE /v1/application-evaluations/{petition_id}` remove o snapshot da aplicação **e** todas as avaliações humanas vinculadas a essa petição
- Não remove o cadastro dos 30 avaliadores nem os tempos globais (`reading_times` / `analysis_times`)
- Petição inexistente → HTTP 404
- No dashboard: botão “Excluir petição” ao lado do seletor, com confirmação explícita do progresso da campanha

## Acceptance criteria

- [x] Scores das 6 dimensões + geral
- [x] API `POST/GET /v1/validations` com comparação MAE/acordo
- [x] Validações persistidas em SQLite; legado JSON importado automaticamente
- [x] `GET /v1/validations/metrics` retorna agregados (inclui médias humanas por dimensão, nota geral e intenção de uso)
- [x] Dashboard acessível na UI com CRUD (nome, tempo, notas do avaliador 0–100% nas 6 dimensões + geral + utilizaria)
- [x] `POST/GET /v1/reading-times` persiste no SQLite e retorna média dos tempos
- [x] CRUD completo de validações com notas em percentual (0–100%) e tempo de avaliação humana
- [x] 30 registros de avaliadores populados com tempos + confiança percentual
- [x] Exportação CSV dos registros e PNG do gráfico de linhas
- [x] Gráfico de pizza humano × aplicação + linhas de média no gráfico de linhas
- [x] Card de médias (tempo + notas) acima do formulário de registro, calculado a partir de todos os registros
- [x] Tempo real da aplicação gravado em SQLite; botão "Medir tempo da aplicação" atualiza a média dos gráficos
- [x] Notas da aplicação persistidas em `application_evaluations` a cada análise; dashboard compara médias app × humano
- [x] Gráfico comparativo de notas da aplicação × humanas e card de aceitação (SIM)
- [x] Cadastro fixo de 30 avaliadores; campanha 0/30 por petição com unicidade `(petition_id, evaluator_id)`
- [x] Reanálise da IA atualiza snapshot sem reiniciar avaliações humanas
- [x] Dashboard: notas e campanha filtrados por petição; tempos (gráficos/cards) agregados de todas as petições
- [x] Exclusão de petição analisada remove snapshot + avaliações humanas da campanha
- [x] Tempo de avaliação: no máx. 30 registros (1 por avaliador), separado das notas por petição
