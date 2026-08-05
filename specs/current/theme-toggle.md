# Feature spec — Temas claro e escuro

**Status:** implemented  
**Owner:** frontend  
**Related:** `specs/current/api-frontend.md`

## Problema

O frontend tem apenas o tema claro atual; usuários em ambientes escuros precisam de um tema dark com alternância rápida.

## Objetivo

Dois temas (claro = atual; escuro) e um ícone no header do chat que alterna entre eles.

## Fora de escopo

- Temas além de claro/escuro
- Preferência sincronizada com conta/backend
- Troca automática por horário

## Requisitos

### R1 — Temas

- **Claro:** visual atual (padrão).
- **Escuro:** fundo e superfícies escuros, texto claro, contraste legível na área do chat e composer.

### R2 — Toggle

Ícone no header do chat (próximo a “Nova conversa”) alterna claro ↔ escuro. Ícone/aria-label refletem o tema **para o qual** se vai.

### R2b — Borda animada do composer

O `.composer-box` tem borda fina (~1px) com gradiente conic nas cores do tema, rotacionando continuamente. Respeita `prefers-reduced-motion` (borda estática).

### R3 — Persistência

Preferência salva em `localStorage` (`critico-juridico-theme`) e restaurada no carregamento (script antecipado evita flash).

### R4 — Sem backend

Nenhuma rota nova.

## Cenários

### Cenário A — alternar

**Dado** tema claro  
**Quando** o usuário clica no ícone de tema  
**Então** a UI muda para escuro e o ícone atualiza

### Cenário B — persistir

**Dado** tema escuro salvo  
**Quando** a página recarrega  
**Então** o tema escuro permanece

## Acceptance criteria

- [x] Temas claro e escuro disponíveis
- [x] Ícone no header alterna os temas
- [x] Preferência persistida em `localStorage`
- [x] Borda fina do input com animação de cores do tema
- [x] Sem mudanças de API

## Impacto técnico

- Frontend: CSS variables (`data-theme`), `useTheme`, `ThemeToggle`, botão no `App.tsx`
- Backend: nenhum
