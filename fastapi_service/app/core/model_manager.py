"""
Model Manager for handling local LLM models
Supports various model types including Transformers, Llama, and other local models
"""

import os
import torch
import aiohttp
import json
from typing import Dict, List, Optional, AsyncGenerator, Union
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    pipeline, TextGenerationPipeline
)
import structlog
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = structlog.get_logger()

@dataclass
class ModelConfig:
    name: str
    model_path: str
    tokenizer_path: str = None
    device: str = "auto"
    max_length: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    model_type: str = "transformers"  # "transformers" or "ollama"
    ollama_name: str = None  # For Ollama models

class ModelManager:
    """Manages loading and inference with local LLM models"""

    def __init__(self):
        self.models: Dict[str, Union[TextGenerationPipeline, str]] = {}
        self.tokenizers: Dict[str, AutoTokenizer] = {}
        self.configs: Dict[str, ModelConfig] = {}
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.ollama_base_url = "http://localhost:11434"

        # Define available models
        self.available_models = {
            # HuggingFace Transformers models
            "microsoft/DialoGPT-medium": ModelConfig(
                name="microsoft/DialoGPT-medium",
                model_path="microsoft/DialoGPT-medium",
                tokenizer_path="microsoft/DialoGPT-medium",
                max_length=1024,
                model_type="transformers"
            ),
            "microsoft/DialoGPT-small": ModelConfig(
                name="microsoft/DialoGPT-small",
                model_path="microsoft/DialoGPT-small",
                tokenizer_path="microsoft/DialoGPT-small",
                max_length=512,
                model_type="transformers"
            ),
            "gpt2": ModelConfig(
                name="gpt2",
                model_path="gpt2",
                tokenizer_path="gpt2",
                max_length=1024,
                model_type="transformers"
            ),
            "gpt2-medium": ModelConfig(
                name="gpt2-medium",
                model_path="gpt2-medium",
                tokenizer_path="gpt2-medium",
                max_length=1024,
                model_type="transformers"
            ),
            "distilgpt2": ModelConfig(
                name="distilgpt2",
                model_path="distilgpt2",
                tokenizer_path="distilgpt2",
                max_length=512,
                model_type="transformers"
            ),
            # Ollama models
            "llama3.1:8b": ModelConfig(
                name="llama3.1:8b",
                model_path="llama3.1:8b",
                max_length=4096,
                model_type="ollama",
                ollama_name="llama3.1:8b"
            ),
            "gemma3:4b": ModelConfig(
                name="gemma3:4b",
                model_path="gemma3:4b",
                max_length=2048,
                model_type="ollama",
                ollama_name="gemma3:4b"
            ),
            "codellama:13b": ModelConfig(
                name="codellama:13b",
                model_path="codellama:13b",
                max_length=4096,
                model_type="ollama",
                ollama_name="codellama:13b"
            ),
            "mistral:7b": ModelConfig(
                name="mistral:7b",
                model_path="mistral:7b",
                max_length=8192,
                model_type="ollama",
                ollama_name="mistral:7b"
            ),
            "phi3:mini": ModelConfig(
                name="phi3:mini",
                model_path="phi3:mini",
                max_length=2048,
                model_type="ollama",
                ollama_name="phi3:mini"
            )
        }

        # Auto-load a default lightweight model
        self._load_default_model()

    async def check_ollama_status(self) -> bool:
        """Check if Ollama is running and accessible"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_base_url}/api/tags", timeout=5) as response:
                    return response.status == 200
        except Exception as e:
            logger.warning("Ollama not accessible", error=str(e))
            return False

    async def list_ollama_models(self) -> List[str]:
        """List available Ollama models"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        return [model["name"] for model in data.get("models", [])]
                    return []
        except Exception as e:
            logger.error("Failed to list Ollama models", error=str(e))
            return []

    async def pull_ollama_model(self, model_name: str) -> bool:
        """Pull/download an Ollama model"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"name": model_name}
                async with session.post(
                    f"{self.ollama_base_url}/api/pull",
                    json=payload,
                    timeout=3600  # Model download can take a while
                ) as response:
                    if response.status == 200:
                        logger.info("Successfully pulled Ollama model", model=model_name)
                        return True
                    else:
                        logger.error("Failed to pull Ollama model",
                                   model=model_name, status=response.status)
                        return False
        except Exception as e:
            logger.error("Error pulling Ollama model", model=model_name, error=str(e))
            return False

    def _load_default_model(self):
        """Load a default lightweight model for immediate availability"""
        try:
            default_model = "distilgpt2"
            logger.info("Loading default model", model=default_model)
            self.load_model(default_model)
            logger.info("Default model loaded successfully", model=default_model)
        except Exception as e:
            logger.error("Failed to load default model", error=str(e))

    def load_model(self, model_name: str) -> bool:
        """Load a model for inference"""
        try:
            if model_name in self.models:
                logger.info("Model already loaded", model=model_name)
                return True

            if model_name not in self.available_models:
                logger.error("Model not available", model=model_name)
                return False

            config = self.available_models[model_name]
            logger.info("Loading model", model=model_name, config=config.model_path, type=config.model_type)

            if config.model_type == "ollama":
                # For Ollama models, just mark as available (they're loaded on-demand)
                self.models[model_name] = config.ollama_name
                self.configs[model_name] = config
                logger.info("Ollama model registered", model=model_name)
                return True

            else:
                # Load HuggingFace transformers model
                return self._load_transformers_model(model_name, config)

        except Exception as e:
            logger.error("Failed to load model", model=model_name, error=str(e))
            return False

    def _load_transformers_model(self, model_name: str, config: ModelConfig) -> bool:
        """Load a HuggingFace transformers model"""
        try:
            # Determine device
            device = self._get_device()

            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                config.tokenizer_path,
                trust_remote_code=True,
                cache_dir="/app/huggingface_cache"
            )

            # Add pad token if it doesn't exist
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            # Load model
            model = AutoModelForCausalLM.from_pretrained(
                config.model_path,
                trust_remote_code=True,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None,
                cache_dir="/app/transformers_cache"
            )

            # Create pipeline
            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                device=0 if device == "cuda" else -1,
                framework="pt"
            )

            self.models[model_name] = pipe
            self.tokenizers[model_name] = tokenizer
            self.configs[model_name] = config

            logger.info("Transformers model loaded successfully",
                       model=model_name,
                       device=device,
                       model_size=f"{sum(p.numel() for p in model.parameters())/1e6:.1f}M params")
            return True

        except Exception as e:
            logger.error("Failed to load transformers model", model=model_name, error=str(e))
            return False

    def _get_device(self) -> str:
        """Determine the best available device"""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():  # Apple Silicon
            return "mps"
        else:
            return "cpu"

    def get_available_models(self) -> List[str]:
        """Get list of available model names"""
        return list(self.available_models.keys())

    def get_loaded_models(self) -> List[str]:
        """Get list of currently loaded model names"""
        return list(self.models.keys())

    async def generate_text(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 50,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """Generate text using specified model"""
        try:
            # Load model if not already loaded
            if model_name not in self.models:
                if not self.load_model(model_name):
                    # Fallback to default model
                    loaded_models = self.get_loaded_models()
                    if not loaded_models:
                        raise Exception("No models available")
                    model_name = loaded_models[0]
                    logger.warning("Using fallback model", fallback=model_name)

            config = self.configs[model_name]

            if config.model_type == "ollama":
                return await self._generate_ollama(
                    model_name, prompt, max_tokens, temperature, top_p, stop_sequences
                )
            else:
                # HuggingFace transformers model
                pipe = self.models[model_name]
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    self._generate_sync,
                    pipe, prompt, max_tokens, temperature, top_p, top_k, stop_sequences
                )
                return result

        except Exception as e:
            logger.error("Failed to generate text",
                        model=model_name,
                        error=str(e),
                        prompt_length=len(prompt))
            raise

    async def _generate_ollama(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """Generate text using Ollama API"""
        try:
            config = self.configs[model_name]
            ollama_model = config.ollama_name

            payload = {
                "model": ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "num_predict": max_tokens
                }
            }

            if stop_sequences:
                payload["options"]["stop"] = stop_sequences

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_base_url}/api/generate",
                    json=payload,
                    timeout=300
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "").strip()
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error: {response.status} - {error_text}")

        except Exception as e:
            logger.error("Ollama generation failed", model=model_name, error=str(e))
            raise

    def _generate_sync(
        self,
        pipe: TextGenerationPipeline,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        stop_sequences: Optional[List[str]]
    ) -> str:
        """Synchronous text generation"""
        try:
            # Generate text
            outputs = pipe(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                do_sample=True,
                num_return_sequences=1,
                pad_token_id=pipe.tokenizer.eos_token_id,
                eos_token_id=pipe.tokenizer.eos_token_id,
                return_full_text=False
            )

            generated_text = outputs[0]['generated_text']

            # Apply stop sequences
            if stop_sequences:
                for stop_seq in stop_sequences:
                    if stop_seq in generated_text:
                        generated_text = generated_text.split(stop_seq)[0]
                        break

            return generated_text.strip()

        except Exception as e:
            logger.error("Sync generation failed", error=str(e))
            return f"Error generating text: {str(e)}"

    async def generate_chat_response(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 100,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50
    ) -> str:
        """Generate chat completion response"""
        try:
            config = self.configs.get(model_name)
            if config and config.model_type == "ollama":
                return await self._generate_ollama_chat(
                    model_name, messages, max_tokens, temperature, top_p
                )
            else:
                # Convert messages to prompt format for transformers models
                prompt = self._messages_to_prompt(messages)

                # Generate response
                response = await self.generate_text(
                    model_name=model_name,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    stop_sequences=["Human:", "Assistant:", "\n\n"]
                )

                return response

        except Exception as e:
            logger.error("Failed to generate chat response",
                        model=model_name, error=str(e))
            raise

    async def _generate_ollama_chat(
        self,
        model_name: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float
    ) -> str:
        """Generate chat response using Ollama chat API"""
        try:
            config = self.configs[model_name]
            ollama_model = config.ollama_name

            payload = {
                "model": ollama_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "num_predict": max_tokens
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_base_url}/api/chat",
                    json=payload,
                    timeout=300
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        message = data.get("message", {})
                        return message.get("content", "").strip()
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama chat API error: {response.status} - {error_text}")

        except Exception as e:
            logger.error("Ollama chat generation failed", model=model_name, error=str(e))
            raise

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert chat messages to prompt format"""
        prompt_parts = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"Human: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        # Add prompt for assistant response
        prompt_parts.append("Assistant:")

        return "\n".join(prompt_parts)

    async def stream_generate_text(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 50,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50
    ) -> AsyncGenerator[str, None]:
        """Stream text generation (simulated streaming)"""
        try:
            # Generate full response
            full_response = await self.generate_text(
                model_name=model_name,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k
            )

            # Stream words with delay
            words = full_response.split()
            for word in words:
                yield f"{word} "
                await asyncio.sleep(0.05)  # Simulate streaming delay

        except Exception as e:
            logger.error("Failed to stream generate", model=model_name, error=str(e))
            yield f"Error: {str(e)}"

# Global model manager instance
model_manager = ModelManager()