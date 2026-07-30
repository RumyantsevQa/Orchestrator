# QASkills Roadmap

Status: Alpha 0.1 source of truth

This roadmap describes product evolution from the current runtime. It is not a
promise of dates or a list of speculative integrations.

## Completed

Priority: Done

- Unified CLI and workspace entrypoint.
- Intent Analyzer, Task Planner, Plan Executor, Capability Registry.
- Response Composer and Source Pack output.
- MemoryService for local Markdown / Obsidian Vault access.
- Persistent JSON metadata Document Index.
- Knowledge search by title, aliases, H1/H2/H3 headings, tags, and path.
- Knowledge Update through `remember`.
- Live read-only Jira commands: `whoami`, `projects`, `issue`.
- SnapshotService for daily Jira snapshots.
- ChangeAnalysisService for factual snapshot comparison.
- DailyBriefService for morning reports.
- Daily Workflow 2.0: Jira facts plus related Obsidian knowledge.
- Optional LLM Provider Router with Local LLM and Codex CLI boundaries.
- Regression test suite.
- Alpha documentation baseline.

## Current

Priority: P0

Goal: stabilize Alpha 0.1 as the baseline for further development.

Current focus:

- keep the repository clean;
- keep documentation aligned with runtime;
- keep tests green;
- document architecture decisions;
- avoid adding new workflows during release stabilization.

## Next

Priority: P1

Goal: improve the two highest-value daily QA workflows without changing the
architecture.

Planned direction:

- make Daily Briefing more useful from real usage feedback;
- connect Jira task preparation more tightly to live issue data and local
knowledge;
- make Obsidian knowledge capture safer and more reviewable;
- improve index freshness visibility;
- add CI when the repository is ready for public release.

## Future

Priority: P2

Future work should happen only after Alpha 0.1 is validated in real daily use.

Possible directions:

- richer QA skill routing;
- full-text search before semantic retrieval;
- semantic retrieval and embeddings when the knowledge corpus requires it;
- browser, calendar, email, or meeting integrations when they support a proven
  QA workflow;
- release and regression intelligence;
- intake for logs, API artifacts, meeting notes, and screencasts;
- packaging and global installation.

## Explicitly Deferred

- Jira writes and issue creation.
- Browser automation.
- Calendar, email, and chat integrations.
- Video/audio ingestion in runtime.
- Vector database and RAG.
- New agent framework.
- UI/dashboard before CLI workflows prove daily value.
