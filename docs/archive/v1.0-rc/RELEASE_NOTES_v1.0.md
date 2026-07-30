# QASkills v1.0 RC Release Notes

Release state: Release Candidate validated by QA  
Release date: 2026-07-23  
Product: QASkills, Knowledge Operating System for QA Engineers

## Overview

QASkills is a local-first command-line product that turns a QA engineer's
Markdown knowledge base into a daily working surface.

The v1.0 Release Candidate focuses on one finished workflow:

```text
Connect local QA knowledge.
Verify that it is ready.
Find relevant sources.
Prepare a structured Source Pack for a work question.
```

This release is source-first. It does not invent answers or call external
services. It helps the user recover trustworthy context quickly and see why each
source was selected.

## Who This Release Is For

QASkills v1.0 RC is intended for:

- QA engineers who keep project memory in Markdown or Obsidian;
- QA engineers preparing for meetings, investigations, or task context recovery;
- QA leads and engineering reviewers evaluating a local knowledge workflow;
- technical interview scenarios where the product must work without external
  credentials or network dependencies.

## What Users Can Do

### Check readiness

```bash
./qaskills doctor
```

Confirms that the Vault, index, memory layer, search, configuration, and answer
mode are ready.

### Search local QA knowledge

```bash
./qaskills find architecture
```

Returns ranked metadata results with match reasons and tags.

### Prepare a Source Pack

```bash
./qaskills ask "Что мы решили про архитектуру?"
```

Builds a structured Source Pack with:

- a brief overview;
- key sources;
- grouped sources;
- recommended reading order;
- notes explaining how to use the sources.

### Run a short product demo

```bash
./qaskills demo
```

Shows the full local workflow: readiness, recent documents, search, and Source
Pack preparation.

## Key Capabilities

### Local Knowledge Base

- Connects to a configured Obsidian Vault.
- Uses local Markdown files as the source of project memory.
- Requires no network access for the validated CLI workflow.
- Falls back to the repository's `knowledge/` folder as a small sample Vault
  when no real Vault path is configured.

### Persistent Metadata Index

The index stores:

- title;
- vault-relative path;
- folder;
- modified time;
- file size;
- H1/H2/H3 headings;
- aliases;
- tags.

### Source-First CLI

Available commands include:

- `qaskills help`;
- `qaskills status`;
- `qaskills doctor`;
- `qaskills find <query>`;
- `qaskills open <query>`;
- `qaskills ask <question>`;
- `qaskills morning`;
- `qaskills demo`.

## Main Release Improvement

The main user-facing improvement is Source Pack preparation.

Earlier `ask` behavior risked feeling too close to ordinary search output. In
this release candidate, `ask` now transforms ranked documents into a practical
reading package:

1. search indexed local knowledge;
2. rank matching documents;
3. group sources by practical context;
4. identify key sources;
5. recommend a reading order.

This makes `ask` useful for recovering context before a meeting, investigation,
or technical discussion, while keeping the result grounded in local evidence.

## Fixed Defects

### QAS-CLI-001: Duplicate Header On No-Match Search

No-match `find` previously printed two product headers. The command now returns
one clean error block with suggestions.

Verified with:

- `./qaskills find zzz-no-such-topic-123`;
- CLI regression tests.

### QAS-CLI-002: Vault Structure Output Too Noisy

`Покажи структуру Vault` previously displayed technical folders and a very long
folder list. The response now shows a compact user-facing overview and filters
technical folders from display.

Verified with:

- `python3 main.py Покажи структуру Vault`;
- pipeline regression tests.

## QA Summary

Final QA evidence:

- `python3 -m unittest` passed: `28 tests OK`;
- `python3 -m py_compile ...` passed;
- `./qaskills doctor` passed;
- `./qaskills ask Что мы решили про архитектуру` passed;
- `./qaskills demo` passed;
- stale user-facing promise scan passed.

QA recommendation: ready for technical interview demonstration with known
limitations.

GitHub Release publication still requires owner review, a clean release commit,
and a tag.

Post-packaging verification also passed after removing obsolete release-tree
artifacts and validating both the sample Vault fallback and configured real
Vault mode.

## Known Limitations

- `ask` prepares Source Packs; it does not generate final answers.
- Search is metadata-based; full Markdown body text is not searched.
- No semantic search, embeddings, vector store, chunks, or RAG.
- No Jira, Browser, Calendar, email, chat, or external API integrations.
- Index freshness is not surfaced as a CLI warning when files change after the
  index was built.
- `open` depends on the local operating system and application handler.
- Global `qaskills` usage assumes PATH setup; verified local executable is
  `./qaskills`.
- Public GitHub Release publication requires a clean commit and tag.

For details, see `KNOWN_LIMITATIONS.md`.

## Release Artifacts

- `README.md`
- `demo.md`
- `TEST_REPORT.md`
- `KNOWN_LIMITATIONS.md`
- `RELEASE_CHECKLIST.md`
- `RELEASE_NOTES_v1.0.md`

## How To Try The Release Candidate

From the repository root:

```bash
./qaskills doctor
./qaskills find architecture
./qaskills ask "Что мы решили про архитектуру?"
./qaskills demo
```

Configuration is environment-based:

```bash
export QASKILLS_MEMORY_VAULT_PATH="/path/to/ObsidianVault"
export QASKILLS_DOCUMENT_INDEX_PATH=".qaskills/document_index.json"
```

Without `QASKILLS_MEMORY_VAULT_PATH`, the CLI uses the repository's `knowledge/`
folder so the product can be started immediately after clone.
