from app.core.artifacts import Artifact, PipelineTrace
from app.providers.router import ProviderRouter
from app.services.base import BaseService, ServiceRequest


class LLMService(BaseService):
    """Deterministic generation boundary used only when a plan asks for it."""

    name = "LLM Service"
    capabilities = {
        "llm.generate": "Generate a user-facing answer.",
    }

    def __init__(self, provider_router: ProviderRouter):
        self.provider_router = provider_router

    def execute(
        self,
        capability: str,
        request: ServiceRequest,
        trace: PipelineTrace | None = None,
    ) -> Artifact:
        if trace:
            trace.add(self.name, f"Executed capability {capability}")

        prompt = request.payload.get("prompt", "")
        provider_result = self.provider_router.generate(str(prompt), trace=trace)

        if provider_result.success:
            return Artifact(
                name="llm_response",
                source=self.name,
                content=provider_result.content,
                metadata={
                    "capability": capability,
                    "provider": provider_result.provider,
                    "provider_success": True,
                    "prompt_preview": str(prompt)[:160],
                },
            )

        return Artifact(
            name="llm_response",
            source=self.name,
            content=(
                "No intelligence provider completed the request. "
                "QASkills is using the collected local context instead."
            ),
            metadata={
                "capability": capability,
                "provider": provider_result.provider,
                "provider_success": False,
                "provider_error": provider_result.error,
                "prompt_preview": str(prompt)[:160],
            },
        )
