from app.prompt.prompt_builder import PromptBuilder
from app.llm.provider_factory import ProviderFactory
from app.context.context_builder import ContextBuilder
from app.core.intent_analyzer import IntentAnalyzer
from app.core.models import UserRequest, OrchestratorResponse
from app.core.skill_resolver import SkillResolver


class Orchestrator:

    def __init__(self):
        self.intent_analyzer = IntentAnalyzer()
        self.skill_resolver = SkillResolver()
        self.context_builder = ContextBuilder()
        self.llm = ProviderFactory.create("local")
        self.prompt_builder = PromptBuilder()

    def process(self, request: UserRequest) -> OrchestratorResponse:

        intent = self.intent_analyzer.analyze(request)

        skill = self.skill_resolver.resolve(intent)

        context = self.context_builder.build(skill)

        return OrchestratorResponse(
            success=True,
            message="Request processed",
            data={
                "original_request": request.text,
                "intent": intent,
                "skill": skill,
                "context": context,
            },
        )

    def ask(self, prompt: str) -> str:

        context = self.context_builder.build(prompt)

        full_prompt = self.prompt_builder.build(
            user_prompt=prompt,
            context=context,
        )

        return self.llm.generate(full_prompt)