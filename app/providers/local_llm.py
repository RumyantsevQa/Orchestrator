import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.providers.base import IntelligenceProvider, ProviderResult


class LocalLLMProvider(IntelligenceProvider):
    """LM Studio-compatible local provider using the OpenAI chat API shape."""

    name = "Local LLM"

    def __init__(
        self,
        base_url: str,
        model: str = "",
        probe_timeout_seconds: float = 1.5,
        timeout_seconds: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.probe_timeout_seconds = probe_timeout_seconds
        self.timeout_seconds = timeout_seconds
        self._resolved_model: str | None = None

    def is_available(self) -> bool:
        return self._resolve_model() is not None

    def generate(self, prompt: str) -> ProviderResult:
        model = self._resolve_model()

        if not model:
            return ProviderResult(
                success=False,
                provider=self.name,
                content="",
                error="Local LLM is not available.",
            )

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.2,
        }
        request = Request(
            self._url("/chat/completions"),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            return ProviderResult(
                success=False,
                provider=self.name,
                content="",
                error=str(error),
            )

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            return ProviderResult(
                success=False,
                provider=self.name,
                content="",
                error=f"Unexpected Local LLM response: {error}",
            )

        return ProviderResult(
            success=True,
            provider=self.name,
            content=str(content).strip(),
        )

    def _resolve_model(self) -> str | None:
        if self.model:
            return self.model

        if self._resolved_model:
            return self._resolved_model

        request = Request(self._url("/models"), method="GET")

        try:
            with urlopen(request, timeout=self.probe_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            return None

        models = data.get("data", [])

        if not models:
            return None

        model_id = models[0].get("id")

        if not model_id:
            return None

        self._resolved_model = str(model_id)
        return self._resolved_model

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"
