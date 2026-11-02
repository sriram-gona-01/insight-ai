"""Text embeddings with normalized vectors. The model loads once per process."""

from functools import cached_property, lru_cache
from typing import Any, Protocol


class TextEmbedder(Protocol):
    def count_tokens(self, text: str) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    import torch

    return "mps" if torch.backends.mps.is_available() else "cpu"


class SentenceTransformerEmbedder:
    """Loads the model on first use, so skipped and rejected files don't pay for it."""

    def __init__(self, model_name: str, revision: str, dim: int, device: str) -> None:
        self._model_name = model_name
        self._revision = revision
        self._dim = dim
        self._device = device

    @cached_property
    def _model(self) -> Any:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            self._model_name, revision=self._revision, device=_resolve_device(self._device)
        )
        actual = model.get_embedding_dimension()
        if actual != self._dim:
            raise ValueError(
                f"{self._model_name} produces {actual} dims, but EMBEDDING_DIM is {self._dim}"
            )
        return model

    def count_tokens(self, text: str) -> int:
        return len(self._model.tokenizer.encode(text, add_special_tokens=False, verbose=False))

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vectors.tolist()


@lru_cache(maxsize=1)
def get_text_embedder(
    model_name: str, revision: str, dim: int, device: str
) -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder(model_name, revision, dim, device)
