# ADR-001: Source Of Truth

Status: Accepted

## Context

QASkills combines Jira, local Markdown notes, snapshots, runtime artifacts, and
optional generated answers. Without clear ownership, the same fact could be
stored in multiple places and become inconsistent.

## Decision

Use explicit source-of-truth boundaries:

- Jira is the source of truth for current issue state.
- Obsidian / Markdown Vault is the source of truth for durable QA knowledge.
- Snapshot files are the source of truth for local historical observations.
- Document index is a derived cache.
- Runtime artifacts and generated answers are not sources of truth.

## Alternatives

- Mirror Jira data into Obsidian.
- Treat generated summaries as knowledge automatically.
- Store everything in one application database.

## Consequences

Positive:

- fewer contradictions;
- easier debugging;
- clearer user trust model;
- local knowledge stays human-readable.

Trade-offs:

- workflows must combine several sources;
- generated output needs explicit save/approval before becoming knowledge;
- snapshots and notes require clear naming and storage rules.
