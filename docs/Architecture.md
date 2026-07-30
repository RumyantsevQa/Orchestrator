# QASkills Architecture

Status: Alpha 0.1 source of truth

QASkills Alpha 0.1 is a local-first CLI application built around a capability
pipeline. Services expose capabilities. The planner selects capabilities. The
executor runs the selected plan through service interfaces.

## High-Level Pipeline

```text
User
  |
  v
CLI / Workspace
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
  +--> LLM Service, only when planned
  |
  v
Response Composer
  |
  v
User Response
```

## CLI

The CLI is the user entrypoint. It provides direct commands and an interactive
workspace. It should stay thin: it parses command intent, calls the
Orchestrator, and renders output.

Important commands in Alpha 0.1:

- `qaskills`
- `qaskills doctor`
- `qaskills status`
- `qaskills find`
- `qaskills ask`
- `qaskills prepare daily`
- `qaskills morning`
- `qaskills remember`
- `qaskills jira whoami`
- `qaskills jira projects`
- `qaskills jira issue KEY`

## Intent Analyzer

The Intent Analyzer converts raw user text and CLI metadata into a structured
intent. It does not execute services. It identifies whether the user wants
knowledge search, document reading, daily preparation, Jira access, knowledge
capture, or generation-backed answering.

## Task Planner

The Task Planner converts an intent into a TaskPlan. It only works with
capability names registered by services. It does not call services directly.

The plan decides:

- which capabilities are required;
- which steps are collection steps;
- whether generation is needed;
- which capabilities are missing.

## Plan Executor

The Plan Executor receives a TaskPlan and runs each collection step through the
Service Registry. It does not know how Jira, Memory, Snapshot, or LLM providers
are implemented.

## Memory

MemoryService works with the configured Markdown / Obsidian Vault. It supports:

- listing indexed documents;
- reading documents by path or name;
- listing recent documents;
- metadata search;
- saving new Markdown notes;
- returning Vault folder structure.

MemoryService uses IndexManager rather than scanning the Vault directly for
every read/list operation.

## Document Index

IndexManager builds and persists a JSON metadata index for Markdown files. It
stores:

- title;
- path;
- folder;
- modified time;
- size;
- H1/H2/H3 headings;
- aliases;
- tags.

The index is a derived cache, not a source of truth.

## Jira

JiraService provides live read-only Jira Cloud access for:

- authenticated user;
- projects;
- issue by key;
- assigned issues for Daily Briefing.

Some workspace-oriented Jira paths are local workflow boundaries and do not
write to Jira.

## Snapshots

SnapshotService saves normalized daily Jira state under the configured Vault:

```text
QASkills/Memory/Snapshots/Daily/
```

Snapshots are local historical observations. They are used for factual change
analysis and do not replace Jira as the source of truth for current issue
state.

## Daily Workflow 2.0

```text
qaskills prepare daily
  |
  v
Intent Analyzer: daily_briefing
  |
  v
Task Planner
  |
  v
JiraService.list_assigned_issues
  |
  v
SnapshotService.daily.save
  |
  v
ChangeAnalysisService.daily.analyze
  |
  v
MemoryService.search(mode=daily_context)
  |
  v
DailyBriefService.prepare
  |
  v
ResponseComposer
```

Daily Workflow 2.0 combines:

- current Jira facts;
- previous snapshot history;
- factual changes;
- related Obsidian knowledge by Jira key, project, open questions, yesterday's
  conclusions, and test ideas.

It does not use LLM generation to invent daily context.

## Skills

SkillService exposes lightweight QA guidance capabilities. It is not a full
Skill Engine in Alpha 0.1. The current service validates the boundary for
daily preparation, feature analysis, bug report guidance, and meeting analysis.

## Optional LLM

LLM is optional. ContextComposer, PromptBuilder, LLMService, and ProviderRouter
are used only when the TaskPlan explicitly includes generation.

Supported provider boundaries:

- LM Studio-compatible local provider;
- Codex CLI adapter;
- provider policy routing.

If no provider is available, QASkills returns collected local context and
source-backed fallback output.
