from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IndexedDocument:
    """Metadata-only representation of a Markdown document."""

    title: str
    path: str
    folder: str
    modified_at: str
    size: int
    headings: dict[str, list[str]] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "path": self.path,
            "folder": self.folder,
            "modified_at": self.modified_at,
            "size": self.size,
            "headings": self.headings,
            "aliases": self.aliases,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexedDocument":
        return cls(
            title=data["title"],
            path=data["path"],
            folder=data["folder"],
            modified_at=data["modified_at"],
            size=data["size"],
            headings={
                "h1": list(data.get("headings", {}).get("h1", [])),
                "h2": list(data.get("headings", {}).get("h2", [])),
                "h3": list(data.get("headings", {}).get("h3", [])),
            },
            aliases=list(data.get("aliases", [])),
            tags=list(data.get("tags", [])),
        )


@dataclass(frozen=True)
class DocumentIndex:
    """Persisted metadata index for one Obsidian vault."""

    vault_path: str
    built_at: str
    documents: list[IndexedDocument]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "vault_path": self.vault_path,
            "built_at": self.built_at,
            "documents": [
                document.to_dict()
                for document in self.documents
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentIndex":
        return cls(
            vault_path=data["vault_path"],
            built_at=data["built_at"],
            documents=[
                IndexedDocument.from_dict(document)
                for document in data.get("documents", [])
            ],
        )
