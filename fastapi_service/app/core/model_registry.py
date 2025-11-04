# fastapi-service/app/core/model_registry.py
import threading
from typing import Dict, Any, Optional, List
import structlog
import time
import torch
import json
import os
from huggingface_hub import snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer

STATE_FILE = './model_cache/registry_state.json'

class ModelWrapper:
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer

    def generate(self, prompt: str, **gen_kwargs) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        outputs = self.model.generate(**inputs, **gen_kwargs)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

class ModelRegistry:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.models: Dict[str, ModelWrapper] = {}
        self.versions: Dict[str, str] = {}
        self.logger = structlog.get_logger()
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        self._load_state()

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                data = json.load(open(STATE_FILE))
                self.versions = data.get('versions', {})
                self.logger.info("Registry state loaded", count=len(self.versions))
            except Exception as e:
                self.logger.error("Failed to load state", error=str(e))

    def _save_state(self):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({'versions': self.versions}, f)
            self.logger.debug("Registry state saved")
        except Exception as e:
            self.logger.error("Failed to save state", error=str(e))

    def load_model(self,
                   name: str,
                   repo_id: str,
                   version: Optional[str] = None,
                   quant_bits: Optional[int] = None,
                   max_memory: Optional[Dict[str, str]] = None,
                   cache_dir: str = './model_cache') -> None:
        local_dir = snapshot_download(repo_id=repo_id, cache_dir=cache_dir)
        torch_kwargs = {}
        if quant_bits == 4:
            torch_kwargs['load_in_4bit'] = True
        elif quant_bits == 8:
            torch_kwargs['load_in_8bit'] = True
        if max_memory:
            torch_kwargs['device_map'] = 'auto'
            torch_kwargs['max_memory'] = max_memory
        model = AutoModelForCausalLM.from_pretrained(local_dir, **torch_kwargs)
        tokenizer = AutoTokenizer.from_pretrained(local_dir, use_fast=True)
        wrapper = ModelWrapper(model, tokenizer)
        self.models[name] = wrapper
        self.versions[name] = version or 'latest'
        self._save_state()
        self.logger.info("Model loaded", name=name, version=self.versions[name])

    def unload_model(self, name: str) -> None:
        if name in self.models:
            try:
                del self.models[name]
                torch.cuda.empty_cache()
            except Exception:
                pass
        self.versions.pop(name, None)
        self._save_state()
        self.logger.info("Model unloaded", name=name)

    def get_model(self, name: str) -> Optional[ModelWrapper]:
        return self.models.get(name)

    def list_models(self) -> Dict[str, str]:
        return self.versions.copy()

    def rollback(self, name: str, target_version: str) -> None:
        if name not in self.versions:
            raise ValueError(f"No model registered under '{name}'")
        current = self.versions[name]
        self.unload_model(name)
        self.load_model(name, repo_id=name, version=target_version)
        self.logger.info("Model rollback completed", name=name, from_version=current, to_version=target_version)

    def hot_swap(self, name: str, repo_id: str, version: str, **kwargs) -> None:
        temp_name = f"{name}_hot"
        self.load_model(temp_name, repo_id=repo_id, version=version, **kwargs)
        new_wrapper = self.models.pop(temp_name)
        old_wrapper = self.models.get(name)
        self.models[name] = new_wrapper
        self.versions[name] = version
        if old_wrapper:
            del old_wrapper
            torch.cuda.empty_cache()
        self._save_state()
        self.logger.info("Hot-swap successful", name=name, new_version=version)

    def monitor_performance(self, name: str) -> Dict[str, Any]:
        wrapper = self.get_model(name)
        if not wrapper:
            return {}
        start = time.time()
        _ = wrapper.generate("", max_new_tokens=1)
        latency = (time.time() - start) * 1000
        mem = torch.cuda.memory_allocated() / (1024 ** 2) if torch.cuda.is_available() else 0
        metrics = {"latency_ms": latency, "memory_mb": mem}
        self.logger.debug("Performance metrics", name=name, metrics=metrics)
        return metrics

    def allocate_resources(self, name: str, **requirements) -> None:
        self.logger.info("Resource allocation", name=name, requirements=requirements)

    def benchmark_model(self, name: str, prompts: List[str], **gen_kwargs) -> Dict[str, Any]:
        wrapper = self.get_model(name)
        if not wrapper:
            raise ValueError(f"Model '{name}' not loaded")
        times = []
        for prompt in prompts:
            start = time.time()
            _ = wrapper.generate(prompt, **gen_kwargs)
            times.append(time.time() - start)
        avg_latency = sum(times) / len(times) * 1000
        throughput = len(prompts) / sum(times)
        metrics = {"avg_latency_ms": avg_latency, "throughput_qps": throughput}
        self.logger.info("Benchmark completed", name=name, metrics=metrics)
        return metrics
