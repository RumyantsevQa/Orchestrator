import os
import shlex
import subprocess
import sys
from pathlib import Path

from app.core.config import load_settings
from app.core.models import UserRequest
from app.core.orchestrator import Orchestrator
from app.index.manager import IndexManager
from app.index.models import IndexedDocument
from app.providers.router import ProviderRouter
from app.core.version import APP_VERSION, PRODUCT_NAME, PRODUCT_TAGLINE


APP_NAME = PRODUCT_NAME
TAGLINE = PRODUCT_TAGLINE
VERSION = APP_VERSION


class Style:
    """Tiny ANSI styling helper used instead of an external CLI dependency."""

    def __init__(self):
        self.enabled = sys.stdout.isatty() and os.getenv("NO_COLOR") is None

    def color(self, text: str, code: str) -> str:
        if not self.enabled:
            return text

        return f"\033[{code}m{text}\033[0m"

    def title(self, text: str) -> str:
        return self.color(text, "1;36")

    def section(self, text: str) -> str:
        return self.color(text, "1;37")

    def ok(self, text: str) -> str:
        return self.color(text, "32")

    def warn(self, text: str) -> str:
        return self.color(text, "33")

    def dim(self, text: str) -> str:
        return self.color(text, "2")


STYLE = Style()


def main(argv: list[str] | None = None) -> int:
    """Run the QASkills demo CLI."""

    args = list(sys.argv[1:] if argv is None else argv)

    if not args:
        return command_home()

    command = args[0].lower()
    rest = args[1:]

    commands = {
        "help": command_help,
        "--help": command_help,
        "-h": command_help,
        "workspace": command_workspace,
        "status": command_status,
        "doctor": command_doctor,
        "find": command_find,
        "open": command_open,
        "ask": command_ask,
        "demo": command_demo,
        "morning": command_morning,
        "prepare": command_prepare,
        "jira": command_jira,
        "remember": command_remember,
        "save": command_remember,
        "запомни": command_remember,
        "сохрани": command_remember,
        "добавь": command_remember,
    }

    if command in commands:
        return commands[command](rest)

    return command_natural_language(" ".join(args))


def command_home(args: list[str] | None = None) -> int:
    _ = args

    if sys.stdin.isatty():
        return command_workspace([])

    header()

    print(STYLE.section("Ready for QA work."))
    print()
    print("Try:")
    bullet("qaskills help")
    bullet("qaskills status")
    bullet("qaskills find architecture")
    bullet("qaskills ask Что мы решили про архитектуру?")

    return 0


def command_workspace(args: list[str] | None = None) -> int:
    _ = args

    if not sys.stdin.isatty():
        header("Workspace")
        print_workspace_menu()
        return 0

    while True:
        header("Workspace")
        print("Доброе утро.")
        print("Что будем делать?")
        print()
        print_workspace_menu()

        choice = input("Выберите действие: ").strip()

        if choice in {"9", "exit", "quit", "выход"}:
            print(STYLE.ok("Рабочая сессия завершена."))
            return 0

        if not choice:
            continue

        print()

        if choice == "1":
            command_prepare(["daily"])
            pause()
            continue

        if choice == "2":
            task = prompt_line("Опишите задачу или укажите Jira key")
            if task:
                run_pipeline_view(f"проанализируй задачу {task}", "Task Analysis")
            pause()
            continue

        if choice == "3":
            query = prompt_line("Что найти в знаниях")
            if query:
                command_find([query])
            pause()
            continue

        if choice == "4":
            context = prompt_line("К чему относится bug report")
            command_jira(["bug", context] if context else ["bug"])
            pause()
            continue

        if choice == "5":
            command_remember([])
            pause()
            continue

        if choice == "6":
            command_jira([])
            continue

        if choice == "7":
            notes = prompt_line("Вставьте краткие заметки встречи")
            if notes:
                run_pipeline_view(f"анализ встречи {notes}", "Meeting Analysis")
            pause()
            continue

        if choice == "8":
            command_status([])
            pause()
            continue

        run_pipeline_view(choice, "QASkills")
        pause()


