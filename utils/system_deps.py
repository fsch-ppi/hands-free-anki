"""
System dependency checker with platform-specific installation instructions.
"""

import platform
import shutil
from typing import Optional, Tuple


def get_platform() -> str:
    """Get the current platform: 'linux', 'windows', 'macos', 'android', 'ios', or 'unknown'."""
    system = platform.system().lower()

    if system == "linux":
        # Check if running on Android (Termux or similar)
        try:
            with open("/system/build.prop", "r") as f:
                return "android"
        except:
            pass
        return "linux"
    elif system == "darwin":
        # Could be macOS or iOS, but iOS doesn't run desktop Anki
        return "macos"
    elif system == "windows":
        return "windows"
    else:
        return "unknown"


def check_tesseract() -> Tuple[bool, Optional[str]]:
    """
    Check if Tesseract OCR is installed.

    Returns:
        Tuple of (is_installed, path_or_none)
    """
    # Check common paths
    tesseract_path = shutil.which("tesseract")

    if tesseract_path:
        return True, tesseract_path

    # Check Windows-specific paths
    if get_platform() == "windows":
        windows_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for path in windows_paths:
            if shutil.which(path) or __import__("os").path.exists(path):
                return True, path

    return False, None


def check_espeak() -> Tuple[bool, Optional[str]]:
    """
    Check if espeak is installed (needed for offline TTS on Linux).

    Returns:
        Tuple of (is_installed, path_or_none)
    """
    espeak_path = shutil.which("espeak") or shutil.which("espeak-ng")
    return (True, espeak_path) if espeak_path else (False, None)


def get_tesseract_install_instructions() -> str:
    """Get platform-specific instructions for installing Tesseract."""
    plat = get_platform()

    instructions = {
        "linux": """
<h3>🐧 Linux Installation</h3>
<p><b>Ubuntu/Debian:</b></p>
<pre>sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu</pre>

<p><b>Fedora:</b></p>
<pre>sudo dnf install tesseract tesseract-langpack-eng tesseract-langpack-deu</pre>

<p><b>Arch Linux:</b></p>
<pre>sudo pacman -S tesseract tesseract-data-eng tesseract-data-deu</pre>
""",

        "macos": """
<h3>🍎 macOS Installation</h3>
<p><b>Using Homebrew:</b></p>
<pre>brew install tesseract tesseract-lang</pre>

<p>If you don't have Homebrew, install it first:</p>
<pre>/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"</pre>
""",

        "windows": """
<h3>🪟 Windows Installation</h3>
<p><b>Option 1: Download Installer (Recommended)</b></p>
<ol>
<li>Download from: <a href="https://github.com/UB-Mannheim/tesseract/wiki">https://github.com/UB-Mannheim/tesseract/wiki</a></li>
<li>Run the installer (choose "Add to PATH" during install)</li>
<li>Select additional languages (German, etc.) during install</li>
<li>Restart Anki after installation</li>
</ol>

<p><b>Option 2: Using Chocolatey</b></p>
<pre>choco install tesseract</pre>

<p><b>Option 3: Using winget</b></p>
<pre>winget install UB-Mannheim.TesseractOCR</pre>
""",

        "android": """
<h3>🤖 Android</h3>
<p>Tesseract OCR is not directly available on Android for desktop Anki.</p>
<p><b>Workarounds:</b></p>
<ul>
<li>Use AnkiDroid's built-in features instead</li>
<li>OCR images on desktop before syncing</li>
<li>Use text descriptions instead of images</li>
</ul>
<p>Note: This addon is designed for desktop Anki (Windows/Mac/Linux).</p>
""",

        "unknown": """
<h3>Installation</h3>
<p>Please install Tesseract OCR for your operating system.</p>
<p>Visit: <a href="https://tesseract-ocr.github.io/tessdoc/Installation.html">https://tesseract-ocr.github.io/tessdoc/Installation.html</a></p>
"""
    }

    return instructions.get(plat, instructions["unknown"])


