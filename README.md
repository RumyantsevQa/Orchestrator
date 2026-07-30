# QASkills

**Knowledge Operating System for QA Engineers**

QASkills is a local-first command-line product that turns a QA engineer's
Markdown or Obsidian knowledge base into a daily working surface.

Current project state: **Alpha 0.1**.

The repository is still named `Orchestrator` internally, but the public product
name is QASkills.

## What QASkills Does Today

QASkills gives a QA engineer one CLI entrypoint for daily work with local
project knowledge:

- open a workspace with `qaskills`;
- inspect Vault and index readiness;
- search local QA knowledge by indexed metadata;
- prepare Source Packs for work questions;
- review recent documents before daily meetings;
- prepare a Daily Brief from Jira snapshots and related Obsidian knowledge;
- save new notes back into the configured Vault;
- open relevant Markdown documents;
- read Jira Cloud user, projects, and issues through a read-only integration;
- start Jira-related QA workflows through a safe local boundary;
- optionally route generated answers through a local LM Studio-compatible
  provider or Codex CLI adapter.

If no intelligence provider is available, QASkills does not fail. It returns the
local context, Source Pack, skill guidance, and workspace artifacts it already
collected.

## Why This Exists

QA work depends on context: product decisions, old investigations, release
notes, project memory, testing ideas, risks, and lessons from previous bugs.

That context often exists, but it is scattered across documents and hard to
restore under time pressure. QASkills makes local QA memory inspectable,
searchable, and usable from one place.

## Current Alpha 0.1 Scope

Implemented in the current runtime:

- interactive workspace opened by `qaskills`;
- unified request pipeline;
- local Markdown / Obsidian Vault connection;
- persistent JSON metadata document index;
- document listing from saved index metadata;
- metadata search across title, aliases, H1/H2/H3 headings, tags, and path;
- Source Pack responses with key sources, groups, match reasons, and reading
  order;
- `ask` flow with optional generation and source fallback;
- persistent Daily Briefing from live Jira assigned issues, saved snapshots,
  factual change analysis, and related Obsidian knowledge;
- `morning` workflow from recent local documents and Daily Skill guidance;
- Knowledge Update workflow through `remember`;
- live Jira Cloud read commands for current user, projects, and issues;
- Jira Workspace boundary for task analysis, daily preparation, and bug report
  drafts;
- provider policies: `AUTO`, `LOCAL_ONLY`, `CODEX_ONLY`, `CODEX_PREFERRED`,
  `ASK`;
- LM Studio-compatible Local LLM provider;
- optional Codex CLI provider adapter;
- automated regression tests.

Not implemented in Alpha:

- Jira write operations;
- Browser automation;
- Calendar, email, or chat integrations;
- video/audio analysis in the product runtime;
- embeddings, vector store, chunks, semantic search, or RAG;
- SQLite index;
- packaged global installation.

See [Known Limitations](KNOWN_LIMITATIONS.md) for the full current limitation
set.

## Architecture

```text
User
  |
  v
QASkills CLI / Workspace
  |
  v
Intent Analyzer
  |
  v
Task Planner
  |
  v
Capability Registry
  |
  v
Plan Executor
  |
  +--> Memory Service
  +--> Skill Service
  +--> Jira Service
  +--> Snapshot Service
  +--> Change Analysis Service
  +--> Daily Brief Service
  |
  v
Context Composer       only when generation is planned
  |
  v
Prompt Builder         only when generation is planned
  |
  v
LLM Service            only when generation is planned
  |
  v
Provider Router        Local LLM / Codex CLI / fallback
  |
  v
Response Composer
  |
  v
User Response
```

The planner works through named capabilities, not concrete service
implementations. The executor runs the plan through the service registry. The
Context Composer and Prompt Builder are created only for requests where the
plan explicitly includes generation.

## Repository Map

```text
main.py                  CLI implementation and workspace commands
qaskills                 Local executable wrapper
app/core/                Intent, planning, execution, capabilities, config
app/index/               Persistent JSON metadata Document Index
app/services/            Service interfaces and current service implementations
app/providers/           Local LLM, Codex CLI adapter, and Provider Router
app/context/             Context composition boundary for generation flows
app/prompt/              Prompt boundary for generation flows
app/response/            User-facing response and Source Pack composition
tests/                   Automated regression tests
knowledge/               Small sample Markdown Vault for first run
docs/archive/            Historical release documentation
```

## Document Index

The index stores metadata for every Markdown document in the configured Vault:

- title;
- vault-relative path;
- folder;
- modified time;
- size;
- H1/H2/H3 headings;
- aliases from frontmatter;
- tags from frontmatter.