def command_help(args: list[str] | None = None) -> int:
    _ = args
    header()
    print(STYLE.section("Commands"))
    print()
    command_group(
        "Knowledge",
        [
            ("qaskills", "Open the QASkills workspace."),
            ("qaskills status", "Show vault and document index status."),
            ("qaskills doctor", "Run demo-readiness diagnostics."),
            ("qaskills prepare daily", "Prepare an analytical Jira daily briefing."),
            ("qaskills morning", "Show a morning QA briefing from local data."),
            ("qaskills remember \"...\"", "Save a new note to the Obsidian vault."),
        ],
    )
    command_group(
        "Search",
        [
            ("qaskills find architecture", "Search title, aliases, headings, tags, and path."),
            ("qaskills find migration", "Find migration-related documents."),
            ("qaskills find QA", "Find documents tagged or titled around QA."),
        ],
    )
    command_group(
        "Questions",
        [
            ("qaskills ask Что мы решили про архитектуру?", "Prepare a grounded source pack from local knowledge."),
        ],
    )
    command_group(
        "AI",
        [
            ("QASKILLS_PROVIDER_POLICY=AUTO qaskills ask ...", "Use local LLM when available, otherwise fall back to sources."),
            ("QASKILLS_PROVIDER_POLICY=LOCAL_ONLY qaskills morning", "Use only the local LM Studio provider."),
            ("QASKILLS_PROVIDER_POLICY=CODEX_PREFERRED qaskills ask ...", "Prefer Codex CLI, then local LLM."),
        ],
    )
    command_group(
        "Navigation",
        [
            ("qaskills open architecture", "Open the best matching document."),
            ("qaskills open QASkills", "Open a known project memory document."),
        ],
    )
    command_group(
        "Jira",
        [
            ("qaskills jira", "Open the Jira workspace."),
            ("qaskills jira whoami", "Show the authenticated Jira user."),
            ("qaskills jira projects", "List Jira projects visible to the user."),
            ("qaskills jira issue SCRUM-42", "Read a Jira issue from Jira Cloud."),
            ("qaskills jira SCRUM-42", "Prepare the workspace for a Jira issue."),
            ("qaskills jira bug SCRUM-42", "Create a bug report draft path."),
        ],
    )
    command_group(
        "Diagnostics",
        [
            ("qaskills demo", "Run the one-minute product demo."),
        ],
    )

    return 0


def command_status(args: list[str] | None = None) -> int:
    _ = args
    manager = index_manager()
    index = manager.ensure_indexed()

    header("System Status")
    status_line("Vault", Path(index.vault_path).exists(), index.vault_path)
    status_line("Document Index", manager.index_path.exists(), str(manager.index_path))
    status_line("Documents Count", True, str(len(index.documents)))
    status_line("Last Index Time", True, index.built_at)
    status_line("Search", True, "metadata search ready")
    status_line("Answer Mode", True, "source-first local knowledge")
    status_line("Jira Workspace", True, "workspace boundary ready")
    provider_status = provider_router().status()
    status_line("Provider Policy", True, str(provider_status["policy"]))
    status_line(
        "Local LLM Provider",
        bool(provider_status["local_provider_reachable"]),
        provider_detail(
            bool(provider_status["local_provider_reachable"]),
            "LM Studio reachable",
            str(provider_status["local_error"] or "LM Studio not reachable"),
        ),
    )
    status_line(
        "Local Chat Model",
        bool(provider_status["local_chat_model_available"]),
        provider_detail(
            bool(provider_status["local_chat_model_available"]),
            f"model {provider_status['local_model']}",
            str(provider_status["local_error"] or "no compatible chat model"),
        ),
    )
    status_line(
        "Local Generation",
        bool(provider_status["local_generation_works"]),
        provider_detail(
            bool(provider_status["local_generation_works"]),
            "lightweight generation works",
            str(provider_status["local_error"] or "generation failed"),
        ),
    )
    status_line(
        "Codex CLI",
        True,
        provider_detail(
            bool(provider_status["codex_available"]),
            "available for CODEX_ONLY/CODEX_PREFERRED",
            "not available, source fallback enabled",
        ),
    )

    return 0


