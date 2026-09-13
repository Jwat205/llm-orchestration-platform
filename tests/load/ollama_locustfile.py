import random
from locust import HttpUser, task, between


PROMPTS = [
    "Write one sentence about the ocean.",
    "Explain gravity in one sentence.",
    "Give me a fun fact about cats.",
    "What is the capital of France?",
    "Describe a sunset in one sentence.",
    "Name three primary colors.",
    "What is 2 plus 2?",
    "Give a one-line movie recommendation.",
]


class OllamaChatUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task
    def chat_completion(self):
        payload = {
            "model": "llama3.2:1b",
            "messages": [{"role": "user", "content": random.choice(PROMPTS)}],
            "max_tokens": 30,
            "temperature": 0.7,
        }
        with self.client.post(
            "/api/v1/chat/dev/completions",
            json=payload,
            catch_response=True,
            name="ollama_chat_completion",
            timeout=60,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
