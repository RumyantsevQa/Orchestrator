import unittest

from app.core.artifacts import Artifact, PipelineTrace
from app.core.intent import UserIntent
from app.core.models import UserRequest
from app.core.task_plan import TaskPlan
from app.response.composer import ResponseComposer


class ResponseComposerWorkContextDeltaTest(unittest.TestCase):
    def setUp(self):
        self.composer = ResponseComposer()

    def test_no_delta_renders_nothing(self):
        self.assertEqual(self.composer._render_work_context_delta([]), [])
        self.assertEqual(
            self.composer._render_work_context_delta(
                [
                    self._delta_artifact(
                        has_changes=False,
                        field_changes=[
                            {
                                "field": "status",
                                "before": "Review",
                                "after": "Done",
                            }
                        ],
                    )
                ]
            ),
            [],
        )

    def test_status_change_renders_status_line(self):
        lines = self.composer._render_work_context_delta(
            [
                self._delta_artifact(
                    field_changes=[
                        {
                            "field": "status",
                            "before": "Review",
                            "after": "Done",
                        }
                    ]
                )
            ]
        )

        self.assertEqual(
            lines,
            [
                "Что изменилось с прошлого просмотра",
                "• Статус:",
                "  Review → Done",
            ],
        )

    def test_priority_change_renders_priority_line(self):
        lines = self.composer._render_work_context_delta(
            [
                self._delta_artifact(
                    field_changes=[
                        {
                            "field": "priority",
                            "before": "Medium",
                            "after": "High",
                        }
                    ]
                )
            ]
        )

        self.assertIn("• Приоритет:", lines)
        self.assertIn("  Medium → High", lines)

    def test_comment_change_renders_comment_line_without_ids(self):
        lines = self.composer._render_work_context_delta(
            [self._delta_artifact(new_comment_ids=["10002"])]
        )

        self.assertEqual(
            lines,
            [
                "Что изменилось с прошлого просмотра",
                "• Добавлен новый комментарий",
            ],
        )
        self.assertNotIn("10002", "\n".join(lines))

    def test_multiple_changes_render_in_stable_order(self):
        lines = self.composer._render_work_context_delta(
            [
                self._delta_artifact(
                    field_changes=[
                        {
                            "field": "priority",
                            "before": "Medium",
                            "after": "High",
                        },
                        {
                            "field": "status",
                            "before": "Review",
                            "after": "Done",
                        },
                    ],
                    new_comment_ids=["10002", "10003"],
                )
            ]
        )

        self.assertEqual(
            lines,
            [
                "Что изменилось с прошлого просмотра",
                "• Статус:",
                "  Review → Done",
                "• Приоритет:",
                "  Medium → High",
                "• Добавлено новых комментариев: 2",
            ],
        )

    def test_prepare_task_without_delta_matches_alpha_baseline_output(self):
        message = self.composer.compose(
            request=UserRequest(text="Подготовь меня к SCRUM-7"),
            intent=self._prepare_task_intent(),
            plan=self._prepare_task_plan(),
            artifacts=[
                self._jira_issue_artifact(),
                self._memory_search_artifact(),
                self._skill_artifact(),
            ],
            llm_artifact=None,
            trace=PipelineTrace(),
        ).message

        self.assertEqual(
            message,
            "\n".join(
                [
                    "Я подготовил задачу SCRUM-7.",
                    "",
                    "Главное",
                    "• Вы будете разбирать: Registration with email confirmation.",
                    "• Рабочее состояние: статус Ready for QA, приоритет High.",
                    "• В Obsidian есть локальный контекст: SCRUM-7 Registration.",
                    "",
                    "На что обратить внимание",
                    "• Есть риск регрессии: регистрация, подтверждение email.",
                    "• Комментарии могут содержать решения, которые не отражены в описании.",
                    "",
                    "Следующий лучший шаг",
                    "• Сначала прочитайте последние комментарии и вынесите решения в тестовый фокус.",
                    "",
                    "Что изменилось",
                    "• Последний комментарий: Moved to Ready for QA.",
                    "",
                    "Что мешает начать",
                    "• Явных блокеров по собранным источникам не видно.",
                    "",
                    "Facts",
                    "• Задача: Registration with email confirmation",
                    "• Текущий статус: Ready for QA",
                    "• Приоритет: High",
                    "• Описание задачи доступно.",
                    "• В задаче есть комментарии, которые могут менять тестовый фокус.",
                    "• Источник из Obsidian: SCRUM-7 Registration (QASkills/Memory/Projects/SCRUM-7.md)",
                    "",
                    "Inferences",
                    "• Комментарии стоит прочитать до чек-листа: там могут быть новые решения.",
                    "• Локальный контекст может подсказать связанные проверки и прошлые решения.",
                    "• QA guidance подходит для следующего шага: тестового фокуса.",
                    "",
                    "Recommendations",
                    "1. Сначала прочитать последние комментарии и вынести решения.",
                    "2. Проверить регрессию в областях: регистрация, подтверждение email.",
                    "3. Использовать найденные заметки как основу тестового фокуса.",
                    "4. После проверки вводных подготовить короткий чек-лист.",
                    "",
                    "Предлагаемые действия",
                    "• [ ] Принять следующий шаг.",
                    "• [ ] Подготовить тестовый чек-лист после проверки вводных.",
                    "• [ ] Сохранить подтверждённые выводы в Obsidian.",
                    "• [ ] Ничего не делать сейчас.",
                    "",
                    "Я ничего не сохранял и не изменял без подтверждения.",
                ]
            ),
        )

    def _delta_artifact(
        self,
        has_changes: bool = True,
        field_changes: list[dict[str, str]] | None = None,
        new_comment_ids: list[str] | None = None,
    ) -> Artifact:
        return Artifact(
            name="work_context_delta",
            source="Personal Work Context",
            content="",
            metadata={
                "delta": {
                    "has_changes": has_changes,
                    "field_changes": list(field_changes or []),
                    "new_comment_ids": list(new_comment_ids or []),
                }
            },
        )

    def _prepare_task_intent(self) -> UserIntent:
        return UserIntent(
            name="prepare_task",
            raw_text="Подготовь меня к SCRUM-7",
            expected_output="task_preparation",
            confidence=0.9,
            metadata={"issue_key": "SCRUM-7"},
        )

    def _prepare_task_plan(self) -> TaskPlan:
        intent = self._prepare_task_intent()

        return TaskPlan(
            goal=intent.raw_text,
            intent=intent,
            steps=[],
            response_contract="task_preparation",
            context_budget=2000,
        )

    def _jira_issue_artifact(self) -> Artifact:
        return Artifact(
            name="jira_issue",
            source="Jira Service",
            content="",
            metadata={
                "issue": {
                    "key": "SCRUM-7",
                    "summary": "Registration with email confirmation",
                    "status": "Ready for QA",
                    "priority": "High",
                    "description": (
                        "User registration flow. "
                        "Acceptance Criteria: email confirmation is required."
                    ),
                    "comments": [
                        {
                            "author": "Developer",
                            "created": "2026-07-31T09:00:00+03:00",
                            "body": "Moved to Ready for QA.",
                        }
                    ],
                    "links": [],
                }
            },
        )

    def _memory_search_artifact(self) -> Artifact:
        return Artifact(
            name="memory_search_results",
            source="Memory Service",
            content="",
            metadata={
                "results": [
                    {
                        "score": 10,
                        "reasons": ["title"],
                        "document": {
                            "title": "SCRUM-7 Registration",
                            "path": "QASkills/Memory/Projects/SCRUM-7.md",
                            "tags": ["qa"],
                            "headings": ["Test ideas"],
                        },
                    }
                ]
            },
        )

    def _skill_artifact(self) -> Artifact:
        return Artifact(
            name="skill_guidance",
            source="Skill Service",
            content="",
            metadata={},
        )


if __name__ == "__main__":
    unittest.main()
