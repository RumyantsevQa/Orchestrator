import requests


class LLMClient:
    """
    Клиент для общения с локальной LLM.
    """

    def __init__(self):
        self.url = "http://localhost:1234/v1/chat/completions"

    def ask(self, prompt: str) -> str:

        payload = {
            "model": "qwen/qwen3-14b",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2
        }

        response = requests.post(self.url, json=payload)

        response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]