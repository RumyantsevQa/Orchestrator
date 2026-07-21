from .base import LLMProvider


class CodexProvider(LLMProvider):
    def generate(self, prompt: str) -> str:
        raise NotImplementedError("CodexProvider пока не реализован.")