"""GlyphMark — text watermarking over ASCII/Unicode channels.

Every feature is exposed twice: once through the non-interactive CLI
(`glyphmark ...`) and once through the Flask web UI / JSON API (`glyphmark serve`).
"""

from .analysis import detect, inspect_text
from .codec import (
    CapacityError,
    DecodeResult,
    EncodeResult,
    GlyphMarkError,
    NoPayloadError,
    decode,
    encode,
    roundtrip_ok,
)
from .frames import FrameError
from .sanitize import DEFAULT_PIPELINE, STAGES, sanitize, stage_docs
from .schemes import SCHEMES, Scheme, get_scheme, scheme_ids

__version__ = "0.1.0"

__all__ = [
    "SCHEMES",
    "Scheme",
    "get_scheme",
    "scheme_ids",
    "FrameError",
    "CapacityError",
    "DecodeResult",
    "EncodeResult",
    "GlyphMarkError",
    "NoPayloadError",
    "decode",
    "encode",
    "roundtrip_ok",
    "detect",
    "inspect_text",
    "STAGES",
    "DEFAULT_PIPELINE",
    "stage_docs",
    "sanitize",
    "__version__",
]
