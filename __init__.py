"""Russian text normalization library."""

try:
    from .options import NormalizeOptions
    from .pipeline import Normalizer, normalize, preprocess_text
except ImportError:  # pragma: no cover - supports direct file import during test collection
    from ru_normalizr.options import NormalizeOptions
    from ru_normalizr.pipeline import Normalizer, normalize, preprocess_text

__all__ = ["NormalizeOptions", "Normalizer", "normalize", "preprocess_text"]
__version__ = "0.2.0"
