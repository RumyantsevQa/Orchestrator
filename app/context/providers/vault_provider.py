from pathlib import Path

from .base import ContextProvider


class VaultProvider(ContextProvider):

    def __init__(self, vault_path: str):
        self.vault = Path(vault_path)

    def list_notes(self) -> list[str]:

        notes = []

        for file in self.vault.rglob("*.md"):
            notes.append(str(file.relative_to(self.vault)))

        return sorted(notes)

    def read_note(self, path: str) -> str:

        file = self.vault / path

        if not file.exists():
            return ""

        return file.read_text(encoding="utf-8")

    def get_context(self) -> str:
        return self.read_note("PROJECT_RULES.md")