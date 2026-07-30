# ADR-004: Capability Pipeline

Status: Accepted

## Context

QASkills must support multiple services without making the planner depend on
their implementations. The system needs to grow while keeping boundaries clear.

## Decision

Use a capability-based pipeline:

- services register named capabilities;
- TaskPlanner builds a TaskPlan from the intent and available capabilities;
- PlanExecutor resolves capabilities through ServiceRegistry;
- services return Artifacts;
- ResponseComposer builds the user response.

## Alternatives

- Let the CLI call services directly.
- Let the planner instantiate services.
- Use a large agent framework.
- Hard-code one pipeline per command.

## Consequences

Positive:

- services are replaceable behind capability names;
- missing capabilities are visible;
- tests can validate planning independently;
- LLM can remain optional.

Trade-offs:

- capability names become an important contract;
- artifact metadata must stay disciplined;
- overusing capabilities for tiny internal details would add noise.
