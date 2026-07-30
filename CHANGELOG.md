# Changelog

All notable changes for QASkills are documented here.

## Alpha 0.1

Status: Alpha baseline

### Added

- Local `qaskills` CLI entrypoint and workspace menu.
- Unified runtime pipeline:
  - Intent Analyzer;
  - Task Planner;
  - Capability Registry;
  - Plan Executor;
  - Response Composer.
- MemoryService for Markdown / Obsidian Vault workflows.
- Persistent JSON metadata Document Index.
- Metadata search across title, aliases, H1/H2/H3 headings, tags, and path.
- Source Pack responses for search and `ask` fallback.
- Knowledge Update workflow through `remember`.
- Live read-only Jira Cloud commands:
  - `qaskills jira whoami`;
  - `qaskills jira projects`;
  - `qaskills jira issue KEY`.
- SnapshotService for local daily Jira snapshots.
- ChangeAnalysisService for factual comparison between daily snapshots.
- DailyBriefService for morning daily reports.
- Daily Workflow 2.0 with related Obsidian knowledge enrichment.
- SkillService boundary for selected QA guidance workflows.
- Optional LLMService and ProviderRouter.
- LM Studio-compatible local provider boundary.
- Codex CLI provider adapter boundary.
- Demo script and Alpha documentation.
- Architecture Decision Records.
- Automated regression tests.

### Changed

- Documentation synchronized to the current Alpha runtime.
- Earlier v1.0 RC documentation moved under `docs/archive/v1.0-rc/`.
- README updated to present Alpha scope, configuration, commands, and
  limitations.
- `.gitignore` updated for local runtime state, snapshots, env files, and
  common Python/test caches.

### Known Limitations

- Jira integration is read-only.
- Jira write operations, comments, transitions, and issue creation are not
  supported.
- Browser, Calendar, email, and chat integrations are not implemented.
- Video/audio ingestion is not part of runtime.
- Search is not semantic retrieval or RAG.
- Full Markdown body search is not a general search feature.
- The document index is a JSON metadata cache, not SQLite.
- Index freshness visibility is limited.
- Global packaging and installation are not part of Alpha 0.1.
- Daily Briefing needs at least two snapshot runs for change history.
- Obsidian enrichment is factual and source-based; if no note is found,
  QASkills says so.

### Verification

- Automated test suite: 60 tests passing.
- Compilation smoke check completed for CLI, core, index, services, response,
  and tests.

### Conscious Deferrals

- New integrations beyond the current runtime.
- New workflows beyond existing Alpha paths.
- Architecture rewrites.
- Agent framework adoption.
- Vector search and embeddings.
