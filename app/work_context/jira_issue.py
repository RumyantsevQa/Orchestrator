import hashlib
import json
from typing import Any

from app.work_context.models import CurrentEntityState


def current_jira_issue_state(issue: dict[str, Any]) -> CurrentEntityState:
    """Extract minimal comparable state from Jira issue metadata."""

    issue_key = str(issue.get("key") or "").strip().upper()

    if not issue_key:
        raise ValueError("Jira issue key is required.")

    comments = _list_of_dicts(issue.get("comments"))

    return CurrentEntityState(
        source="jira",
        entity_type="issue",
        entity_id=issue_key,
        source_updated_at=str(issue.get("updated") or ""),
        status=str(issue.get("status") or ""),
        priority=str(issue.get("priority") or ""),
        summary_fingerprint=_text_fingerprint(issue.get("summary")),
        description_fingerprint=_text_fingerprint(issue.get("description")),
        links_fingerprint=_links_fingerprint(issue.get("links")),
        comment_ids=[
            _comment_id(comment)
            for comment in comments
        ],
    )


def _text_fingerprint(value: Any) -> str:
    text = " ".join(str(value or "").split())

    if not text:
        return ""

    return _fingerprint(text)


def _links_fingerprint(value: Any) -> str:
    links = []

    for link in _list_of_dicts(value):
        links.append(
            {
                "key": str(link.get("key") or ""),
                "status": str(link.get("status") or ""),
                "summary": str(link.get("summary") or ""),
                "type": str(link.get("type") or ""),
            }
        )

    if not links:
        return ""

    return _fingerprint(
        json.dumps(
            sorted(links, key=lambda item: (item["key"], item["type"])),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _comment_id(comment: dict[str, Any]) -> str:
    raw_id = str(comment.get("id") or "").strip()

    if raw_id:
        return raw_id

    return _fingerprint(
        json.dumps(
            {
                "author": str(comment.get("author") or ""),
                "body": str(comment.get("body") or ""),
                "created": str(comment.get("created") or ""),
                "updated": str(comment.get("updated") or ""),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, dict)]
