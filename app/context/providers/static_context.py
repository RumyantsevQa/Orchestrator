from .base import ContextProvider


class StaticContextProvider(ContextProvider):

    def get_context(self) -> str:
        return """
Ты работаешь над проектом QAOS.

Главная задача — помогать QA-инженеру выполнять рабочие задачи.
""".strip()