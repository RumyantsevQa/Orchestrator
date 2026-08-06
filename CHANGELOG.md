# Changelog

Все заметные изменения QA Knowledge OS фиксируются здесь.

## v0.2 — Portfolio-ready MVP — 2026-08-06

### Добавлено

- README полностью переписан на русском языке под российский CTO/Team Lead/HR
  review.
- Добавлены Mermaid-схемы архитектуры и границы ответственности.
- Добавлен CI pipeline: lint + tests.
- Добавлены обезличенные demo-данные.
- Добавлены списки скриншотов и GIF-сценарий.
- Добавлены release notes, contributing guide и GitHub metadata.

### Изменено

- Репозиторий позиционируется как runtime-слой экосистемы: QA Knowledge OS.
- Публичная упаковка отделена от внутренней истории QASkills.
- Усилена GitHub hygiene: локальные state/cache/env/output не должны попадать
  в публикацию.

## v0.1 — Runtime baseline

### Добавлено

- CLI entrypoint.
- Pipeline: intent, planner, capability registry, executor, response composer.
- MemoryService для Markdown/Obsidian vault.
- Persistent JSON document index.
- Metadata search по title, aliases, headings, tags и path.
- Source Pack responses.
- Read-only Jira commands.
- SnapshotService и daily change analysis.
- Optional LLM provider boundary.
- MCP server.
- Regression tests.

### Ограничения

- Jira только read-only.
- Нет semantic search/vector DB.
- Нет packaged installer.
- UI пока CLI-first.
