from dataclasses import dataclass, field
from typing import Any


SEEN_STATE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SeenEntityState:
    """Minimal record of what the user has already seen for one source entity."""

    source: str
    entity_type: str
    entity_id: str
    last_seen_at: str
    source_updated_at: str = ""
    status_seen: str = ""
    priority_seen: str = ""
    summary_fingerprint: str = ""
    description_fingerprint: str = ""
    links_fingerprint: str = ""
    comments_seen: list[str] = field(default_factory=list)
    last_workflow: str = ""
    recommendation_fingerprints: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ["source", "entity_type", "entity_id"]:
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required.")

    @property
    def key(self) -> str:
        """Return a stable storage key for this seen entity."""

        return self.entity_key(
            source=self.source,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "last_seen_at": self.last_seen_at,
            "source_updated_at": self.source_updated_at,
            "status_seen": self.status_seen,
            "priority_seen": self.priority_seen,
            "summary_fingerprint": self.summary_fingerprint,
            "description_fingerprint": self.description_fingerprint,
            "links_fingerprint": self.links_fingerprint,
            "comments_seen": list(self.comments_seen),
            "last_workflow": self.last_workflow,
            "recommendation_fingerprints": list(self.recommendation_fingerprints),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SeenEntityState":
        return cls(
            source=str(data.get("source") or ""),
            entity_type=str(data.get("entity_type") or ""),
            entity_id=str(data.get("entity_id") or ""),
            last_seen_at=str(data.get("last_seen_at") or ""),
            source_updated_at=str(data.get("source_updated_at") or ""),
            status_seen=str(data.get("status_seen") or ""),
            priority_seen=str(data.get("priority_seen") or ""),
            summary_fingerprint=str(data.get("summary_fingerprint") or ""),
            description_fingerprint=str(
                data.get("description_fingerprint") or ""
            ),
            links_fingerprint=str(data.get("links_fingerprint") or ""),
            comments_seen=_string_list(data.get("comments_seen")),
            last_workflow=str(data.get("last_workflow") or ""),
            recommendation_fingerprints=_string_list(
                data.get("recommendation_fingerprints")
            ),
        )

    @staticmethod
    def entity_key(source: str, entity_type: str, entity_id: str) -> str:
        return f"{source.strip()}:{entity_type.strip()}:{entity_id.strip()}"


@dataclass(frozen=True)
class PersonalSeenState:
    """Local, minimal state describing what the user has already seen."""

    schema_version: int = SEEN_STATE_SCHEMA_VERSION
    entities: dict[str, SeenEntityState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "entities": [
                entity.to_dict()
                for _, entity in sorted(self.entities.items())
            ],
        }

    @classmethod
    def empty(cls) -> "PersonalSeenState":
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonalSeenState":
        if int(data.get("schema_version") or 0) != SEEN_STATE_SCHEMA_VERSION:
            return cls.empty()

        entities = {}

        for raw_entity in data.get("entities", []):
            if not isinstance(raw_entity, dict):
                continue

            try:
                entity = SeenEntityState.from_dict(raw_entity)
            except ValueError:
                continue

            entities[entity.key] = entity

        return cls(
            schema_version=SEEN_STATE_SCHEMA_VERSION,
            entities=entities,
        )

    def get(
        self,
        source: str,
        entity_type: str,
        entity_id: str,
    ) -> SeenEntityState | None:
        return self.entities.get(
            SeenEntityState.entity_key(
                source=source,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        )

    def with_entity(self, entity: SeenEntityState) -> "PersonalSeenState":
        entities = dict(self.entities)
        entities[entity.key] = entity

        return PersonalSeenState(
            schema_version=SEEN_STATE_SCHEMA_VERSION,
            entities=entities,
        )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [str(item) for item in value]


@dataclass(frozen=True)
class CurrentEntityState:
    """Minimal current state extracted from one external source entity."""

    source: str
    entity_type: str
    entity_id: str
    source_updated_at: str = ""
    status: str = ""
    priority: str = ""
    summary_fingerprint: str = ""
    description_fingerprint: str = ""
    links_fingerprint: str = ""
    comment_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in ["source", "entity_type", "entity_id"]:
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required.")

    @property
    def key(self) -> str:
        """Return the storage-compatible key for this source entity."""

        return SeenEntityState.entity_key(
            source=self.source,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
        )


@dataclass(frozen=True)
class DeltaFieldChange:
    """One user-relevant field change between seen and current source state."""

    field: str
    before: str
    after: str

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class SeenStateDelta:
    """Comparison result between current source facts and previous seen state."""

    source: str
    entity_type: str
    entity_id: str
    has_previous: bool
    has_changes: bool
    last_seen_at: str = ""
    previous_workflow: str = ""
    source_updated_at: str = ""
    field_changes: list[DeltaFieldChange] = field(default_factory=list)
    new_comment_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "has_previous": self.has_previous,
            "has_changes": self.has_changes,
            "last_seen_at": self.last_seen_at,
            "previous_workflow": self.previous_workflow,
            "source_updated_at": self.source_updated_at,
            "field_changes": [
                change.to_dict()
                for change in self.field_changes
            ],
            "new_comment_ids": list(self.new_comment_ids),
        }
