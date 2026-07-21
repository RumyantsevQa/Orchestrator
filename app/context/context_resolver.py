class ContextResolver:

    def resolve(self, user_request: str) -> list[str]:

        request = user_request.lower()

        #
        # Архитектура
        #
        if any(word in request for word in [
            "архитектур",
            "architecture",
            "core",
            "ядро",
            "core objects"
        ]):
            return [
                "03 Architecture/Architecture.md",
                "03 Architecture/Core Objects.md",
                "03 Architecture/Architecture Principles.md",
            ]

        #
        # LeadQA
        #
        if "leadqa" in request:
            return [
                "LeadQA.md",
            ]

        #
        # Старый QAOS
        #
        if "qaos" in request:
            return [
                "Archive/QAOS Legacy/INDEX.md",
            ]

        #
        # Общие вопросы о проекте
        #
        if any(word in request for word in [
            "qaskills",
            "проект",
            "оркестратор",
            "obsidian",
            "правила",
            "constitution",
            "agent"
        ]):
            return [
                "PROJECT_RULES.md",
                "AGENTS.md",
                "Foundation/Project Constitution.md",
            ]

        #
        # Всё остальное —
        # вообще без контекста
        #
        return []