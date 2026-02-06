"""
OCR service for extracting text from card images.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Optional
from io import BytesIO
import base64

from ..config import OCRConfig, Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class OCRService:
    """
    OCR service for extracting text from images in Anki cards.
    Supports caching to avoid repeated OCR on the same images.
    """

    # Class-level flag to avoid showing dialog multiple times
    _tesseract_dialog_shown = False

    def __init__(self, config: OCRConfig, openai_api_key: str = ""):
        self.config = config
        self._openai_api_key = openai_api_key
        self._tesseract_available: Optional[bool] = None
        self._tesseract_path: Optional[str] = None
        self._easyocr_reader = None
        self._openai_client = None
        self._cache_dir = Config.get_cache_dir() / "ocr"
        self._cache_dir.mkdir(exist_ok=True)

        # Check tesseract availability on init (unless user chose to skip or using GPT-4 Vision)
        if self.config.engine == "gpt4_vision":
            self._tesseract_available = False
        elif not self.config.skipped_by_user:
            self._check_tesseract()
        else:
            self._tesseract_available = False

    def _check_tesseract(self) -> bool:
        """
        Check if Tesseract is available and show install dialog if not.

        Returns:
            True if Tesseract is available
        """
        if self._tesseract_available is not None:
            return self._tesseract_available

        # If user previously chose to skip, don't check or show dialog
        if self.config.skipped_by_user:
            self._tesseract_available = False
            return False

        try:
            from ..utils.system_deps import check_tesseract, show_tesseract_install_dialog

            is_installed, path = check_tesseract()

            if is_installed:
                self._tesseract_available = True
                self._tesseract_path = path
                return True

            self._tesseract_available = False

            # Show dialog only once per session and only if OCR is enabled
            if self.config.enabled and not OCRService._tesseract_dialog_shown:
                OCRService._tesseract_dialog_shown = True

                # Use timer to show dialog after Anki UI is ready
                from aqt import mw
                from aqt.qt import QTimer

                def show_dialog():
                    try:
                        show_tesseract_install_dialog(mw)
                    except Exception as e:
                        print(f"Error showing tesseract dialog: {e}")

                QTimer.singleShot(1000, show_dialog)

            return False

        except Exception as e:
            print(f"Error checking tesseract: {e}")
            self._tesseract_available = False
            return False

    def is_available(self) -> bool:
        """Check if OCR is available."""
        if self.config.engine == "gpt4_vision":
            return bool(self._openai_api_key)
        return self._tesseract_available or False

    def is_skipped_by_user(self) -> bool:
        """Check if user chose to skip OCR."""
        return self.config.skipped_by_user

    def extract_text_from_html(self, html: str, card_id: int) -> str:
        """
        Extract text from HTML content, including OCR on images.

        Args:
            html: HTML content of the card
            card_id: Card ID for caching

        Returns:
            Combined text content including OCR results
        """
        if not self.config.enabled:
            return self._strip_html(html)

        # Extract regular text
        text_parts = [self._strip_html(html)]

        # Find and process images
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        images = re.findall(img_pattern, html, re.IGNORECASE)

        for img_src in images:
            try:
                ocr_text = self._ocr_image(img_src, card_id)
                if ocr_text:
                    text_parts.append(f"[Image: {ocr_text}]")
            except Exception as e:
                print(f"OCR error for {img_src}: {e}")

        return " ".join(text_parts)

    def _ocr_image(self, img_src: str, card_id: int) -> Optional[str]:
        """
        Perform OCR on an image.

        Args:
            img_src: Image source (path or data URL)
            card_id: Card ID for caching

        Returns:
            Extracted text or None
        """
        # Generate cache key
        cache_key = self._get_cache_key(img_src, card_id)

        # Check cache
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        # Load image
        image = self._load_image(img_src)
        if image is None:
            return None

        # Perform OCR based on engine
        if self.config.engine == "gpt4_vision":
            text = self._ocr_with_gpt4_vision(image, img_src)
        elif self.config.engine == "easyocr":
            text = self._ocr_with_easyocr(image)
        else:
            text = self._ocr_with_tesseract(image)

        # Cache result
        if text:
            self._save_to_cache(cache_key, text)

        return text

    def _load_image(self, img_src: str):
        """Load image from source."""
        from PIL import Image

        try:
            if img_src.startswith("data:"):
                # Data URL
                header, data = img_src.split(",", 1)
                image_data = base64.b64decode(data)
                return Image.open(BytesIO(image_data))
            else:
                # File path - resolve relative to Anki media folder
                from aqt import mw
                media_dir = Path(mw.col.media.dir())
                img_path = media_dir / img_src

                if img_path.exists():
                    return Image.open(img_path)

        except Exception as e:
            print(f"Failed to load image {img_src}: {e}")

        return None

    def _get_openai_client(self):
        """Get or create OpenAI client."""
        if self._openai_client is None:
            if not self._openai_api_key:
                logger.warning(
                    "No OpenAI API key configured for GPT-4 Vision OCR")
                return None
            try:
                from ..vendor.openai import OpenAI
                self._openai_client = OpenAI(api_key=self._openai_api_key)
            except Exception as e:
                logger.error(f"Failed to create OpenAI client: {e}")
                return None
        return self._openai_client

    def _image_to_base64(self, image, img_src: str = "") -> Optional[str]:
        """Convert PIL image to base64 data URL."""
        try:
            # Determine format from original source or default to PNG
            img_format = "PNG"
            if img_src:
                ext = Path(img_src).suffix.lower()
                format_map = {
                    ".jpg": "JPEG",
                    ".jpeg": "JPEG",
                    ".png": "PNG",
                    ".gif": "GIF",
                    ".webp": "WEBP"
                }
                img_format = format_map.get(ext, "PNG")

            # Convert to RGB if necessary (for JPEG)
            if img_format == "JPEG" and image.mode in ("RGBA", "P"):
                image = image.convert("RGB")

            # Save to bytes
            buffer = BytesIO()
            image.save(buffer, format=img_format)
            img_bytes = buffer.getvalue()

            # Encode to base64
            b64_data = base64.b64encode(img_bytes).decode("utf-8")
            mime_type = f"image/{img_format.lower()}"
            if img_format == "JPEG":
                mime_type = "image/jpeg"

            return f"data:{mime_type};base64,{b64_data}"

        except Exception as e:
            logger.error(f"Failed to convert image to base64: {e}")
            return None

    def _ocr_with_gpt4_vision(self, image, img_src: str = "") -> Optional[str]:
        """
        Perform OCR using GPT-4 Vision.

        This uses OpenAI's vision API to describe image content,
        which is more flexible than traditional OCR for various content types.
        """
        client = self._get_openai_client()
        if client is None:
            return None

        try:
            # Convert image to base64 data URL
            image_url = self._image_to_base64(image, img_src)
            if not image_url:
                return None

            # Build language context
            lang_names = {
                "eng": "English",
                "deu": "German",
                "fra": "French",
                "spa": "Spanish",
                "ita": "Italian",
                "por": "Portuguese",
                "nld": "Dutch",
                "rus": "Russian",
                "jpn": "Japanese",
                "kor": "Korean",
                "zho": "Chinese"
            }
            languages = [lang_names.get(l, l) for l in self.config.languages]
            lang_context = " and ".join(
                languages) if languages else "any language"

            # Create prompt for OCR
            prompt = f"""Extract and transcribe ALL text visible in this image.

