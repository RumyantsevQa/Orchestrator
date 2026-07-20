from pathlib import Path


class ContextBuilder:
    """
    Загружает знания для выбранного Skill.
    """

    def __init__(self):
        self.knowledge_path = Path("knowledge")

    def build(self, skill: str) -> str:
        file_path = self.knowledge_path / f"{skill}.md"

        if not file_path.exists():
            return ""

        return file_path.read_text(encoding="utf-8")