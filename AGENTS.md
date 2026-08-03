# AGENTS.md

This is the Codex entry point for the `Orchestrator` repository.

For workspace-level responsibilities, first read `../AGENTS.md`.

## Repository Identity

`Orchestrator` is the runtime code repository for QASkills.

Its current role is the QASkills Knowledge Engine. It exposes structured
knowledge to external AI agents, primarily Codex.

## What This Repository Owns

This repository owns:

- Python runtime code;
- KnowledgeAPI;
- CodexAdapter;
- local MCP Server;
- document indexing implementation;
- MemoryService integration with the configured Vault;
- Jira read integration;
- tests;
- runtime configuration;
- developer-facing debugging entrypoints.

## What This Repository Does Not Own

This repository does not own:

- durable product truth;
- QA Skill content;
- Obsidian knowledge organization;
- product vision;
- architecture decision content beyond runtime documentation;
- natural-language reasoning;
- final user-facing answers.

Durable knowledge belongs in the `../QASkills` Vault.

## Current Runtime Boundary

Orchestrator is not an AI agent.

It must not decide user intent from natural language. Codex does that. The
runtime receives structured calls through Python interfaces or MCP tools and
returns structured data.

Preferred flow:

```text
Codex
  ↓
MCP tool call
  ↓
CodexAdapter
  ↓
KnowledgeAPI
  ↓
Memory / Index / Jira / Skills metadata
  ↓
Knowledge Pack
  ↓
Codex
```

## Development Rules

- Do not add new architecture layers unless the user explicitly asks.
- Do not reintroduce IntentAnalyzer, Planner, ProviderRouter, or LLM reasoning
  into the Knowledge Engine path unless explicitly requested.
- Keep KnowledgeAPI stable once a task says it is the accepted core.
- Do not change public behavior while doing organizational or documentation
  work.
- Keep runtime artifacts out of Git: `.qaskills/`, caches, `__pycache__/`,
  `.pytest_cache/`, `.venv/`, and local secrets.
- Never print Jira tokens or other secrets.

## Source of Truth

When product or architecture meaning is unclear, read the Vault documents in
`../QASkills`, starting with:

1. `../QASkills/AGENTS.md`
2. `../QASkills/CANONICAL_TRUTH.md`
3. `../QASkills/Product/Vision.md`
4. `../QASkills/Product/Principles.md`
5. `../QASkills/PROJECT_RULES.md`

Do not copy large amounts of Vault content into this repository. Link or query
the Vault through the Knowledge Engine instead.
