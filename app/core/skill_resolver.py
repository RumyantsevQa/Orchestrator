class SkillResolver:
    """
    Определяет, какой Skill должен обработать запрос.
    Первая версия всегда возвращает общий Skill.
    """

    def resolve(self, intent: str) -> str:
        return "general"