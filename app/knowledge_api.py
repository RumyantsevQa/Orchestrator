import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.artifacts import Artifact
from app.core.config import Settings, load_settings
from app.core.intent import UserIntent
from app.core.task_plan import TaskPlan
from app.services.base import ServiceRequest
from app.services.jira import JiraService
from app.services.jira_client import JiraCredentials
from app.services.memory import MemoryService


DEFAULT_INCLUDE = ("jira", "knowledge", "skills", "rules")
DEFAULT_RULES = (
    {
        "id": "evidence_first",
        "title": "Evidence First",
        "path": "QASkills/Knowledge/QA/Evidence First.md",
        "summary": (
            "Every claim must be grounded in evidence or clearly marked as "
            "interpretation, hypothesis, assumption, contradiction, or unknown."
        ),
    },
    {
        "id": "human_controlled_knowledge",
        "title": "Human Controlled Knowledge",
        "path": "QASkills/Knowledge/QA/Human Controlled Knowledge.md",
        "summary": "Durable knowledge is saved only after human confirmation.",
    },
    {
        "id": "safe_external_actions",
        "title": "Safe External Actions",
        "path": "PROJECT_RULES.md",
        "summary": "Do not perform irreversible external actions without approval.",
    },
)
GOAL_SKILLS = {
    "task_preparation": ("AnalyzeFeature", "AnalyzeRequirement", "RiskAnalysis"),
    "testing_strategy": ("AnalyzeFeature", "GenerateTestCases", "RiskAnalysis"),
    "bug_reporting": ("BugInvestigation", "QACommunication"),
    "daily_preparation": ("LeadQA", "ContextRecovery"),
    "meeting_analysis": ("AnalyzeMeeting", "QACommunication"),
    "knowledge_update": ("KnowledgeCuration",),
    "regression": ("PrepareRegression", "RiskAnalysis"),
    "release": ("ReleaseReview", "RiskAnalysis"),
}
QUERY_EXPANSIONS = {
    "auth": [
        "authentication",
        "authorization",
        "login",
        "session",
        "token",
        "cookie",
        "access control",
    ],
    "authorization": [
        "authentication",
        "auth",
        "login",
        "session",
        "token",
        "cookie",
        "access control",
    ],
    "authentication": [
        "authorization",
        "auth",
        "login",
        "session",
        "token",
        "cookie",
        "access control",
    ],
    "oauth": [
        "authentication",
        "authorization",
        "auth",
        "token",
        "session",
        "api",
        "redirect",
        "callback",
    ],
    "авторизация": [
        "authorization",
        "authentication",
        "auth",
        "login",
        "session",
        "token",
        "cookie",
        "access control",
    ],
    "авторизацию": [
        "authorization",
        "authentication",
        "auth",
        "login",
        "session",
        "token",
        "cookie",
        "access control",
    ],
    "авторизации": [
        "authorization",
        "authentication",
        "auth",
        "login",
        "session",
        "token",
        "cookie",
        "access control",
    ],
    "аутентификация": ["authentication", "authorization", "auth", "login", "session"],
    "аутентификацию": ["authentication", "authorization", "auth", "login", "session"],
    "логин": ["login", "authentication", "auth", "session"],
    "сессия": ["session", "cookie", "token", "authentication"],
    "сессию": ["session", "cookie", "token", "authentication"],
    "токен": ["token", "session", "authentication", "authorization"],
    "пароль": ["password", "authentication", "login", "recovery"],
    "доступ": ["access control", "authorization", "permissions"],
}
FALLBACK_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "how",
    "in",
    "is",
    "me",
    "my",
    "of",
    "on",
    "the",
    "to",
    "what",
    "with",
    "а",
    "в",
    "всё",
    "все",
    "где",
    "для",
    "и",
    "как",
    "какие",
    "какой",
    "меня",
    "мне",
    "найди",
    "о",
    "об",
    "от",
    "по",
    "подготовь",
    "про",
    "что",
}
ARCHIVE_STATUSES = {"archive", "archived", "historical", "superseded"}
NON_SOURCE_PATH_PARTS = {
    ".venv",
    "__pycache__",
    ".git",
    "node_modules",
}
NON_SOURCE_PATH_PREFIXES = (
    "output/",
    "qaos-core/.venv/",
)
RELATIONSHIP_FIELDS = (
    "related",
    "depends_on",
    "available_to",
    "applies_to",
    "derived_from",
    "supersedes",
    "jira_keys",
    "projects",
    "meeting",
    "decision",
)


@dataclass(frozen=True)
class KnowledgeContextRequest:
    """Structured request from an external AI agent to QASkills."""

    user_goal: str
    query: str = ""
    jira_key: str = ""
    include: tuple[str, ...] = DEFAULT_INCLUDE
    limit: int = 5

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "KnowledgeContextRequest":
        include = data.get("include", DEFAULT_INCLUDE)

        if isinstance(include, str):
            include = tuple(item.strip() for item in include.split(",") if item.strip())

        return cls(
            user_goal=str(data.get("user_goal") or data.get("goal") or "").strip(),
            query=str(data.get("query") or "").strip(),
            jira_key=str(data.get("jira_key") or "").strip().upper(),
            include=tuple(include or DEFAULT_INCLUDE),
            limit=int(data.get("limit") or 5),
        )


