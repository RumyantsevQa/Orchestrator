# QASkills Alpha Known Limitations

This document describes confirmed limitations of the current QASkills Alpha
runtime. It is not a roadmap and does not list hypothetical future features.

## Product State

QASkills is currently an Alpha 0.1 product.

User impact:

- it is usable for local QA memory workflows;
- it is not yet a packaged public release;
- documentation and demos should describe it as Alpha 0.1, not as a final v1.0
  release.

Product impact:

- the project can be demonstrated as a working product direction;
- GitHub Release publication still requires owner approval.

## Local Knowledge First

QASkills works primarily with a configured Markdown or Obsidian Vault.

If `QASKILLS_MEMORY_VAULT_PATH` is not set, it falls back to the repository's
small `knowledge/` sample Vault.

User impact:

- meaningful daily usage requires configuring a real Vault;
- the sample Vault is useful for first run and smoke checks, but it is not a
  substitute for real project memory.

Product impact:

- the product can run immediately after clone;
- demo quality depends heavily on the connected Vault.

## Metadata Search Only

Search uses indexed metadata:

- title;
- aliases;
- H1/H2/H3 headings;
- tags;
- path.

It does not search full Markdown body text.

User impact:

- documents that mention a topic only in body text may not be found;
- good headings, tags, aliases, and filenames improve search quality;
- users may need to reformulate queries.

Product impact:

- search results are explainable and fast;
- recall is narrower than full-text or semantic retrieval.

## No Semantic Retrieval

The current Alpha does not use:

- embeddings;
- vector store;
- chunks;
- semantic similarity;
- RAG.

`qaskills ask` prepares source-backed context from metadata search results. It
is not a full Retrieval-Augmented Generation implementation.

User impact:

- exact or metadata-aligned queries work best;
- indirect phrasing and conceptual similarity can be missed.

Product impact:

- Alpha favors inspectability and deterministic behavior;
- it should not be presented as semantic search or RAG.

## Optional LLM Providers

QASkills contains an LLM Service and Provider Router.

Generation is used only when the Task Planner includes an `llm.generate` step.
Current generation-capable flows include `ask`, `morning`, and selected Jira
workspace paths such as analysis, bug report, and daily context.

Supported provider boundaries:

- LM Studio-compatible local provider;
- optional Codex CLI adapter;
- provider policies: `AUTO`, `LOCAL_ONLY`, `CODEX_ONLY`, `CODEX_PREFERRED`,
  `ASK`.

If no provider is available, QASkills returns a clear fallback with collected
local context, Source Pack, skill guidance, or workspace artifacts.

User impact:

- the product remains useful without LM Studio or Codex generation;
- generated prose quality depends on the configured provider;
- fallback output may be more source-pack-like than assistant-like.

Product impact:

- LLM is an optional tool, not the mandatory center of the system;
- provider behavior must be demonstrated honestly.

## Jira Integration Is Read-Only

QASkills Alpha includes live Jira Cloud read commands:

```bash
./qaskills jira whoami
./qaskills jira projects
./qaskills jira issue SCRUM-42
```

These commands require `JIRA_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN` in the
environment or repository-local `.env`.

User impact:

- the user can verify the authenticated Jira account;
- visible projects can be listed;
- a Jira issue can be opened by key;
- no Jira issue is created or updated.

Product impact:

- Alpha should be presented as a read-only Jira integration;
- write workflows, transitions, comments, and issue creation are not
  implemented.

### Jira Workspace Commands Are Still Local Workflows

QASkills also includes workspace-oriented Jira paths:

```bash
./qaskills jira
./qaskills jira SCRUM-42
./qaskills jira analyze SCRUM-42
./qaskills jira bug SCRUM-42
./qaskills jira daily SCRUM-42
```

These paths prepare local QA analysis, daily context, or bug report drafts. They
do not write to Jira.

## Daily Briefing Needs Snapshot History

`qaskills prepare daily` saves Jira snapshots under the configured Vault and
compares the current snapshot with the previous one. It also searches the
configured Markdown/Obsidian Vault for related Jira keys, project notes, open
questions, yesterday's conclusions, and test ideas.

User impact:

- the first run cannot know what changed before QASkills started tracking;
- the first report explicitly says `Insufficient historical data`;
- meaningful "what changed" analysis starts from the second run;
- snapshot quality depends on the Jira fields visible to the authenticated
  account;
- Obsidian enrichment is factual and source-based; when no related note is
  found, the report says so instead of inventing context.

Product impact:

- daily intelligence is factual and time-aware;
- there is no database or retention policy yet;
- snapshots are local memory artifacts, not Jira write operations;
- related knowledge search is not semantic RAG; it relies on Jira keys, project
  references, headings, tags, path, and matching note text.

