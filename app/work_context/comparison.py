from app.work_context.models import (
    CurrentEntityState,
    DeltaFieldChange,
    SeenEntityState,
    SeenStateDelta,
)


def compare_seen_state(
    previous: SeenEntityState,
    current: CurrentEntityState,
) -> SeenStateDelta:
    """Compare previously seen state with current source state."""

    if previous.key != current.key:
        raise ValueError("Cannot compare different seen entities.")

    field_changes = [
        change
        for change in [
            _change("status", previous.status_seen, current.status),
            _change("priority", previous.priority_seen, current.priority),
            _change(
                "summary",
                previous.summary_fingerprint,
                current.summary_fingerprint,
            ),
            _change(
                "description",
                previous.description_fingerprint,
                current.description_fingerprint,
            ),
            _change("links", previous.links_fingerprint, current.links_fingerprint),
        ]
        if change is not None
    ]
    new_comment_ids = [
        comment_id
        for comment_id in current.comment_ids
        if comment_id not in previous.comments_seen
    ]

    return SeenStateDelta(
        source=current.source,
        entity_type=current.entity_type,
        entity_id=current.entity_id,
        has_previous=True,
        has_changes=bool(field_changes or new_comment_ids),
        last_seen_at=previous.last_seen_at,
        previous_workflow=previous.last_workflow,
        source_updated_at=current.source_updated_at,
        field_changes=field_changes,
        new_comment_ids=new_comment_ids,
    )


def _change(
    field_name: str,
    previous_value: str,
    current_value: str,
) -> DeltaFieldChange | None:
    previous = str(previous_value or "")
    current = str(current_value or "")

    if previous == current:
        return None

    return DeltaFieldChange(
        field=field_name,
        before=previous,
        after=current,
    )
