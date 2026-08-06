# GIF demo

Продолжительность: 30-40 секунд.

## Сценарий

1. Открыть README и показать короткое описание.
2. Перейти в терминал.
3. Выполнить:

```bash
export QASKILLS_MEMORY_VAULT_PATH="./demo/vault"
export QASKILLS_DOCUMENT_INDEX_PATH=".qaskills/demo_document_index.json"
./qaskills doctor
./qaskills find authorization
./qaskills ask "Что проверить в авторизации?"
```

4. Вернуться к Mermaid-схеме архитектуры.

## Что должен понять зритель

Проект не просто “вызывает AI”. Он собирает контекст из источников и только
после этого отдаёт его ассистенту или пользователю.