def command_doctor(args: list[str] | None = None) -> int:
    _ = args
    manager = index_manager()

    header("Doctor")
    checks = []

    try:
        index = manager.ensure_indexed()
        checks.append(("Vault", Path(index.vault_path).exists(), index.vault_path))
        checks.append(("Index", manager.index_path.exists(), str(manager.index_path)))
        checks.append(("Memory", len(index.documents) > 0, f"{len(index.documents)} documents"))
        checks.append(("Search", True, "metadata search is available"))
        checks.append(("Configuration", True, "environment/defaults loaded"))
        checks.append(("Answer Mode", True, "source-first local knowledge"))
        checks.append(("Jira Workspace", True, "boundary ready, no live API required"))
        provider_status = provider_router().status()
        checks.append(("Provider Policy", True, str(provider_status["policy"])))
        checks.append(
            (
                "Local LLM Provider",
                bool(provider_status["local_provider_reachable"]),
                provider_detail(
                    bool(provider_status["local_provider_reachable"]),
                    "LM Studio reachable",
                    str(provider_status["local_error"] or "LM Studio not reachable"),
                ),
            )
        )
        checks.append(
            (
                "Local Chat Model",
                bool(provider_status["local_chat_model_available"]),
                provider_detail(
                    bool(provider_status["local_chat_model_available"]),
                    f"model {provider_status['local_model']}",
                    str(provider_status["local_error"] or "no compatible chat model"),
                ),
            )
        )
        checks.append(
            (
                "Local Generation",
                bool(provider_status["local_generation_works"]),
                provider_detail(
                    bool(provider_status["local_generation_works"]),
                    "lightweight generation works",
                    str(provider_status["local_error"] or "generation failed"),
                ),
            )
        )
        checks.append(("Codex CLI", True, self_check_label(provider_status["codex_available"])))
    except Exception as error:
        checks.append(("Index", False, str(error)))

    for name, ok, detail in checks:
        status_line(name, ok, detail)

    print()
    if all(ok for _, ok, _ in checks):
        print(STYLE.ok("✅ Everything is ready."))
        return 0

    print(STYLE.warn("⚠ Some checks need attention."))
    return 1


def command_find(args: list[str] | None = None) -> int:
    query = " ".join(args or []).strip()

    if not query:
        return friendly_error(
            "По запросу ничего не найдено.",
            ["qaskills find architecture", "qaskills find migration", "qaskills find QASkills"],
        )

    response = Orchestrator().process(UserRequest(text=f"find {query}"))

    if not has_search_results(response):
        return friendly_error(
            f"По запросу '{query}' ничего не найдено.",
            ["architecture", "migration", "qaskills"],
        )

    header(f"Find: {query}")
    print(STYLE.section("Pipeline"))
    for event in response.data["pipeline"]:
        bullet(f"{event['component']} → {event['message']}")
    print()
    print(STYLE.section("Results"))
    print(response.message)

    return 0


def command_open(args: list[str] | None = None) -> int:
    query = " ".join(args or []).strip()

    if not query:
        return friendly_error(
            "Документ не найден.",
            ["qaskills open architecture", "qaskills open migration", "qaskills open QASkills"],
        )

    search_response = Orchestrator().process(UserRequest(text=f"find {query}"))
    results = search_results_from_response(search_response)

    if not results:
        return friendly_error(
            "Документ не найден.",
            ["architecture", "migration", "qaskills"],
        )

    selected = choose_document(results)

    if not selected:
        return 0

    full_path = Path(load_settings().memory_vault_path).expanduser().resolve() / selected.path
    header("Open Document")
    key_value("Document", selected.title)
    key_value("Path", selected.path)

    try:
        subprocess.run(["open", str(full_path)], check=False)
        print()
        print(STYLE.ok("✅ Открываю документ в системном приложении."))
    except OSError as error:
        print()
        print(STYLE.warn(f"Не удалось открыть документ: {error}"))
        return 1

    return 0


