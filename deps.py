"""
Dependency installer for Hands-Free Anki.

This module checks for required dependencies and provides
installation instructions if they are missing.
"""

import subprocess
import sys
from typing import List, Tuple

# Required packages and their import names
# These are lightweight and don't require torch/CUDA
REQUIRED_PACKAGES = [
    ("pyttsx3", "pyttsx3"),
    ("gtts", "gtts"),
    ("pygame", "pygame"),
    ("SpeechRecognition", "speech_recognition"),
    ("pyaudio", "pyaudio"),
    ("pytesseract", "pytesseract"),
    ("Pillow", "PIL"),
]

# Optional packages for enhanced features
OPTIONAL_PACKAGES = [
    ("spacy", "spacy"),         # For lightweight semantic embeddings
    ("openai", "openai"),       # For LLM scoring
    ("anthropic", "anthropic"),  # For Claude scoring
    ("httpx", "httpx"),         # For Ollama
    ("easyocr", "easyocr"),     # Alternative OCR
]

# spaCy models for each language (small models ~15MB each)
SPACY_MODELS = {
    "en": "en_core_web_sm",
    "de": "de_core_news_sm",
}

# All packages needed for full functionality
ALL_PACKAGES = [
    "pyttsx3", "gtts", "pygame", "SpeechRecognition", "pyaudio",
    "pytesseract", "Pillow", "spacy", "openai", "anthropic", "httpx",
    "numpy",  # Required by spacy
]


def has_bundled_deps() -> bool:
    """Check if dependencies are bundled in vendor folder."""
    from pathlib import Path
    vendor_dir = Path(__file__).parent / "vendor"
    # Check for a few key packages to verify vendor is properly set up
    return (vendor_dir / "spacy").exists() and (vendor_dir / "pygame").exists()


def check_dependencies() -> Tuple[List[str], List[str]]:
    """
    Check which dependencies are missing.
    If bundled in vendor folder, assumes all are available.

    Returns:
        Tuple of (missing_required, missing_optional)
    """
    # If we have bundled deps, skip checking (they're all there)
    if has_bundled_deps():
        return [], []

    missing_required = []
    missing_optional = []

    for pip_name, import_name in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing_required.append(pip_name)

    for pip_name, import_name in OPTIONAL_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing_optional.append(pip_name)

    return missing_required, missing_optional


def get_install_command(packages: List[str]) -> str:
    """Get the pip install command for the given packages."""
    return f"{sys.executable} -m pip install {' '.join(packages)}"


def install_packages(packages: List[str], to_vendor: bool = True) -> Tuple[bool, str]:
    """
    Attempt to install packages using pip.

    Args:
        packages: List of package names to install
        to_vendor: If True, install to vendor/ folder (recommended)

    Returns:
        Tuple of (success, message)
    """
    if not packages:
        return True, "No packages to install"

    try:
        from pathlib import Path
        addon_dir = Path(__file__).parent
        vendor_dir = addon_dir / "vendor"
        vendor_dir.mkdir(exist_ok=True)

        if to_vendor:
            cmd = [sys.executable, "-m", "pip", "install",
                   "-t", str(vendor_dir)] + packages
        else:
            cmd = [sys.executable, "-m", "pip", "install"] + packages

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for large packages
        )

        if result.returncode == 0:
            return True, "Packages installed successfully"
        else:
            return False, f"Installation failed: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Installation timed out"
    except Exception as e:
        return False, f"Installation error: {str(e)}"


def get_missing_deps_message() -> str:
    """Get a user-friendly message about missing dependencies."""
    missing_required, missing_optional = check_dependencies()

    if not missing_required:
        return ""

    msg = "Hands-Free Anki is missing required dependencies:\n\n"
    msg += ", ".join(missing_required)
    msg += "\n\nTo install, run this command in a terminal:\n\n"
    msg += get_install_command(missing_required)
    msg += "\n\nNote: On Linux, you may also need system packages:\n"
    msg += "sudo apt install portaudio19-dev tesseract-ocr espeak"

    return msg


def has_all_required_deps() -> bool:
    """Check if all required dependencies are installed."""
    # If bundled, always return True
    if has_bundled_deps():
        return True
    missing_required, _ = check_dependencies()
    return len(missing_required) == 0


def check_spacy_model(language: str = "en") -> bool:
    """Check if spaCy model for language is installed (bundled or system)."""
    from pathlib import Path

    model_name = SPACY_MODELS.get(language, "en_core_web_sm")

    # First check if bundled
    addon_dir = Path(__file__).parent
    bundled_path = addon_dir / "vendor" / "spacy_models" / model_name / model_name
    if bundled_path.exists():
        return True

    # Then check system-installed
    try:
        import spacy
        spacy.load(model_name)
        return True
    except (ImportError, OSError):
        return False


def install_spacy_model(language: str = "en") -> Tuple[bool, str]:
    """
    Install spaCy model for the given language.
    Note: If using bundled version, models are already included.

    Returns:
        Tuple of (success, message)
    """
    from pathlib import Path

    model_name = SPACY_MODELS.get(language, "en_core_web_sm")

    # Check if already bundled
    addon_dir = Path(__file__).parent
    bundled_path = addon_dir / "vendor" / "spacy_models" / model_name
    if bundled_path.exists():
        return True, f"spaCy model '{model_name}' is already bundled with the addon"

    try:
        cmd = [sys.executable, "-m", "spacy", "download", model_name]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            return True, f"spaCy model '{model_name}' installed successfully"
        else:
            return False, f"Failed to install model: {result.stderr}"
    except Exception as e:
        return False, f"Installation error: {str(e)}"


def get_spacy_models_status() -> dict:
    """Get installation status of all spaCy models."""
    status = {}
    for lang, model in SPACY_MODELS.items():
        status[lang] = check_spacy_model(lang)
    return status


def install_all_dependencies() -> Tuple[bool, str]:
    """
    Install all required and optional dependencies to the vendor folder.
    This is for users who download the lite version without bundled deps.

    Returns:
        Tuple of (success, message)
    """
    from pathlib import Path

    # Install all packages to vendor
    success, msg = install_packages(ALL_PACKAGES, to_vendor=True)
    if not success:
        return False, f"Failed to install packages: {msg}"

    # Try to install spaCy models
    messages = [msg]
    for lang in ["en", "de"]:
        model_success, model_msg = install_spacy_model(lang)
        messages.append(model_msg)

    return True, "\n".join(messages)


def check_and_prompt_install() -> bool:
    """
    Check if dependencies are missing and prompt user to install.
    Returns True if deps are available (either bundled or after install).
    """
    if has_bundled_deps():
        return True

    missing_required, _ = check_dependencies()
    if not missing_required:
        return True

    # Dependencies are missing - user needs to install
    return False
