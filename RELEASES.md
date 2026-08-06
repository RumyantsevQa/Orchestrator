# Релизы

## v0.2 — Portfolio-ready MVP

Фокус: показать QA Knowledge OS как инженерный runtime для AI-assisted QA.

Что входит:

- русскоязычный README для CTO/Team Lead/HR;
- CI pipeline: lint + tests;
- demo-данные без личной информации;
- GitHub hygiene;
- Source Pack / MCP / Jira read-only story;
- список скриншотов и GIF-сценарий.

## v0.1 — Runtime baseline

Фокус: доказать, что локальный knowledge engine работает.

Что вошло:

- CLI;
- Markdown/Obsidian index;
- metadata search;
- Knowledge API;
- MCP server;
- read-only Jira boundary;
- daily snapshots;
- fallback без LLM;
- базовые regression tests.

## Checklist релиза

- [ ] `pytest -q` проходит локально.
- [ ] `ruff check` проходит локально.
- [ ] В репозитории нет `.env`, `.venv`, кэшей и локального state.
- [ ] Demo запускается без личных данных.
- [ ] README отвечает на вопросы: что это, зачем, как проверить.
