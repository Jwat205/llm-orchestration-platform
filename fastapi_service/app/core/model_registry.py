from dataclasses import dataclass
from typing import Dict, List

from app.config import settings
from app.core.backends.base import ModelBackend
from app.core.backends.ollama_backend import OllamaBackend

# The in-process Transformers backend lives in app/backends_inactive/transformers/
# — fully wired and importable, but disconnected from the active registry
# while this project focuses on the Ollama backend. To reactivate:
#   from app.backends_inactive.transformers.transformers_backend import TransformersBackend
# and re-add it to _STATIC_MODELS / _backends below.


@dataclass(frozen=True)
class ModelEntry:
    name: str          # picker-facing id, e.g. "llama3.1:8b" or "dialogpt-medium"
    backend: str        # "ollama" | "transformers"
    model_id: str       # id passed to the backend (Ollama tag, or HF repo id)
    label: str = ""      # display name for the picker


# Ollama models are discovered dynamically from the Ollama server.
_STATIC_MODELS: List[ModelEntry] = []

_backends: Dict[str, ModelBackend] = {
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