def get_espeak_install_instructions() -> str:
    """Get platform-specific instructions for installing espeak (Linux only)."""
    plat = get_platform()

    if plat != "linux":
        return "<p>espeak is only required on Linux. Your platform uses native TTS.</p>"

    return """
<h3>🐧 Linux - espeak Installation</h3>
<p><b>Ubuntu/Debian:</b></p>
<pre>sudo apt install espeak</pre>

<p><b>Fedora:</b></p>
<pre>sudo dnf install espeak</pre>

<p><b>Arch Linux:</b></p>
<pre>sudo pacman -S espeak</pre>
"""


def get_portaudio_install_instructions() -> str:
    """Get platform-specific instructions for installing PortAudio."""
    plat = get_platform()

    instructions = {
        "linux": """
<h3>🐧 Linux - PortAudio Installation</h3>
<p><b>Ubuntu/Debian:</b></p>
<pre>sudo apt install portaudio19-dev</pre>

<p><b>Fedora:</b></p>
<pre>sudo dnf install portaudio-devel</pre>

<p><b>Arch Linux:</b></p>
<pre>sudo pacman -S portaudio</pre>
""",

        "macos": """
<h3>🍎 macOS - PortAudio Installation</h3>
<pre>brew install portaudio</pre>
""",

        "windows": """
<h3>🪟 Windows</h3>
<p>PortAudio is bundled with the addon. No additional installation needed.</p>
""",
    }

    return instructions.get(plat, "<p>Please install PortAudio for your platform.</p>")


def show_tesseract_install_dialog(parent=None) -> bool:
    """
    Show a dialog with Tesseract installation instructions.

    Returns:
        True if user will install, False if user wants to skip OCR
    """
    from aqt.qt import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QCheckBox

    dialog = QDialog(parent)
    dialog.setWindowTitle("Tesseract OCR Required")
    dialog.setMinimumWidth(600)
    dialog.setMinimumHeight(450)

    layout = QVBoxLayout(dialog)

    # Header
    header = QLabel("<h2>⚠️ Tesseract OCR Not Found</h2>")
    layout.addWidget(header)

    info = QLabel(
        "<p>Tesseract OCR is required to extract text from images in your cards.</p>"
        "<p>Without it, images will be skipped during review (text cards work fine).</p>"
    )
    info.setWordWrap(True)
    layout.addWidget(info)

    # Instructions
    instructions = QTextBrowser()
    instructions.setOpenExternalLinks(True)
    instructions.setHtml(get_tesseract_install_instructions())
    layout.addWidget(instructions)

    # Remember choice checkbox
    remember_check = QCheckBox("Don't show this again")
    layout.addWidget(remember_check)

    # Buttons
    btn_layout = QHBoxLayout()

    ok_btn = QPushButton("OK, I'll Install It")
    ok_btn.clicked.connect(dialog.accept)

    skip_btn = QPushButton("Skip OCR (Continue Without)")
    skip_btn.clicked.connect(dialog.reject)

    btn_layout.addWidget(ok_btn)
    btn_layout.addWidget(skip_btn)
    layout.addLayout(btn_layout)

    result = dialog.exec()
    user_will_install = result == QDialog.DialogCode.Accepted

    # If user chose to skip and wants to remember, save the preference
    if not user_will_install and remember_check.isChecked():
        try:
            from ..config import Config
            config = Config.load()
            config.ocr.skipped_by_user = True
            config.save()
        except Exception as e:
            print(f"Failed to save OCR skip preference: {e}")

    return user_will_install


def check_all_system_deps() -> dict:
    """
    Check all system dependencies.

    Returns:
        Dict with status of each dependency
    """
    tesseract_ok, tesseract_path = check_tesseract()
    espeak_ok, espeak_path = check_espeak()

    plat = get_platform()

    return {
        "platform": plat,
        "tesseract": {
            "installed": tesseract_ok,
            "path": tesseract_path,
            "required": True,  # For OCR
        },
        "espeak": {
            "installed": espeak_ok,
            "path": espeak_path,
            "required": plat == "linux",  # Only required on Linux
        },
    }
