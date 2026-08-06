# Как вносить изменения

Этот репозиторий — портфолио-проект и runtime-слой QA Knowledge OS. Главная
цель изменений: сделать систему более понятной, проверяемой и полезной для
реальных QA-workflow.

## Принципы

- Runtime собирает контекст, но не притворяется AI-агентом.
- Источники и evidence важнее красивой генерации.
- Jira и внешние системы читаются безопасно и без скрытых write-действий.
- Локальные данные, `.env`, кэши и snapshots не попадают в Git.
- Новая возможность должна улучшать реальный рабочий сценарий QA-инженера.

## Локальный запуск

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check app tests main.py --select E9,F63,F7,F82
```

## Checklist перед PR

- [ ] Изменение не смешивает runtime и durable knowledge.
- [ ] Добавлены или обновлены тесты.
- [ ] README/docs обновлены, если изменилось поведение.
- [ ] Нет `.env`, `.venv`, `.qaskills`, кэшей, snapshots и личных данных.
- [ ] Ошибки внешних систем обрабатываются явно.
