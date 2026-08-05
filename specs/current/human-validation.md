# Spec vigente — Análise e validação humana

**Status:** partial  
**Módulo:** scoring, analyze petition, API `/v1/validations`

## Objetivo

Analisar petição nas 6 dimensões do fluxograma Intelligent e permitir registro de validação humana (lawyer-in-the-loop) via API.

## Dimensões de score

1. estrutura  
2. clareza  
3. coerencia  
4. fundamentacao  
5. consistencia  
6. elementos_essenciais  

## Acceptance criteria

- [x] Scores das 6 dimensões + geral
- [x] API `POST/GET /v1/validations` com comparação MAE/acordo
- [x] UI **não** exibe card “Comparação humano × protótipo” (removido de propósito)
- [ ] UI opcional mínima de validação (só se nova spec aprovar)

## Nota de produto

Validação humana permanece disponível na API/persistência (`backend/validacoes/`); a interface React prioriza o fluxo de chat/análise sem o card de comparação.
