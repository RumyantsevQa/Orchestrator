from pathlib import Path

from app.core.artifacts import Artifact, PipelineTrace
from app.services.base import BaseService, ServiceRequest


class SkillService(BaseService):
    """Rule-based service for QA skill guidance."""

    name = "Skill Service"
    capabilities = {
        "skill.daily_preparation": "Prepare daily QA briefing guidance.",
        "skill.analyze_feature": "Apply feature analysis QA guidance.",
        "skill.bug_report": "Apply bug report QA communication guidance.",
        "skill.analyze_meeting": "Apply meeting analysis QA guidance.",
    }

    skill_references = {
        "skill.analyze_feature": ("Analyze Feature", "AnalyzeFeature"),
        "skill.bug_report": ("Bug Report", "QACommunication"),
        "skill.analyze_meeting": ("Analyze Meeting", "AnalyzeMeeting"),
    }

    def __init__(self, vault_path: str | None = None):
        self.skills_root = (
            Path(vault_path).expanduser().resolve() / "QASkills" / "Skills"
            if vault_path
            else None
        )

    def execute(
        self,
        capability: str,
        request: ServiceRequest,
        trace: PipelineTrace | None = None,
    ) -> Artifact:
        if trace:
            trace.add(self.name, f"Executed capability {capability}")

        if capability == "skill.daily_preparation":
            return self._daily_preparation(request)

        if capability in self.skill_references:
            return self._referenced_skill_guidance(capability, request)

        raise ValueError(f"Unsupported skill capability: {capability}")

    def _daily_preparation(self, request: ServiceRequest) -> Artifact:
        recent_titles = []

        for artifact in request.artifacts:
            if artifact.name not in {"memory_recent_documents", "memory_documents"}:
                continue

            for document in artifact.metadata.get("documents", [])[:5]:
                recent_titles.append(f"- {document['title']} ({document['path']})")

        recent_section = (
            "\n".join(recent_titles)
            if recent_titles
            else "- No local documents were available for daily preparation."
        )

        return Artifact(
            name="skill_guidance",
            source=self.name,
            content=(
                "Daily Preparation Skill:\n"
                "1. Review the latest project memory updates.\n"
                "2. Identify blockers, risks, and open questions.\n"
                "3. Prepare a short status for the team.\n\n"
                f"Local context to review:\n{recent_section}"
            ),
            metadata={"capability": "skill.daily_preparation", "mode": "rule_based"},
        )

    def _referenced_skill_guidance(
        self,
        capability: str,
        request: ServiceRequest,
    ) -> Artifact:
        skill_name, folder = self.skill_references[capability]
        skill_path = (
            self.skills_root / folder / "SKILL.md"
            if self.skills_root
            else None
        )
        summary = self._skill_summary(skill_path)
        evidence = self._artifact_evidence(request)

        return Artifact(
            name="skill_guidance",
            source=self.name,
            content=(
                f"{skill_name} Skill:\n"
                f"{summary}\n\n"
                "Evidence to use:\n"
                f"{evidence}"
            ),
            metadata={
                "capability": capability,
                "mode": "skill_reference",
                "skill_path": str(skill_path) if skill_path else "",
                "available": bool(skill_path and skill_path.exists()),
            },
        )

    def _skill_summary(self, skill_path: Path | None) -> str:
        if not skill_path or not skill_path.exists():
            return "Use the standard QA workflow for this task."

        text = skill_path.read_text(encoding="utf-8")

        for line in text.splitlines():
            stripped = line.strip()

            if stripped.startswith("description:"):
                return stripped[len("description:") :].strip()

        return f"Use guidance from {skill_path.name}."

    def _artifact_evidence(self, request: ServiceRequest) -> str:
        lines = []

        for artifact in request.artifacts:
            first_line = artifact.content.splitlines()[0] if artifact.content else ""
            lines.append(f"- {artifact.source}: {first_line}")

        return "\n".join(lines) if lines else "- No prior artifacts were produced."