def command_ask(args: list[str] | None = None) -> int:
    question = " ".join(args or []).strip()

    if not question:
        header("Ask QASkills")
        question = input("> ").strip()

    if not question:
        return friendly_error(
            "Вопрос пустой.",
            ["qaskills ask Что мы решили про архитектуру?", "qaskills ask Как устроен индекс?"],
        )

    response = Orchestrator().process(UserRequest(text=f"ask {question}"))

    header("Ask")
    key_value("Question", question)
    print()
    print(STYLE.section("Search"))
    print("Searching indexed local knowledge through the unified pipeline...")
    print()
    print(STYLE.section("Pipeline"))
    for event in response.data["pipeline"]:
        bullet(f"{event['component']} → {event['message']}")
    print()
    print(STYLE.section("Answer"))
    print(response.message)

    return 0 if response.success and has_search_results(response) else 1


def command_demo(args: list[str] | None = None) -> int:
    _ = args
    settings = load_settings()
    recent_response = Orchestrator().process(
        UserRequest(text="Покажи последние документы")
    )
    search_response = Orchestrator().process(UserRequest(text="find architecture"))
    ask_response = Orchestrator().process(
        UserRequest(text="ask Что мы решили про архитектуру?")
    )
    recent_artifact = first_artifact(recent_response, "memory_recent_documents")
    document_count = (
        recent_artifact.get("metadata", {}).get("document_count", 0)
        if recent_artifact
        else 0
    )

    header("Welcome to QASkills Demo")
    status_line(
        "Vault connected",
        Path(settings.memory_vault_path).expanduser().exists(),
        settings.memory_vault_path,
    )
    status_line("Index ready", bool(recent_artifact), "checked through Memory Service")
    status_line("Documents loaded", document_count > 0, str(document_count))
    status_line("Answer mode", True, "source-first local knowledge")
    print()

    print(STYLE.section("1. Morning snapshot"))
    print(recent_response.message)
    print()

    print(STYLE.section("2. Search local knowledge"))
    print(search_response.message)
    print()

    print(STYLE.section("3. Ask with grounded sources"))
    print("Question: Что мы решили про архитектуру?")
    if has_search_results(ask_response):
        print(STYLE.ok("✅ Found candidate sources."))
        print(ask_response.message)
    else:
        print(STYLE.warn("No architecture-specific documents found in metadata."))
    print()

    print(STYLE.ok("✅ Demo completed."))

    return 0


def command_morning(args: list[str] | None = None) -> int:
    _ = args
    response = Orchestrator().process(UserRequest(text="Подготовь меня к дейли"))

    header("Good Morning")
    print(STYLE.section("Pipeline"))
    for event in response.data["pipeline"]:
        bullet(f"{event['component']} → {event['message']}")
    print()
    print(STYLE.section("Briefing"))
    print(response.message)

    return 0 if response.success else 1


def command_prepare(args: list[str] | None = None) -> int:
    arguments = [item.lower() for item in (args or []) if item.strip()]

    if arguments in (["daily"], ["дейли"]):
        response = Orchestrator().process(
            UserRequest(
                text="prepare daily",
                metadata={"action": "daily.prepare"},
            )
        )

        header("Daily Brief")
        print(response.message)

        return (
            0
            if response.success
            and not has_jira_error(response)
            and not has_daily_brief_error(response)
            else 1
        )

    return friendly_error(
        "Unknown prepare command.",
        ["qaskills prepare daily"],
    )


