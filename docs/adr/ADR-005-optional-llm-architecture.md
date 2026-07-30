# ADR-005: Optional LLM Architecture

Status: Accepted

## Context

QASkills should be useful without depending on a cloud model or a constantly
available local model. Some tasks require only memory, Jira, snapshots, or
deterministic formatting.

## Decision

LLM generation is optional and plan-driven. ContextComposer, PromptBuilder,
LLMService, and ProviderRouter participate only when TaskPlanner explicitly
adds an `llm.generate` step.

Supported provider boundaries in Alpha 0.1:

- LM Studio-compatible local provider;
- Codex CLI adapter;
- provider policies such as `AUTO`, `LOCAL_ONLY`, `CODEX_ONLY`,
  `CODEX_PREFERRED`, and `ASK`.

## Alternatives

- Always call an LLM at the end of every request.
- Make Codex the center of the architecture.
- Use only local deterministic responses.
- Use only one provider implementation.

## Consequences

Positive:

- QASkills remains usable when providers are unavailable;
- factual workflows can avoid hallucination risk;
- providers can evolve behind a stable boundary;
- user experience degrades gracefully.

Trade-offs:

- some responses are source-pack-like rather than assistant-like;
- provider availability must be communicated clearly;
- generation quality depends on local configuration.