The index is saved on disk and reused between commands. It is rebuilt when no
saved index exists, when the configured Vault path changes, or after
`qaskills remember` saves a new note.

## Configuration

QASkills reads configuration from environment variables:

```bash
export QASKILLS_MEMORY_VAULT_PATH="/path/to/ObsidianVault"
export QASKILLS_DOCUMENT_INDEX_PATH=".qaskills/document_index.json"
export QASKILLS_PROVIDER_POLICY="AUTO"
export QASKILLS_LOCAL_LLM_BASE_URL="http://localhost:1234/v1"
export JIRA_URL="https://your-domain.atlassian.net"
export JIRA_EMAIL="you@example.com"
export JIRA_API_TOKEN="your-api-token"
```

QASkills also automatically reads a local `.env` file from the repository root.
Do not commit `.env`.

If `QASKILLS_MEMORY_VAULT_PATH` is not set, QASkills uses the repository's
`knowledge/` folder as a small sample Vault. For real usage, point the variable
to your Obsidian Vault or another Markdown knowledge base.

Provider policy controls routing behavior:

- `AUTO`: use the local LM Studio-compatible provider when available,
  otherwise continue with local source fallback;
- `LOCAL_ONLY`: use only the local LM Studio-compatible provider;
- `CODEX_ONLY`: use only the Codex CLI adapter;
- `CODEX_PREFERRED`: try Codex CLI first, then the local provider;
- `ASK`: ask interactively when a terminal is available.

## Quick Start

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

./qaskills
./qaskills doctor
./qaskills find architecture
./qaskills ask "What is QASkills architecture?"
./qaskills prepare daily
./qaskills morning
./qaskills remember "Daily decision: use QASkills as the QA entrypoint"
./qaskills jira whoami
./qaskills jira projects
./qaskills jira issue SCRUM-42
./qaskills jira SCRUM-42
./qaskills jira bug SCRUM-42
```

With a real Obsidian Vault:

```bash
export QASKILLS_MEMORY_VAULT_PATH="/path/to/ObsidianVault"
export QASKILLS_DOCUMENT_INDEX_PATH=".qaskills/document_index.json"

./qaskills doctor
./qaskills find architecture
./qaskills ask "Что мы решили про архитектуру?"
```

Python entrypoint:

```bash
.venv/bin/python main.py help
.venv/bin/python main.py status
.venv/bin/python main.py demo
```

## CLI Commands

### Workspace

```bash
./qaskills
./qaskills workspace
```

In an interactive terminal, `qaskills` opens the workspace menu. The workspace
offers daily preparation, task analysis, knowledge search, bug report drafting,
knowledge saving, Jira work, meeting analysis, and settings.

### Knowledge

```bash
./qaskills status
./qaskills doctor
./qaskills prepare daily
./qaskills morning
./qaskills remember "Decision: keep QASkills local-first for Alpha"
```

`remember` saves a Markdown note to the configured Vault and refreshes the
document index immediately.

### Daily Briefing

```bash
./qaskills prepare daily
```

Builds a readable morning brief from live Jira data assigned to the current
user. QASkills collects the assigned issues through JiraService, saves the
current state as a local snapshot, loads the previous snapshot, compares both
states through ChangeAnalysisService, and then renders the final report through
DailyBriefService.

After Jira changes are collected, the same workflow also asks MemoryService to
look for related Obsidian/Markdown knowledge. It checks indexed notes and note
content for the current Jira keys, project references, open questions,
yesterday's conclusions, and test ideas. These sources are included in the
Daily Brief as factual references. If no related knowledge exists, QASkills says
that explicitly. This step does not use LLM generation.

Snapshots are saved as local QASkills memory artifacts under:

```text
QASkills/Memory/Snapshots/Daily/
```

Each snapshot stores timestamp, project, assigned issues, status, priority,
assignee, updated time, sprint, due date, labels, story points when available,
description hash, and comment count.

Example shape:

```text
🌅 Good morning, Ilya

Today's Daily Brief

Sprint: QAOS Sprint 5
Assigned: 3 issues
Snapshot: 2026-07-30
Compared with: 2026-07-29

Assigned Work:
• SCRUM-1 Implement authentication
  Status: In Progress | Priority: Medium | Due: No due date | Updated: 2026-07-30

Obsidian Knowledge:
• Found 2 related Obsidian source(s).
• Linked Jira notes:
  - SCRUM-1 Auth Daily (QASkills/Memory/Projects/SCRUM-1 Auth Daily.md)
    Evidence: # SCRUM-1 Auth Daily
• Open questions:
  - SCRUM-1 Auth Daily (QASkills/Memory/Projects/SCRUM-1 Auth Daily.md)
    Evidence: ## Open questions