def command_remember(args: list[str] | None = None) -> int:
    raw_content = strip_memory_command_prefix(" ".join(args or []).strip())

    if not raw_content:
        if not sys.stdin.isatty():
            return friendly_error(
                "Нет текста для сохранения.",
                ["qaskills remember \"Решение: ...\"", "qaskills"],
            )

        header("Save Knowledge")
        print("Введите текст заметки. Завершите ввод строкой с одной точкой.")
        raw_content = read_multiline()

    if not raw_content.strip():
        return friendly_error(
            "Нет текста для сохранения.",
            ["qaskills remember \"Решение: ...\"", "qaskills"],
        )

    title = suggest_note_title(raw_content)
    content = raw_content.strip()

    if sys.stdin.isatty():
        header("Review Knowledge")
        key_value("Suggested Title", title)
        print()
        print(STYLE.section("Content"))
        print(content)
        print()

        edited_title = input(f"Название [{title}]: ").strip()
        title = edited_title or title

        if confirm("Изменить текст заметки?"):
            print("Введите новый текст. Завершите ввод строкой с одной точкой.")
            content = read_multiline().strip() or content

        if not confirm("Сохранить заметку в Obsidian Vault?"):
            print(STYLE.warn("Сохранение отменено."))
            return 0

    response = Orchestrator().process(
        UserRequest(
            text="Запомни это",
            metadata={
                "action": "memory.write",
                "title": title,
                "content": content,
            },
        )
    )
    artifact = first_artifact(response, "memory_document_saved")

    header("Knowledge Saved")
    print(STYLE.section("Pipeline"))
    for event in response.data["pipeline"]:
        bullet(f"{event['component']} → {event['message']}")
    print()

    if not artifact:
        print(STYLE.warn(response.message))
        return 1

    document = artifact["metadata"]["document"]
    key_value("Title", document["title"])
    key_value("Path", document["path"])
    status_line("Document Index", True, "updated")

    return 0


def command_jira(args: list[str] | None = None) -> int:
    arguments = [item for item in (args or []) if item.strip()]

    if not arguments:
        if not sys.stdin.isatty():
            return run_pipeline_view("jira мои задачи", "Jira Workspace")

        return command_jira_workspace()

    first = arguments[0].lower()
    rest = " ".join(arguments[1:]).strip()

    if first in {"whoami", "me", "myself"}:
        return run_pipeline_view("jira whoami", "Jira Whoami")

    if first in {"projects", "project-list", "проекты"}:
        return run_pipeline_view("jira projects", "Jira Projects")

    if first in {"issue", "task", "задача"}:
        if not rest:
            return friendly_error(
                "Jira issue key is required.",
                ["qaskills jira issue SCRUM-42"],
            )

        return run_pipeline_view(f"jira issue {rest}", "Jira Issue")

    if first in {"tasks", "list", "мои", "задачи"}:
        return run_pipeline_view("jira мои задачи", "Jira Workspace")

    if first in {"bug", "bug-report", "баг"}:
        text = f"jira bug report {rest}".strip()
        return run_pipeline_view(text, "Bug Report")

    if first in {"daily", "дейли"}:
        text = f"jira daily {rest}".strip()
        return run_pipeline_view(text, "Jira Daily")

    if first in {"analyze", "analysis", "анализ", "проанализируй"}:
        text = f"jira анализ задачи {rest}".strip()
        return run_pipeline_view(text, "Jira Task Analysis")

    return run_pipeline_view(f"jira {' '.join(arguments)}", "Jira Issue")


