"""Text-to-Speech service supporting multiple online providers with fallbacks."""

import base64
import hashlib
import hmac
import json
import os
import tempfile
import threading
from datetime import datetime

import requests

from ..config import TTSConfig


class TTSService:
    """Text-to-Speech service that tries preferred providers before offline fallback."""

    def __init__(self, config: TTSConfig):
        self.config = config
        self._pyttsx3_engine = None
        self._init_lock = threading.Lock()
        self._debug_logger = None  # Optional external logger
        self._current_rate = config.rate  # Current speaking rate
        self._current_language = config.language  # Current language
        self._stop_requested = False  # Flag to stop current speech

    def set_debug_logger(self, logger):
        """Set an external debug logger function."""
        self._debug_logger = logger

    def set_rate(self, rate: int):
        """Set the speaking rate for next speech."""
        self._current_rate = rate

    def set_language(self, language: str):
        """Set the language for next speech."""
        self._current_language = language

    def request_stop(self):
        """Request to stop current speech."""
        self._stop_requested = True

    def _log(self, message: str, level: str = "tts"):
        """Log a debug message."""
        # Log to file
        from ..utils.logger import log_tts, log_error, log_warning
        if level == "error":
            log_error(f"[TTS] {message}")
        elif level == "warning":
            log_warning(f"[TTS] {message}")
        else:
            log_tts(message)

        # Log to debug panel if available
        if self._debug_logger:
            self._debug_logger(message, level)
        print(f"[TTS {level.upper()}] {message}")

    def _get_offline_engine(self):
        """Lazily initialize pyttsx3 engine."""
        if self._pyttsx3_engine is None:
            with self._init_lock:
                if self._pyttsx3_engine is None:
                    import pyttsx3
                    self._pyttsx3_engine = pyttsx3.init()
                    self._pyttsx3_engine.setProperty('rate', self.config.rate)

                    # Try to set voice based on language
                    voices = self._pyttsx3_engine.getProperty('voices')
                    lang_code = "german" if self.config.language == "de" else "english"

                    for voice in voices:
                        if lang_code in voice.name.lower() or lang_code in str(voice.languages).lower():
                            self._pyttsx3_engine.setProperty('voice', voice.id)
                            break

        return self._pyttsx3_engine

    def speak(self, text: str, blocking: bool = True) -> bool:
        """
        Speak the given text.

        Args:
            text: The text to speak
            blocking: Whether to block until speech is complete

        Returns:
            True if successful, False otherwise
        """
        if not text or not text.strip():
            return True

        # Reset stop flag
        self._stop_requested = False

        text = self._clean_html(text)

        # Debug: show provider chain
        chain = self._provider_chain()
        self._log(f"Provider chain: {chain}")

        for provider in chain:
            if self._stop_requested:
                self._log("Speech interrupted by user", "warning")
                return False

            handler = getattr(self, f"_speak_{provider}", None)
            if handler is None:
                self._log(f"{provider}: No handler found", "warning")
                continue
            try:
                self._log(f"Trying {provider}...")
                if handler(text, blocking):
                    self._log(f"{provider}: SUCCESS", "success")
                    return True
                else:
                    self._log(
                        f"{provider}: No credentials or returned False", "warning")
            except Exception as e:
                self._log(f"{provider} FAILED: {e}", "error")

        self._log("All providers failed, using offline fallback", "warning")
        return self._speak_offline(text, blocking)

    def _provider_chain(self) -> list[str]:
        """Return ordered provider list with offline safety net."""
        chain = [p for p in self.config.providers if p in {
            "elevenlabs", "google_cloud", "amazon_polly", "gtts", "offline"
        }]
        if "offline" not in chain:
            chain.append("offline")
        return chain

    def _extract_voice_id(self, voice_input: str) -> str:
        """
        Extract ElevenLabs voice ID from various input formats:
        - Direct voice ID: "7eVMgwCnXydb3CikjV7a"
        - Voice name: "sarah", "rachel"
        - Full URL: "https://elevenlabs.io/app/voice-library?voice=7eVMgwCnXydb3CikjV7a:hash:Name"
        - Voice parameter: "7eVMgwCnXydb3CikjV7a:hash:Name"
        """
        import re
        from urllib.parse import urlparse, parse_qs, unquote

        voice_input = voice_input.strip()

        # If it's a URL, extract the voice parameter
        if voice_input.startswith("http"):
            try:
                parsed = urlparse(voice_input)
                query_params = parse_qs(parsed.query)
                if "voice" in query_params:
                    voice_input = unquote(query_params["voice"][0])
            except Exception:
                pass

        # If it contains colons (voice library format: id:hash:name)
        if ":" in voice_input:
            # The voice ID is the first part before the colon
            voice_id = voice_input.split(":")[0]
            return voice_id

        # Check if it's a known voice name
        voice_name_to_id = {
            # Current premade voices
            "roger": "CwhRBWXzGAHq8TQ4Fs17",
            "sarah": "EXAVITQu4vr4xnSDxMaL",
            "laura": "FGY2WhTYpPnrIDTdsKH5",
            "charlie": "IKne3meq5aSn9XLyUdCD",
            "george": "JBFqnCBsd6RMkjVDRZzb",
            "callum": "N2lVS1w4EtoT3dr4eOWO",
            "river": "SAz9YHcvj6GT2YYXdXww",
            "liam": "TX3LPaxmHKxFdv7VOQHJ",
            "alice": "Xb7hH8MSUJpSbSDYk0k2",
            "matilda": "XrExE9yKIg1WjnnlVkGX",
            "will": "bIHbv24MWmeRgasZH58o",
            "jessica": "cgSgspJ2msm6clMCkdW9",
            "eric": "cjVigY5qzO86Huf0OWal",
            "chris": "iP95p4xoKVk53GoZ742B",
            "brian": "nPczCjzI2devNBz1zQrb",
            "daniel": "onwK4e9ZLuTAKqWW03F9",
            "lily": "pFZP5JQG7iQjIQuC4Bku",
            "bill": "pqHfZKP75CvOlQylNhV4",
            "adam": "pNInz6obpgDQGcFmaJgB",
            "rachel": "21m00Tcm4TlvDq8ikWAM",
            "lea": "7eVMgwCnXydb3CikjV7a",
        }

        if voice_input.lower() in voice_name_to_id:
            return voice_name_to_id[voice_input.lower()]

        # Otherwise assume it's already a voice ID
        return voice_input

    def _speak_elevenlabs(self, text: str, blocking: bool) -> bool:
        if not self.config.elevenlabs_api_key:
            return False

        # Extract voice ID from URL, name, or direct ID
        voice_input = self.config.elevenlabs_voice_id or "EXAVITQu4vr4xnSDxMaL"
        voice_id = self._extract_voice_id(voice_input)

        model_id = self.config.elevenlabs_model_id or "eleven_multilingual_v2"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "xi-api-key": self.config.elevenlabs_api_key,
            "accept": "audio/mpeg",
            "content-type": "application/json",
        }

        # Convert rate (default 150) to ElevenLabs speed (0.5-2.0, default 1.0)
        # Rate 150 = 1.0x, Rate 300 = 2.0x, Rate 75 = 0.5x
        speed = max(0.5, min(2.0, self._current_rate / 150))

        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "speed": speed
            }
        }

        response = requests.post(url, headers=headers,
                                 json=payload, timeout=30)
        response.raise_for_status()

        return self._play_audio_bytes(response.content, blocking, suffix=".mp3")

    def _speak_google_cloud(self, text: str, blocking: bool) -> bool:
        api_key = self.config.google_tts_api_key
        if not api_key:
            return False

        language_code = self._language_to_google_code()
        voice_name = self.config.google_tts_voice or f"{language_code}-Standard-B"
        speaking_rate = max(0.25, min(4.0, self._current_rate / 150))

        payload = {
            "input": {"text": text},
            "voice": {"languageCode": language_code, "name": voice_name},
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": speaking_rate,
            },
        }

        params = {"key": api_key}
        response = requests.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            params=params,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        audio_content = data.get("audioContent")
        if not audio_content:
            raise RuntimeError("Google Cloud TTS did not return audio content")

        audio_bytes = base64.b64decode(audio_content)
        return self._play_audio_bytes(audio_bytes, blocking, suffix=".mp3")

    def _speak_amazon_polly(self, text: str, blocking: bool) -> bool:
        access_key = self.config.amazon_polly_access_key
        secret_key = self.config.amazon_polly_secret_key
        region = self.config.amazon_polly_region or "us-east-1"

        if not access_key or not secret_key:
            return False

        host = f"polly.{region}.amazonaws.com"
        endpoint = f"https://{host}/v1/speech"
        amz_target = "Polly_20161031.SynthesizeSpeech"

        language_code = self._language_to_polly_code()
        payload_dict = {
            "Text": text,
            "OutputFormat": "mp3",
            "VoiceId": self.config.amazon_polly_voice_id or "Joanna",
        }
        if language_code:
            payload_dict["LanguageCode"] = language_code

        payload = json.dumps(payload_dict)
        current_time = datetime.utcnow()
        amz_date = current_time.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = current_time.strftime("%Y%m%d")

        canonical_uri = "/v1/speech"
        canonical_querystring = ""
        canonical_headers = (
            f"content-type:application/json\n"
            f"host:{host}\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-target:{amz_target}\n"
        )
        signed_headers = "content-type;host;x-amz-date;x-amz-target"
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = "\n".join([
            "POST",
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ])

        credential_scope = f"{date_stamp}/{region}/polly/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ])

        signing_key = self._get_aws_signature_key(
            secret_key, date_stamp, region, "polly")
        signature = hmac.new(signing_key, string_to_sign.encode(
            "utf-8"), hashlib.sha256).hexdigest()

        authorization_header = (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers = {
            "Content-Type": "application/json",
            "X-Amz-Date": amz_date,
            "X-Amz-Target": amz_target,
            "Authorization": authorization_header,
            "Accept": "audio/mpeg",
        }

        response = requests.post(
            endpoint, data=payload, headers=headers, timeout=30)
        response.raise_for_status()

        return self._play_audio_bytes(response.content, blocking, suffix=".mp3")

    def _speak_gtts(self, text: str, blocking: bool) -> bool:
        from gtts import gTTS

        lang = "de" if self.config.language == "de" else "en"
        tts = gTTS(text=text, lang=lang)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_path = f.name

        try:
            tts.save(temp_path)
            return self._play_audio_file(temp_path, blocking)
        finally:
            if blocking:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def _speak_offline(self, text: str, blocking: bool) -> bool:
        """Use pyttsx3 (offline)."""
        try:
            engine = self._get_offline_engine()

            if blocking:
                engine.say(text)
                engine.runAndWait()
            else:
                # Non-blocking: run in separate thread
                def speak_thread():
                    engine.say(text)
                    engine.runAndWait()

                thread = threading.Thread(target=speak_thread)
                thread.daemon = True
                thread.start()

            return True

        except Exception as e:
            print(f"Offline TTS error: {e}")
            return False

    def _play_audio_file(self, path: str, blocking: bool) -> bool:
        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        pygame.mixer.music.load(path)
        pygame.mixer.music.play()

        if blocking:
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
        else:
            def waiter():
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
                try:
                    os.unlink(path)
                except OSError:
                    pass

            threading.Thread(target=waiter, daemon=True).start()

        return True

    def _play_audio_bytes(self, audio_bytes: bytes, blocking: bool, suffix: str = ".mp3") -> bool:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            temp_path = tmp.name

        success = self._play_audio_file(temp_path, blocking)
        if blocking:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        return success

    def _language_to_google_code(self) -> str:
        lang = self._current_language.lower()
        if lang.startswith("de"):
            return "de-DE"
        elif lang.startswith("fr"):
            return "fr-FR"
        elif lang.startswith("es"):
            return "es-ES"
        elif lang.startswith("it"):
            return "it-IT"
        elif lang.startswith("pt"):
            return "pt-PT"
        elif lang.startswith("nl"):
            return "nl-NL"
        elif lang.startswith("pl"):
            return "pl-PL"
        elif lang.startswith("ru"):
            return "ru-RU"
        elif lang.startswith("ja"):
            return "ja-JP"
        elif lang.startswith("zh"):
            return "zh-CN"
        elif lang.startswith("ko"):
            return "ko-KR"
        return "en-US"

    def _language_to_polly_code(self) -> str:
        lang = self._current_language.lower()
        if lang.startswith("de"):
            return "de-DE"
        elif lang.startswith("fr"):
            return "fr-FR"
        elif lang.startswith("es"):
            return "es-ES"
        elif lang.startswith("it"):
            return "it-IT"
        elif lang.startswith("pt"):
            return "pt-PT"
        elif lang.startswith("nl"):
            return "nl-NL"
        elif lang.startswith("pl"):
            return "pl-PL"
        elif lang.startswith("ru"):
            return "ru-RU"
        elif lang.startswith("ja"):
            return "ja-JP"
        elif lang.startswith("zh"):
            return "cmn-CN"
        elif lang.startswith("ko"):
            return "ko-KR"
        return "en-US"

    def _get_aws_signature_key(self, secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
        def _sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
        k_region = _sign(k_date, region)
        k_service = _sign(k_region, service)
        return _sign(k_service, "aws4_request")

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        return text.strip()

    def stop(self):
        """Stop any ongoing speech."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except:
            pass

        if self._pyttsx3_engine:
            try:
                self._pyttsx3_engine.stop()
            except:
                pass

    def cleanup(self):
        """Clean up resources."""
        self.stop()
        self._pyttsx3_engine = None
