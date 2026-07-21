from .local_provider import LocalProvider
from .codex_provider import CodexProvider


class ProviderFactory:

    @staticmethod
    def create(mode: str = "local"):

        if mode == "codex":
            return CodexProvider()

        return LocalProvider()