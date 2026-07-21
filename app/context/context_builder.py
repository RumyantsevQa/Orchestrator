from app.context.providers.vault_provider import VaultProvider
from app.context.context_resolver import ContextResolver


class ContextBuilder:

    def __init__(self):

        self.provider = VaultProvider(
            "/Users/ilya_motion/Job/QASkills"
        )

        self.resolver = ContextResolver()

    def build(self, user_request: str) -> str:

        documents = self.resolver.resolve(user_request)

        context = []

        for document in documents:

            text = self.provider.read_note(document)

            if text:
                context.append(text)

        return "\n\n".join(context)