"""
Configuration management for Hands-Free Anki.
"""

from dataclasses import dataclass, field, asdict
from typing import Literal
import json
from pathlib import Path

from aqt import mw


LLMProvider = Literal["openai", "anthropic", "ollama", "mistral", "none"]
EmbeddingProvider = Literal["local", "spacy", "openai"]
ScoringMethod = Literal["embedding", "llm", "hybrid"]
TTSProvider = Literal["elevenlabs", "google_cloud",
                      "amazon_polly", "gtts", "offline"]
STTProvider = Literal["elevenlabs", "whisper", "google", "sphinx"]


@dataclass
class TTSConfig:
    """Text-to-Speech configuration."""
    providers: list[TTSProvider] = field(
        default_factory=lambda: [
            "elevenlabs",
            "google_cloud",
            "amazon_polly",
            "gtts",
            "offline",
        ]
    )
    language: str = "en"  # "en" or "de"
    rate: int = 300  # Default rate (words per minute for offline TTS)
    front_rate: int = 100  # Rate for reading front of card
    back_rate: int = 200  # Rate for reading back of card
    read_card_ease: bool = False  # Read out how well the card is known
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # Sarah - reliable voice
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    google_tts_api_key: str = ""
    google_tts_voice: str = ""
    amazon_polly_access_key: str = ""
    amazon_polly_secret_key: str = ""
    amazon_polly_region: str = "us-east-1"
    amazon_polly_voice_id: str = "Joanna"


@dataclass
class STTConfig:
    """Speech-to-Text configuration."""
    provider: STTProvider = "whisper"
    language: str = "en-US"  # "en-US" or "de-DE"
    silence_timeout: float = 0.75  # Seconds of silence before stopping
    min_recording_time: float = 0.5  # Minimum recording duration
    max_recording_time: float = 60.0  # Maximum recording duration
    microphone_index: int | None = None  # None = system default
    # Minimum audio energy to be considered speech (0-4000)
    energy_threshold: int = 1384
    dynamic_threshold: bool = False  # Auto-adjust threshold based on ambient noise
    whisper_model: str = "whisper-large-v3"
    elevenlabs_api_key: str = ""  # Can share with TTS key
    elevenlabs_model_id: str = "scribe_v1"  # ElevenLabs STT model
    enable_google_fallback: bool = True
    enable_sphinx_fallback: bool = True


@dataclass
class OCRConfig:
    """OCR configuration."""
    enabled: bool = True
    engine: Literal["tesseract", "easyocr", "gpt4_vision"] = "gpt4_vision"
    languages: list[str] = field(default_factory=lambda: ["eng", "deu"])
    # User chose to skip OCR (tesseract not installed)
    skipped_by_user: bool = False
    # GPT-4 Vision model (gpt-4o is recommended for best results)
    gpt4_vision_model: str = "gpt-4o"


@dataclass
class ScoringConfig:
    """Answer scoring configuration."""
    method: ScoringMethod = "llm"  # embedding, llm, or hybrid

    # Thresholds for rating (1-4) - slightly lenient to be forgiving
    threshold_4: float = 0.85  # >= 85% = Easy (4)
    threshold_3: float = 0.60  # >= 60% = Good (3)
    threshold_2: float = 0.35  # >= 35% = Hard (2)
    # < 35% = Again (1)

    # For hybrid mode: weight of embedding vs LLM score
    embedding_weight: float = 0.5


@dataclass
class AnnouncementConfig:
    """Rating announcement configuration."""
    enabled: bool = True  # Whether to announce ratings at all

    # Custom phrases for each rating (one per line, random selection)
    # Empty string means use defaults
    phrases_again_en: str = ""  # Rating 1 - Again (English)
    phrases_hard_en: str = ""   # Rating 2 - Hard (English)
    phrases_good_en: str = ""   # Rating 3 - Good (English)
    phrases_easy_en: str = ""   # Rating 4 - Easy (English)

    phrases_again_de: str = ""  # Rating 1 - Nochmal (German)
    phrases_hard_de: str = ""   # Rating 2 - Schwer (German)
    phrases_good_de: str = ""   # Rating 3 - Gut (German)
    phrases_easy_de: str = ""   # Rating 4 - Leicht (German)


