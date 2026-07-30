# QASkills Knowledge Model

Status: Alpha 0.1 source of truth

QASkills combines several kinds of information. The main rule is that each data
type has one clear role.

## Sources Of Truth

| Data type | Source of truth |
|---|---|
| Current Jira issue state | Jira |
| Long-term QA knowledge | Obsidian / Markdown Vault |
| User-authored notes | Obsidian / Markdown Vault |
| Historical Jira observations | Snapshot files |
| Search index | Derived cache |
| Runtime artifacts | Temporary pipeline state |
| Generated answers | Derived output, not source of truth |

## Jira

Jira is the source of truth for current operational work:

- issue key;
- summary;
- status;
- priority;
- assignee;
- reporter;
- description;
- comments and issue fields visible to the authenticated account.

QASkills reads Jira. Alpha 0.1 does not write to Jira.

## Obsidian / Markdown Vault

The Vault is the source of truth for durable QA knowledge:

- project notes;
- decisions;
- open questions;
- test ideas;
- investigation outcomes;
- release notes;
- QA playbooks;
- human-authored memory.

QASkills treats Obsidian as a local Markdown knowledge base. It does not depend
on Obsidian plugins or APIs.

## Snapshot

Snapshots are historical local observations of Jira state. They are stored in
the configured Vault but are machine-readable artifacts, not ordinary user
notes.

Snapshot role:

- remember what QASkills saw at a point in time;
- enable daily change comparison;
- provide factual historical context.

Snapshot is not the current Jira source of truth.

## Memory Layer

MemoryService and IndexManager are the boundary between runtime workflows and
the Vault.

Memory Layer responsibilities:

- build and reuse metadata index;
- read Markdown documents;
- search indexed metadata and selected note content for daily context;
- save new Markdown notes through approved workflows.

## Runtime Artifacts

Artifacts are temporary results passed through the pipeline:

- memory search results;
- Jira data;
- snapshots;
- change reports;
- daily memory context;
- daily brief;
- LLM output when generation is planned.

Artifacts are not durable unless a service explicitly saves them.

## Long-Term, Temporary, Historical

Long-term:

- Markdown notes in the Vault;
- user-approved knowledge updates;
- project decisions and QA notes.

Historical:

- daily Jira snapshots;
- future persisted evidence records.

Temporary:

- plan artifacts;
- prompts;
- generated fallback responses;
- command output.

## Duplication Rules

- Do not mirror entire Jira issues into Obsidian as knowledge.
- Store durable conclusions, decisions, risks, and links to Jira keys.
- Treat the index as rebuildable cache.
- Treat snapshots as factual history, not user-authored notes.
- Save generated text only after explicit user confirmation.

## Daily Workflow Knowledge Use

Daily Workflow 2.0 searches the Vault for:

- notes with the same Jira key;
- project-related notes;
- open questions;
- yesterday's conclusions;
- test ideas.

If no matching knowledge is found, QASkills says so explicitly.