## Browser, Calendar, Email, And Chat Are Not Implemented

QASkills Alpha does not include runtime integrations for:

- Browser automation;
- Calendar;
- email;
- chat or team messengers.

User impact:

- browser context, meetings, and team communication must be opened outside
  QASkills;
- the current demo should focus on local knowledge, workspace, read-only Jira,
  and provider fallback.

Product impact:

- Alpha has fewer operational dependencies;
- it is not yet a full work orchestration platform.

## Video And Audio Analysis Are Not Runtime Features

The wider QASkills knowledge system contains QA skills for analyzing meetings
and screencasts, but the current product runtime does not include a video or
audio ingestion pipeline.

User impact:

- video/audio work requires manually prepared notes, transcripts, subtitles, or
  frames;
- `qaskills` does not currently transcribe or analyze video files by itself.

Product impact:

- demo claims must stay limited to CLI workflows that exist in runtime.

## Skill Service Is Limited

The current `SkillService` exposes a small set of runtime capabilities:

- daily preparation;
- feature analysis guidance;
- bug report guidance;
- meeting analysis guidance.

It is not a full Skill Engine.

User impact:

- some QA skills from the broader Project Memory are not directly callable from
  the CLI yet;
- available skill guidance is intentionally lightweight.

Product impact:

- Alpha validates the service boundary and selected workflows;
- it should not be described as complete automation of all QA Skills.

## Simple Frontmatter Parsing

The index extracts `aliases` and `tags` from simple frontmatter forms. It does
not implement full YAML parsing.

User impact:

- complex frontmatter structures may not be represented in the index;
- simple `aliases` and `tags` formats are safest for predictable results.

Product impact:

- the index avoids additional parser dependencies;
- metadata extraction is intentionally limited.

## Index Freshness

The saved index is reused between commands.

The index is rebuilt when:

- no saved index exists;
- the configured Vault path changes;
- `qaskills remember` saves a new note.

The current CLI does not display a freshness warning when an existing Markdown
file changes after the index was built.

User impact:

- recently edited existing notes may not appear until the index is rebuilt by
  the current lifecycle;
- before a live demo, run `qaskills status` or `qaskills doctor` and verify the
  expected document count.

Product impact:

- command startup remains fast;
- freshness visibility is limited.

## Technical Files Can Be Indexed

The index scans Markdown files under the configured Vault. If technical folders
inside the Vault contain Markdown files, their metadata may be indexed.

The user-facing Vault structure response filters some technical folders from
display, but the underlying index remains metadata-complete for the configured
Vault.

User impact:

- search may return technical documents if they are inside the configured Vault
  and match the query;
- the configured Vault should be chosen deliberately.

Product impact:

- indexing remains simple and transparent;
- Vault hygiene affects search quality.

## Local Executable

The verified executable is:

```bash
./qaskills
```

Examples using `qaskills` assume the script is available on the user's PATH.
Packaging and global installation are not part of the current Alpha state.

User impact:

- users should run commands from the repository root unless they configure PATH;
- copy-pasting global `qaskills` examples may not work on a new machine without
  setup.

Product impact:

- the project is ready for local demonstration;
- public distribution still requires packaging or installation instructions.

## macOS-Centric Open Command

`qaskills open` uses the local system opener.

User impact:

- positive opening behavior depends on the operating system and registered
  Markdown application;
- live demos should prefer `find`, `ask`, `doctor`, and `demo` unless document
  opening was checked manually on the target machine.

Product impact:

- navigation is useful locally;
- cross-platform GUI opening is not certified.

## Testing Limitations

Currently verified:

- local macOS workspace;
- Python runtime available on the development machine;
- automated unit/regression suite with `60` tests;
- default sample Vault;
- one real Project Memory Vault with `478` indexed Markdown documents during
  recovery validation;
- CLI smoke checks for `help`, `status`, `doctor`, `find`, `ask`, `morning`,
  `prepare daily`, `jira`, `jira bug`, and `demo`.

Not fully verified:

- Windows or Linux behavior;
- large Vault performance boundaries;
- concurrent index access;
- global command installation;
- positive GUI document opening on every target machine;
- CI execution;
- public GitHub Release tag workflow.

User impact:

- behavior is validated for local Alpha usage and demonstration, not every
  machine configuration.

Product impact:

- Alpha has enough evidence for controlled demos;
- public release confidence requires a tag, release review, and owner approval.

## Documentation History

Earlier v1.0 RC documentation is archived under:

```text
docs/archive/v1.0-rc/
```

Those files preserve an earlier release-candidate stage and are not the current
Alpha source of truth.
