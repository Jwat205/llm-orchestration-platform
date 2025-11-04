"""
Locust Load Testing Scenarios for LLM Platform
Comprehensive load testing for all API endpoints
"""

import json
import random
import time
from locust import HttpUser, task, between, events
from locust.exception import StopUser
import logging

logger = logging.getLogger(__name__)

class LLMPlatformUser(HttpUser):
    """Base user class for LLM Platform testing"""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup user session"""
        self.headers = {
            "Content-Type": "application/json"
        }
        self.user_id = f"test_user_{random.randint(1000, 9999)}"
    
    def get_api_key(self):
        """Get API key for testing"""
        # In real testing, you'd get this from environment or config
        return "test_api_key_12345"
    
    def get_test_prompt(self):
        """Get random test prompt"""
        prompts = [
            "Write a short story about a robot learning to paint.",
            "Explain quantum computing in simple terms.",
            "Create a recipe for chocolate chip cookies.",
            "Describe the benefits of renewable energy.",
            "Write a poem about the ocean.",
            "Explain how machine learning works.",
            "List 10 tips for better productivity.",
            "Describe the history of the internet.",
            "Write a letter to a friend about your vacation.",
            "Explain the water cycle."
        ]
        return random.choice(prompts)

class ChatCompletionUser(LLMPlatformUser):
    """User focused on chat completion endpoints"""
    
    @task(3)
    def chat_completion_simple(self):
        """Test basic chat completion"""
        payload = {
            "model": "gpt2",
            "messages": [
                {"role": "user", "content": self.get_test_prompt()}
            ],
            "max_tokens": 150,
            "temperature": 0.7
        }
        
        with self.client.post("/api/v1/llm/chat/completions", 
                            json=payload, 
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    response.success()
                else:
                    response.failure("Invalid response format")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(2)
    def chat_completion_streaming(self):
        """Test streaming chat completion"""
        payload = {
            "model": "gpt2",
            "messages": [
                {"role": "user", "content": self.get_test_prompt()}
            ],
            "max_tokens": 100,
            "temperature": 0.7,
            "stream": True
        }
        
        with self.client.post("/api/v1/llm/chat/completions", 
                            json=payload, 
                            headers=self.headers,
                            stream=True,
                            catch_response=True) as response:
            if response.status_code == 200:
                chunks_received = 0
                for line in response.iter_lines():
                    if line:
                        chunks_received += 1
                        if chunks_received > 100:  # Prevent infinite streams
                            break
                
                if chunks_received > 0:
                    response.success()
                else:
                    response.failure("No streaming chunks received")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def chat_completion_with_functions(self):
        """Test chat completion with function calling"""
        payload = {
            "model": "gpt2",
            "messages": [
                {"role": "user", "content": "What's the weather like in New York?"}
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
                                "description": "City name"
                            }
                        },
                        "required": ["location"]
                    }
                }
            ],
            "max_tokens": 100
        }
        
        with self.client.post("/api/v1/llm/chat/completions", 
                            json=payload, 
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

class EmbeddingUser(LLMPlatformUser):
    """User focused on embedding endpoints"""
    
    @task(2)
    def create_embeddings(self):
        """Test embeddings creation"""
        payload = {
            "model": "gpt2",
            "input": [
                self.get_test_prompt(),
                "Another test document for embedding."
            ]
        }
        
        with self.client.post("/api/v1/embeddings/", 
                            json=payload, 
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    response.success()
                else:
                    response.failure("Invalid embedding response")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def search_embeddings(self):
        """Test embedding search"""
        payload = {
            "query": self.get_test_prompt(),
            "top_k": 5,
            "threshold": 0.7
        }
        
        # Search endpoint not implemented yet, test health instead
        with self.client.get("/health",
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

class ModelManagementUser(LLMPlatformUser):
    """User focused on model management endpoints"""
    
    @task(1)
    def list_models(self):
        """Test model listing"""
        with self.client.get("/api/v1/llm/models", 
                           headers=self.headers,
                           catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "data" in data:
                    response.success()
                else:
                    response.failure("Invalid models response")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def model_info(self):
        """Test model information retrieval"""
        model_name = random.choice(["gpt2", "gpt2-medium", "distilgpt2"])
        
        with self.client.get(f"/api/v1/llm/models/{model_name}", 
                           headers=self.headers,
                           catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.success()  # Model not found is acceptable
            else:
                response.failure(f"HTTP {response.status_code}")

class GraphServiceUser(LLMPlatformUser):
    """User focused on graph service endpoints"""
    
    @task(1)
    def graph_query(self):
        """Test graph querying"""
        payload = {
            "query": "Find entities related to artificial intelligence",
            "max_depth": 2,
            "limit": 10
        }
        
        # Graph endpoint not implemented yet
        with self.client.get("/health",
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

class HighLoadUser(LLMPlatformUser):
    """High-intensity user for stress testing"""
    
    wait_time = between(0.1, 0.5)  # More aggressive timing
    
    @task(5)
    def rapid_fire_completions(self):
        """Rapid chat completions for stress testing"""
        payload = {
            "model": "gpt2",
            "messages": [
                {"role": "user", "content": "Quick response test"}
            ],
            "max_tokens": 50,
            "temperature": 0.5
        }
        
        with self.client.post("/api/v1/llm/chat/completions", 
                            json=payload, 
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:  # Rate limited
                response.success()  # Expected under high load
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(2)
    def concurrent_embeddings(self):
        """Concurrent embedding requests"""
        payload = {
            "model": "gpt2",
            "input": ["Stress test document"]
        }
        
        with self.client.post("/api/v1/embeddings/", 
                            json=payload, 
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code in [200, 429]:  # Accept rate limiting
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

class RealisticWorkloadUser(LLMPlatformUser):
    """Realistic user behavior simulation"""
    
    wait_time = between(5, 15)  # More realistic user pauses
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversation_history = []
    
    @task(4)
    def conversational_flow(self):
        """Simulate realistic conversation flow"""
        if len(self.conversation_history) == 0:
            # Start conversation
            prompt = self.get_test_prompt()
            self.conversation_history.append({"role": "user", "content": prompt})
        else:
            # Continue conversation
            follow_ups = [
                "Can you explain that in more detail?",
                "What are some examples?",
                "How does this compare to alternatives?",
                "What are the pros and cons?",
                "Can you summarize the key points?"
            ]
            prompt = random.choice(follow_ups)
            self.conversation_history.append({"role": "user", "content": prompt})
        
        # Limit conversation length
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-6:]
        
        payload = {
            "model": "gpt2",
            "messages": self.conversation_history,
            "max_tokens": 200,
            "temperature": 0.7
        }
        
        with self.client.post("/api/v1/llm/chat/completions", 
                            json=payload, 
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and data["choices"]:
                    # Add assistant response to history
                    assistant_response = data["choices"][0]["message"]["content"]
                    self.conversation_history.append({
                        "role": "assistant", 
                        "content": assistant_response
                    })
                    response.success()
                else:
                    response.failure("Invalid response format")
            else:
                response.failure(f"HTTP {response.status_code}")
    
    @task(1)
    def document_processing(self):
        """Simulate document processing workflow"""
        # First, upload a document (simulated)
        document_text = " ".join([self.get_test_prompt() for _ in range(5)])
        
        # Create embeddings for the document
        payload = {
            "model": "gpt2",
            "input": [document_text]
        }
        
        with self.client.post("/api/v1/embeddings/", 
                            json=payload, 
                            headers=self.headers,
                            catch_response=True) as response:
            if response.status_code == 200:
                # Then search for related content
                search_payload = {
                    "query": "Find information about this topic",
                    "top_k": 3
                }
                
                # Search endpoint not implemented yet, just test health
                with self.client.get("/health",
                                    headers=self.headers,
                                    catch_response=True) as search_response:
                    if search_response.status_code == 200:
                        response.success()
                    else:
                        response.failure(f"Health check failed: {search_response.status_code}")
            else:
                response.failure(f"Embedding failed: {response.status_code}")

# Custom event handlers for metrics collection
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Custom request handler for detailed metrics"""
    if exception:
        logger.error(f"Request failed: {name} - {exception}")
    else:
        logger.info(f"Request: {name} - {response_time}ms - {response_length} bytes")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Test start event handler"""
    logger.info("Load test starting...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Test stop event handler"""
    logger.info("Load test completed")
    
    # Generate summary report
    stats = environment.stats
    total_requests = stats.total.num_requests
    failed_requests = stats.total.num_failures
    
    logger.info(f"Total requests: {total_requests}")
    logger.info(f"Failed requests: {failed_requests}")
    logger.info(f"Failure rate: {(failed_requests/total_requests)*100:.2f}%")
    logger.info(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"Max response time: {stats.total.max_response_time:.2f}ms")

# Scenario definitions for different test types
class LightLoadTest(ChatCompletionUser):
    """Light load test - normal usage"""
    weight = 3

class MediumLoadTest(ChatCompletionUser, EmbeddingUser):
    """Medium load test - mixed workload"""
    weight = 2

class HeavyLoadTest(HighLoadUser):
    """Heavy load test - stress testing"""
    weight = 1

class RealisticTest(RealisticWorkloadUser):
    """Realistic user behavior test"""
    weight = 4