@dataclass
class LLMConfig:
    """LLM configuration."""
    provider: LLMProvider = "openai"

    # API Keys (stored separately for security)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    mistral_api_key: str = ""

    # Model settings
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-opus-20240229"
    ollama_model: str = "llama3.2"
    ollama_base_url: str = "http://localhost:11434"
    mistral_model: str = "mistral-small-latest"

    # Prompt customization
    scoring_prompt: str = """You are evaluating a flashcard answer. The user may paraphrase or use different words - focus on whether they understood the concept.

Question/Front: {front}
Expected Answer/Back: {back}
User's Answer: {user_answer}

Rate from 0.0 to 1.0:
- 1.0 = Correct meaning, even if worded differently
- 0.7-0.9 = Mostly correct, minor details missing
- 0.5-0.7 = Partial understanding, key concepts present
- 0.3-0.5 = Some relevant ideas but significant gaps
- 0.0-0.3 = Wrong or irrelevant

IMPORTANT: Accept synonyms, paraphrasing, and equivalent expressions. Judge understanding, not exact wording.

Respond with ONLY a number between 0.0 and 1.0."""


@dataclass
class EmbeddingConfig:
    """Embedding configuration."""
    provider: EmbeddingProvider = "openai"  # API-based by default
    local_model: str = "all-MiniLM-L6-v2"  # Fast, good for similarity
    openai_model: str = "text-embedding-3-small"


@dataclass
class VoiceCommandsConfig:
    """Voice commands configuration."""
    # Comma-separated words that trigger each command
    stop_words: str = "stop,halt,stopp,beenden,aufhören,ende"
    skip_words: str = "skip,überspringen,überspring,auslassen"
    next_words: str = "next,weiter,nächste,nächstes,nächster"
    disable_words: str = "disable,deaktivieren,ausschalten,off,aus"


@dataclass
class DeckSettings:
    """Settings for a single deck."""
    language: str = ""  # Language code (de, en, etc.) - empty means use default
    include_fields: list[str] = field(
        default_factory=list)  # Fields to read (empty = all)

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "include_fields": self.include_fields
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeckSettings":
        return cls(
            language=data.get("language", ""),
            include_fields=data.get("include_fields", [])
        )


@dataclass
class DeckSettingsConfig:
    """Per-deck settings configuration."""
    # Dictionary mapping deck name to DeckSettings
    # Stored as JSON string for dataclass compatibility
    deck_settings: str = "{}"  # JSON dict

    # Default fields to skip when no deck-specific settings
    default_skip_fields: str = "ID,Audio,Sound,Comments,Attribution,Tags,Source,Reference,Notes,Extra"

    def get_settings_for_deck(self, deck_name: str) -> DeckSettings | None:
        """Get settings for a specific deck, or None if not set."""
        try:
            mapping = json.loads(self.deck_settings)
            if deck_name in mapping:
                return DeckSettings.from_dict(mapping[deck_name])
            return None
        except:
            return None

    def get_language_for_deck(self, deck_name: str) -> str | None:
        """Get the language for a specific deck, or None if not set."""
        settings = self.get_settings_for_deck(deck_name)
        return settings.language if settings and settings.language else None

    def get_fields_for_deck(self, deck_name: str) -> list[str] | None:
        """Get the fields to read for a specific deck, or None if not set."""
        settings = self.get_settings_for_deck(deck_name)
        return settings.include_fields if settings and settings.include_fields else None

    def get_default_skip_fields(self) -> list[str]:
        """Get the default fields to skip."""
        return [f.strip() for f in self.default_skip_fields.split(",") if f.strip()]

    def set_settings_for_deck(self, deck_name: str, language: str, include_fields: list[str]):
        """Set settings for a specific deck."""
        try:
            mapping = json.loads(self.deck_settings)
        except:
            mapping = {}
        mapping[deck_name] = DeckSettings(
            language=language, include_fields=include_fields).to_dict()
        self.deck_settings = json.dumps(mapping)

    def remove_deck(self, deck_name: str):
        """Remove a deck from settings."""
        try:
            mapping = json.loads(self.deck_settings)
            if deck_name in mapping:
                del mapping[deck_name]
                self.deck_settings = json.dumps(mapping)
        except:
            pass

    def get_all(self) -> dict[str, DeckSettings]:
        """Get all deck settings."""
        try:
            mapping = json.loads(self.deck_settings)
            return {name: DeckSettings.from_dict(data) for name, data in mapping.items()}
        except:
            return {}


@dataclass
class DisplayConfig:
    """Display/UI configuration."""
    show_debug_console: bool = False  # Show debug terminal panel during review
    show_user_answer: bool = True  # Show recognized speech overlay
    show_rating_indicator: bool = True  # Show rating visual feedback
    show_recording_indicator: bool = True  # Show recording status
    show_audio_level_monitor: bool = False  # Show audio level debug panel


