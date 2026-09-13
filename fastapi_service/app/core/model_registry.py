from dataclasses import dataclass
from typing import Dict, List

from app.config import settings
from app.core.backends.base import ModelBackend
from app.core.backends.ollama_backend import OllamaBackend
from app.core.backends.transformers_backend import TransformersBackend


@dataclass(frozen=True)
class ModelEntry:
    name: str          # picker-facing id, e.g. "llama3.1:8b" or "dialogpt-medium"
    backend: str        # "ollama" | "transformers"
    model_id: str       # id passed to the backend (Ollama tag, or HF repo id)
    label: str = ""      # display name for the picker


# Statically known transformers models (loaded in-process on first use).
# Ollama models are discovered dynamically from the Ollama server on top of
# this, so companies can add new local models with `ollama pull` alone.
_STATIC_MODELS: List[ModelEntry] = [
    ModelEntry(
        name=settings.transformers_default_model,
        backend="transformers",
        model_id=settings.transformers_default_model,
        label=f"{settings.transformers_default_model} (local, in-process)",
    ),
]

_backends: Dict[str, ModelBackend] = {
    "transformers": TransformersBackend(),
    "ollama": OllamaBackend(),
}


def get_backend(backend_name: str) -> ModelBackend:
    try:
        return _backends[backend_name]
    except KeyError:
        raise ValueError(f"Unknown backend '{backend_name}'")


async def list_models() -> List[ModelEntry]:
    models = list(_STATIC_MODELS)
    ollama: OllamaBackend = _backends["ollama"]
    for tag in await ollama.list_models():
        models.append(ModelEntry(name=tag, backend="ollama", model_id=tag, label=tag))
    return models


async def resolve_model(name: str) -> ModelEntry:
    """
    Look up a picker-facing model name. Falls back to treating the name as
    an Ollama tag directly, since Ollama models don't need to be registered
    ahead of time — just pulled on the server.
    """
    for entry in await list_models():
        if entry.name == name:
            return entry
    return ModelEntry(name=name, backend="ollama", model_id=name, label=name)
