# ADR-003: Snapshot Model

Status: Accepted

## Context

Daily preparation needs to answer what changed since the previous run. Jira can
show current state, but QASkills needs a local previous observation to compare
against.

## Decision

Persist normalized Jira daily snapshots as local JSON artifacts under the
configured Vault:

```text
QASkills/Memory/Snapshots/Daily/
```

Use SnapshotService to save current state and load previous state. Use
ChangeAnalysisService to compare snapshots.

## Alternatives

- Query Jira changelog for every daily report.
- Store snapshots in a database.
- Store snapshots as Markdown notes.
- Avoid persistence and only show current Jira state.

## Consequences

Positive:

- deterministic daily comparison;
- works independently from Jira changelog availability;
- keeps historical observations local;
- separates current Jira truth from local history.

Trade-offs:

- first run has no history;
- snapshots need retention policy later;
- JSON snapshots are not ordinary human-authored notes.
