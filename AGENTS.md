# AGENTS.md — Constituição do projeto (SDD)

Este repositório usa **Spec-Driven Development (SDD)**.
A especificação é a fonte da verdade; o código implementa a spec.

## Fluxo obrigatório

1. **Specify** — atualizar/criar spec em `specs/`
2. **Clarify** — remover ambiguidades e critérios de aceite
3. **Plan** — plano técnico derivado da spec
4. **Tasks** — tarefas atômicas verificáveis
5. **Implement** — só então alterar código
6. **Validate** — checar aceite da spec (não “parece ok”)

## Princípios (constitution)

1. Clean Architecture: `presentation → application → domain`; infra implementa ports.
2. Backend em `backend/`, frontend em `frontend/`.
3. Base RAG trinária: `aceitas/` (deferido), `rejeitadas/` (indeferido) e `parcial/`; índice usa as três.
4. Chat com personas jurídicas selecionáveis (Geral + especialidades); prompts em `personas.py`.
5. Chat: respostas limpas; referências no painel (não ecoar PDFs no texto).
6. Análise de petição anexada inclui varredura de injeção de prompt (OWASP LLM01), exibida no painel e no chat.
7. Não inventar endpoints/comportamentos fora da spec; atualize a spec primeiro.
8. Sem commits sem pedido explícito do usuário.
9. Respostas ao usuário em português.

## Onde estão as specs

| Artefato | Caminho |
|---|---|
| Constituição / SDD | `specs/constitution.md`, este `AGENTS.md` |
| Visão do produto | `specs/product/overview.md` |
| Specs vigentes | `specs/current/*.md` |
| Backlog / próximas | `specs/backlog/` |
| Templates | `specs/templates/` |

## Ao implementar uma feature

- Copie `specs/templates/feature-spec.md` → `specs/current/<feature>.md` (ou `specs/backlog/` se ainda não aprovada).
- Preencha requisitos, cenários e **acceptance criteria**.
- Só depois edite código em `backend/` / `frontend/`.
- Ao terminar, marque critérios de aceite e atualize a spec se o comportamento mudou.
