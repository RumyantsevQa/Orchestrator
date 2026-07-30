# ADR-002: Role Of Obsidian

Status: Accepted

## Context

QASkills needs long-term project memory. The project already uses Markdown and
Obsidian-style Vaults for requirements, decisions, QA notes, and skills.

## Decision

Use Obsidian / Markdown Vault as the durable knowledge store for Alpha 0.1.
QASkills accesses it through the filesystem and MemoryService. It does not
require Obsidian plugins, Dataview, sync APIs, or a running Obsidian app.

## Alternatives

- Store all knowledge in SQLite.
- Use a cloud note API.
- Depend on an Obsidian plugin.
- Use only Jira as the knowledge source.

## Consequences

Positive:

- local-first and inspectable;
- easy to back up and version;
- works without network access for memory workflows;
- users can edit knowledge outside QASkills.

Trade-offs:

- no native Obsidian graph integration in runtime;
- search quality depends on note structure;
- QASkills must manage index freshness clearly.
