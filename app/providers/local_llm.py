import json
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.providers.base import IntelligenceProvider, ProviderResult


EMBEDDING_MODEL_MARKERS = (
    "embedding",
    "embed",
    "bge",
    "e5-",
    "gte-",
)


@dataclass(frozen=True)
class LocalLLMHealth:
    """Diagnostic state for the LM Studio-compatible provider."""

    provider_reachable: bool
    chat_model_available: bool
    generation_works: bool
    model: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "provider_reachable": self.provider_reachable,
            "chat_model_available": self.chat_model_available,
            "generation_works": self.generation_works,
            "model": self.model,
            "error": self.error,
        }


class LocalLLMProvider(IntelligenceProvider):
    """LM Studio-compatible local provider using the OpenAI chat API shape."""

    name = "Local LLM"

    def __init__(
        self,
        base_url: str,
        model: str = "",
        probe_timeout_seconds: float = 1.5,
        timeout_seconds: float = 60.0,
        max_tokens: int = 512,
        health_timeout_seconds: float = 10.0,
        health_max_tokens: int = 32,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self.probe_timeout_seconds = probe_timeout_seconds
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.health_timeout_seconds = health_timeout_seconds
        self.health_max_tokens = health_max_tokens
        self._resolved_model: str | None = None

    def is_available(self) -> bool:
        return self._resolve_model() is not None

    def generate(self, prompt: str) -> ProviderResult:
        model, model_error = self._resolve_model_with_error()

        if not model:
            return ProviderResult(
                success=False,
                provider=self.name,
                content="",
                error=model_error or "No compatible local chat model is available.",
            )

        data, error = self._chat_completion(
            prompt=prompt,
            model=model,
            timeout_seconds=self.timeout_seconds,
            max_tokens=self.max_tokens,
        )

        if error:
            return ProviderResult(
                success=False,
                provider=self.name,
                content="",
                error=error,
            )

        content, error = self._completion_content(data)

        if error:
            return ProviderResult(
                success=False,
                provider=self.name,
                content="",
                error=error,
            )

        return ProviderResult(
            success=True,
            provider=self.name,
            content=content,
        )

    def health_check(self) -> LocalLLMHealth:
        models_data, error = self._models_response()

        if error:
            return LocalLLMHealth(
                provider_reachable=False,
                chat_model_available=False,
                generation_works=False,
                error=error,
            )

        model = self._select_model(models_data)

        if not model:
            return LocalLLMHealth(
                provider_reachable=True,
                chat_model_available=False,
                generation_works=False,
                error="No compatible local chat model is available.",
            )

        data, error = self._chat_completion(
            prompt="Reply with OK.",
            model=model,
            timeout_seconds=self.health_timeout_seconds,
            max_tokens=self.health_max_tokens,
        )

        if error:
            return LocalLLMHealth(
                provider_reachable=True,
                chat_model_available=True,
                generation_works=False,
                model=model,
                error=error,
            )

        _, error = self._completion_content(data)

        if error:
            return LocalLLMHealth(
                provider_reachable=True,
                chat_model_available=True,
                generation_works=False,
                model=model,
                error=error,
            )

        return LocalLLMHealth(
            provider_reachable=True,
            chat_model_available=True,
            generation_works=True,
            model=model,
        )

    def _resolve_model(self) -> str | None:
        model, _ = self._resolve_model_with_error()
        return model

    def _resolve_model_with_error(self) -> tuple[str | None, str | None]:
        if self.model:
            return self.model, None

        if self._resolved_model:
            return self._resolved_model, None

        data, error = self._models_response()

        if error:
            return None, error

        self._resolved_model = self._select_model(data)

        if not self._resolved_model:
            return None, "No compatible local chat model is available."

        return self._resolved_model, None

    def _models_response(self) -> tuple[dict | None, str | None]:
        request = Request(self._url("/models"), method="GET")

        try:
            with urlopen(request, timeout=self.probe_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except json.JSONDecodeError:
            return None, "Local LLM returned invalid JSON from /models."
        except (HTTPError, URLError, TimeoutError, OSError, socket.timeout) as error:
            return None, self._request_error(error)

        if not isinstance(data, dict):
            return None, "Local LLM returned malformed /models response."

        return data, None

    def _select_model(self, data: dict | None) -> str | None:
        if self.model:
            return self.model

        if not isinstance(data, dict):
            return None

        models = data.get("data", [])

        if not isinstance(models, list):
            return None

        for model in models:
            if not isinstance(model, dict):
                continue

            model_id = str(model.get("id") or "").strip()

            if model_id and self._is_compatible_chat_model(model_id, model):
                return model_id

        return None

    def _chat_completion(
        self,
        prompt: str,
        model: str,
        timeout_seconds: float,
        max_tokens: int,
    ) -> tuple[dict | None, str | None]:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        request = Request(
            self._url("/chat/completions"),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except json.JSONDecodeError:
            return None, "Local LLM returned invalid JSON from /chat/completions."
        except (HTTPError, URLError, TimeoutError, OSError, socket.timeout) as error:
            return None, self._request_error(error)

        if not isinstance(data, dict):
            return None, "Local LLM returned malformed generation response."

        return data, None

    def _completion_content(self, data: dict | None) -> tuple[str, str | None]:
        if not isinstance(data, dict):
            return "", "Local LLM returned malformed generation response."

        provider_error = data.get("error")

        if provider_error:
            return "", self._provider_payload_error(provider_error)

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            return "", "Local LLM returned malformed generation response."

        if not isinstance(message, dict):
            return "", "Local LLM returned malformed generation response."

        content = self._visible_text(message.get("content"))

        if content:
            return content, None

        reasoning_content = self._visible_text(message.get("reasoning_content"))

        if reasoning_content:
            return reasoning_content, None

        return "", "Local LLM returned an empty response."

    def _is_compatible_chat_model(self, model_id: str, model: dict) -> bool:
        model_type = str(model.get("type") or model.get("object") or "").lower()
        searchable = f"{model_id} {model_type}".lower()

        return not any(marker in searchable for marker in EMBEDDING_MODEL_MARKERS)

    def _request_error(self, error: Exception) -> str:
        if isinstance(error, HTTPError):
            return f"Local LLM returned HTTP {error.code}: {error.reason}."

        if isinstance(error, TimeoutError | socket.timeout):
            return "Local LLM request timed out."

        if isinstance(error, URLError):
            reason = getattr(error, "reason", None)
            return f"Local LLM is unreachable: {reason or error}."

        return f"Local LLM request failed: {error}."

    def _provider_payload_error(self, error: object) -> str:
        if isinstance(error, dict):
            message = self._visible_text(error.get("message"))
            error_type = self._visible_text(error.get("type"))

            if message and error_type:
                return f"Local LLM error ({error_type}): {message}"

            if message:
                return f"Local LLM error: {message}"

        return f"Local LLM error: {self._visible_text(error) or 'unknown error'}"

    def _visible_text(self, value: object) -> str:
        return " ".join(str(value or "").split())

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"
