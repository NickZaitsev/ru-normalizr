from __future__ import annotations

from collections.abc import Iterable

from .normalizer import PipelineNormalizer, preprocess_text
from .options import NormalizeOptions


class Normalizer:
    """Normalization-only facade for Russian text."""

    def __init__(self, options: NormalizeOptions | None = None) -> None:
        self.options = options or NormalizeOptions()
        self._normalizer = PipelineNormalizer(self.options)

    def normalize(self, text: str) -> str:
        return self._normalizer.normalize_text(text)

    def normalize_batch(self, texts: Iterable[str]) -> list[str]:
        return [self.normalize(text) for text in texts]

    def run_stage(self, stage: str, text: str) -> str:
        return self._normalizer.run_stage(stage, text)


def normalize(text: str, options: NormalizeOptions | None = None) -> str:
    return Normalizer(options).normalize(text)


__all__ = ["Normalizer", "normalize", "preprocess_text"]
