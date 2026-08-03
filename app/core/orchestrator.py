from datetime import UTC, datetime
from pathlib import Path

from app.context.composer import ContextComposer
from app.core.config import load_settings
from app.core.artifacts import Artifact, PipelineTrace
from app.core.capabilities import CapabilityRegistry
from app.core.executor import PlanExecutor
from app.core.intent import UserIntent
from app.core.intent_analyzer import IntentAnalyzer
from app.core.models import UserRequest, OrchestratorResponse
from app.core.planner import TaskPlanner
from app.core.task_plan import TaskPlan
from app.prompt.prompt_builder import PromptBuilder
from app.providers.router import ProviderRouter
from app.response.composer import ResponseComposer
from app.services.jira_client import JiraCredentials
from app.work_context import (
    SeenStateDelta,
    SeenEntityState,
    SeenStateStorage,
    compare_seen_state,
    current_jira_issue_state,
)
from app.services import (
    ChangeAnalysisService,
    DailyBriefService,
    JiraService,
    LLMService,
    MemoryService,
    ServiceRegistry,
    SkillService,
    SnapshotService,
)


class Orchestrator:
    """Application service that wires the current request pipeline together."""

    def __init__(self):
        self.settings = load_settings()
        self.capabilities = CapabilityRegistry()
        self.services = ServiceRegistry(self.capabilities)

        for service in [
            MemoryService(
                vault_path=self.settings.memory_vault_path,
                index_path=self.settings.document_index_path,
            ),
            SkillService(vault_path=self.settings.memory_vault_path),
            JiraService(
                credentials=JiraCredentials.from_settings(self.settings),
            ),
            SnapshotService(vault_path=self.settings.memory_vault_path),
            ChangeAnalysisService(),
            DailyBriefService(),
            LLMService(
                provider_router=ProviderRouter.from_settings(self.settings),
            ),
        ]:
            self.services.register(service)

        self.intent_analyzer = IntentAnalyzer()
        self.task_planner = TaskPlanner(self.capabilities)
        self.plan_executor = PlanExecutor(self.services)
        self.response_composer = ResponseComposer()
        self.seen_state_storage = SeenStateStorage(
            self.settings.personal_seen_state_path
        )

    def process(self, request: UserRequest) -> OrchestratorResponse:
        trace = PipelineTrace()

        trace.add("Orchestrator", "Started request pipeline")
        intent = self.intent_analyzer.analyze(request)
        trace.add("Intent Analyzer", f"Detected intent {intent.name}")

        if intent.name == "working_session_follow_up":
            return self._process_working_session_follow_up(
                request=request,
                intent=intent,
                trace=trace,
            )

        plan = self.task_planner.plan(intent, trace=trace)

        artifacts = self.plan_executor.execute_collection(
            plan=plan,
            request=request,
            intent=intent,
            trace=trace,
        )
        artifacts = self._with_seen_state_delta(
            intent=intent,
            artifacts=artifacts,
        )
        artifacts = self._remember_working_session_issue(
            intent=intent,
            artifacts=artifacts,
        )

        llm_artifact = None

        if plan.needs_generation():
            context = ContextComposer().compose(
                plan=plan,
                artifacts=artifacts,
                trace=trace,
            )

            prompt = PromptBuilder().build(
                request=request,
                plan=plan,
                context=context,
                trace=trace,
            )

            llm_artifact = self._generate_response_artifact(
                plan=plan,
                request=request,
                intent=intent,
                artifacts=artifacts,
                prompt_text=prompt.text,
                trace=trace,
            )

        return self.response_composer.compose(
            request=request,
            intent=intent,
            plan=plan,
            artifacts=artifacts,
            llm_artifact=llm_artifact,
            trace=trace,
        )

    def _process_working_session_follow_up(
        self,
        request: UserRequest,
        intent: UserIntent,
        trace: PipelineTrace,
    ) -> OrchestratorResponse:
        trace.add("Task Planner", "Using active Working Session context")
        action = intent.metadata.get("action", "update")
        active = self.seen_state_storage.load().latest_entity()

        if not active:
            trace.add("Response Composer", "Composed final user response")
            return OrchestratorResponse(
                success=True,
                message=(
                    "Активная рабочая сессия не найдена.\n\n"
                    "Открой задачу: `Берём SCRUM-11`."
                ),
                data=self._working_session_response_data(
                    request=request,
                    intent=intent,
                    artifacts=[],
                    trace=trace,
                ),
            )

        issue_key = active.entity_id
        investigation_path = self._find_investigation_path(issue_key)
        investigation_text = (
            investigation_path.read_text(encoding="utf-8")
            if investigation_path
            else ""
        )
        updates = self._working_session_updates(
            action=action,
            text=request.text,
            issue_key=issue_key,
            investigation_text=investigation_text,
        )

        if investigation_path and updates["section_updates"]:
            updated_text = self._updated_investigation_text(
                text=investigation_text,
                section_updates=updates["section_updates"],
            )
            investigation_path.write_text(updated_text, encoding="utf-8")
            investigation_text = updated_text

        jira_delta_artifact = (
            self._jira_delta_artifact(issue_key=issue_key, active=active)
            if action in {"resume", "morning_resume"}
            else None
        )
        artifacts = [
            Artifact(
                name="working_session_update",
                source="Working Session",
                content=updates["message"],
                metadata={
                    "issue_key": issue_key,
                    "action": action,
                    "investigation_path": (
                        str(investigation_path)
                        if investigation_path
                        else ""
                    ),
                    "remaining": self._section_items(
                        investigation_text,
                        "Test Scope",
                    ),
                },
            )
        ]

        if jira_delta_artifact:
            artifacts.append(jira_delta_artifact)

        trace.add("Response Composer", "Composed final user response")
        return OrchestratorResponse(
            success=True,
            message=self._working_session_message(
                issue_key=issue_key,
                action=action,
                updates=updates,
                investigation_text=investigation_text,
                jira_delta_artifact=jira_delta_artifact,
                has_investigation=bool(investigation_path),
            ),
            data=self._working_session_response_data(
                request=request,
                intent=intent,
                artifacts=artifacts,
                trace=trace,
            ),
        )

    def ask(self, prompt: str) -> str:
        response = self.process(UserRequest(text=prompt))
        return response.message

    def _generate_response_artifact(
        self,
        plan: TaskPlan,
        request: UserRequest,
        intent: UserIntent,
        artifacts: list[Artifact],
        prompt_text: str,
        trace: PipelineTrace,
    ) -> Artifact | None:
        generation_step = plan.generation_step()

        if not generation_step:
            return None

        return self.plan_executor.execute_step(
            step=generation_step,
            plan=plan,
            request=request,
            intent=intent,
            artifacts=artifacts,
            trace=trace,
            payload={"prompt": prompt_text},
        )

    def _remember_working_session_issue(
        self,
        intent: UserIntent,
        artifacts: list[Artifact],
    ) -> list[Artifact]:
        if intent.metadata.get("working_session_mode") not in {"open", "resume"}:
            return artifacts

        jira_issue = self._artifact_named(artifacts, "jira_issue")

        if not jira_issue:
            return artifacts

        issue = jira_issue.metadata.get("issue")

        if not isinstance(issue, dict):
            return artifacts

        try:
            current = current_jira_issue_state(issue)
        except ValueError:
            return artifacts

        previous = self.seen_state_storage.load().latest_entity()
        switch_artifact = None

        if (
            previous
            and previous.entity_id != current.entity_id
            and previous.last_workflow == "working_session"
        ):
            paused_path = self._pause_investigation_for_switch(
                previous_issue_key=previous.entity_id,
                next_issue_key=current.entity_id,
            )
            switch_artifact = Artifact(
                name="working_session_switch",
                source="Working Session",
                content=(
                    f"Previous session {previous.entity_id} paused before "
                    f"opening {current.entity_id}."
                ),
                metadata={
                    "previous_issue_key": previous.entity_id,
                    "current_issue_key": current.entity_id,
                    "paused_investigation_path": (
                        str(paused_path) if paused_path else ""
                    ),
                },
            )

        self.seen_state_storage.upsert(
            SeenEntityState(
                source=current.source,
                entity_type=current.entity_type,
                entity_id=current.entity_id,
                last_seen_at=self._now_iso(),
                source_updated_at=current.source_updated_at,
                status_seen=current.status,
                priority_seen=current.priority,
                summary_fingerprint=current.summary_fingerprint,
                description_fingerprint=current.description_fingerprint,
                links_fingerprint=current.links_fingerprint,
                comments_seen=current.comment_ids,
                last_workflow="working_session",
            )
        )

        if switch_artifact:
            return [*artifacts, switch_artifact]

        return artifacts

    def _with_seen_state_delta(
        self,
        intent: UserIntent,
        artifacts: list[Artifact],
    ) -> list[Artifact]:
        if intent.name not in {"prepare_task", "test_task_strategy"}:
            return artifacts

        jira_issue = self._artifact_named(artifacts, "jira_issue")

        if not jira_issue:
            return artifacts

        issue = jira_issue.metadata.get("issue")

        if not isinstance(issue, dict):
            return artifacts

        try:
            current = current_jira_issue_state(issue)
        except ValueError:
            return artifacts

        previous = self.seen_state_storage.get(
            source=current.source,
            entity_type=current.entity_type,
            entity_id=current.entity_id,
        )

        if not previous:
            return artifacts

        delta = compare_seen_state(previous, current)

        return [
            *artifacts,
            Artifact(
                name="work_context_delta",
                source="Personal Work Context",
                content=self._delta_content(delta),
                metadata={"delta": delta.to_dict()},
            ),
        ]

    def _delta_content(self, delta: SeenStateDelta) -> str:
        if delta.has_changes:
            return (
                "Personal Seen State delta calculated: "
                f"{len(delta.field_changes)} field changes, "
                f"{len(delta.new_comment_ids)} new comments."
            )

        return "Personal Seen State delta calculated: no changes."

    def _artifact_named(
        self,
        artifacts: list[Artifact],
        name: str,
    ) -> Artifact | None:
        for artifact in artifacts:
            if artifact.name == name:
                return artifact

        return None

    def _find_investigation_path(self, issue_key: str) -> Path | None:
        investigations = (
            Path(self.settings.memory_vault_path).expanduser().resolve()
            / "QASkills"
            / "Investigations"
        )

        if not investigations.exists():
            return None

        matches = sorted(investigations.glob(f"*{issue_key}*.md"))

        return matches[0] if matches else None

    def _working_session_updates(
        self,
        action: str,
        text: str,
        issue_key: str,
        investigation_text: str,
    ) -> dict:
        stamp = self._now_iso()
        section_updates: dict[str, list[str]] = {}

        if action == "refresh_checked":
            return {
                "message": "Refresh checked, but result is missing.",
                "progress": [],
                "observations": [],
                "missing": ["Refresh прошёл или снова был 401?"],
                "next": "Ответьте коротко: `прошёл` или `снова 401`, плюс browser/build.",
                "section_updates": {},
            }

        if action == "safari_only":
            observation = f"- {stamp}: User reported Safari-specific behavior."
            section_updates["Observations"] = [observation]
            section_updates["Risks"] = [
                f"- {stamp}: Safari-specific regression risk remains active."
            ]
            section_updates["Reasoning Timeline"] = [
                f"- {stamp}: Added Safari-specific observation for {issue_key}."
            ]
            return {
                "message": "Safari-specific observation added.",
                "progress": [],
                "observations": ["• Поведение пока связано с Safari."],
                "missing": ["Нужны Safari version, build/env и actual result."],
                "next": "Повторите refresh в Safari с Network/Application evidence.",
                "section_updates": section_updates,
            }

        if action == "checked_passed":
            section_updates["Evidence"] = [
                f"- {stamp}: User note: `{text}`."
            ]
            section_updates["Results"] = [
                f"- {stamp}: User reported a passing check. Evidence is incomplete until browser, build, and attempts are recorded."
            ]
            section_updates["Reasoning Timeline"] = [
                f"- {stamp}: Added passing user-reported check for {issue_key}."
            ]
            return {
                "message": "Passing check recorded with evidence gap.",
                "progress": ["• Проверка отмечена как passed по сообщению пользователя."],
                "observations": [],
                "missing": ["Нужны browser, build/env и attempts count."],
                "next": "Продолжайте следующий remaining check или добавьте окружение для этого результата.",
                "section_updates": section_updates,
            }

        if action == "checked":
            section_updates["Evidence"] = [
                f"- {stamp}: User note: `{text}`."
            ]
            section_updates["Results"] = [
                f"- {stamp}: User reported a completed check. Result is incomplete until pass/fail, browser, build, and evidence are recorded."
            ]
            section_updates["Reasoning Timeline"] = [
                f"- {stamp}: Added completed-check update for {issue_key}."
            ]
            return {
                "message": "Completed check recorded with missing result.",
                "progress": ["• Проверка записана, но результат ещё неясен."],
                "observations": [],
                "missing": ["Проверка прошла или упала? Нужны browser/build/evidence."],
                "next": "Ответьте коротко: `прошло` или `снова 401/failed`.",
                "section_updates": section_updates,
            }

        if action == "checked_failed":
            section_updates["Evidence"] = [
                f"- {stamp}: User note: `{text}`."
            ]
            section_updates["Results"] = [
                f"- {stamp}: User reported a failing check. Evidence is incomplete until exact steps, actual result, browser, build, and artifact are recorded."
            ]
            section_updates["Bug Candidate"] = [
                f"- {stamp}: Possible defect from user-reported failure: `{text}`.",
                "- Missing: exact steps, actual result, expected result, environment, evidence.",
            ]
            section_updates["Reasoning Timeline"] = [
                f"- {stamp}: Added failing user-reported check and bug candidate for {issue_key}."
            ]
            return {
                "message": "Failing check recorded as bug candidate.",
                "progress": ["• Проверка отмечена как failed по сообщению пользователя."],
                "observations": ["• Возможный дефект требует evidence before bug draft."],
                "missing": [
                    "Нужны exact steps, actual result, expected result, browser/build и evidence."
                ],
                "next": "Пришлите окружение и артефакт; затем можно готовить bug report.",
                "section_updates": section_updates,
            }

        if action == "bug_found":
            section_updates["Bug Candidate"] = [
                f"- {stamp}: User reported a bug during {issue_key} verification.",
                "- Missing: steps, actual result, expected result, environment, evidence.",
            ]
            section_updates["Reasoning Timeline"] = [
                f"- {stamp}: Bug candidate opened from user report."
            ]
            return {
                "message": "Bug candidate opened.",
                "progress": [],
                "observations": ["• Есть потенциальный дефект."],
                "missing": [
                    "Нужны steps, actual result, expected result, browser/build и evidence."
                ],
                "next": "Пришлите фактический результат и окружение; затем подготовлю bug draft.",
                "section_updates": section_updates,
            }

        if action == "not_reproduced":
            section_updates["Results"] = [
                f"- {stamp}: User reported that the issue is not reproduced. Evidence is incomplete until attempts, environment, and build are recorded."
            ]
            section_updates["Reasoning Timeline"] = [
                f"- {stamp}: Added not-reproduced result with evidence gap."
            ]
            return {
                "message": "Not-reproduced result recorded with evidence gap.",
                "progress": ["• Не воспроизводится: записано как результат с ограничением."],
                "observations": [],
                "missing": ["Нужны attempts count, browser, build/env."],
                "next": "Зафиксируйте количество попыток и окружение перед выводом по фиксу.",
                "section_updates": section_updates,
            }

        if action == "blocker":
            section_updates["Open Questions"] = [
                f"- {stamp}: User reported a blocker. Details are missing."
            ]
            section_updates["Reasoning Timeline"] = [
                f"- {stamp}: Working session marked as blocked pending details."
            ]
            return {
                "message": "Blocker noted.",
                "progress": [],
                "observations": ["• Есть блокер, детали пока не указаны."],
                "missing": ["Что именно блокирует проверку: доступ, build, данные или окружение?"],
                "next": "Назовите блокер одним сообщением; я обновлю Stop Point.",
                "section_updates": section_updates,
            }

        if action == "stop_point":
            section_updates["Current Reasoning State"] = [
                "Stop Point: Working session paused.",
                "Next Step: continue from Remaining checks.",
            ]
            section_updates["Stop Point"] = [
                f"Working session paused on {stamp}.",
                "Next Step: continue from Remaining checks.",
            ]
            section_updates["Reasoning Timeline"] = [
                f"- {stamp}: Stop Point saved for the working session."
            ]
            return {
                "message": "Stop Point saved.",
                "progress": ["• Stop Point сохранён."],
                "observations": [],
                "missing": [],
                "next": "Завтра напишите `Продолжаем` или `Продолжаем SCRUM-11`.",
                "section_updates": section_updates,
            }

        if action == "bug_draft":
            return {
                "message": "Bug draft can be prepared from current context.",
                "progress": [],
                "observations": [],
                "missing": self._bug_candidate_missing(investigation_text),
                "next": "Если missing evidence закрыт, можно готовить bug report.",
                "section_updates": {},
            }

        return {
            "message": "Workspace state loaded.",
            "progress": [],
            "observations": [],
            "missing": [],
            "next": "Продолжайте проверку или спросите `Что осталось?`.",
            "section_updates": {},
        }

    def _working_session_message(
        self,
        issue_key: str,
        action: str,
        updates: dict,
        investigation_text: str,
        jira_delta_artifact: Artifact | None,
        has_investigation: bool,
    ) -> str:
        lines = [f"{issue_key}", "Working Session"]

        if action == "remaining":
            lines.extend(["", "Remaining"])
            lines.extend(self._section_items(investigation_text, "Test Scope") or ["• Remaining не найден в Investigation."])
            lines.extend(["", "Next Action", "• " + self._next_step_from_investigation(investigation_text)])
            return "\n".join(lines)

        if action == "known":
            lines.extend(["", "Что известно"])
            lines.extend(self._section_items(investigation_text, "Confirmed Facts") or ["• Known facts не найдены в Investigation."])
            lines.extend(["", "Observations"])
            lines.extend(self._section_items(investigation_text, "Observations") or ["• Новых observations нет."])
            return "\n".join(lines)

        if action in {"resume", "morning_resume"}:
            if action == "morning_resume":
                lines = [f"Доброе утро. Возвращаемся к {issue_key}.", "Working Session"]
            lines.extend(["", "Stop Point"])
            lines.extend(self._section_items(investigation_text, "Stop Point") or ["• Stop Point не найден."])
            lines.extend(["", "Что изменилось"])
            lines.extend(self._delta_lines_from_artifact(jira_delta_artifact))
            lines.extend(["", "Remaining"])
            lines.extend(self._section_items(investigation_text, "Test Scope") or ["• Remaining не найден в Investigation."])
            lines.extend(["", "Next Action", "• " + self._next_step_from_investigation(investigation_text)])
            return "\n".join(lines)

        if not has_investigation:
            lines.extend(["", "Missing Evidence", "• Investigation для активной задачи не найдена."])
            lines.extend(["", "Next Action", "• Откройте задачу заново или создайте Investigation."])
            return "\n".join(lines)

        if updates.get("progress"):
            lines.extend(["", "Progress"])
            lines.extend(updates["progress"])

        if updates.get("observations"):
            lines.extend(["", "Observation"])
            lines.extend(updates["observations"])

        remaining = self._section_items(investigation_text, "Test Scope")
        lines.extend(["", "Remaining"])
        lines.extend(remaining or ["• Remaining не найден в Investigation."])

        if updates.get("missing"):
            lines.extend(["", "Missing Evidence"])
            lines.extend(f"• {item}" for item in updates["missing"])

        lines.extend(["", "Next Action", f"• {updates['next']}"])

        return "\n".join(lines)

    def _pause_investigation_for_switch(
        self,
        previous_issue_key: str,
        next_issue_key: str,
    ) -> Path | None:
        path = self._find_investigation_path(previous_issue_key)

        if not path:
            return None

        text = path.read_text(encoding="utf-8")
        stamp = self._now_iso()
        updated = self._updated_investigation_text(
            text=text,
            section_updates={
                "Current Reasoning State": [
                    f"Stop Point: Paused because user switched to {next_issue_key}.",
                    f"Next Step: resume {previous_issue_key} from Remaining checks.",
                ],
                "Stop Point": [
                    f"Paused because user switched to {next_issue_key}.",
                    f"Next Step: resume {previous_issue_key} from Remaining checks.",
                ],
                "Reasoning Timeline": [
                    f"- {stamp}: Working session paused because user switched to {next_issue_key}."
                ],
            },
        )
        path.write_text(updated, encoding="utf-8")

        return path

    def _delta_lines_from_artifact(self, artifact: Artifact | None) -> list[str]:
        if not artifact:
            return ["• Jira delta не проверен: Jira-контекст недоступен."]

        delta = artifact.metadata.get("delta", {})
        if not isinstance(delta, dict):
            return ["• Jira delta не проверен."]

        if not delta.get("has_changes"):
            return ["• С прошлого просмотра изменений Jira не видно."]

        lines = []
        for change in delta.get("field_changes", []):
            if not isinstance(change, dict):
                continue
            field = str(change.get("field") or "")
            if field in {"status", "priority"}:
                lines.append(
                    f"• {field}: {change.get('before') or ''} → {change.get('after') or ''}"
                )

        new_comments = delta.get("new_comment_ids", [])
        if isinstance(new_comments, list) and new_comments:
            lines.append(f"• Новых комментариев Jira: {len(new_comments)}")

        return lines or ["• Изменения Jira есть, но они не требуют действия сейчас."]

    def _jira_delta_artifact(
        self,
        issue_key: str,
        active: SeenEntityState,
    ) -> Artifact | None:
        jira_service = self.services.get("jira.get_issue")
        artifact = jira_service.execute(
            capability="jira.get_issue",
            request=self._service_request_for_issue(issue_key),
        )

        issue = artifact.metadata.get("issue")
        if not isinstance(issue, dict):
            return None

        try:
            current = current_jira_issue_state(issue)
            delta = compare_seen_state(active, current)
        except ValueError:
            return None

        self.seen_state_storage.upsert(
            SeenEntityState(
                source=current.source,
                entity_type=current.entity_type,
                entity_id=current.entity_id,
                last_seen_at=self._now_iso(),
                source_updated_at=current.source_updated_at,
                status_seen=current.status,
                priority_seen=current.priority,
                summary_fingerprint=current.summary_fingerprint,
                description_fingerprint=current.description_fingerprint,
                links_fingerprint=current.links_fingerprint,
                comments_seen=current.comment_ids,
                last_workflow="working_session",
            )
        )

        return Artifact(
            name="work_context_delta",
            source="Personal Work Context",
            content=self._delta_content(delta),
            metadata={"delta": delta.to_dict()},
        )

    def _service_request_for_issue(self, issue_key: str):
        intent = UserIntent(
            name="jira_get_issue",
            raw_text=f"jira issue {issue_key}",
            expected_output="jira_issue",
            confidence=0.95,
            metadata={"issue_key": issue_key},
        )
        plan = TaskPlan(
            goal=intent.raw_text,
            intent=intent,
            steps=[],
            response_contract=intent.expected_output,
            context_budget=2000,
        )

        from app.services.base import ServiceRequest

        return ServiceRequest(
            user_text=intent.raw_text,
            intent=intent,
            plan=plan,
            payload={"issue_key": issue_key},
        )

    def _updated_investigation_text(
        self,
        text: str,
        section_updates: dict[str, list[str]],
    ) -> str:
        updated = text

        for heading, lines in section_updates.items():
            updated = self._append_to_section(
                text=updated,
                heading=heading,
                lines=lines,
            )

        return updated

    def _append_to_section(
        self,
        text: str,
        heading: str,
        lines: list[str],
    ) -> str:
        addition = "\n".join(lines).strip()
        if not addition:
            return text

        marker = f"## {heading}"
        next_heading_pattern = "\n## "

        if marker not in text:
            insert_before = "## Current Reasoning State"
            section = f"\n## {heading}\n\n{addition}\n"
            if insert_before in text:
                return text.replace(insert_before, f"{section}\n{insert_before}", 1)
            return f"{text.rstrip()}\n\n{section}"

        start = text.index(marker) + len(marker)
        next_heading = text.find(next_heading_pattern, start)
        if next_heading == -1:
            return f"{text.rstrip()}\n{addition}\n"

        before = text[:next_heading].rstrip()
        after = text[next_heading:]

        return f"{before}\n{addition}\n{after}"

    def _section_items(self, text: str, heading: str) -> list[str]:
        section = self._section_text(text, heading)
        items = []

        for line in section.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                items.append(f"• {stripped[2:]}")
            elif stripped and heading == "Stop Point":
                items.append(f"• {stripped}")

        return [
            item
            for item in items
            if item not in {"• None yet.", "• TBD"}
        ][:8]

    def _section_text(self, text: str, heading: str) -> str:
        marker = f"## {heading}"
        if marker not in text:
            return ""

        start = text.index(marker) + len(marker)
        next_heading = text.find("\n## ", start)

        if next_heading == -1:
            return text[start:].strip()

        return text[start:next_heading].strip()

    def _next_step_from_investigation(self, text: str) -> str:
        state = self._section_text(text, "Current Reasoning State")
        for line in state.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("next step:"):
                return stripped.split(":", 1)[1].strip() or "continue testing."

        stop = self._section_items(text, "Stop Point")
        if stop:
            return stop[-1].lstrip("• ").strip()

        return "continue from the next remaining check."

    def _bug_candidate_missing(self, investigation_text: str) -> list[str]:
        section = self._section_text(investigation_text, "Bug Candidate")
        missing = []

        for field in ["steps", "actual result", "expected result", "environment", "evidence"]:
            if field not in section.lower():
                missing.append(field)

        return missing or ["Проверьте, что evidence не содержит секретов."]

    def _working_session_response_data(
        self,
        request: UserRequest,
        intent: UserIntent,
        artifacts: list[Artifact],
        trace: PipelineTrace,
    ) -> dict:
        return {
            "request": request.text,
            "intent": {
                "name": intent.name,
                "expected_output": intent.expected_output,
                "confidence": intent.confidence,
                "metadata": dict(intent.metadata),
            },
            "plan": {
                "goal": intent.raw_text,
                "intent": intent.name,
                "response_contract": intent.expected_output,
                "context_budget": 2000,
                "missing_capabilities": [],
                "steps": [],
            },
            "artifacts": [artifact.to_dict() for artifact in artifacts],
            "llm_artifact": None,
            "pipeline": trace.to_dicts(),
        }

    def _now_iso(self) -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")
