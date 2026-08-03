import json
import unittest
from urllib.error import URLError
from unittest.mock import patch

from app.providers.local_llm import LocalLLMProvider


class FakeHTTPResponse:
    def __init__(self, payload: object):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        if isinstance(self.payload, bytes):
            return self.payload

        return json.dumps(self.payload).encode("utf-8")


class LocalLLMProviderTest(unittest.TestCase):
    def test_configured_model_is_used_without_auto_probe(self):
        provider = LocalLLMProvider(
            "http://localhost:1234/v1",
            model="configured-chat-model",
        )

        with patch(
            "app.providers.local_llm.urlopen",
            return_value=FakeHTTPResponse(self.completion("ready")),
        ) as urlopen_mock:
            result = provider.generate("hello")

        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        self.assertTrue(result.success)
        self.assertEqual(result.content, "ready")
        self.assertEqual(payload["model"], "configured-chat-model")
        self.assertEqual(urlopen_mock.call_count, 1)

    def test_auto_model_selection_uses_first_chat_model(self):
        provider = LocalLLMProvider("http://localhost:1234/v1")

        with patch(
            "app.providers.local_llm.urlopen",
            side_effect=[
                FakeHTTPResponse(
                    self.models(
                        "text-embedding-nomic-embed-text-v1.5",
                        "qwen/qwen3-14b",
                    )
                ),
                FakeHTTPResponse(self.completion("answer")),
            ],
        ) as urlopen_mock:
            result = provider.generate("hello")

        request = urlopen_mock.call_args_list[1].args[0]
        payload = json.loads(request.data.decode("utf-8"))

        self.assertTrue(result.success)
        self.assertEqual(payload["model"], "qwen/qwen3-14b")

    def test_auto_model_selection_ignores_embedding_models(self):
        provider = LocalLLMProvider("http://localhost:1234/v1")

        with patch(
            "app.providers.local_llm.urlopen",
            return_value=FakeHTTPResponse(
                self.models(
                    "text-embedding-embeddinggemma-300m",
                    "text-embedding-nomic-embed-text-v1.5",
                )
            ),
        ):
            result = provider.generate("hello")

        self.assertFalse(result.success)
        self.assertIn("No compatible local chat model", result.error or "")

    def test_reasoning_content_is_used_when_content_is_empty(self):
        provider = LocalLLMProvider(
            "http://localhost:1234/v1",
            model="reasoning-model",
        )

        with patch(
            "app.providers.local_llm.urlopen",
            return_value=FakeHTTPResponse(
                self.completion("", reasoning_content="Reasoning model response.")
            ),
        ):
            result = provider.generate("hello")

        self.assertTrue(result.success)
        self.assertEqual(result.content, "Reasoning model response.")

    def test_empty_response_is_rejected(self):
        provider = LocalLLMProvider(
            "http://localhost:1234/v1",
            model="chat-model",
        )

        with patch(
            "app.providers.local_llm.urlopen",
            return_value=FakeHTTPResponse(self.completion("   ")),
        ):
            result = provider.generate("hello")

        self.assertFalse(result.success)
        self.assertIn("empty response", result.error or "")

    def test_timeout_returns_useful_error(self):
        provider = LocalLLMProvider(
            "http://localhost:1234/v1",
            model="chat-model",
        )

        with patch(
            "app.providers.local_llm.urlopen",
            side_effect=TimeoutError(),
        ):
            result = provider.generate("hello")

        self.assertFalse(result.success)
        self.assertIn("timed out", result.error or "")

    def test_invalid_provider_response_is_rejected(self):
        provider = LocalLLMProvider(
            "http://localhost:1234/v1",
            model="chat-model",
        )

        with patch(
            "app.providers.local_llm.urlopen",
            return_value=FakeHTTPResponse({"choices": []}),
        ):
            result = provider.generate("hello")

        self.assertFalse(result.success)
        self.assertIn("malformed generation response", result.error or "")

    def test_provider_error_payload_is_reported(self):
        provider = LocalLLMProvider(
            "http://localhost:1234/v1",
            model="chat-model",
        )

        with patch(
            "app.providers.local_llm.urlopen",
            return_value=FakeHTTPResponse(
                {
                    "error": {
                        "message": "Model loading was stopped.",
                        "type": "invalid_request_error",
                    }
                }
            ),
        ):
            result = provider.generate("hello")

        self.assertFalse(result.success)
        self.assertIn("invalid_request_error", result.error or "")
        self.assertIn("Model loading was stopped", result.error or "")

    def test_invalid_json_is_rejected(self):
        provider = LocalLLMProvider(
            "http://localhost:1234/v1",
            model="chat-model",
        )

        with patch(
            "app.providers.local_llm.urlopen",
            return_value=FakeHTTPResponse(b"{"),
        ):
            result = provider.generate("hello")

        self.assertFalse(result.success)
        self.assertIn("invalid JSON", result.error or "")

    def test_unavailable_server_returns_useful_error(self):
        provider = LocalLLMProvider("http://localhost:1234/v1")

        with patch(
            "app.providers.local_llm.urlopen",
            side_effect=URLError("connection refused"),
        ):
            result = provider.generate("hello")

        self.assertFalse(result.success)
        self.assertIn("unreachable", result.error or "")

    def test_successful_generation_includes_max_tokens(self):
        provider = LocalLLMProvider(
            "http://localhost:1234/v1",
            model="chat-model",
            max_tokens=128,
        )

        with patch(
            "app.providers.local_llm.urlopen",
            return_value=FakeHTTPResponse(self.completion("final answer")),
        ) as urlopen_mock:
            result = provider.generate("hello")

        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        self.assertTrue(result.success)
        self.assertEqual(result.content, "final answer")
        self.assertEqual(payload["max_tokens"], 128)

    def test_health_check_distinguishes_reachability_and_generation(self):
        provider = LocalLLMProvider("http://localhost:1234/v1")

        with patch(
            "app.providers.local_llm.urlopen",
            side_effect=[
                FakeHTTPResponse(self.models("qwen/qwen3-14b")),
                FakeHTTPResponse(self.completion("OK")),
            ],
        ):
            health = provider.health_check()

        self.assertTrue(health.provider_reachable)
        self.assertTrue(health.chat_model_available)
        self.assertTrue(health.generation_works)
        self.assertEqual(health.model, "qwen/qwen3-14b")

    def completion(
        self,
        content: str,
        reasoning_content: str = "",
    ) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": content,
                        "reasoning_content": reasoning_content,
                    }
                }
            ]
        }

    def models(self, *model_ids: str) -> dict:
        return {
            "data": [
                {
                    "id": model_id,
                    "object": "model",
                }
                for model_id in model_ids
            ]
        }


if __name__ == "__main__":
    unittest.main()