def command_jira_workspace() -> int:
    while True:
        header("Jira Workspace")
        print("Работа с Jira")
        print()
        print("1. Просмотреть мои задачи")
        print("2. Найти задачу по ключу")
        print("3. Подготовить анализ задачи")
        print("4. Создать шаблон Bug Report")
        print("5. Подготовиться к Daily по задаче")
        print("6. Назад")
        print()

        choice = input("Выберите действие: ").strip()

        if choice in {"6", "back", "назад", "exit", "выход"}:
            return 0

        print()

        if choice == "1":
            run_pipeline_view("jira мои задачи", "Jira Workspace")
            pause()
            continue

        if choice == "2":
            issue_key = prompt_line("Jira key")
            if issue_key:
                run_pipeline_view(f"jira {issue_key}", "Jira Issue")
            pause()
            continue

        if choice == "3":
            issue = prompt_line("Jira key или описание задачи")
            if issue:
                run_pipeline_view(f"jira анализ задачи {issue}", "Jira Task Analysis")
            pause()
            continue

        if choice == "4":
            issue = prompt_line("Jira key или краткий симптом")
            run_pipeline_view(f"jira bug report {issue}".strip(), "Bug Report")
            pause()
            continue

        if choice == "5":
            issue = prompt_line("Jira key")
            if issue:
                run_pipeline_view(f"jira daily {issue}", "Jira Daily")
            pause()
            continue

        print(STYLE.warn("Не понял выбор. Попробуйте номер из списка."))
        pause()


def command_natural_language(text: str) -> int:
    if looks_like_memory_command(text):
        try:
            args = shlex.split(text)
        except ValueError:
            args = text.split()

        return command_remember(args[1:])

    response = Orchestrator().process(UserRequest(text=text))

    header("QASkills")
    print(STYLE.section("Pipeline"))
    for event in response.data["pipeline"]:
        bullet(f"{event['component']} → {event['message']}")

    print()
    print(STYLE.section("Answer"))
    print(response.message)

    return 0


def run_pipeline_view(text: str, title: str) -> int:
    response = Orchestrator().process(UserRequest(text=text))

    header(title)
    print(STYLE.section("Pipeline"))
    for event in response.data["pipeline"]:
        bullet(f"{event['component']} → {event['message']}")

    print()
    print(STYLE.section("Result"))
    print(response.message)

    return 0 if response.success and not has_jira_error(response) else 1


def index_manager() -> IndexManager:
    settings = load_settings()
    return IndexManager(
        vault_path=settings.memory_vault_path,
        index_path=settings.document_index_path,
    )


def provider_router() -> ProviderRouter:
    return ProviderRouter.from_settings(load_settings())


def print_workspace_menu() -> None:
    print("1. Подготовиться к Daily")
    print("2. Проанализировать задачу")
    print("3. Найти знания")
    print("4. Создать Bug Report")
    print("5. Сохранить новое знание")
    print("6. Работа с Jira")
    print("7. Анализ встречи")
    print("8. Настройки")
    print("9. Выход")
    print()


def prompt_line(label: str) -> str:
    if not sys.stdin.isatty():
        return ""

    return input(f"{label}: ").strip()


def pause() -> None:
    if sys.stdin.isatty():
        input("\nEnter — продолжить...")


def confirm(question: str) -> bool:
    answer = input(f"{question} [y/N]: ").strip().lower()

    return answer in {"y", "yes", "д", "да"}


def read_multiline() -> str:
    lines = []

    while True:
        try:
            line = input()
        except EOFError:
            break

        if line.strip() == ".":
            break

        lines.append(line)

    return "\n".join(lines)