@dataclass
class Config:
    """Main configuration class."""
    enabled: bool = False
    debug_mode: bool = False  # Legacy - mapped to display.show_audio_level_monitor
    show_debug_panel: bool = False  # Legacy - mapped to display.show_debug_console

    display: DisplayConfig = field(default_factory=DisplayConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    announcement: AnnouncementConfig = field(
        default_factory=AnnouncementConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    voice_commands: VoiceCommandsConfig = field(
        default_factory=VoiceCommandsConfig)
    deck_settings: DeckSettingsConfig = field(
        default_factory=DeckSettingsConfig)

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the path to the config file."""
        addon_dir = Path(__file__).parent
        return addon_dir / "user_config.json"

    @classmethod
    def get_cache_dir(cls) -> Path:
        """Get the cache directory for OCR results."""
        addon_dir = Path(__file__).parent
        cache_dir = addon_dir / "cache"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get the path to the default config file."""
        addon_dir = Path(__file__).parent
        return addon_dir / "default_config.json"

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file."""
        config_path = cls.get_config_path()
        default_path = cls.get_default_config_path()

        # Try user config first
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                return cls._from_dict(data)
            except Exception as e:
                print(f"Error loading user config: {e}")

        # Fall back to default config
        if default_path.exists():
            try:
                with open(default_path, "r") as f:
                    data = json.load(f)
                return cls._from_dict(data)
            except Exception as e:
                print(f"Error loading default config: {e}")

        return cls()

    def save(self):
        """Save configuration to file."""
        config_path = self.get_config_path()
        with open(config_path, "w") as f:
            json.dump(self._to_dict(), f, indent=2)

    def _to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "enabled": self.enabled,
            "debug_mode": self.debug_mode,
            "show_debug_panel": self.show_debug_panel,
            "display": asdict(self.display),
            "tts": asdict(self.tts),
            "stt": asdict(self.stt),
            "ocr": asdict(self.ocr),
            "scoring": asdict(self.scoring),
            "announcement": asdict(self.announcement),
            "llm": asdict(self.llm),
            "embedding": asdict(self.embedding),
            "voice_commands": asdict(self.voice_commands),
            "deck_settings": asdict(self.deck_settings),
        }

    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        """Create config from dictionary."""
        config = cls()

        if "enabled" in data:
            config.enabled = data["enabled"]
        
        # Load display config first (new format)
        if "display" in data:
            config.display = DisplayConfig(**data["display"])
        else:
            # Migrate from legacy fields if no display section exists
            if "debug_mode" in data:
                config.debug_mode = data["debug_mode"]
                config.display.show_audio_level_monitor = data["debug_mode"]
            if "show_debug_panel" in data:
                config.show_debug_panel = data["show_debug_panel"]
                config.display.show_debug_console = data["show_debug_panel"]
        
        if "tts" in data:
            # Filter out old fields that no longer exist
            tts_data = {k: v for k, v in data["tts"].items()
                        if k not in ("skip_fields", "include_fields")}
            config.tts = TTSConfig(**tts_data)
        if "stt" in data:
            config.stt = STTConfig(**data["stt"])
        if "ocr" in data:
            config.ocr = OCRConfig(**data["ocr"])
        if "scoring" in data:
            config.scoring = ScoringConfig(**data["scoring"])
        if "announcement" in data:
            config.announcement = AnnouncementConfig(**data["announcement"])
        if "llm" in data:
            config.llm = LLMConfig(**data["llm"])
        if "embedding" in data:
            config.embedding = EmbeddingConfig(**data["embedding"])
        if "voice_commands" in data:
            config.voice_commands = VoiceCommandsConfig(
                **data["voice_commands"])
        if "deck_settings" in data:
            config.deck_settings = DeckSettingsConfig(**data["deck_settings"])
        # Migration: convert old deck_languages to new deck_settings
        elif "deck_languages" in data:
            old_data = data["deck_languages"]
            if "deck_languages" in old_data:
                try:
                    import json as json_mod
                    old_mapping = json_mod.loads(old_data["deck_languages"])
                    # Convert old format {deck: lang} to new format {deck: {language, include_fields}}
                    new_mapping = {}
                    for deck_name, lang in old_mapping.items():
                        new_mapping[deck_name] = {
                            "language": lang, "include_fields": []}
                    config.deck_settings = DeckSettingsConfig(
                        deck_settings=json_mod.dumps(new_mapping)
                    )
                except:
                    pass

        return config
