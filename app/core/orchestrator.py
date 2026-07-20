from app.context.context_builder import ContextBuilder
from app.core.intent_analyzer import IntentAnalyzer
from app.core.models import UserRequest, OrchestratorResponse
from app.core.skill_resolver import SkillResolver


class Orchestrator:

    def __init__(self):
        self.intent_analyzer = IntentAnalyzer()
        self.skill_resolver = SkillResolver()
        self.context_builder = ContextBuilder()

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
                "context": context
            }
        )