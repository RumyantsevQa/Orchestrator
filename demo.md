# QASkills Alpha Demo Script

This script is designed for a five-minute employer demo of the current
QASkills Alpha runtime.

## Goal

Show that QASkills is already usable as a local QA work surface:

- it opens one workspace;
- checks local readiness;
- searches a Markdown or Obsidian Vault;
- prepares source-backed context;
- supports daily preparation;
- saves new knowledge;
- exposes Jira work paths and optional live read-only Jira commands.

Main message:

> QASkills is a local-first QA workspace. It connects my project memory, routes
> work through one pipeline, and helps me recover context before I act.

## Before The Demo

From the repository root:

```bash
.venv/bin/python -m unittest discover -s tests
./qaskills doctor
```

For the strongest demo, connect a real Obsidian Vault:

```bash
export QASKILLS_MEMORY_VAULT_PATH="/path/to/ObsidianVault"
export QASKILLS_DOCUMENT_INDEX_PATH=".qaskills/document_index.json"
```

If no Vault path is configured, QASkills uses the repository's `knowledge/`
folder as a small sample Vault. That proves the product starts, but it is less
impressive than a real project memory.

Keep the terminal large enough to show the pipeline output cleanly.

## Minute 1: Open The Workspace

Command:

```bash
./qaskills
```

What happens:

- in an interactive terminal, QASkills opens the workspace menu;
- the user sees daily preparation, task analysis, knowledge search, bug report
  drafting, knowledge saving, Jira work, meeting analysis, settings, and exit.

What to say:

> I do not want a QA engineer to remember ten tools and ten commands in the
> morning. QASkills starts as one workspace and routes the request from there.

Point out:

- this is the main product entrypoint;
- direct commands still exist for fast usage;
- the workspace is a UX layer over the same runtime pipeline.

## Minute 2: Readiness Check

Command:

```bash
./qaskills status
./qaskills doctor
```

What happens:

- Vault path is shown;
- document index path is shown;
- document count and last index time are shown;
- search readiness is shown;
- provider policy is shown;
- Local LLM availability and Codex CLI availability are shown;
- Jira Workspace boundary readiness is shown.

What to say:

> Before I ask the system to help with QA work, I want to know what it can
> actually use right now: memory, index, search, providers, and Jira boundary.

Point out:

- QASkills is honest about unavailable providers;
- if LM Studio is not running, it falls back to local sources;
- the product does not need network access for the memory workflow.

## Minute 3: Search Project Knowledge

Command:

```bash
./qaskills find architecture
```

What happens:

- the request goes through the unified pipeline;
- Memory Service searches indexed metadata;
- Response Composer returns a Source Pack;
- the output shows key sources, groups, match reasons, tags, and reading order.

What to say:

> This is not magic search. It is explainable metadata search over local QA
> memory. The user can see why each document matched.

Point out:

- the search uses title, aliases, headings, tags, and path;
- it does not claim semantic search yet;
- it is useful even with no LLM provider.

## Minute 4: Ask With Sources And Optional Generation

Command:

```bash
./qaskills ask "Что мы решили про архитектуру?"
```

What happens:

- QASkills searches local knowledge;
- builds a context package;
- builds a provider-neutral prompt;
- calls LLM Service only because the plan includes generation;
- routes through Provider Router;
- if no provider is available, returns a clear fallback plus Source Pack.

What to say:

> `ask` is source-first. If a provider is available, QASkills can generate from
> the collected context. If not, I still get the useful part: the relevant
> sources and the recommended reading order.

Point out:

- Context Composer and Prompt Builder appear only in generation flows;
- sources remain visible;
- fallback behavior is part of the product, not an error.

## Minute 5: Daily And Jira Work Paths

Commands:

```bash
./qaskills morning
./qaskills jira SCRUM-42
./qaskills jira bug SCRUM-42
```

If live Jira credentials are configured, also show:

```bash
./qaskills prepare daily
./qaskills jira whoami
./qaskills jira issue SCRUM-42
```

What happens:

- `morning` collects recent documents and Daily Skill guidance;
- `jira SCRUM-42` prepares the local Jira workspace boundary for a task;
- `jira bug SCRUM-42` prepares a bug report draft path and local source pack;
- `prepare daily` collects assigned Jira issues, saves a snapshot, compares it
  with the previous snapshot, and enriches the brief with related Obsidian
  knowledge when Jira credentials are configured;
- `jira whoami` and `jira issue` use the live read-only Jira Cloud API when
  credentials are configured;
- no Jira write operation is performed in Alpha 0.1.

What to say:

> This is the direction of the product: QA work starts with memory, then moves
> into the specific workflow. Read-only Jira data is already connected for
> account, projects, issues, and Daily Briefing, while write operations remain
> deliberately out of scope for Alpha.

Point out:

- Jira output is intentionally honest about read-only scope;
- local knowledge is searched first;
- bug report drafting already uses Skill Service guidance and workspace
  artifacts.

## Automatic Demo

Command:

```bash
./qaskills demo
```

What happens:

- Vault connection is shown;
- index readiness is shown;
- recent documents are shown;
- metadata search is demonstrated;
- `ask` is demonstrated with provider fallback when needed;
- the demo ends with a clean completion message.

Use this command when time is short or when you want a low-risk live demo.

## Strongest Commands

Use these if the interview is short:

```bash
./qaskills doctor
./qaskills find architecture
./qaskills ask "Что мы решили про архитектуру?"
./qaskills prepare daily
./qaskills jira issue SCRUM-42
./qaskills jira bug SCRUM-42
./qaskills demo
```

## Commands To Avoid Presenting As Finished

Do not present these as current top-level product commands:

```bash
./qaskills prepare ...
./qaskills bug ...
```

The current Alpha Jira paths are:

```bash
./qaskills jira analyze SCRUM-42
./qaskills jira bug SCRUM-42
```

## Questions To Expect

### Why Obsidian?

Because Markdown gives the project memory a local, inspectable, portable source
of truth. QASkills does not replace notes; it makes them operational.

### Why metadata search before RAG?

Because Alpha optimizes for trust and explainability. QA work needs visible
sources before generated conclusions. Semantic retrieval can come later without
changing the user-facing workflow.

### Why read-only Jira first?

Because Alpha should improve preparation without risking production Jira data.
Read-only Jira gives QASkills real task context, while writes, transitions, and
comments stay out of scope until the workflow is proven.

### What is the most important engineering decision?

LLM is not mandatory. The planner decides whether generation is needed, and
QASkills remains useful when no provider is available.

## Closing Line

> QASkills Alpha is not trying to be a giant AI platform. It is a working local
> QA workspace: memory, index, source packs, Daily Workflow 2.0, read-only Jira,
> optional providers, and honest fallback behavior.
