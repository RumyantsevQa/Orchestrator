# QASkills Vision

Status: Alpha 0.1 source of truth

## Why QASkills Exists

QA work is context-heavy. A QA engineer often starts the day by opening Jira,
notes, old decisions, testing ideas, browser tabs, and an AI assistant
separately. The problem is not a lack of tools. The problem is that the working
context is fragmented.

QASkills exists to make QA context operational. It connects local knowledge,
Jira state, daily snapshots, QA skills, and optional intelligence providers into
one working surface.

## Problem Statement

A QA engineer needs to answer practical questions quickly:

- What changed since yesterday?
- Which tasks need attention?
- What do we already know about this project or Jira issue?
- What risks, open questions, or test ideas were captured before?
- How should I prepare for daily, testing, regression, or a bug report?

Without a system like QASkills, the engineer has to reconstruct that context
manually from scattered tools.

## Product Principle

The user does not work with Python, Jira, Obsidian, or an LLM directly.

The user works with QASkills.

QASkills decides which local capabilities are useful for the request:

- memory;
- document index;
- Jira;
- snapshots;
- change analysis;
- skills;
- optional LLM generation.

## Why A QA Engineer Opens It Every Morning

QASkills should become the first daily entrypoint because it answers the most
important morning question:

> What should I know before I start working?

In Alpha 0.1 this is expressed through:

- a workspace entrypoint;
- readiness checks;
- local knowledge search;
- persistent daily snapshots from Jira;
- factual change analysis;
- Daily Briefing enriched with related Obsidian knowledge;
- source-backed answers and fallback behavior.

## Difference From A Regular CLI

A regular CLI exposes commands. QASkills exposes QA work intent.

The command line is only the first interface. The product direction is a
personal QA operating surface where commands are routed through one pipeline and
results are grounded in real sources.

## End-State Vision

The long-term vision is a local-first QA operating system that helps a QA
engineer:

- prepare for the day;
- prepare for a Jira task;
- recover project context;
- design checks and test cases;
- investigate bugs;
- analyze logs, APIs, meetings, and release risk;
- preserve durable knowledge in a personal or team Vault;
- keep AI optional, controlled, and source-grounded.

QASkills should improve the QA process by reducing context loss, making
decisions reusable, and turning scattered knowledge into daily operational
support.
