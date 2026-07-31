import json
from pathlib import Path

from app.work_context.models import PersonalSeenState, SeenEntityState


DEFAULT_SEEN_STATE_PATH = ".qaskills/personal_seen_state.json"


class SeenStateStorage:
    """Safe local JSON storage for Personal Seen State."""

    def __init__(self, path: str | Path = DEFAULT_SEEN_STATE_PATH):
        self.path = Path(path).expanduser()

    def load(self) -> PersonalSeenState:
        """Load state or return an empty state when storage is absent or invalid."""

        if not self.path.exists():
            return PersonalSeenState.empty()

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return PersonalSeenState.empty()

        if not isinstance(data, dict):
            return PersonalSeenState.empty()

        try:
            return PersonalSeenState.from_dict(data)
        except (TypeError, ValueError):
            return PersonalSeenState.empty()

    def save(self, state: PersonalSeenState) -> None:
        """Persist state atomically enough for local CLI usage."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(
                state.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temp_path.replace(self.path)

    def get(
        self,
        source: str,
        entity_type: str,
        entity_id: str,
    ) -> SeenEntityState | None:
        """Return a seen entity from the current stored state."""

        return self.load().get(
            source=source,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    def upsert(self, entity: SeenEntityState) -> PersonalSeenState:
        """Store one seen entity and return the updated state."""

        state = self.load().with_entity(entity)
        self.save(state)

        return state
