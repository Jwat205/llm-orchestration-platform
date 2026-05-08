import threading
import os
import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from app.models.chat import ChatCompletionResponse, ChatCompletionChoice, ChatCompletionChunk, Usage


class ModelManager:
    """
    Singleton manager for loading/swapping models and running inference (sync & streaming).
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._load_default()
        return cls._instance


    def _load_default(self):
        """
        Load the default model from DEFAULT_MODEL env var (or fallback).
        """
        self.model_name = os.getenv("DEFAULT_MODEL", "microsoft/DialoGPT-medium")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load tokenizer & model onto the right device
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = (
            AutoModelForCausalLM.from_pretrained(self.model_name)
            .to(self.device)
        )

    def swap_model(self, new_model_name: str):
        """
        Swap in a different HuggingFace-style model at runtime.
        """
        self.model_name = new_model_name
        self._load_default()

    def available_models(self) -> list[str]:
        """
        List currently loaded (or supported) models.
        """
        return [self.model_name]
    
    def load_model(self, model_name: str):
        """
        Loads a new model and tokenizer by name.
        """
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name).to(self.device)


    async def generate_completion(self, payload: "ChatCompletionRequest") -> ChatCompletionResponse:
        """
        Produce a single, batched completion matching OpenAI’s format.
        """
        prompt = payload.messages[-1].content
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=payload.max_tokens,
            temperature=payload.temperature,
            do_sample=True
        )
        text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)

        # Here we simply wrap it into the OpenAI-style response
        choice = ChatCompletionChoice(
            index=0,
            message={"role": "assistant", "content": text},
            finish_reason="stop"
        )
        usage = Usage(
            prompt_tokens=inputs.input_ids.shape[-1],
            completion_tokens=output_ids.shape[-1] - inputs.input_ids.shape[-1],
            total_tokens=output_ids.shape[-1]
        )
        return ChatCompletionResponse(
            id="local-chatcmpl-1",
            object="chat.completion",
            created=int(time.time()),
            model=self.model_name,
            choices=[choice],
            usage=usage
        )

    async def generate_stream(self, payload: "ChatCompletionRequest") -> "AsyncGenerator[ChatCompletionChunk, None]":
        """
        Stub streaming: yields ChatCompletionChunk for each token.
        """
        prompt = payload.messages[-1].content
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)

        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=payload.max_tokens,
            temperature=payload.temperature,
            do_sample=True
        )
        text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
        tokens = text.split()

        for idx, tk in enumerate(tokens):
            yield ChatCompletionChunk(
                id="local-stream-1",
                object="chat.completion.chunk",
                index=idx,
                delta={"role": "assistant", "content": tk + (" " if idx < len(tokens)-1 else "")},
                finish_reason=None
            )
        # final “[DONE]” is emitted by the endpoint itself
