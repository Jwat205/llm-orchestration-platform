"""
Load testing for LLM Platform using Locust
"""

from locust import HttpUser, task, between, events
import json
import random
import time
from typing import List, Dict, Any


class LLMPlatformUser(HttpUser):
    """Simulated user for LLM Platform load testing"""
    
    wait_time = between(1, 5)  # Wait 1-5 seconds between requests
    
    def on_start(self):
        """Initialize user session"""
        self.api_key = "test_api_key_123"  # Use test API key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Test models to use
        self.models = [
            "gpt-3.5-turbo",
            "gpt-4",
            "claude-2",
            "llama-2-7b",
            "llama-2-13b"
        ]
        
        # Sample messages for variety
        self.sample_messages = [
            "Hello, how are you today?",
            "Explain quantum computing in simple terms.",
            "Write a short story about a robot.",
            "What are the benefits of renewable energy?",
            "Help me debug this Python code.",
            "Translate 'Hello world' to Spanish.",
            "Summarize the latest news in technology.",
            "What's the weather like today?",
            "Create a recipe for chocolate cake.",
            "Explain the theory of relativity."
        ]
        
        # Different conversation contexts
        self.conversation_contexts = [
            [{"role": "system", "content": "You are a helpful assistant."}],
            [{"role": "system", "content": "You are a coding expert."}],
            [{"role": "system", "content": "You are a creative writer."}],
            [{"role": "system", "content": "You are a science teacher."}],
            []  # No system message
        ]
    
    @task(10)
    def chat_completion_short(self):
        """Test short chat completions (most common)"""
        model = random.choice(self.models)
        context = random.choice(self.conversation_contexts)
        message = random.choice(self.sample_messages)
        
        messages = context + [{"role": "user", "content": message}]
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": random.randint(50, 200),
            "temperature": round(random.uniform(0.1, 1.0), 1),
            "stream": False
        }
        
        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="chat_completion_short"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        response.success()
                    else:
                        response.failure("Invalid response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(5)
    def chat_completion_long(self):
        """Test longer chat completions"""
        model = random.choice(self.models)
        
        # Create a longer conversation
        messages = [
            {"role": "system", "content": "You are a detailed assistant who provides comprehensive answers."},
            {"role": "user", "content": "Explain machine learning algorithms in detail."},
            {"role": "assistant", "content": "Machine learning algorithms are computational methods that enable systems to learn and improve from data..."},
            {"role": "user", "content": "Can you give me specific examples with use cases?"}
        ]
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": random.randint(300, 800),
            "temperature": 0.7,
            "stream": False
        }
        
        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="chat_completion_long"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(3)
    def streaming_chat_completion(self):
        """Test streaming chat completions"""
        model = random.choice(self.models)
        message = random.choice(self.sample_messages)
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "max_tokens": random.randint(100, 300),
            "temperature": 0.8,
            "stream": True
        }
        
        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers=self.headers,
            stream=True,
            catch_response=True,
            name="streaming_chat_completion"
        ) as response:
            if response.status_code == 200:
                # Read streaming response
                chunks_received = 0
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            chunks_received += 1
                            if line.strip() == 'data: [DONE]':
                                break
                
                if chunks_received > 0:
                    response.success()
                else:
                    response.failure("No streaming chunks received")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(2)
    def embeddings_request(self):
        """Test embeddings endpoint"""
        texts = [
            random.choice(self.sample_messages),
            "Another text for embedding",
            "Document embedding test",
            "Semantic search query"
        ]
        
        payload = {
            "model": "text-embedding-ada-002",
            "input": random.sample(texts, random.randint(1, 3))
        }
        
        with self.client.post(
            "/v1/embeddings",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="embeddings_request"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "data" in data and len(data["data"]) > 0:
                        response.success()
                    else:
                        response.failure("Invalid embeddings response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def function_calling_request(self):
        """Test function calling"""
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "What's the weather like in San Francisco?"}
            ],
            "functions": [
                {
                    "name": "get_weather",
                    "description": "Get current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state"
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "Temperature unit"
                            }
                        },
                        "required": ["location"]
                    }
                }
            ],
            "function_call": "auto"
        }
        
        with self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="function_calling_request"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(8)
    def models_list(self):
        """Test models listing (lightweight operation)"""
        with self.client.get(
            "/v1/models",
            headers=self.headers,
            catch_response=True,
            name="models_list"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "data" in data and isinstance(data["data"], list):
                        response.success()
                    else:
                        response.failure("Invalid models response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(15)
    def health_check(self):
        """Test health check endpoint (very lightweight)"""
        with self.client.get(
            "/health",
            catch_response=True,
            name="health_check"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


class BurstyUser(HttpUser):
    """User that creates bursty traffic patterns"""
    
    wait_time = between(0.1, 1)  # Very short wait times
    weight = 1  # Lower weight than regular users
    
    def on_start(self):
        self.api_key = "burst_test_key"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    @task
    def burst_requests(self):
        """Create burst of requests"""
        for _ in range(random.randint(3, 8)):
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Quick test"}],
                "max_tokens": 50
            }
            
            self.client.post(
                "/v1/chat/completions",
                json=payload,
                headers=self.headers,
                name="burst_request"
            )
            
            time.sleep(0.1)  # Very short delay between burst requests


class StressTestUser(HttpUser):
    """User for stress testing with heavy payloads"""
    
    wait_time = between(2, 10)
    weight = 1  # Lower weight
    
    def on_start(self):
        self.api_key = "stress_test_key"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    @task
    def heavy_completion_request(self):
        """Large completion request"""
        # Create a very long conversation
        messages = [
            {"role": "system", "content": "You are a comprehensive assistant."}
        ]
        
        # Add multiple turns to create a long context
        for i in range(10):
            messages.extend([
                {"role": "user", "content": f"Question {i+1}: Tell me about topic {i+1} in detail."},
                {"role": "assistant", "content": f"Detailed response about topic {i+1}..."}
            ])
        
        messages.append({"role": "user", "content": "Summarize everything we discussed."})
        
        payload = {
            "model": "gpt-4",
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        self.client.post(
            "/v1/chat/completions",
            json=payload,
            headers=self.headers,
            name="heavy_completion_request"
        )


# Event listeners for custom metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Custom request logging"""
    if exception:
        print(f"Request failed: {name} - {exception}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Test start event"""
    print("Load test started")
    print(f"Target host: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Test stop event"""
    print("Load test completed")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")


# Custom task sets for different scenarios
class NormalOperationsTaskSet(HttpUser):
    """Normal business operations task set"""
    
    tasks = {
        "chat_completion_short": 40,
        "chat_completion_long": 20,
        "streaming_chat_completion": 15,
        "embeddings_request": 10,
        "models_list": 10,
        "health_check": 5
    }
    
    def chat_completion_short(self):
        LLMPlatformUser.chat_completion_short(self)
    
    def chat_completion_long(self):
        LLMPlatformUser.chat_completion_long(self)
    
    def streaming_chat_completion(self):
        LLMPlatformUser.streaming_chat_completion(self)
    
    def embeddings_request(self):
        LLMPlatformUser.embeddings_request(self)
    
    def models_list(self):
        LLMPlatformUser.models_list(self)
    
    def health_check(self):
        LLMPlatformUser.health_check(self)


class PeakHoursTaskSet(HttpUser):
    """Peak hours with higher load"""
    
    wait_time = between(0.5, 2)  # Faster requests during peak
    
    tasks = {
        "chat_completion_short": 50,
        "streaming_chat_completion": 30,
        "embeddings_request": 15,
        "models_list": 5
    }
    
    def chat_completion_short(self):
        LLMPlatformUser.chat_completion_short(self)
    
    def streaming_chat_completion(self):
        LLMPlatformUser.streaming_chat_completion(self)
    
    def embeddings_request(self):
        LLMPlatformUser.embeddings_request(self)
    
    def models_list(self):
        LLMPlatformUser.models_list(self)


if __name__ == "__main__":
    # Can be run directly for testing
    import subprocess
    import sys
    
    # Run locust with default settings
    cmd = [
        sys.executable, "-m", "locust",
        "-f", __file__,
        "--host", "http://localhost:8001",
        "--users", "10",
        "--spawn-rate", "2",
        "--run-time", "60s",
        "--headless"
    ]
    
    subprocess.run(cmd)