Yesterday:
• Closed SCRUM-14: Login validation
• SCRUM-18 moved from To Do to In Progress

New today:
• SCRUM-27 OAuth callback

Risks:
• 1 high-priority assigned issue remains open.

Suggested Daily Report
"Since the previous snapshot, SCRUM-14 moved to done. Status changed for SCRUM-18. Newly assigned: SCRUM-27."
```

### Search

```bash
./qaskills find architecture
./qaskills find migration
./qaskills find "QASkills Architecture"
```

Search uses indexed metadata, not full Markdown body text.

### Questions

```bash
./qaskills ask "Что мы решили про архитектуру?"
```

The command searches indexed local knowledge and prepares a grounded Source
Pack. If a selected intelligence provider is available, QASkills also asks it
to generate a response from the composed context. If no provider is available,
the command returns a clear fallback with sources and collected context.

### Navigation

```bash
./qaskills open architecture
./qaskills open QASkills
```

If several documents match, QASkills offers a numbered choice in an interactive
terminal.

### Jira Workspace

```bash
./qaskills jira
./qaskills jira whoami
./qaskills jira projects
./qaskills jira issue SCRUM-42
./qaskills jira SCRUM-42
./qaskills jira analyze SCRUM-42
./qaskills jira bug SCRUM-42
./qaskills jira daily SCRUM-42
```

`whoami`, `projects`, and `issue` call the Jira Cloud REST API. Analysis,
daily, and bug report commands still use the local QASkills workspace path and
combine local memory, Skill Service guidance, optional generation, and Jira
workspace artifacts.

## Live Jira Integration

QASkills supports Jira Cloud Basic Auth with an Atlassian account email and API
token.

Create an API token:

1. Open the Atlassian account API token page:
   <https://id.atlassian.com/manage-profile/security/api-tokens>.
2. Create a token for QASkills.
3. Copy it once and store it only in your local `.env`.

Create `.env` in the repository root:

```text
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your-api-token
```

Never commit `.env` and never paste the token into terminal output, docs, or
issues.

Verify the connection:

```bash
./qaskills jira whoami
./qaskills jira projects
./qaskills jira issue SCRUM-42
```

If configuration is incomplete, QASkills prints which variables are missing
without printing the token.

### Diagnostics

```bash
./qaskills demo
```

Runs a short product demonstration: Vault connection, index readiness, recent
documents, metadata search, Source Pack preparation, optional provider
fallback, and completion summary.

## Natural Language Examples

The planner can route these local-memory requests:

```bash
.venv/bin/python main.py Покажи мои проекты
.venv/bin/python main.py Покажи последние документы
.venv/bin/python main.py Открой документ QASkills
.venv/bin/python main.py Покажи структуру Vault
.venv/bin/python main.py Покажи документы проекта QASkills
.venv/bin/python main.py Покажи документы с тегом QA
.venv/bin/python main.py Покажи документы, где есть заголовок Architecture
.venv/bin/python main.py Запомни это: решение обсуждено на daily
.venv/bin/python main.py jira анализ задачи SCRUM-42
```

## Demo

Run:

```bash
./qaskills demo
```

For a five-minute presentation flow, see [demo.md](demo.md).

## Documentation

- [Demo Script](demo.md)
- [Vision](docs/Vision.md)
- [Roadmap](docs/Roadmap.md)
- [Architecture](docs/Architecture.md)
- [Knowledge Model](docs/KnowledgeModel.md)
- [Architecture Decision Records](docs/adr/)
- [Changelog](CHANGELOG.md)
- [Known Limitations](KNOWN_LIMITATIONS.md)
- [Historical v1.0 RC documents](docs/archive/v1.0-rc/)

The archived v1.0 RC documents preserve an earlier release-candidate stage.
They are not the current Alpha source of truth.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m py_compile main.py qaskills app/core/config.py app/core/orchestrator.py app/index/manager.py app/index/models.py app/services/memory.py app/services/jira.py app/services/jira_client.py app/services/daily_models.py app/services/snapshot.py app/services/change_analysis.py app/services/daily_brief.py app/response/composer.py tests/test_cli.py tests/test_application_pipeline.py tests/test_jira_client.py tests/test_snapshot_service.py tests/test_change_analysis_service.py tests/test_daily_brief_service.py
./qaskills doctor
./qaskills ask "What is QASkills architecture?"
./qaskills workspace
./qaskills prepare daily
./qaskills jira whoami
./qaskills jira projects
./qaskills jira issue SCRUM-42
./qaskills jira SCRUM-42
./qaskills demo
```
