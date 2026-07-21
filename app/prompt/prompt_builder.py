class PromptBuilder:

    def build(
        self,
        user_prompt: str,
        context: str = ""
    ) -> str:

        parts = [
            self.system_prompt(),
            self.context(context),
            self.user_prompt(user_prompt)
        ]

        return "\n\n".join(part for part in parts if part)

    def system_prompt(self) -> str:
        return "Ты помощник QA-инженера."

    def context(self, context: str) -> str:
        if not context:
            return ""

        return f"Контекст:\n{context}"

    def user_prompt(self, prompt: str) -> str:
        return f"Запрос пользователя:\n{prompt}"