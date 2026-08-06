# Demo: QA Knowledge OS

Этот demo-сценарий использует только обезличенные данные из `demo/`.

## 1. Установка

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
```

## 2. Запуск на demo vault

```bash
export QASKILLS_MEMORY_VAULT_PATH="./demo/vault"
export QASKILLS_DOCUMENT_INDEX_PATH=".qaskills/demo_document_index.json"

./qaskills doctor
./qaskills find authorization
./qaskills ask "Что проверить в авторизации?"
```

## 3. Ожидаемый результат

Система должна:

- найти документы из demo vault;
- показать источники и причины совпадения;
- не требовать реальный Jira/API token;
- вернуть source-backed fallback, если LLM не настроен.

## 4. Что это демонстрирует

- локальный индекс знаний;
- evidence-first подход;
- безопасную деградацию без LLM;
- подготовку контекста для AI-ассистента.
