import json
from datetime import datetime
from pathlib import Path

from app.index.models import DocumentIndex, IndexedDocument


class IndexManager:
    """Builds, saves, loads, and serves a metadata-only vault document index."""

    def __init__(self, vault_path: str, index_path: str):
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.index_path = Path(index_path).expanduser()

        if not self.index_path.is_absolute():
            self.index_path = Path.cwd() / self.index_path

        self._index: DocumentIndex | None = None

    def ensure_indexed(self) -> DocumentIndex:
        """Return the loaded index, building it once when no saved index exists."""

        if self._index:
            return self._index

        if self.index_path.exists():
            self._index = self.load()

            if self._index.vault_path != str(self.vault_path):
                return self.rebuild()

            return self._index

        return self.rebuild()

    def rebuild(self) -> DocumentIndex:
        """Scan the vault and persist a fresh metadata index."""

        documents = [
            self._index_document(path)
            for path in self._markdown_files()
        ]
        index = DocumentIndex(
            vault_path=str(self.vault_path),
            built_at=datetime.now().isoformat(timespec="seconds"),
            documents=sorted(documents, key=lambda document: document.path.lower()),
        )

        self.save(index)
        self._index = index

        return index

    def load(self) -> DocumentIndex:
        """Load the saved document index from disk."""

        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        return DocumentIndex.from_dict(data)

    def save(self, index: DocumentIndex) -> None:
        """Persist the document index as JSON metadata."""

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(index.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def documents(self) -> list[IndexedDocument]:
        """Return indexed document metadata without scanning the vault."""

        return list(self.ensure_indexed().documents)

    def document_by_path(self, path: str) -> IndexedDocument | None:
        """Return indexed metadata by vault-relative path."""

        normalized = path.strip().lower()

        for document in self.documents():
            if document.path.lower() == normalized:
                return document

        return None

    def documents_by_name(self, name: str) -> list[IndexedDocument]:
        """Return indexed metadata whose title, filename, or alias matches name."""

        normalized = self._normalize_name(name)

        return [
            document
            for document in self.documents()
            if normalized in self._document_names(document)
        ]

    def recent_documents(self, limit: int = 10) -> list[IndexedDocument]:
        """Return recently modified documents using saved metadata."""

        return sorted(
            self.documents(),
            key=lambda document: document.modified_at,
            reverse=True,
        )[:limit]

    def documents_in_projects(self, project_name: str | None = None) -> list[IndexedDocument]:
        """Return project documents from indexed folder metadata."""

        documents = [
            document
            for document in self.documents()
            if "Projects" in Path(document.path).parts
        ]

        if not project_name:
            return documents

        normalized = project_name.strip().lower()

        return [
            document
            for document in documents
            if normalized in document.title.lower()
            or normalized in document.path.lower()
            or normalized in [alias.lower() for alias in document.aliases]
        ]

    def documents_with_tag(self, tag: str) -> list[IndexedDocument]:
        """Return documents whose indexed frontmatter tags include tag."""

        normalized = tag.strip().lstrip("#").lower()

        return [
            document
            for document in self.documents()
            if normalized in [item.lower().lstrip("#") for item in document.tags]
        ]

    def documents_with_heading(self, heading: str) -> list[IndexedDocument]:
        """Return documents whose indexed H1/H2/H3 headings include heading text."""

        normalized = heading.strip().lower()

        return [
            document
            for document in self.documents()
            if any(
                normalized in title.lower()
                for titles in document.headings.values()
                for title in titles
            )
        ]

    def vault_structure(self) -> dict[str, int]:
        """Return folder-level Markdown document counts from saved metadata."""

        structure: dict[str, int] = {}

        for document in self.documents():
            folder = document.folder or "."
            structure[folder] = structure.get(folder, 0) + 1

        return dict(sorted(structure.items(), key=lambda item: item[0].lower()))

    def _markdown_files(self) -> list[Path]:
        if not self.vault_path.exists():
            return []

        return [
            path
            for path in self.vault_path.rglob("*.md")
            if path.is_file()
        ]

    def _index_document(self, path: Path) -> IndexedDocument:
        relative_path = path.relative_to(self.vault_path)
        text = path.read_text(encoding="utf-8")
        stat = path.stat()
        frontmatter, body = self._split_frontmatter(text)
        headings = self._extract_headings(body)

        return IndexedDocument(
            title=self._title(path, headings),
            path=str(relative_path),
            folder=str(relative_path.parent) if str(relative_path.parent) != "." else "",
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(
                timespec="seconds"
            ),
            size=stat.st_size,
            headings=headings,
            aliases=self._frontmatter_list(frontmatter, "aliases"),
            tags=self._frontmatter_list(frontmatter, "tags"),
        )

    def _split_frontmatter(self, text: str) -> tuple[list[str], str]:
        lines = text.splitlines()

        if not lines or lines[0].strip() != "---":
            return [], text

        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return lines[1:index], "\n".join(lines[index + 1 :])

        return [], text

    def _extract_headings(self, text: str) -> dict[str, list[str]]:
        headings = {"h1": [], "h2": [], "h3": []}

        for line in text.splitlines():
            stripped = line.strip()

            if stripped.startswith("### "):
                headings["h3"].append(stripped[4:].strip())
            elif stripped.startswith("## "):
                headings["h2"].append(stripped[3:].strip())
            elif stripped.startswith("# "):
                headings["h1"].append(stripped[2:].strip())

        return headings

    def _frontmatter_list(self, frontmatter: list[str], key: str) -> list[str]:
        values: list[str] = []
        reading_block = False

        for line in frontmatter:
            stripped = line.strip()

            if reading_block:
                if stripped.startswith("- "):
                    values.append(self._clean_value(stripped[2:]))
                    continue

                if not line.startswith(" "):
                    reading_block = False

            if stripped.startswith(f"{key}:"):
                raw = stripped[len(key) + 1 :].strip()

                if not raw:
                    reading_block = True
                    continue

                values.extend(self._parse_inline_list(raw))

        return sorted({value for value in values if value})

    def _parse_inline_list(self, raw: str) -> list[str]:
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]

        return [
            self._clean_value(value)
            for value in raw.split(",")
            if self._clean_value(value)
        ]

    def _clean_value(self, value: str) -> str:
        return value.strip().strip('"').strip("'").lstrip("#")

    def _title(self, path: Path, headings: dict[str, list[str]]) -> str:
        if headings["h1"]:
            return headings["h1"][0]

        return path.stem

    def _document_names(self, document: IndexedDocument) -> set[str]:
        names = {
            document.title.lower(),
            Path(document.path).stem.lower(),
            Path(document.path).name.lower(),
        }
        names.update(alias.lower() for alias in document.aliases)

        return names

    def _normalize_name(self, name: str) -> str:
        stripped = name.strip().strip('"').strip("'").lower()

        return stripped
