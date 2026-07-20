from app.core.models import UserRequest


class IntentAnalyzer:
    """
    Определяет намерение пользователя.
    Пока реализована простейшая версия.
    """

    def analyze(self, request: UserRequest) -> str:
        return "general"