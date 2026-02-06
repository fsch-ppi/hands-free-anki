"""
Services package for Hands-Free Anki.

Services are imported lazily to avoid loading heavy dependencies
at Anki startup time.
"""


def __getattr__(name: str):
    """Lazy import of services."""
    if name == "TTSService":
        from .tts import TTSService
        return TTSService
    elif name == "STTService":
        from .stt import STTService
        return STTService
    elif name == "OCRService":
        from .ocr import OCRService
        return OCRService
    elif name == "ScoringService":
        from .scoring import ScoringService
        return ScoringService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["TTSService", "STTService", "OCRService", "ScoringService"]