class KnowledgeAPI:
    """
    Thin internal facade for exposing QASkills as a Knowledge Engine.

    The API does not understand natural language, plan work, reason, call an
    LLM, or compose final user answers. External agents such as Codex provide a
    structured request and receive structured knowledge.
    """

    def __init__(
        self,
        memory_service: MemoryService | None = None,
        jira_service: JiraService | None = None,
        skills_root: str | Path | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or load_settings()
        self.memory = memory_service or MemoryService(
            vault_path=self.settings.memory_vault_path,
            index_path=self.settings.document_index_path,
        )
        self.jira = jira_service or JiraService(
            credentials=JiraCredentials.from_settings(self.settings),
        )
        self.vault_path = self.memory.vault_path
        self.skills_root = (
            Path(skills_root).expanduser().resolve()
            if skills_root
            else self.vault_path / "QASkills" / "Skills"
        )

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search indexed knowledge metadata and return structured matches."""

        return [
            {
                "score": score,
                "reasons": reasons,
                "document": document.to_dict(),
            }
            for score, document, reasons in self.memory.search(
                query=query,
                limit=limit,
            )
        ]

    def read(self, path_or_name: str) -> dict[str, Any]:
        """Read one Markdown document by vault-relative path or document name."""

        try:
            document = self.memory.read_document_by_path(path_or_name)
        except FileNotFoundError:
            document = self.memory.read_document_by_name(path_or_name)

        return document.to_dict()

    def ingest(
        self,
        file_path: str | Path,
        target_folder: str = "QASkills/Memory/Inbox",
    ) -> dict[str, Any]:
        """Import a Markdown file into the configured Vault and refresh index."""

        source_path = Path(file_path).expanduser().resolve()

        if not source_path.is_file():
            raise FileNotFoundError(str(source_path))

        content = source_path.read_text(encoding="utf-8")
        title = self._title_from_markdown(content=content, fallback=source_path.stem)
        document = self.memory.write_document(
            title=title,
            content=content,
            folder=target_folder,
        )

        return document.to_dict()

    def list_skills(self) -> list[dict[str, Any]]:
        """Return metadata for QA Skills stored in the configured Vault."""

        if not self.skills_root.exists():
            return []

        return [
            self._skill_summary(path)
            for path in sorted(self.skills_root.glob("*/SKILL.md"))
        ]

    def show_skill(self, skill_name: str) -> dict[str, Any]:
        """Return one QA Skill with full source content."""

        normalized = self._normalize_key(skill_name)

        for path in sorted(self.skills_root.glob("*/SKILL.md")):
            summary = self._skill_summary(path)
            names = {
                self._normalize_key(path.parent.name),
                self._normalize_key(summary["name"]),
            }

            if normalized in names:
                return {
                    **summary,
                    "content": path.read_text(encoding="utf-8"),
                }

        raise FileNotFoundError(skill_name)

    def build_context(
        self,
        request: KnowledgeContextRequest | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build a structured Knowledge Pack for an external AI agent."""

        context_request = self._context_request(request=request, kwargs=kwargs)
        include = set(context_request.include)
        related_jira = None
        missing_information: list[str] = []
        evidence: list[dict[str, str]] = []
        important_context = {
            "facts": [],
            "open_questions": [],
            "source_limits": [],
        }

        if "jira" in include and context_request.jira_key:
            related_jira = self._jira_issue(context_request.jira_key)
            evidence.append(
                {
                    "type": "jira",
                    "source": "Jira",
                    "reference": context_request.jira_key,
                    "selection": "explicit",
                    "why_selected": "User or Codex provided jira_key.",
                }
            )

            if related_jira.get("available"):
                related_jira.setdefault(
                    "why_selected",
                    ["User or Codex provided jira_key."],
                )
                related_jira.setdefault("selection", "explicit")
                related_jira.setdefault("source", "Jira")
                important_context["facts"].append(
                    f"Jira issue {context_request.jira_key} was loaded."
                )
            else:
                related_jira.setdefault(
                    "why_selected",
                    ["Jira was requested through jira_key but source was unavailable."],
                )
                related_jira.setdefault("selection", "source_limit")
                related_jira.setdefault("source", "Jira")
                missing_information.append(str(related_jira.get("error")))
                important_context["source_limits"].append(
                    "Jira source was requested but unavailable."
                )
        elif "jira" in include:
            related_jira = {"available": False, "reason": "jira_key_not_provided"}

        query = self._knowledge_query(context_request, related_jira)
        expanded_query = self._expanded_query(query)
        entry_point = self._entry_point(
            request=context_request,
            query=query,
            expanded_query=expanded_query,
            related_jira=related_jira,
        )
        document_candidates = (
            self.search(
                query=expanded_query,
                limit=self._candidate_limit(context_request.limit),
            )
            if "knowledge" in include and query
            else []
        )
        relevant_documents, excluded_documents = self._select_knowledge(
            candidates=document_candidates,
            limit=context_request.limit,
            query=expanded_query,
        )

        if relevant_documents:
            important_context["facts"].append(
                f"Selected {len(relevant_documents)} relevant knowledge document(s)."
            )
            evidence.extend(
                {
                    "type": "document",
                    "source": "Obsidian Vault",
                    "reference": item["document"]["path"],
                    "selection": item.get("selection", "fallback_scoring"),
                    "authority": item.get("authority", "unknown"),
                    "why_selected": item.get("why_selected", [])[:3],
                }
                for item in relevant_documents
            )
        elif "knowledge" in include:
            missing_information.append("No relevant indexed documents were found.")

        if excluded_documents:
            important_context["source_limits"].append(
                f"Excluded {len(excluded_documents)} archived or superseded document(s)."
            )

        related_skills = (
            self._related_skills(
                context_request=context_request,
                query=expanded_query,
                documents=relevant_documents,
                related_jira=related_jira,
            )
            if "skills" in include
            else []
        )

        if related_skills:
            important_context["facts"].append(
                f"Matched {len(related_skills)} related QA Skill(s)."
            )
            evidence.extend(
                {
                    "type": "skill",
                    "source": "QASkills Skill Catalog",
                    "reference": item["path"],
                    "selection": item.get("selection", "explicit"),
                    "authority": item.get("authority", "unknown"),
                    "why_selected": item.get("why_selected", [])[:3],
                }
                for item in related_skills
            )
        elif "skills" in include:
            missing_information.append("No related QA Skills matched the goal.")

        rules = (
            self._rules(
                context_request=context_request,
                documents=relevant_documents,
                skills=related_skills,
            )
            if "rules" in include
            else []
        )

        if rules:
            evidence.extend(
                {
                    "type": "rule",
                    "source": "QASkills Rules",
                    "reference": item["path"],
                    "selection": item.get("selection", "explicit"),
                    "authority": item.get("authority", "unknown"),
                    "why_selected": item.get("why_selected", [])[:3],
                }
                for item in rules
            )

        known_risks = self._known_risks(
            request=context_request,
            query=expanded_query,
            documents=relevant_documents,
            skills=related_skills,
        )
        missing_details = self._missing_information_details(
            request=context_request,
            query=expanded_query,
            documents=relevant_documents,
            skills=related_skills,
        )
        missing_information.extend(item["message"] for item in missing_details)

        return {
            "schema_version": 1,
            "kind": "knowledge_pack",
            "user_goal": context_request.user_goal,
            "query": context_request.query,
            "effective_query": expanded_query,
            "entry_point": entry_point,
            "related_jira": related_jira,
            "relevant_knowledge": relevant_documents,
            "relevant_documents": relevant_documents,
            "excluded_documents": excluded_documents,
            "related_qa_skills": related_skills,
            "rules": rules,
            "important_context": important_context,
            "known_risks": known_risks,
            "evidence": evidence,
            "confidence": self._confidence(
                related_jira=related_jira,
                documents=relevant_documents,
                skills=related_skills,
                excluded_documents=excluded_documents,
            ),
            "missing_information_details": missing_details,
            "missing_information": [
                item
                for item in dict.fromkeys(missing_information)
                if item
            ],
        }

    def _context_request(
        self,
        request: KnowledgeContextRequest | dict[str, Any] | None,
        kwargs: dict[str, Any],
    ) -> KnowledgeContextRequest:
        if isinstance(request, KnowledgeContextRequest):
            return request

        if isinstance(request, dict):
            data = {**request, **kwargs}
            return KnowledgeContextRequest.from_mapping(data)

        return KnowledgeContextRequest.from_mapping(kwargs)

    def _jira_issue(self, jira_key: str) -> dict[str, Any]:
        artifact = self.jira.execute(
            "jira.get_issue",
            self._service_request(
                user_text=jira_key,
                payload={"issue_key": jira_key},
            ),
        )

        if artifact.name == "jira_error":
            return {
                "available": False,
                "key": jira_key,
                "error": artifact.content,
            }

        issue = dict(artifact.metadata.get("issue", {}))
        comments = issue.get("comments", [])
        issue["important_comments"] = [
            {
                "id": str(comment.get("id") or ""),
                "author": str(comment.get("author") or ""),
                "created": str(comment.get("created") or ""),
                "body": self._compact_text(comment.get("body", "")),
            }
            for comment in comments[-3:]
        ]

        return {
            "available": True,
            **issue,
        }

    def _service_request(
        self,
        user_text: str,
        payload: dict[str, Any] | None = None,
    ) -> ServiceRequest:
        intent = UserIntent(
            name="knowledge_api",
            raw_text=user_text,
            expected_output="knowledge_pack",
            confidence=1.0,
        )
        plan = TaskPlan(
            goal=user_text,
            intent=intent,
            steps=[],
            response_contract="knowledge_pack",
            context_budget=0,
        )

        return ServiceRequest(
            user_text=user_text,
            intent=intent,
            plan=plan,
            payload=payload or {},
        )

    def _knowledge_query(
        self,
        request: KnowledgeContextRequest,
        related_jira: dict[str, Any] | None,
    ) -> str:
        parts = [
            request.query,
            request.jira_key,
        ]

        if related_jira and related_jira.get("available"):
            parts.append(str(related_jira.get("summary") or ""))

        query = " ".join(part for part in parts if part).strip()

        return query or request.user_goal

    def _entry_point(
        self,
        request: KnowledgeContextRequest,
        query: str,
        expanded_query: str,
        related_jira: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if request.jira_key:
            entry_type = "jira_issue"
            value = request.jira_key
            why_selected = ["User or Codex provided an explicit Jira key."]
            selection = "explicit"
        elif request.query:
            entry_type = "query"
            value = request.query
            why_selected = ["Codex provided an explicit knowledge query."]
            selection = "explicit"
        else:
            entry_type = "user_goal"
            value = request.user_goal
            why_selected = ["User goal is the only entry point."]
            selection = "explicit"

        if related_jira and related_jira.get("available"):
            why_selected.append("Jira summary was added to the effective query.")

        if expanded_query != query:
            why_selected.append(
                "Effective query was expanded with deterministic aliases for entry-point discovery."
            )

        return {
            "type": entry_type,
            "value": value,
            "query": query,
            "effective_query": expanded_query,
            "selection": selection,
            "why_selected": why_selected,
        }

    def _expanded_query(self, query: str) -> str:
        tokens = self._query_tokens(query)
        parts = [query]

        for token in tokens:
            parts.append(token)
            parts.extend(QUERY_EXPANSIONS.get(token, []))

        return " ".join(dict.fromkeys(part for part in parts if part)).strip()

    def _query_tokens(self, query: str) -> list[str]:
        raw_tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9_#/-]+", query.lower())
        tokens = []

        for token in raw_tokens:
            normalized = token.strip().lstrip("#")

            if not normalized or normalized in FALLBACK_STOP_WORDS:
                continue

            tokens.append(normalized)

        return list(dict.fromkeys(tokens))

    def _candidate_limit(self, limit: int) -> int:
        return max(limit, min(50, limit * 3 + 5))

    def _select_knowledge(
        self,
        candidates: list[dict[str, Any]],
        limit: int,
        query: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        enriched = [
            self._enriched_knowledge_item(item, query=query)
            for item in candidates
        ]
        current = [
            item
            for item in enriched
            if not self._is_archived_knowledge(item)
            and not self._is_non_source_document(item)
        ]
        archived = [
            item
            for item in enriched
            if self._is_archived_knowledge(item)
        ]
        non_source = [
            item
            for item in enriched
            if not self._is_archived_knowledge(item)
            and self._is_non_source_document(item)
        ]

        if current:
            selected = sorted(current, key=self._knowledge_priority)[:limit]
            excluded = [*archived, *non_source][:10]
        else:
            selected = enriched[:limit]
            excluded = []

            for item in selected:
                if self._is_archived_knowledge(item):
                    item["why_selected"].append(
                        "No current knowledge candidate was found; archived source kept as a source limit."
                    )
                elif self._is_non_source_document(item):
                    item["why_selected"].append(
                        "No source-of-truth knowledge candidate was found; generated or dependency source kept as a source limit."
                    )

        for item in excluded:
            item["selection"] = "excluded"
            if self._is_archived_knowledge(item):
                item["why_excluded"] = [
                    "Current knowledge candidate exists, so archived or superseded source was not selected."
                ]
            else:
                item["why_excluded"] = [
                    "Source-of-truth knowledge candidate exists, so generated or dependency source was not selected."
                ]

        return selected, excluded

    def _enriched_knowledge_item(
        self,
        item: dict[str, Any],
        query: str,
    ) -> dict[str, Any]:
        document = item["document"]
        details = self._document_details(document["path"])
        reasons = list(item.get("reasons", []))
        why_selected = [
            (
                "Matched indexed metadata "
                f"({', '.join(reasons)}) with score {item.get('score', 0)}."
            )
        ]

        if details["status"] != "unknown":
            why_selected.append(f"Document status is {details['status']}.")

        if details["authority"] != "unknown":
            why_selected.append(f"Document authority is {details['authority']}.")

        if details["relationships"]["available_to"]:
            why_selected.append("Document declares explicit Available to relationships.")

        return {
            **item,
            "authority": details["authority"],
            "status": details["status"],
            "document_type": details["document_type"],
            "source": "Obsidian Vault",
            "selection": "fallback_scoring",
            "why_selected": why_selected,
            "relationships": details["relationships"],
            "wiki_links": details["wiki_links"],
            "source_confidence": details["confidence"],
            "query": query,
        }

    def _related_skills(
        self,
        context_request: KnowledgeContextRequest,
        query: str,
        documents: list[dict[str, Any]],
        related_jira: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        available = self.list_skills()
        skills_by_key: dict[str, dict[str, Any]] = {}

        for skill in available:
            for key in self._skill_keys(skill):
                skills_by_key[key] = skill

        entries: dict[str, dict[str, Any]] = {}

        def add_skill(
            skill: dict[str, Any] | None,
            score: int,
            selection: str,
            reason: str,
            matched_knowledge: dict[str, Any] | None = None,
        ) -> None:
            if not skill:
                return

            key = self._normalize_key(skill["folder"])
            entry = entries.setdefault(
                key,
                {
                    **skill,
                    "score": 0,
                    "selection": "fallback_scoring",
                    "selection_signals": [],
                    "why_selected": [],
                    "matched_knowledge": [],
                    "authority": "skill_catalog",
                    "source": "QASkills Skill Catalog",
                },
            )
            entry["score"] += score

            if reason not in entry["why_selected"]:
                entry["why_selected"].append(reason)

            if selection not in entry["selection_signals"]:
                entry["selection_signals"].append(selection)

            if selection != "fallback_scoring":
                entry["selection"] = "explicit"

            if matched_knowledge:
                reference = {
                    "path": matched_knowledge["document"]["path"],
                    "title": matched_knowledge["document"]["title"],
                    "authority": matched_knowledge.get("authority", "unknown"),
                    "status": matched_knowledge.get("status", "unknown"),
                }

                if reference not in entry["matched_knowledge"]:
                    entry["matched_knowledge"].append(reference)

                if reference["authority"] != "unknown":
                    entry["authority"] = reference["authority"]

        for name in GOAL_SKILLS.get(context_request.user_goal, ()):
            add_skill(
                skills_by_key.get(self._normalize_key(name)),
                score=70,
                selection="structured_goal",
                reason=f"Structured goal maps to {name}.",
            )

        for document in documents:
            for name in document["relationships"].get("available_to", []):
                skill = skills_by_key.get(self._normalize_key(name))
                add_skill(
                    skill,
                    score=120,
                    selection="explicit_available_to",
                    reason=(
                        f"{document['document']['path']} declares Available to: "
                        f"{skill['folder'] if skill else name}."
                    ),
                    matched_knowledge=document,
                )

        for skill in available:
            for document in documents:
                if self._skill_depends_on_document(skill, document):
                    add_skill(
                        skill,
                        score=100,
                        selection="explicit_dependency",
                        reason=(
                            f"{skill['path']} has a Knowledge Dependency on "
                            f"{document['document']['path']}."
                        ),
                        matched_knowledge=document,
                    )

        if not entries:
            fallback_text = " ".join(
                [
                    context_request.user_goal,
                    context_request.query,
                    query,
                    str(related_jira.get("summary", ""))
                    if related_jira and related_jira.get("available")
                    else "",
                ]
            )
            tokens = self._query_tokens(self._expanded_query(fallback_text))

            for skill in available:
                search_text = self._skill_search_text(skill)
                matched_terms = [
                    token
                    for token in tokens
                    if token and token in search_text
                ]

                if matched_terms:
                    add_skill(
                        skill,
                        score=20 + len(matched_terms) * 5,
                        selection="fallback_scoring",
                        reason=(
                            "Fallback matched skill metadata terms: "
                            f"{', '.join(matched_terms[:8])}."
                        ),
                    )

        return sorted(
            entries.values(),
            key=lambda item: (
                item["selection"] == "fallback_scoring",
                -item["score"],
                item["folder"].lower(),
            ),
        )[:6]

    def _rules(
        self,
        context_request: KnowledgeContextRequest,
        documents: list[dict[str, Any]],
        skills: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rules = []

        for rule in DEFAULT_RULES:
            path = self.vault_path / rule["path"]
            details = self._document_details(rule["path"])
            rules.append(
                {
                    **rule,
                    "available": path.exists(),
                    "authority": details["authority"],
                    "status": details["status"],
                    "source": "QASkills Rules",
                    "selection": "explicit_rule",
                    "why_selected": self._rule_reasons(
                        rule_id=rule["id"],
                        context_request=context_request,
                        documents=documents,
                        skills=skills,
                    ),
                }
            )

        return rules

    def _confidence(
        self,
        related_jira: dict[str, Any] | None,
        documents: list[dict[str, Any]],
        skills: list[dict[str, Any]],
        excluded_documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        signals = []

        if related_jira and related_jira.get("available"):
            signals.append("jira_issue_found")

        if documents:
            signals.append("documents_found")

        if any(item.get("status") == "current" for item in documents):
            signals.append("current_knowledge_found")

        if any(item.get("authority") != "unknown" for item in documents):
            signals.append("authority_found")

        if skills:
            signals.append("skills_found")

        if any(item.get("selection") == "explicit" for item in skills):
            signals.append("explicit_relationships_found")

        if excluded_documents:
            signals.append("archived_sources_excluded")

        has_current_authority = (
            "current_knowledge_found" in signals
            and "authority_found" in signals
        )
        has_explicit_skills = "explicit_relationships_found" in signals

        if related_jira and related_jira.get("available") and has_current_authority and has_explicit_skills:
            level = "high"
        elif has_current_authority and has_explicit_skills:
            level = "medium"
        elif len(signals) >= 2:
            level = "medium"
        else:
            level = "low"

        return {
            "level": level,
            "basis": signals or ["no_sources_found"],
            "explanation": self._confidence_explanation(
                level=level,
                signals=signals,
            ),
        }

    def _document_details(self, relative_path: str) -> dict[str, Any]:
        default = {
            "authority": "unknown",
            "status": "unknown",
            "document_type": "unknown",
            "confidence": "unknown",
            "relationships": {
                field: []
                for field in RELATIONSHIP_FIELDS
            },
            "wiki_links": [],
        }

        try:
            document = self.memory.read_document_by_path(relative_path)
        except FileNotFoundError:
            return default

        text = document.content
        frontmatter = self._frontmatter_fields(text)
        relationships = {
            field: self._frontmatter_list(frontmatter, field)
            for field in RELATIONSHIP_FIELDS
        }
        available_to = self._body_field_list(text, "Available to")

        if available_to:
            relationships["available_to"] = list(
                dict.fromkeys([*relationships["available_to"], *available_to])
            )

        return {
            "authority": (
                self._frontmatter_text(frontmatter, "authority")
                or self._body_field(text, "Authority")
                or "unknown"
            ),
            "status": (
                self._frontmatter_text(frontmatter, "status")
                or self._body_field(text, "Status")
                or "unknown"
            ).lower(),
            "document_type": (
                self._frontmatter_text(frontmatter, "type")
                or self._body_field(text, "Type")
                or "unknown"
            ),
            "confidence": (
                self._frontmatter_text(frontmatter, "confidence")
                or self._body_field(text, "Confidence")
                or "unknown"
            ),
            "relationships": relationships,
            "wiki_links": self._wiki_links(text),
        }

    def _is_archived_knowledge(self, item: dict[str, Any]) -> bool:
        document = item["document"]
        status = self._normalize_key(str(item.get("status", "")))
        tags = {
            self._normalize_key(tag)
            for tag in document.get("tags", [])
        }
        folder = str(document.get("folder", "")).lower()
        title = str(document.get("title", "")).lower()

        return (
            status in ARCHIVE_STATUSES
            or bool(tags.intersection(ARCHIVE_STATUSES))
            or folder.startswith("archive")
            or "superseded" in folder
            or title.startswith("archived")
        )

    def _is_non_source_document(self, item: dict[str, Any]) -> bool:
        path = item["document"]["path"].replace("\\", "/")
        normalized = path.lower()
        parts = {part.lower() for part in normalized.split("/")}

        return bool(parts.intersection(NON_SOURCE_PATH_PARTS)) or any(
            normalized.startswith(prefix) for prefix in NON_SOURCE_PATH_PREFIXES
        )

    def _knowledge_priority(self, item: dict[str, Any]) -> tuple[int, int, int, int]:
        status = self._normalize_key(str(item.get("status", "")))
        relationships = item.get("relationships", {})
        has_relationships = any(
            relationships.get(field) for field in RELATIONSHIP_FIELDS
        )
        has_authority = item.get("authority", "unknown") != "unknown"
        is_current = status in {"current", "approved", "active"}

        return (
            0 if is_current else 1,
            0 if has_authority else 1,
            0 if has_relationships else 1,
            -int(item.get("score", 0)),
        )

    def _skill_keys(self, skill: dict[str, Any]) -> set[str]:
        return {
            self._normalize_key(skill["folder"]),
            self._normalize_key(skill["name"]),
        }

    def _skill_depends_on_document(
        self,
        skill: dict[str, Any],
        document: dict[str, Any],
    ) -> bool:
        document_keys = self._knowledge_reference_keys(document)

        for items in skill.get("knowledge_dependencies", {}).values():
            for dependency in items:
                normalized_dependency = self._normalize_reference(dependency)

                if any(key and key in normalized_dependency for key in document_keys):
                    return True

        return False

    def _knowledge_reference_keys(self, document: dict[str, Any]) -> set[str]:
        metadata = document["document"]
        path = str(metadata.get("path", ""))
        title = str(metadata.get("title", ""))
        stem = Path(path).with_suffix("").as_posix()

        return {
            self._normalize_reference(path),
            self._normalize_reference(stem),
            self._normalize_reference(title),
            self._normalize_key(Path(path).stem),
        }

    def _skill_search_text(self, skill: dict[str, Any]) -> str:
        dependency_text = " ".join(
            item
            for items in skill.get("knowledge_dependencies", {}).values()
            for item in items
        )

        return " ".join(
            [
                skill.get("name", ""),
                skill.get("folder", ""),
                skill.get("description", ""),
                dependency_text,
            ]
        ).lower()

    def _rule_reasons(
        self,
        rule_id: str,
        context_request: KnowledgeContextRequest,
        documents: list[dict[str, Any]],
        skills: list[dict[str, Any]],
    ) -> list[str]:
        if rule_id == "evidence_first":
            return [
                "Evidence Pack requires every selected item to be grounded in a source.",
            ]

        if rule_id == "human_controlled_knowledge":
            return [
                "Vault knowledge remains human-controlled; runtime only reads relationships.",
            ]

        if rule_id == "safe_external_actions":
            if context_request.jira_key:
                return [
                    "Jira context may be read, but irreversible external actions still require approval.",
                ]

            return [
                "Included as a project safety rule for any follow-up external action.",
            ]

        if documents or skills:
            return ["Selected as a default QASkills rule."]

        return ["Included because rules were requested in the Knowledge Pack."]

    def _known_risks(
        self,
        request: KnowledgeContextRequest,
        query: str,
        documents: list[dict[str, Any]],
        skills: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        risks = []
        tokens = set(self._query_tokens(query))
        auth_context = self._has_auth_context(tokens=tokens, documents=documents)
        api_context = (
            "api" in tokens
            or "oauth" in tokens
            or any(
                "API Contract" in item["document"]["title"]
                for item in documents
            )
        )
        first_auth_document = self._first_document_matching(
            documents,
            terms=("Authentication", "Session", "Authorization"),
        )
        risk_skill_names = {
            self._normalize_key(skill.get("folder", ""))
            for skill in skills
        }

        if auth_context:
            risks.append(
                {
                    "title": "Authentication and session behavior can break access control and account state.",
                    "source": self._risk_source(first_auth_document),
                    "authority": self._risk_authority(first_auth_document),
                    "selection": "inferred_from_knowledge",
                    "why_selected": [
                        "Authentication/session knowledge was selected.",
                        "Selected knowledge covers credentials, protected resources, session lifetime, and recovery.",
                    ],
                }
            )

        if api_context:
            risks.append(
                {
                    "title": "API authentication can fail at status-code, header, token, or permission boundaries.",
                    "source": self._risk_source(
                        self._first_document_matching(
                            documents,
                            terms=("API Contract", "HTTP Response", "REST"),
                        )
                    ),
                    "authority": self._risk_authority(first_auth_document),
                    "selection": "inferred_from_knowledge",
                    "why_selected": [
                        "API or OAuth terms were present in the entry point.",
                        "API-related knowledge was selected or requested by the effective query.",
                    ],
                }
            )

        if auth_context and "riskanalysis" in risk_skill_names:
            risks.append(
                {
                    "title": "Auth work needs explicit risk triage before test scope is treated as sufficient.",
                    "source": "QASkills Skill Catalog",
                    "authority": "skill_catalog",
                    "selection": "explicit_skill_relationship",
                    "why_selected": [
                        "RiskAnalysis was selected through explicit knowledge relationships.",
                    ],
                }
            )

        return risks

    def _missing_information_details(
        self,
        request: KnowledgeContextRequest,
        query: str,
        documents: list[dict[str, Any]],
        skills: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        details = []
        tokens = set(self._query_tokens(query))

        if self._has_auth_context(tokens=tokens, documents=documents):
            source = self._risk_source(
                self._first_document_matching(
                    documents,
                    terms=("Authentication", "Session", "Authorization"),
                )
            )
            details.extend(
                [
                    {
                        "message": "Missing authentication contract: valid and invalid credentials, roles, lockout, MFA, recovery, and exact error policy.",
                        "source": source,
                        "selection": "inferred_from_knowledge",
                        "why_selected": [
                            "Authentication knowledge requires product-specific contract details.",
                        ],
                    },
                    {
                        "message": "Missing session policy: timeout, remember-me behavior, concurrent sessions, logout, revocation, and browser storage expectations.",
                        "source": source,
                        "selection": "inferred_from_knowledge",
                        "why_selected": [
                            "Selected session knowledge needs product policy to become executable checks.",
                        ],
                    },
                    {
                        "message": "Missing authorization matrix: protected resources, roles, ownership boundaries, and expected 401/403 behavior.",
                        "source": source,
                        "selection": "inferred_from_knowledge",
                        "why_selected": [
                            "Authorization risk cannot be closed by login-screen evidence alone.",
                        ],
                    },
                ]
            )

        if "oauth" in tokens:
            details.append(
                {
                    "message": "Missing OAuth contract: provider, scopes, redirect/callback behavior, token lifetime, refresh policy, and error handling.",
                    "source": "Entry Point",
                    "selection": "fallback_domain_gap",
                    "why_selected": [
                        "OAuth was present in the entry point.",
                    ],
                }
            )

        if not skills:
            details.append(
                {
                    "message": "No QA Skill could be proven from explicit Vault relationships or fallback metadata.",
                    "source": "QASkills Skill Catalog",
                    "selection": "source_limit",
                    "why_selected": [
                        "Skill selection returned no candidates.",
                    ],
                }
            )

        return details

    def _confidence_explanation(self, level: str, signals: list[str]) -> str:
        if level == "high":
            return (
                "High confidence because Jira, current authoritative knowledge, "
                "and explicit skill relationships were found."
            )

        if level == "medium":
            return (
                "Medium confidence because useful sources were found, but at least "
                "one of Jira, authority, or explicit relationships is incomplete."
            )

        return "Low confidence because the pack has weak or incomplete evidence."

    def _has_auth_context(
        self,
        tokens: set[str],
        documents: list[dict[str, Any]],
    ) -> bool:
        auth_terms = {
            "auth",
            "authentication",
            "authorization",
            "oauth",
            "login",
            "session",
            "token",
            "cookie",
            "password",
            "авторизация",
            "авторизацию",
            "авторизации",
        }

        return bool(tokens.intersection(auth_terms)) or any(
            self._normalize_key(item["document"]["title"])
            in {
                "webauthenticationandsessionheuristics",
                "глава07webбраузерdevtoolsавторизацияиссессии",
            }
            or "authentication" in item["document"]["title"].lower()
            or "session" in item["document"]["title"].lower()
            or "authorization" in item["document"]["title"].lower()
            for item in documents
        )

    def _first_document_matching(
        self,
        documents: list[dict[str, Any]],
        terms: tuple[str, ...],
    ) -> dict[str, Any] | None:
        normalized_terms = tuple(term.lower() for term in terms)

        for document in documents:
            title = str(document["document"].get("title", "")).lower()
            path = str(document["document"].get("path", "")).lower()

            if any(term.lower() in title or term.lower() in path for term in normalized_terms):
                return document

        return documents[0] if documents else None

    def _risk_source(self, document: dict[str, Any] | None) -> str:
        if not document:
            return "Entry Point"

        return document["document"]["path"]

    def _risk_authority(self, document: dict[str, Any] | None) -> str:
        if not document:
            return "unknown"

        return str(document.get("authority") or "unknown")

    def _frontmatter_fields(self, text: str) -> dict[str, list[str]]:
        lines = text.splitlines()

        if not lines or lines[0].strip() != "---":
            return {}

        fields: dict[str, list[str]] = {}
        current = ""

        for line in lines[1:]:
            stripped = line.strip()

            if stripped == "---":
                break

            if stripped.startswith("- ") and current:
                fields.setdefault(current, []).append(
                    self._clean_relationship_target(stripped[2:])
                )
                continue

            if ":" not in stripped:
                continue

            key, value = stripped.split(":", 1)
            current = key.strip()
            values = self._list_from_value(value.strip())

            if values:
                fields.setdefault(current, []).extend(values)
            else:
                fields.setdefault(current, [])

        return {
            key: list(dict.fromkeys(value for value in values if value))
            for key, values in fields.items()
        }

    def _frontmatter_text(
        self,
        frontmatter: dict[str, list[str]],
        key: str,
    ) -> str:
        values = frontmatter.get(key, [])

        return values[0] if values else ""

    def _frontmatter_list(
        self,
        frontmatter: dict[str, list[str]],
        key: str,
    ) -> list[str]:
        return list(frontmatter.get(key, []))

    def _body_field(self, text: str, key: str) -> str:
        prefix = f"{key.lower()}:"

        for line in text.splitlines():
            stripped = line.strip()

            if stripped.lower().startswith(prefix):
                return stripped.split(":", 1)[1].strip()

        return ""

    def _body_field_list(self, text: str, key: str) -> list[str]:
        return self._list_from_value(self._body_field(text, key))

    def _list_from_value(self, value: str) -> list[str]:
        cleaned = value.strip()

        if not cleaned:
            return []

        if cleaned.startswith("[") and cleaned.endswith("]"):
            cleaned = cleaned[1:-1]

        return [
            self._clean_relationship_target(item)
            for item in cleaned.split(",")
            if self._clean_relationship_target(item)
        ]

    def _wiki_links(self, text: str) -> list[str]:
        links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)

        return list(dict.fromkeys(self._clean_relationship_target(link) for link in links))

    def _clean_relationship_target(self, value: str) -> str:
        cleaned = value.strip().strip('"').strip("'").strip()
        cleaned = cleaned.strip("`")

        if cleaned.startswith("[[") and cleaned.endswith("]]"):
            cleaned = cleaned[2:-2]

        if "|" in cleaned:
            cleaned = cleaned.split("|", 1)[0].strip()

        return cleaned

    def _normalize_reference(self, value: str) -> str:
        cleaned = self._clean_relationship_target(value)

        if cleaned.endswith(".md"):
            cleaned = cleaned[:-3]

        return self._normalize_key(cleaned)

    def _skill_summary(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        frontmatter = self._frontmatter(text)
        dependencies = self._knowledge_dependencies(text)

        return {
            "name": frontmatter.get("name") or path.parent.name,
            "folder": path.parent.name,
            "path": str(path.relative_to(self.vault_path)),
            "description": frontmatter.get("description", ""),
            "knowledge_dependencies": dependencies,
        }

    def _frontmatter(self, text: str) -> dict[str, str]:
        lines = text.splitlines()

        if not lines or lines[0].strip() != "---":
            return {}

        values: dict[str, str] = {}

        for line in lines[1:]:
            if line.strip() == "---":
                break

            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")

        return values

    def _knowledge_dependencies(self, text: str) -> dict[str, list[str]]:
        dependencies: dict[str, list[str]] = {}
        in_section = False
        current = ""

        for line in text.splitlines():
            stripped = line.strip()

            if stripped == "## Knowledge Dependencies":
                in_section = True
                continue

            if in_section and stripped.startswith("## "):
                break

            if not in_section:
                continue

            if stripped.endswith(":"):
                current = stripped[:-1]
                dependencies.setdefault(current, [])
                continue

            if current and stripped.startswith("- "):
                dependencies.setdefault(current, []).append(stripped[2:].strip())

        return dependencies

    def _title_from_markdown(self, content: str, fallback: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()

            if stripped.startswith("# "):
                return stripped[2:].strip()

        return fallback

    def _compact_text(self, text: object, limit: int = 500) -> str:
        compact = " ".join(str(text or "").split())

        if len(compact) <= limit:
            return compact

        return f"{compact[:limit].rstrip()}..."

    def _normalize_key(self, value: str) -> str:
        return "".join(character.lower() for character in value if character.isalnum())
