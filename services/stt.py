"""
Speech-to-Text service with Voice Activity Detection and multi-provider support.
"""

import io
import os
import threading
import time
from typing import Optional, Callable

import requests

from ..config import STTConfig, LLMConfig
from ..utils import is_online


class STTService:
    """
    Speech-to-Text service with Voice Activity Detection (VAD).
    Uses online recognition when available, offline when not.
    """

    def __init__(self, config: STTConfig, llm_config: Optional[LLMConfig] = None):
        self.config = config
        self._llm_config = llm_config
        self._recognizer = None
        self._microphone = None
        self._is_recording = False
        self._stop_event = threading.Event()
        self._openai_client = None
        self._openai_api_key = None
        self._debug_logger = None  # Optional external logger

        if llm_config and llm_config.openai_api_key:
            self._openai_api_key = llm_config.openai_api_key
        else:
            self._openai_api_key = os.environ.get("OPENAI_API_KEY")

    def set_debug_logger(self, logger):
        """Set an external debug logger function."""
        self._debug_logger = logger

    def _log(self, message: str, level: str = "stt"):
        """Log a debug message."""
        # Log to file
        from ..utils.logger import log_stt, log_error, log_warning
        if level == "error":
            log_error(f"[STT] {message}")
        elif level == "warning":
            log_warning(f"[STT] {message}")
        else:
            log_stt(message)

        # Log to debug panel if available
        if self._debug_logger:
            self._debug_logger(message, level)
        print(f"[STT {level.upper()}] {message}")

    def _init_recognizer(self):
        """Initialize the speech recognizer."""
        if self._recognizer is None:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()

            # Adjust for ambient noise sensitivity using config values
            self._recognizer.energy_threshold = self.config.energy_threshold
            self._recognizer.dynamic_energy_threshold = self.config.dynamic_threshold
            self._recognizer.pause_threshold = self.config.silence_timeout

        return self._recognizer

    def update_threshold(self, energy_threshold: int, dynamic: bool):
        """Update the energy threshold settings."""
        if self._recognizer:
            self._recognizer.energy_threshold = energy_threshold
            self._recognizer.dynamic_energy_threshold = dynamic

    def calibrate(self, duration: float = 3.0, on_level: Optional[Callable[[float], None]] = None) -> tuple[int, int]:
        """
        Calibrate the microphone by measuring ambient noise and speech levels.

        Args:
            duration: How long to listen for speech (seconds)
            on_level: Callback for real-time audio level updates (0.0-1.0)

        Returns:
            Tuple of (ambient_level, speech_level)
        """
        import speech_recognition as sr
        import audioop

        recognizer = self._init_recognizer()
        ambient_level = 0
        speech_level = 0

        try:
            with self._get_microphone() as source:
                # Measure ambient noise first
                ambient_level = int(recognizer.energy_threshold)
                recognizer.adjust_for_ambient_noise(source, duration=1.0)
                ambient_level = int(recognizer.energy_threshold)

                # Now record speech and find peak level
                sample_rate = source.SAMPLE_RATE
                chunk_size = source.CHUNK

                # Record for specified duration
                frames = []
                max_energy = 0

                import time
                start_time = time.time()

                while time.time() - start_time < duration:
                    try:
                        buffer = source.stream.read(chunk_size)
                        if buffer:
                            # Calculate RMS energy
                            energy = audioop.rms(buffer, source.SAMPLE_WIDTH)
                            if energy > max_energy:
                                max_energy = energy

                            # Report normalized level (0-1 scale, capped at 4000)
                            if on_level:
                                normalized = min(energy / 4000.0, 1.0)
                                on_level(normalized)
                    except Exception:
                        break

                speech_level = max_energy

        except Exception as e:
            print(f"Calibration error: {e}")

        return ambient_level, speech_level

    def get_audio_level(self, duration: float = 0.1) -> int:
        """
        Get current audio level from microphone.

        Args:
            duration: How long to sample (seconds)

        Returns:
            Current audio energy level
        """
        import audioop

        try:
            with self._get_microphone() as source:
                chunk_size = source.CHUNK
                buffer = source.stream.read(chunk_size)
                if buffer:
                    return audioop.rms(buffer, source.SAMPLE_WIDTH)
        except Exception as e:
            print(f"Error getting audio level: {e}")

        return 0

    def _get_microphone(self):
        """Get or create microphone instance."""
        import speech_recognition as sr

        # Use specific device if configured, otherwise system default
        device_index = self.config.microphone_index
        return sr.Microphone(device_index=device_index)

    @staticmethod
    def list_microphones() -> list[tuple[int, str]]:
        """
        List available microphone devices.

        Returns:
            List of (index, name) tuples for each microphone
        """
        try:
            import speech_recognition as sr
            mic_list = sr.Microphone.list_microphone_names()
            return [(i, name) for i, name in enumerate(mic_list)]
        except Exception as e:
            print(f"Error listing microphones: {e}")
            return []

    def listen_and_recognize(
        self,
        on_recording_start: Optional[Callable[[], None]] = None,
        on_recording_end: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """
        Listen for speech and return recognized text.

        Uses Voice Activity Detection to determine when the user
        has finished speaking.

        Args:
            on_recording_start: Callback when recording starts
            on_recording_end: Callback when recording ends

        Returns:
            Recognized text or None if recognition failed
        """
        import speech_recognition as sr

        recognizer = self._init_recognizer()

        try:
            with self._get_microphone() as source:
                # Adjust for ambient noise
                recognizer.adjust_for_ambient_noise(source, duration=0.5)

                if on_recording_start:
                    on_recording_start()

                self._is_recording = True
                self._stop_event.clear()

                # Listen with timeout
                try:
                    audio = recognizer.listen(
                        source,
                        timeout=5.0,  # Wait up to 5 seconds for speech to start
                        phrase_time_limit=self.config.max_recording_time
                    )
                except sr.WaitTimeoutError:
                    print("No speech detected within timeout")
                    return None
                finally:
                    self._is_recording = False
                    if on_recording_end:
                        on_recording_end()

            # Try to recognize the speech
            return self._recognize_audio(audio)

        except Exception as e:
            print(f"Recording error: {e}")
            self._is_recording = False
            if on_recording_end:
                on_recording_end()
            return None

    def _recognize_audio(self, audio) -> Optional[str]:
        """Recognize speech from audio data using configured providers."""
        import speech_recognition as sr

        recognizer = self._init_recognizer()
        lang = self._map_language_code(self.config.language)

        chain = self._build_provider_chain()
        self._log(f"Provider chain: {chain}")

        for provider in chain:
            if provider == "elevenlabs":
                if not self._can_use_elevenlabs():
                    self._log(f"elevenlabs: No API key configured", "warning")
                    continue
                try:
                    self._log(f"Trying ElevenLabs Scribe...")
                    text = self._recognize_with_elevenlabs(audio)
                    if text:
                        self._log(f"ElevenLabs: SUCCESS", "success")
                        return text
                except Exception as e:
                    self._log(f"ElevenLabs FAILED: {e}", "error")
            elif provider == "whisper":
                if not self._can_use_whisper():
                    self._log(
                        f"whisper: No OpenAI API key configured", "warning")
                    continue
                try:
                    self._log(
                        f"Trying OpenAI Whisper (model: {self.config.whisper_model})...")
                    text = self._recognize_with_whisper(audio)
                    if text:
                        self._log(f"Whisper: SUCCESS", "success")
                        return text
                except Exception as e:
                    self._log(f"Whisper FAILED: {e}", "error")
            elif provider == "google":
                if not self._can_use_google():
                    self._log(f"google: Offline, skipping", "warning")
                    continue
                try:
                    self._log(f"Trying Google Speech...")
                    text = recognizer.recognize_google(audio, language=lang)
                    if text:
                        self._log(f"Google: SUCCESS", "success")
                        return text
                except sr.UnknownValueError:
                    self._log(f"Google: Could not understand audio", "warning")
                except sr.RequestError as e:
                    self._log(f"Google FAILED: {e}", "error")
            elif provider == "sphinx":
                if not self._can_use_sphinx(lang):
                    self._log(
                        f"sphinx: Language not supported (need English)", "warning")
                    continue
                try:
                    self._log(f"Trying CMU Sphinx (offline)...")
                    text = recognizer.recognize_sphinx(audio)
                    if text:
                        self._log(f"Sphinx: SUCCESS", "success")
                        return text
                except sr.UnknownValueError:
                    self._log(f"Sphinx: Could not understand audio", "warning")
                except sr.RequestError as e:
                    self._log(f"Sphinx FAILED: {e}", "error")
                except Exception as e:
                    print(f"Offline recognition not available: {e}")

        return None

    def _build_provider_chain(self) -> list[str]:
        """Create ordered list of STT providers to attempt."""
        chain: list[str] = []

        def add(provider: str):
            if provider not in chain:
                chain.append(provider)

        add(self.config.provider)
        if self.config.enable_google_fallback:
            add("google")
        if self.config.enable_sphinx_fallback:
            add("sphinx")
        return chain

    def _map_language_code(self, configured: str) -> str:
        """Normalize language code for provider compatibility."""
        lang_map = {
            "en-US": "en-US",
            "en": "en-US",
            "de-DE": "de-DE",
            "de": "de-DE",
        }
        return lang_map.get(configured, "en-US")

    def _can_use_google(self) -> bool:
        return is_online()

    def _can_use_sphinx(self, lang: str) -> bool:
        return lang.startswith("en")

    def _can_use_whisper(self) -> bool:
        if not is_online():
            return False
        if not self._openai_api_key:
            self._openai_api_key = os.environ.get("OPENAI_API_KEY")
        return bool(self._openai_api_key)

    def _get_openai_client(self):
        """Lazily construct OpenAI client."""
        if not self._can_use_whisper():
            return None

        if self._openai_client is None:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self._openai_api_key)
            except Exception as e:
                print(f"Could not initialize OpenAI client: {e}")
                self._openai_client = None
        return self._openai_client

    def _recognize_with_whisper(self, audio) -> Optional[str]:
        """Use OpenAI Whisper Large V3 for transcription."""
        client = self._get_openai_client()
        if client is None:
            return None

        wav_bytes = audio.get_wav_data()
        buffer = io.BytesIO(wav_bytes)
        buffer.name = "speech.wav"

        response = client.audio.transcriptions.create(
            model=self.config.whisper_model,
            file=buffer,
            language=self.config.language.split("-")[0]
        )

        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text.strip()
        return None

    def _can_use_elevenlabs(self) -> bool:
        """Check if ElevenLabs STT is available."""
        if not is_online():
            return False
        return bool(self.config.elevenlabs_api_key)

    def _recognize_with_elevenlabs(self, audio) -> Optional[str]:
        """
        Use ElevenLabs Scribe for speech-to-text.

        API docs: https://elevenlabs.io/docs/api-reference/speech-to-text
        """
        api_key = self.config.elevenlabs_api_key
        if not api_key:
            return None

        # Get audio as WAV bytes
        wav_bytes = audio.get_wav_data()

        # ElevenLabs STT endpoint
        url = "https://api.elevenlabs.io/v1/speech-to-text"

        headers = {
            "xi-api-key": api_key,
        }

        # Prepare multipart form data
        files = {
            "audio": ("speech.wav", wav_bytes, "audio/wav"),
        }

        data = {
            "model_id": self.config.elevenlabs_model_id or "scribe_v1",
        }

        # Add language hint if configured
        lang = self.config.language.split("-")[0]  # e.g., "en-US" -> "en"
        if lang:
            data["language_code"] = lang

        try:
            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()

            # Extract transcription text
            text = result.get("text", "")
            if isinstance(text, str) and text.strip():
                return text.strip()

        except requests.exceptions.RequestException as e:
            print(f"ElevenLabs STT request error: {e}")
        except Exception as e:
            print(f"ElevenLabs STT error: {e}")

        return None

    def stop_recording(self):
        """Stop any ongoing recording."""
        self._stop_event.set()
        self._is_recording = False

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    def cleanup(self):
        """Clean up resources."""
        self.stop_recording()
        self._recognizer = None
