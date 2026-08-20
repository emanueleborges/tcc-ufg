# Relatório — Tempo de avaliação de petição: humano × protótipo

**Objetivo:** comparar o tempo que um advogado leva, humanamente, para ler e avaliar integralmente uma petição com o tempo que a aplicação leva para analisar a mesma petição.

## Avaliação humana

**Amostra:** 30 avaliações realizadas por advogados (`reading_times`).

| Métrica | Tempo |
|---|---|
| **Tempo médio** | **2h02** |
| Mediana | ≈ 2h00 |
| Mínimo | 1h30 |
| Máximo | 2h30 |

## Avaliação pela aplicação

**Fonte:** tabela `analysis_times` no SQLite (`validacoes/validacoes.db`) — média de **todas** as medições gravadas (botão “Medir” + análises reais no chat).

| # | Petição (resumo) | Tempo (s) | Origem |
|---|---|---:|---|
| 1 | 030-kelly-matos-lucrecio… | 0,185 | measure |
| 2 | 030-kelly-matos-lucrecio… | 0,182 | measure |
| 3 | 030-kelly-matos-lucrecio… | 0,238 | measure |
| 4 | 013-tribunal-de-justica-de-minas… | 10,856 | auto |
| 5 | art20180815-20… | 0,579 | auto |
| 6 | boletimjulgados… | 7,144 | auto |
| 7 | 051-…uber_ok… | 1,223 | auto |
| 8 | 057-cb6bbc89… | 2,980 | auto |
| 9 | 076-pdf-acao-indenizatoria… | 0,511 | auto |
| 10 | boletimjulgados… | 7,081 | auto |
| 11 | 041-diario-da-justica… | 5,377 | auto |
| | **Média (11 medições)** | **3,305 s ≈ 3,3 s** | |

## Comparação

| | Humano | Aplicação |
|---|---|---|
| Tempo médio | 2h02 (7.338 s) | **3,3 s** |
| Amostra | 30 registros | 11 medições |

- A aplicação é cerca de **2.221× mais rápida** que a avaliação humana.
- **Redução de ≈ 99,95%** no tempo de análise da petição.

## Conclusão

Enquanto um advogado leva em média **cerca de 2 horas** para ler e avaliar uma petição completa, a aplicação realiza a análise multidimensional em **cerca de 3,3 segundos** (média real da base), permitindo triagem imediata sem substituir o julgamento jurídico do profissional.

*Fontes: `reading_times` e `analysis_times` no SQLite do dashboard.*