Guidelines:
- Extract text in {lang_context}
- Include all text content, labels, annotations, and captions
- Preserve the reading order (top to bottom, left to right)
- If the image contains formulas, describe them in a readable way
- If there are diagrams or charts, briefly describe what they show
- If no text is visible, describe what the image shows in 1-2 sentences

Return ONLY the extracted text and brief descriptions. Be concise."""

            logger.debug(
                f"Calling GPT-4 Vision for OCR with model {self.config.gpt4_vision_model}")

            response = client.chat.completions.create(
                model=self.config.gpt4_vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            }
                        ]
                    }
                ],
                max_tokens=500
            )

            text = response.choices[0].message.content
            logger.debug(f"GPT-4 Vision OCR result: {text[:100]}..." if len(
                text) > 100 else f"GPT-4 Vision OCR result: {text}")
            return text.strip() if text else None

        except Exception as e:
            logger.error(f"GPT-4 Vision OCR error: {e}")
            return None

    def _ocr_with_tesseract(self, image) -> Optional[str]:
        """Perform OCR using Tesseract."""
        # Check if tesseract is available
        if not self._tesseract_available:
            return None

        try:
            import pytesseract

            # Set tesseract path if we found it
            if self._tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = self._tesseract_path

            # Configure language
            lang = "+".join(self.config.languages)

            text = pytesseract.image_to_string(image, lang=lang)
            return text.strip() if text else None

        except Exception as e:
            print(f"Tesseract OCR error: {e}")

            # If tesseract command not found, mark as unavailable
            if "not found" in str(e).lower() or "not installed" in str(e).lower():
                self._tesseract_available = False

            return None

    def _ocr_with_easyocr(self, image) -> Optional[str]:
        """Perform OCR using EasyOCR."""
        try:
            if self._easyocr_reader is None:
                import easyocr
                # Map language codes
                lang_map = {"eng": "en", "deu": "de"}
                langs = [lang_map.get(l, l) for l in self.config.languages]
                self._easyocr_reader = easyocr.Reader(langs)

            # Convert PIL image to numpy array
            import numpy as np
            img_array = np.array(image)

            results = self._easyocr_reader.readtext(img_array)
            text = " ".join([r[1] for r in results])
            return text.strip() if text else None

        except Exception as e:
            print(f"EasyOCR error: {e}")
            return None

    def _get_cache_key(self, img_src: str, card_id: int) -> str:
        """Generate cache key for an image."""
        content = f"{card_id}:{img_src}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """Get OCR result from cache."""
        cache_file = self._cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    return data.get("text")
            except Exception:
                pass

        return None

    def _save_to_cache(self, cache_key: str, text: str):
        """Save OCR result to cache."""
        cache_file = self._cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, "w") as f:
                json.dump({"text": text}, f)
        except Exception as e:
            print(f"Cache save error: {e}")

    def invalidate_cache(self, card_id: Optional[int] = None):
        """
        Invalidate cache entries.

        Args:
            card_id: If provided, only invalidate for this card.
                    If None, invalidate all cache.
        """
        if card_id is None:
            # Clear all cache
            for cache_file in self._cache_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                except Exception:
                    pass
        else:
            # We can't easily invalidate by card_id with current key structure
            # So we clear all for now
            self.invalidate_cache()

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags from text."""
        # Remove script and style elements
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>',
                      '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Decode common entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def cleanup(self):
        """Clean up resources."""
        self._easyocr_reader = None
