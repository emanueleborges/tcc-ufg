# Spec-Driven Development (SDD)

Este TCC usa SDD: **especificação primeiro**, implementação depois.

## Ciclo

```text
Specify → Clarify → Plan → Tasks → Implement → Validate
```

| Fase | Saída |
|---|---|
| Specify | Spec em `specs/current/` ou `specs/backlog/` |
| Clarify | Critérios de aceite sem ambiguidade |
| Plan | Arquitetura / contratos / impacto |
| Tasks | Lista atômica |
| Implement | Código alinhado à spec |
| Validate | Checklist de aceite marcado |

## Estrutura

```text
specs/
├── constitution.md
├── README.md                 ← este arquivo
├── product/overview.md
├── current/                  ← comportamento vigente
├── backlog/                  ← ainda não implementado / em design
└── templates/
    ├── feature-spec.md
    ├── plan.md
    └── tasks.md
```

## Como pedir trabalho ao agente

Exemplos de prompt:

- “Atualize a spec `specs/current/rag-corpus.md` e só depois implemente.”
- “Crie spec em backlog para X, com critérios de aceite, sem codar.”
- “Implemente a spec `specs/current/chat-routing.md` (SDD).”

A regra Cursor `.cursor/rules/sdd.mdc` reforça esse fluxo em toda sessão.