def strip_memory_command_prefix(text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()

    for prefix in [
        "это:",
        "это",
        "вывод:",
        "вывод",
        "в память:",
        "в память",
        "this:",
        "this",
    ]:
        if lowered.startswith(prefix):
            return stripped[len(prefix) :].strip().lstrip(":").strip()

    return stripped


def looks_like_memory_command(text: str) -> bool:
    return text.strip().lower().startswith(
        (
            "запомни",
            "сохрани вывод",
            "сохрани это",
            "добавь в память",
            "remember ",
            "save this",
        )
    )


def suggest_note_title(content: str) -> str:
    for line in content.splitlines():
        candidate = line.strip().strip("#").strip()

        if candidate:
            return candidate[:80]

    return "Knowledge Update"


def self_check_label(available: object) -> str:
    return "available" if available else "not available, graceful fallback enabled"


def provider_detail(
    available: bool,
    available_text: str,
    unavailable_text: str,
) -> str:
    return available_text if available else unavailable_text


def has_search_results(response) -> bool:
    artifacts = response.data.get("artifacts", []) if response.data else []

    for artifact in artifacts:
        if artifact.get("name") == "memory_search_results":
            return artifact.get("metadata", {}).get("document_count", 0) > 0

    return True


def has_jira_error(response) -> bool:
    artifacts = response.data.get("artifacts", []) if response.data else []

    return any(artifact.get("name") == "jira_error" for artifact in artifacts)


def has_daily_brief_error(response) -> bool:
    artifacts = response.data.get("artifacts", []) if response.data else []

    for artifact in artifacts:
        if artifact.get("name") != "daily_brief":
            continue

        return artifact.get("metadata", {}).get("success") is False

    return False


def first_artifact(response, name: str) -> dict | None:
    artifacts = response.data.get("artifacts", []) if response.data else []

    for artifact in artifacts:
        if artifact.get("name") == name:
            return artifact

    return None


def search_results_from_response(
    response,
) -> list[tuple[int, IndexedDocument, list[str]]]:
    artifact = first_artifact(response, "memory_search_results")

    if not artifact:
        return []

    results = []

    for result in artifact.get("metadata", {}).get("results", []):
        results.append(
            (
                int(result.get("score", 0)),
                IndexedDocument.from_dict(result["document"]),
                list(result.get("reasons", [])),
            )
        )

    return results


def choose_document(
    results: list[tuple[int, IndexedDocument, list[str]]],
) -> IndexedDocument | None:
    if len(results) == 1:
        return results[0][1]

    header("Choose Document")
    print("Найдено несколько документов:")
    print()

    for index, (_, document, reasons) in enumerate(results[:10], start=1):
        print(f"{index}. {document.title}")
        print(f"   {STYLE.dim(document.path)}")
        print(f"   match: {', '.join(reasons)}")

    print()

    if not sys.stdin.isatty():
        print(STYLE.warn("Запустите команду в терминале, чтобы выбрать документ."))
        return None

    choice = input("Открыть номер: ").strip()

    if not choice.isdigit():
        print(STYLE.warn("Открытие отменено."))
        return None

    index = int(choice)

    if index < 1 or index > min(len(results), 10):
        print(STYLE.warn("Открытие отменено."))
        return None

    return results[index - 1][1]


def header(title: str | None = None) -> None:
    print("─" * 56)
    print(STYLE.title(APP_NAME))
    print(TAGLINE)
    print(STYLE.dim(VERSION))

    if title:
        print("─" * 56)
        print(STYLE.section(title))

    print("─" * 56)


def command_group(title: str, commands: list[tuple[str, str]]) -> None:
    print(STYLE.section(title))

    for command, description in commands:
        print(f"  {STYLE.ok('•')} {command}")
        print(f"    {description}")

    print()


def status_line(name: str, ok: bool, detail: str) -> None:
    icon = "✅" if ok else "⚠️"
    color = STYLE.ok if ok else STYLE.warn
    print(f"{color(icon)} {name:<22} {detail}")


def key_value(name: str, value: str) -> None:
    print(f"{STYLE.dim(name + ':'):<24} {value}")


def bullet(text: str) -> None:
    print(f"• {text}")


def friendly_error(message: str, suggestions: list[str]) -> int:
    header("Nothing Found")
    print(STYLE.warn(message))

    print_suggestions(suggestions)

    return 1


def print_suggestions(suggestions: list[str]) -> None:
    if suggestions:
        print()
        print("Попробуйте:")
        for suggestion in suggestions:
            bullet(suggestion)


if __name__ == "__main__":
    raise SystemExit(main())
