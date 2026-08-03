import re

from app.core.artifacts import Artifact, PipelineTrace
from app.core.intent import UserIntent
from app.core.models import OrchestratorResponse, UserRequest
from app.core.task_plan import TaskPlan


class ResponseComposer:
    """Builds the final response returned to the user."""

    def compose(
        self,
        request: UserRequest,
        intent: UserIntent,
        plan: TaskPlan,
        artifacts: list[Artifact],
        llm_artifact: Artifact | None,
        trace: PipelineTrace,
    ) -> OrchestratorResponse:
        trace.add("Response Composer", "Composed final user response")

        message = (
            self._compose_generated_response(llm_artifact, artifacts)
            if llm_artifact
            else self._compose_service_response(intent, artifacts)
        )

        return OrchestratorResponse(
            success=True,
            message=message,
            data={
                "request": request.text,
                "intent": {
                    "name": intent.name,
                    "expected_output": intent.expected_output,
                    "confidence": intent.confidence,
                    "metadata": dict(intent.metadata),
                },
                "plan": plan.to_dict(),
                "artifacts": [artifact.to_dict() for artifact in artifacts],
                "llm_artifact": llm_artifact.to_dict() if llm_artifact else None,
                "pipeline": trace.to_dicts(),
            },
        )

    def _compose_service_response(
        self,
        intent: UserIntent,
        artifacts: list[Artifact],
    ) -> str:
        if not artifacts:
            return "No service artifacts were produced."

        if intent.name == "test_task_strategy":
            if intent.metadata.get("working_session_mode"):
                return self._compose_working_session_opening_response(
                    intent,
                    artifacts,
                )
            return self._compose_test_strategy_response(intent, artifacts)

        if intent.name == "prepare_task":
            if intent.metadata.get("working_session_mode"):
                return self._compose_working_session_opening_response(
                    intent,
                    artifacts,
                )
            return self._compose_task_preparation_response(intent, artifacts)

        if len(artifacts) == 1 and artifacts[0].source == "Memory Service":
            return self._compose_memory_response(artifacts[0])

        if len(artifacts) == 1 and artifacts[0].source == "Jira Service":
            return artifacts[0].content

        daily_brief = self._artifact_named(artifacts, "daily_brief")

        if daily_brief:
            return daily_brief.content

        search_artifact = self._artifact_named(artifacts, "memory_search_results")

        if search_artifact:
            if len(artifacts) == 1:
                return self._compose_source_pack_response(search_artifact)

            return self._compose_workspace_response(search_artifact, artifacts)

        lines = ["Service results:"]
        lines.extend(
            f"- {artifact.source}: {artifact.content}"
            for artifact in artifacts
        )

        return "\n".join(lines)

    def _compose_working_session_opening_response(
        self,
        intent: UserIntent,
        artifacts: list[Artifact],
    ) -> str:
        jira_issue = self._artifact_named(artifacts, "jira_issue")
        jira_error = self._artifact_named(artifacts, "jira_error")
        search_artifact = self._artifact_named(artifacts, "memory_search_results")
        issue = jira_issue.metadata.get("issue", {}) if jira_issue else {}
        sources = search_artifact.metadata.get("results", []) if search_artifact else []
        comments = issue.get("comments", [])
        links = issue.get("links", [])
        issue_key = issue.get("key") or intent.metadata.get("issue_key") or "Task"
        title = issue.get("summary") or intent.metadata.get("query") or intent.raw_text
        mode = intent.metadata.get("working_session_mode")
        switch_artifact = self._artifact_named(artifacts, "working_session_switch")

        lines = [
            str(issue_key),
            str(title),
            "",
        ]

        if switch_artifact:
            previous_issue_key = switch_artifact.metadata.get("previous_issue_key")
            if previous_issue_key:
                lines.extend(
                    [
                        "Previous Session",
                        f"• {previous_issue_key} приостановлена перед переключением.",
                        "",
                    ]
                )

        delta_lines = self._render_work_context_delta(artifacts)

        if mode == "resume":
            if delta_lines:
                lines.extend([*delta_lines, ""])
            else:
                lines.extend(["Что изменилось", "• С прошлого просмотра изменений Jira не видно.", ""])

        lines.append("Что известно")
        lines.extend(self._workspace_known_lines(issue, comments, links, sources, jira_error))
        lines.extend(["", "Что осталось"])
        lines.extend(self._workspace_remaining_lines(issue, comments, links, sources))
        lines.extend(["", "Риски"])
        lines.extend(self._task_risks(issue, sources, comments))
        lines.extend(["", "Блокеры"])
        lines.extend(self._task_start_blockers(issue, sources, jira_error))
        lines.extend(["", "Что делать сейчас"])
        lines.append(f"• {self._workspace_next_action(issue, comments, sources)}")
        lines.extend(["", "Ready To Work"])
        lines.append("Можно начинать тестирование и писать короткие обновления без номера задачи.")

        return "\n".join(lines)

    def _workspace_known_lines(
        self,
        issue: dict,
        comments: list[dict],
        links: list[dict],
        sources: list[dict],
        jira_error: Artifact | None,
    ) -> list[str]:
        if jira_error:
            lines = [
                f"• Jira-контекст недоступен: {self._jira_error_summary(jira_error)}"
            ]
            if sources:
                lines.append(
                    "• Локальная память: "
                    f"{self._source_titles(sources[:2])}."
                )
            return lines

        text = self._strategy_text(issue, sources, comments)
        known = []

        if comments:
            latest = self._comment_meaning(str(comments[-1].get("body") or ""))
            if latest:
                known.append(f"• Последний комментарий: {latest}")
            else:
                excerpt = self._safe_comment_excerpt(str(comments[-1].get("body") or ""))
                if excerpt:
                    known.append(f"• Последний комментарий: {excerpt}")

        if self._contains_any(text, ["401"]):
            known.append("• Есть риск 401 после login/refresh.")

        if self._contains_any(text, ["safari"]):
            known.append("• Safari уже фигурирует в evidence.")

        if links:
            linked = ", ".join(
                link.get("key", "")
                for link in links[:3]
                if link.get("key")
            )
            if linked:
                known.append(f"• Есть связанные задачи: {linked}.")

        if issue.get("status") or issue.get("priority"):
            known.append(f"• Jira: {issue.get('status') or 'статус неизвестен'}, {issue.get('priority') or 'priority unknown'}.")

        return known[:5] or ["• Контекст открыт, но подтверждённых фактов пока мало."]

    def _workspace_remaining_lines(
        self,
        issue: dict,
        comments: list[dict],
        links: list[dict],
        sources: list[dict],
    ) -> list[str]:
        text = self._strategy_text(issue, sources, comments)
        remaining = []

        if self._contains_any(text, ["refresh", "обнов"]):
            remaining.append("□ Refresh после логина.")

        if self._contains_any(text, ["safari"]):
            remaining.append("□ Safari.")

        if self._contains_any(text, ["logout", "логаут", "выход"]):
            remaining.append("□ Logout в другой вкладке.")

        if self._contains_any(text, ["cookie", "cookies"]):
            remaining.append("□ Старые cookies.")

        if links or self._contains_any(text, ["oauth", "google"]):
            remaining.append("□ OAuth/callback smoke, если входит в scope.")

        if not remaining:
            areas = self._risk_areas(issue, sources, comments)
            remaining = [f"□ {area}." for area in areas[:4]]

        return remaining or ["□ Первый проверочный сценарий ещё не выделен."]

    def _workspace_next_action(
        self,
        issue: dict,
        comments: list[dict],
        sources: list[dict],
    ) -> str:
        text = self._strategy_text(issue, sources, comments)

        if self._contains_any(text, ["refresh", "401"]):
            return "Начать с login → protected page → refresh и сохранить browser/build/evidence."

        if comments:
            return "Начать с проверки последнего developer note."

        return "Начать с первого unchecked сценария и писать результат коротким сообщением."

    def _compose_generated_response(
        self,
        llm_artifact: Artifact,
        artifacts: list[Artifact],
    ) -> str:
        lines = [llm_artifact.content]

        provider_success = llm_artifact.metadata.get("provider_success")
        provider = llm_artifact.metadata.get("provider")
        provider_error = llm_artifact.metadata.get("provider_error")

        if provider_success is False:
            lines.append("")
            lines.append("Provider status:")
            lines.append(f"- {provider}: {provider_error or 'unavailable'}")

        skill_artifact = self._artifact_named(artifacts, "skill_guidance")

        if skill_artifact and provider_success is False:
            lines.append("")
            lines.append("Skill guidance:")
            lines.append(skill_artifact.content)

        workspace_artifacts = self._workspace_artifacts(artifacts)

        if workspace_artifacts and provider_success is False:
            lines.append("")
            lines.append("Workspace artifacts:")
            lines.extend(
                f"- {artifact.source}: {artifact.content}"
                for artifact in workspace_artifacts
            )

        search_artifact = self._artifact_named(artifacts, "memory_search_results")

        if search_artifact:
            lines.append("")
            lines.append(self._compose_source_pack_response(search_artifact))

        return "\n".join(lines)

    def _compose_memory_response(self, artifact: Artifact) -> str:
        if artifact.name == "memory_vault_structure":
            structure = artifact.metadata.get("structure", {})

            if not structure:
                return "Структура Vault: ничего не найдено."

            visible_items = self._visible_vault_structure_items(structure)
            shown_items = visible_items[:30]
            hidden_count = len(visible_items) - len(shown_items)
            lines = [
                (
                    f"Структура Vault: {len(structure)} папок "
                    f"(показано {len(shown_items)} пользовательских)"
                )
            ]

            for folder, count in shown_items:
                lines.append(f"- {folder}: {count} markdown-файлов")

            if hidden_count > 0:
                lines.append(f"...и ещё {hidden_count} папок.")

            return "\n".join(lines)

        if artifact.name in {"memory_documents", "memory_recent_documents"}:
            documents = artifact.metadata.get("documents", [])
            title = (
                "Последние документы"
                if artifact.name == "memory_recent_documents"
                else "Документы"
            )

            if artifact.metadata.get("scope") == "projects":
                title = "Проекты"

            if artifact.metadata.get("project_name"):
                title = f"Документы проекта {artifact.metadata['project_name']}"

            if artifact.metadata.get("tag"):
                title = f"Документы с тегом {artifact.metadata['tag']}"

            if artifact.metadata.get("heading"):
                title = f"Документы с заголовком {artifact.metadata['heading']}"

            if not documents:
                return f"{title}: ничего не найдено."

            lines = [f"{title}: {len(documents)}"]

            for document in documents[:20]:
                lines.append(
                    (
                        f"- {document['title']} "
                        f"({document['path']}, {document['size']} bytes, "
                        f"modified {document['modified_at']})"
                    )
                )

            if len(documents) > 20:
                lines.append(f"...и ещё {len(documents) - 20}.")

            return "\n".join(lines)

        if artifact.name == "memory_document":
            document = artifact.metadata["document"]
            info = document["info"]

            return "\n".join(
                [
                    f"Документ: {info['title']}",
                    f"Путь: {info['path']}",
                    f"Папка: {info['folder'] or '.'}",
                    f"Размер: {info['size']} bytes",
                    f"Изменён: {info['modified_at']}",
                    "",
                    document["content"],
                ]
            )

        if artifact.name == "memory_document_not_found":
            return artifact.content

        if artifact.name == "memory_search_results":
            return self._compose_source_pack_response(artifact)

        if artifact.name in {"memory_document_saved", "memory_write_failed"}:
            return artifact.content

        return artifact.content

    def _compose_workspace_response(
        self,
        search_artifact: Artifact,
        artifacts: list[Artifact],
    ) -> str:
        lines = [
            self._compose_source_pack_response(search_artifact),
            "",
            "Workspace Results",
        ]

        for artifact in self._workspace_artifacts(artifacts):
            lines.append(f"- {artifact.source}:")
            lines.extend(f"  {line}" for line in artifact.content.splitlines())

        return "\n".join(lines)

    def _workspace_artifacts(self, artifacts: list[Artifact]) -> list[Artifact]:
        return [
            artifact
            for artifact in artifacts
            if artifact.name not in {"memory_search_results", "skill_guidance"}
        ]

    def _compose_source_pack_response(self, artifact: Artifact) -> str:
        query = artifact.metadata.get("query", "")
        results = artifact.metadata.get("results", [])

        if not results:
            return (
                "Source Pack\n"
                "Источники не найдены в локальном индексе.\n"
                f"Query: {query}"
            )

        lines = [
            "Source Pack",
            f"Question: {query}",
            f"Found {len(results)} source documents.",
            "",
            "Key Sources",
        ]

        for index, result in enumerate(results[:3], start=1):
            document = result["document"]
            lines.append(f"{index}. {document['title']}")
            lines.append(f"   path: {document['path']}")
            lines.append(
                f"   score {result['score']} · match: {', '.join(result['reasons'])}"
            )

            if document.get("tags"):
                lines.append(f"   tags: {', '.join(document['tags'])}")

        groups: dict[str, list[dict]] = {}

        for result in results:
            document = result["document"]
            groups.setdefault(self._source_group(document), []).append(result)

        lines.append("")
        lines.append("Grouped Sources")

        for group, group_results in groups.items():
            lines.append(f"{group} ({len(group_results)})")

            for result in group_results:
                document = result["document"]
                lines.append(f"  - {document['title']} — {document['path']}")

        lines.append("")
        lines.append("Recommended Reading Order")

        for index, result in enumerate(results, start=1):
            document = result["document"]
            lines.append(f"{index}. {document['title']} — {document['path']}")

        return "\n".join(lines)

    def _compose_task_preparation_response(
        self,
        intent: UserIntent,
        artifacts: list[Artifact],
    ) -> str:
        jira_issue = self._artifact_named(artifacts, "jira_issue")
        jira_error = self._artifact_named(artifacts, "jira_error")
        search_artifact = self._artifact_named(artifacts, "memory_search_results")
        skill_artifact = self._artifact_named(artifacts, "skill_guidance")
        issue = jira_issue.metadata.get("issue", {}) if jira_issue else {}
        sources = search_artifact.metadata.get("results", []) if search_artifact else []
        comments = issue.get("comments", [])
        links = issue.get("links", [])
        blockers = self._task_start_blockers(issue, sources, jira_error)
        risks = self._task_risks(issue, sources, comments)
        next_action = self._task_next_best_action(issue, blockers, sources, comments)
        issue_key = issue.get("key") or intent.metadata.get("issue_key") or ""

        lines = [
            (
                f"Я подготовил задачу {issue_key}."
                if issue_key
                else "Подготовка завершена."
            ),
        ]
        delta_lines = self._render_work_context_delta(artifacts)

        if delta_lines:
            lines.extend(["", *delta_lines])

        lines.extend([
            "",
            "Главное",
        ])
        lines.extend(self._task_headline_lines(intent, issue, jira_error, sources))
        lines.extend(["", "На что обратить внимание"])
        lines.extend(risks)
        lines.extend(["", "Следующий лучший шаг"])
        lines.append(f"• {next_action}")
        if not delta_lines:
            lines.extend(["", "Что изменилось"])
            lines.extend(self._task_change_lines(issue, comments))
        lines.extend(["", "Что мешает начать"])
        lines.extend(blockers)
        lines.extend(["", "Facts"])
        lines.extend(self._task_fact_lines(issue, sources, comments, links, jira_error))
        lines.extend(["", "Inferences"])
        lines.extend(self._task_inference_lines(issue, sources, comments, skill_artifact))
        lines.extend(["", "Recommendations"])
        lines.extend(self._task_recommendation_lines(issue, blockers, sources, comments))
        lines.extend(["", "Предлагаемые действия"])
        lines.extend(
            [
                "• [ ] Принять следующий шаг.",
                "• [ ] Подготовить тестовый чек-лист после проверки вводных.",
                "• [ ] Сохранить подтверждённые выводы в Obsidian.",
                "• [ ] Ничего не делать сейчас.",
                "",
                "Я ничего не сохранял и не изменял без подтверждения.",
            ]
        )

        return "\n".join(lines)

    def _compose_test_strategy_response(
        self,
        intent: UserIntent,
        artifacts: list[Artifact],
    ) -> str:
        jira_issue = self._artifact_named(artifacts, "jira_issue")
        jira_error = self._artifact_named(artifacts, "jira_error")
        search_artifact = self._artifact_named(artifacts, "memory_search_results")
        skill_artifact = self._artifact_named(artifacts, "skill_guidance")
        issue = jira_issue.metadata.get("issue", {}) if jira_issue else {}
        sources = search_artifact.metadata.get("results", []) if search_artifact else []
        comments = issue.get("comments", [])
        issue_key = issue.get("key") or intent.metadata.get("issue_key") or ""
        areas = self._risk_areas(issue, sources, comments)

        lines = [
            (
                f"Продолжаю по {issue_key}: стратегия тестирования."
                if issue_key
                else "Продолжаю: стратегия тестирования."
            ),
            "",
            "Коротко",
        ]
        lines.extend(
            self._test_strategy_summary_lines(
                intent=intent,
                issue=issue,
                jira_error=jira_error,
                sources=sources,
                areas=areas,
            )
        )
        lines.extend(["", "Что проверить в первую очередь"])
        lines.extend(self._test_strategy_priority_lines(issue, sources, comments, areas))
        lines.extend(["", "Основные пользовательские сценарии"])
        lines.extend(self._test_strategy_user_scenario_lines(issue, sources, comments))
        lines.extend(["", "Негативные проверки"])
        lines.extend(self._test_strategy_negative_lines(issue, sources, comments))
        lines.extend(["", "Граничные случаи"])
        lines.extend(self._test_strategy_boundary_lines(issue, sources, comments))
        lines.extend(["", "Возможные регрессии"])
        lines.extend(self._test_strategy_regression_lines(issue, sources, comments, areas))
        lines.extend(["", "Что пока неизвестно"])
        lines.extend(
            self._test_strategy_unknown_lines(
                issue=issue,
                jira_error=jira_error,
                sources=sources,
                comments=comments,
            )
        )
        lines.extend(["", "Основано на"])
        lines.extend(
            self._test_strategy_evidence_lines(
                jira_issue=jira_issue,
                jira_error=jira_error,
                sources=sources,
                skill_artifact=skill_artifact,
            )
        )
        lines.extend(
            [
                "",
                "Это не полный чек-лист. Это направление тестирования, чтобы начать спокойно и осознанно.",
                "Я ничего не сохранял и не изменял без подтверждения.",
            ]
        )

        return "\n".join(lines)

    def _test_strategy_summary_lines(
        self,
        intent: UserIntent,
        issue: dict,
        jira_error: Artifact | None,
        sources: list[dict],
        areas: list[str],
    ) -> list[str]:
        if issue:
            summary = issue.get("summary") or intent.raw_text
            lines = [f"• Фокус задачи: {summary}."]
        elif jira_error:
            lines = [
                "• Jira-контекст недоступен, поэтому стратегия основана "
                "на локальных знаниях и названии задачи."
            ]
        else:
            lines = [f"• Фокус взят из запроса: {intent.raw_text}."]

        if areas:
            lines.append(f"• Основные зоны внимания: {', '.join(areas[:4])}.")

        if sources:
            lines.append(
                "• Локальная память добавляет контекст: "
                f"{self._source_titles(sources[:2])}."
            )

        return lines

    def _test_strategy_priority_lines(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
        areas: list[str],
    ) -> list[str]:
        lines = []

        if comments:
            meaning = self._comment_meaning(str(comments[-1].get("body") or ""))

            if meaning:
                lines.append(f"• Сначала проверить уточнение из последнего комментария: {meaning}")
            else:
                excerpt = self._safe_comment_excerpt(str(comments[-1].get("body") or ""))
                lines.append(
                    f"• Сначала проверить последний комментарий: {excerpt}"
                    if excerpt
                    else "• Сначала прочитать последний комментарий перед чек-листом."
                )

        next_step_prefix = "Затем" if lines else "Сначала"

        if areas:
            lines.append(f"• {next_step_prefix} пройти основной поток: {areas[0]}.")
        elif issue.get("summary"):
            lines.append(
                f"• {next_step_prefix} пройти happy path для: "
                f"{issue.get('summary')}."
            )
        else:
            lines.append(f"• {next_step_prefix} восстановить основной happy path задачи.")

        if sources:
            lines.append("• После этого сверить тестовый фокус с найденными заметками Obsidian.")

        return lines[:4]

    def _test_strategy_user_scenario_lines(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
    ) -> list[str]:
        text = self._strategy_text(issue, sources, comments)
        scenarios = []

        if self._contains_any(text, ["registration", "signup", "sign up", "регистрац"]):
            scenarios.append("• Пользователь успешно проходит регистрацию от начала до конца.")

        if self._contains_any(text, ["email", "e-mail", "почт", "confirmation"]):
            scenarios.append("• Пользователь подтверждает email и получает ожидаемый доступ.")

        if self._contains_any(text, ["login", "sign in", "логин", "авторизац"]):
            scenarios.append("• Пользователь входит после выполнения нового сценария.")

        if self._contains_any(text, ["restore", "reset", "forgot", "восстанов"]):
            scenarios.append("• Пользователь восстанавливает доступ после изменения.")

        if self._contains_any(text, ["api", "endpoint", "request", "response"]):
            scenarios.append("• Клиент получает корректный API-ответ для успешного запроса.")

        if not scenarios:
            scenarios.append("• Основной пользовательский путь из описания задачи.")
            scenarios.append("• Повторное выполнение сценария без неожиданных побочных эффектов.")

        return scenarios[:5]

    def _test_strategy_negative_lines(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
    ) -> list[str]:
        text = self._strategy_text(issue, sources, comments)
        checks = []

        if self._contains_any(text, ["registration", "signup", "sign up", "регистрац"]):
            checks.append("• Попытка регистрации с уже занятым email.")
            checks.append("• Регистрация с незаполненными обязательными полями.")

        if self._contains_any(text, ["email", "e-mail", "почт", "confirmation"]):
            checks.append("• Подтверждение email с недействительной или просроченной ссылкой.")

        if self._contains_any(text, ["password", "парол"]):
            checks.append("• Пароль не соответствует правилам сложности.")

        if self._contains_any(text, ["api", "endpoint", "request", "response"]):
            checks.append("• Некорректный запрос возвращает понятную ошибку без побочных действий.")

        if not checks:
            checks.append("• Невалидные обязательные данные не должны приводить к успешному сценарию.")
            checks.append("• Ошибка сервиса должна быть понятной и не ломать состояние пользователя.")

        return checks[:5]

    def _test_strategy_boundary_lines(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
    ) -> list[str]:
        text = self._strategy_text(issue, sources, comments)
        checks = []

        if self._contains_any(text, ["email", "e-mail", "почт"]):
            checks.append("• Минимальная и длинная допустимая длина email.")
            checks.append("• Email с допустимыми спецсимволами и разным регистром.")

        if self._contains_any(text, ["password", "парол"]):
            checks.append("• Минимальная и максимальная длина пароля.")
            checks.append("• Пароль на границе правил сложности.")

        if self._contains_any(text, ["timeout", "expire", "expires", "просроч"]):
            checks.append("• Действие сразу до и сразу после истечения срока.")

        if not checks:
            checks.append("• Границы пока неочевидны: нужны правила валидации или ограничения данных.")

        return checks[:5]

    def _test_strategy_regression_lines(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
        areas: list[str],
    ) -> list[str]:
        if areas:
            return [f"• Проверить, что не сломались: {', '.join(areas[:4])}."]

        text = self._strategy_text(issue, sources, comments)
        regressions = []

        if self._contains_any(text, ["user", "пользователь"]):
            regressions.append("• Существующий пользовательский путь остаётся рабочим.")

        if self._contains_any(text, ["permission", "role", "роль", "доступ"]):
            regressions.append("• Права доступа и роли не изменились неожиданно.")

        if not regressions:
            regressions.append("• Ближайшие соседние сценарии вокруг изменённой функции.")

        return regressions[:4]

    def _test_strategy_unknown_lines(
        self,
        issue: dict,
        jira_error: Artifact | None,
        sources: list[dict],
        comments: list[dict],
    ) -> list[str]:
        unknowns = []
        description = str(issue.get("description") or "")

        if jira_error:
            unknowns.append("• Нет актуального Jira-описания и комментариев.")

        if issue and not description:
            unknowns.append("• В задаче нет описания.")

        if issue and description and not self._has_acceptance_criteria(description):
            unknowns.append("• Acceptance Criteria не выделены явно.")

        if not comments:
            unknowns.append("• Нет комментариев, которые уточняют последние решения.")

        if not sources:
            unknowns.append("• Нет локальных заметок Obsidian по этой задаче.")

        return unknowns or ["• Критичных неизвестных по собранным источникам не видно."]

    def _test_strategy_evidence_lines(
        self,
        jira_issue: Artifact | None,
        jira_error: Artifact | None,
        sources: list[dict],
        skill_artifact: Artifact | None,
    ) -> list[str]:
        lines = []

        if jira_issue:
            issue = jira_issue.metadata.get("issue", {})
            lines.append(f"• Jira: {issue.get('key') or 'задача'} получена.")
        elif jira_error:
            lines.append(f"• Jira: {self._jira_error_summary(jira_error)}")

        if sources:
            lines.append(f"• Obsidian: {self._source_titles(sources[:3])}.")

        if skill_artifact:
            lines.append("• QA guidance: анализ функциональности и рисков.")

        return lines

    def _task_headline_lines(
        self,
        intent: UserIntent,
        issue: dict,
        jira_error: Artifact | None,
        sources: list[dict],
    ) -> list[str]:
        lines = []
        issue_key = issue.get("key") or intent.metadata.get("issue_key") or "задача"

        if issue:
            summary = issue.get("summary") or "summary не указан"
            lines.append(f"• Вы будете разбирать: {summary}.")
            lines.append(self._task_work_state_line(issue))
        elif jira_error:
            lines.append(
                f"• Jira-контекст для {issue_key} не получен: "
                f"{self._jira_error_summary(jira_error)}"
            )
        else:
            lines.append(f"• Готовлю контекст по запросу: {intent.raw_text}")

        if sources:
            source_titles = ", ".join(
                result["document"]["title"]
                for result in sources[:2]
            )
            lines.append(f"• В Obsidian есть локальный контекст: {source_titles}.")
        else:
            lines.append("• Локальных знаний по этой теме пока не найдено.")

        return lines

    def _task_change_lines(self, issue: dict, comments: list[dict]) -> list[str]:
        if comments:
            latest = comments[-1]
            meaning = self._comment_meaning(str(latest.get("body") or ""))

            if meaning:
                return [f"• Последний комментарий: {meaning}"]

            excerpt = self._safe_comment_excerpt(str(latest.get("body") or ""))

            if excerpt:
                return [f"• Последний комментарий: {excerpt}"]

            return ["• Последний комментарий стоит прочитать перед тестированием."]

        if issue:
            return [
                "• Новых решений из комментариев по этой задаче не видно."
            ]

        return ["• Изменения не определены: Jira-контекст недоступен."]

    def _task_start_blockers(
        self,
        issue: dict,
        sources: list[dict],
        jira_error: Artifact | None,
    ) -> list[str]:
        blockers = []
        description = str(issue.get("description") or "")

        if jira_error:
            blockers.append("• Нет актуального Jira-контекста.")

        if issue and not description:
            blockers.append("• В Jira нет описания задачи.")

        if issue and description and not self._has_acceptance_criteria(description):
            blockers.append("• Acceptance Criteria не выделены явно.")

        return blockers or ["• Явных блокеров по собранным источникам не видно."]

    def _task_risks(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
    ) -> list[str]:
        risks = []
        priority = str(issue.get("priority") or "").lower()
        description = str(issue.get("description") or "")
        risk_areas = self._risk_areas(issue, sources, comments)

        if priority in {"high", "highest", "critical", "blocker"}:
            if risk_areas:
                risks.append(
                    "• Есть риск регрессии: "
                    f"{', '.join(risk_areas[:3])}."
                )
            else:
                risks.append(
                    "• Высокий приоритет: начните с основного пользовательского пути."
                )

        if issue and not self._has_acceptance_criteria(description):
            risks.append("• Неявные Acceptance Criteria повышают риск неполного покрытия.")

        if comments:
            risks.append("• Комментарии могут содержать решения, которые не отражены в описании.")

        if risk_areas and priority not in {"high", "highest", "critical", "blocker"}:
            risks.append(
                "• Затронутые области для регрессии: "
                f"{', '.join(risk_areas[:3])}."
            )

        return risks or ["• По собранным источникам специфические риски пока не видны."]

    def _task_fact_lines(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
        links: list[dict],
        jira_error: Artifact | None,
    ) -> list[str]:
        facts = []

        if issue:
            facts.append(f"• Задача: {issue.get('summary') or issue.get('key')}")

            if issue.get("status"):
                facts.append(f"• Текущий статус: {issue.get('status')}")

            if issue.get("priority") and issue.get("priority") != "Unavailable":
                facts.append(f"• Приоритет: {issue.get('priority')}")

            if issue.get("description"):
                facts.append("• Описание задачи доступно.")

        if jira_error:
            facts.append(f"• Jira: {self._jira_error_summary(jira_error)}")

        if comments:
            facts.append(
                "• В задаче есть комментарии, которые могут менять тестовый фокус."
            )

        if links:
            linked = ", ".join(
                link.get("key", "")
                for link in links[:3]
                if link.get("key")
            )
            if linked:
                facts.append(f"• Есть связанные задачи: {linked}.")

        for result in sources[:3]:
            document = result["document"]
            facts.append(
                f"• Источник из Obsidian: {document['title']} "
                f"({document['path']})"
            )

        return facts or ["• Полезных фактов для решения пока не собрано."]

    def _task_inference_lines(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
        skill_artifact: Artifact | None,
    ) -> list[str]:
        inferences = []
        description = str(issue.get("description") or "")

        if issue and not self._has_acceptance_criteria(description):
            inferences.append(
                "• Перед качественным тестированием стоит уточнить ожидаемое поведение."
            )

        if comments:
            inferences.append(
                "• Комментарии стоит прочитать до чек-листа: там могут быть новые решения."
            )

        if sources:
            inferences.append(
                "• Локальный контекст может подсказать связанные проверки и прошлые решения."
            )

        if skill_artifact:
            inferences.append(
                "• QA guidance подходит для следующего шага: тестового фокуса."
            )

        return inferences or ["• Пока недостаточно данных для уверенных выводов."]

    def _task_recommendation_lines(
        self,
        issue: dict,
        blockers: list[str],
        sources: list[dict],
        comments: list[dict],
    ) -> list[str]:
        recommendations = []

        if comments:
            recommendations.append(
                "Сначала прочитать последние комментарии и вынести решения."
            )

        if any("Acceptance Criteria" in blocker for blocker in blockers):
            recommendations.append("Уточнить Acceptance Criteria до финального чек-листа.")

        risk_areas = self._risk_areas(issue, sources, comments)

        if risk_areas:
            recommendations.append(
                "Проверить регрессию в областях: "
                f"{', '.join(risk_areas[:3])}."
            )

        if sources:
            recommendations.append(
                "Использовать найденные заметки как основу тестового фокуса."
            )

        recommendations.append("После проверки вводных подготовить короткий чек-лист.")

        return [
            f"{index}. {recommendation}"
            for index, recommendation in enumerate(recommendations, start=1)
        ]

    def _task_next_best_action(
        self,
        issue: dict,
        blockers: list[str],
        sources: list[dict],
        comments: list[dict],
    ) -> str:
        if any("Jira-контекста" in blocker for blocker in blockers):
            return "Сначала восстановить актуальный Jira-контекст или проверить Jira-настройки."

        if any("Acceptance Criteria" in blocker for blocker in blockers):
            return "Сначала уточнить Acceptance Criteria, затем переходить к чек-листу."

        if comments:
            meaning = self._comment_meaning(str(comments[-1].get("body") or ""))

            if meaning:
                return f"Сначала проверьте решение из последнего комментария: {meaning}"

            return "Сначала прочитайте последние комментарии и вынесите решения в тестовый фокус."

        if sources:
            return "Сначала прочитать найденные знания, затем составить тестовый чек-лист."

        if issue and issue.get("description"):
            return "Начать с описания задачи и сразу выделить основной happy path."

        return "Начать с короткого уточнения у разработчика и после этого собрать чек-лист."

    def _render_work_context_delta(self, artifacts: list[Artifact]) -> list[str]:
        delta_artifact = self._artifact_named(artifacts, "work_context_delta")

        if not delta_artifact:
            return []

        delta = delta_artifact.metadata.get("delta")

        if not isinstance(delta, dict) or not delta.get("has_changes"):
            return []

        lines = []
        lines.extend(self._work_context_field_change_lines(delta))
        lines.extend(self._work_context_comment_change_lines(delta))

        if not lines:
            return []

        return ["Что изменилось с прошлого просмотра", *lines]

    def _work_context_field_change_lines(self, delta: dict) -> list[str]:
        field_labels = {
            "status": "Статус",
            "priority": "Приоритет",
            "assignee": "Исполнитель",
        }
        field_order = {
            field: index
            for index, field in enumerate(field_labels)
        }
        raw_changes = delta.get("field_changes", [])

        if not isinstance(raw_changes, list):
            return []

        changes = [
            change
            for change in raw_changes
            if isinstance(change, dict)
            and change.get("field") in field_labels
            and self._visible_delta_value(change.get("before"))
            and self._visible_delta_value(change.get("after"))
            and self._visible_delta_value(change.get("before"))
            != self._visible_delta_value(change.get("after"))
        ]
        changes.sort(
            key=lambda change: field_order[str(change.get("field"))]
        )

        lines = []

        for change in changes:
            field = str(change.get("field"))
            before = self._visible_delta_value(change.get("before"))
            after = self._visible_delta_value(change.get("after"))
            lines.append(f"• {field_labels[field]}:")
            lines.append(f"  {before} → {after}")

        return lines

    def _work_context_comment_change_lines(self, delta: dict) -> list[str]:
        new_comment_ids = delta.get("new_comment_ids", [])

        if not isinstance(new_comment_ids, list) or not new_comment_ids:
            return []

        if len(new_comment_ids) == 1:
            return ["• Добавлен новый комментарий"]

        return [f"• Добавлено новых комментариев: {len(new_comment_ids)}"]

    def _visible_delta_value(self, value: object) -> str:
        return " ".join(str(value or "").split())

    def _jira_error_summary(self, jira_error: Artifact) -> str:
        content = " ".join(str(jira_error.content).split())

        if "Jira is not configured" in content:
            return "подключение к Jira не настроено."

        return content

    def _safe_comment_excerpt(self, text: str, limit: int = 140) -> str:
        excerpt = " ".join(text.split())

        if not excerpt:
            return ""

        excerpt = re.sub(r"https?://\S+", "[link]", excerpt)
        excerpt = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[email]", excerpt)
        excerpt = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[secret]", excerpt)

        if len(excerpt) <= limit:
            return excerpt

        return f"{excerpt[: limit - 1].rstrip()}…"

    def _strategy_text(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
    ) -> str:
        chunks = [
            str(issue.get("summary") or ""),
            str(issue.get("description") or ""),
        ]
        chunks.extend(str(comment.get("body") or "") for comment in comments)

        for result in sources:
            document = result.get("document", {})
            chunks.append(str(document.get("title") or ""))
            chunks.append(str(document.get("path") or ""))
            chunks.extend(str(tag) for tag in document.get("tags", []))
            chunks.extend(str(heading) for heading in document.get("headings", []))

        return " ".join(chunks).lower()

    def _contains_any(self, text: str, markers: list[str]) -> bool:
        return any(marker in text for marker in markers)

    def _source_titles(self, sources: list[dict]) -> str:
        titles = [
            str(result.get("document", {}).get("title") or "").strip()
            for result in sources
        ]
        visible_titles = [title for title in titles if title]

        return ", ".join(visible_titles) if visible_titles else "без названия"

    def _task_work_state_line(self, issue: dict) -> str:
        status = str(issue.get("status") or "").strip()
        priority = str(issue.get("priority") or "").strip()
        parts = []

        if status and status != "Unavailable":
            parts.append(f"статус {status}")

        if priority and priority != "Unavailable":
            parts.append(f"приоритет {priority}")

        if not parts:
            return "• Jira не дала статуса или приоритета, поэтому фокус нужно определить по описанию."

        return f"• Рабочее состояние: {', '.join(parts)}."

    def _comment_meaning(self, text: str) -> str:
        normalized = text.lower()

        if not normalized.strip():
            return ""

        patterns = [
            (
                ["email", "e-mail", "почт", "подтвержден", "подтверждён", "confirmation"],
                "уточнена логика подтверждения email.",
            ),
            (
                ["password", "парол", "символ", "длин", "complexity"],
                "уточнены ограничения пароля.",
            ),
            (
                ["registration", "регистрац", "signup", "sign up"],
                "уточнён сценарий регистрации.",
            ),
            (
                ["login", "логин", "авторизац", "sign in"],
                "затронут вход пользователя.",
            ),
            (
                ["restore", "reset", "forgot", "восстанов"],
                "затронуто восстановление доступа.",
            ),
            (
                ["api", "endpoint", "request", "response"],
                "есть уточнение по API-поведению.",
            ),
            (
                ["error", "ошиб", "validation", "валидац"],
                "уточнена обработка ошибок или валидации.",
            ),
        ]

        for markers, meaning in patterns:
            if any(marker in normalized for marker in markers):
                return meaning

        return ""

    def _risk_areas(
        self,
        issue: dict,
        sources: list[dict],
        comments: list[dict],
    ) -> list[str]:
        texts = [
            str(issue.get("summary") or ""),
            str(issue.get("description") or ""),
        ]
        texts.extend(str(comment.get("body") or "") for comment in comments)

        for result in sources:
            document = result.get("document", {})
            texts.append(str(document.get("title") or ""))
            texts.append(str(document.get("path") or ""))
            texts.extend(str(tag) for tag in document.get("tags", []))
            texts.extend(str(heading) for heading in document.get("headings", []))

        normalized = " ".join(texts).lower()
        candidates = [
            ("регистрация", ["registration", "signup", "sign up", "регистрац"]),
            ("логин", ["login", "sign in", "логин", "авторизац"]),
            ("подтверждение email", ["email", "e-mail", "почт", "confirmation"]),
            ("восстановление пароля", ["restore", "reset", "forgot", "восстанов"]),
            ("валидация формы", ["validation", "валидац", "form", "форма"]),
            ("API-контракт", ["api", "endpoint", "request", "response"]),
        ]
        areas = []

        for label, markers in candidates:
            if any(marker in normalized for marker in markers):
                areas.append(label)

        return areas

    def _has_acceptance_criteria(self, text: str) -> bool:
        normalized = text.lower()

        return any(
            marker in normalized
            for marker in [
                "acceptance criteria",
                "acceptance",
                "criteria",
                "ac:",
                "критерии приемки",
                "критерии приёмки",
                "критерии",
            ]
        )

    def _source_group(self, document: dict) -> str:
        path = str(document.get("path", "")).lower()
        tags = {str(tag).lower() for tag in document.get("tags", [])}
        title = str(document.get("title", "")).lower()

        if "memory/projects" in path or "project" in tags:
            return "Project Memory"

        if "investigations" in path or "investigation" in tags or "audit" in tags:
            return "Investigations"

        if "03 architecture" in path or "architecture" in tags or title.startswith("adr"):
            return "Architecture"

        if "knowledge" in path:
            return "Knowledge Base"

        return "Reference"

    def _artifact_named(
        self,
        artifacts: list[Artifact],
        name: str,
    ) -> Artifact | None:
        for artifact in artifacts:
            if artifact.name == name:
                return artifact

        return None

    def _visible_vault_structure_items(
        self,
        structure: dict[str, int],
    ) -> list[tuple[str, int]]:
        items = [
            (folder, count)
            for folder, count in structure.items()
            if self._is_user_facing_folder(folder)
        ]

        return items or list(structure.items())[:30]

    def _is_user_facing_folder(self, folder: str) -> bool:
        technical_parts = {
            ".agents",
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".qaos",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "site-packages",
        }
        parts = folder.split("/")

        return not any(
            part.startswith(".qaos")
            or part in technical_parts
            or part.endswith(".dist-info")
            for part in parts
        )
