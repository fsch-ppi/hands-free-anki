"""
Hands-Free Anki - Review cards using voice commands and TTS
"""

# Initialize vendor packages FIRST, before any other imports
from .utils.logger import (
    setup_logger, install_exception_handler, log_info, log_error,
    log_exception, log_session_start, log_session_end
)
from .deps import has_all_required_deps, get_missing_deps_message, install_packages, check_dependencies
from .config import Config
from aqt.utils import showInfo, showWarning
from aqt.qt import QAction
from aqt import mw, gui_hooks
import sys
from pathlib import Path

# Add vendor directory to path for bundled dependencies
_addon_dir = Path(__file__).parent
_vendor_dir = _addon_dir / "vendor"
if _vendor_dir.exists():
    # Insert vendor at the front so bundled packages take priority
    if str(_vendor_dir) not in sys.path:
        sys.path.insert(0, str(_vendor_dir))
    # Also add spacy_models subdirectory
    _spacy_models_dir = _vendor_dir / "spacy_models"
    if _spacy_models_dir.exists() and str(_spacy_models_dir) not in sys.path:
        sys.path.insert(0, str(_spacy_models_dir))

# Set up logging early
setup_logger()
install_exception_handler()
log_info("Hands-Free Anki addon loaded")


# Global instance (lazily initialized)
hands_free_reviewer = None
_ocr_service = None


def check_and_install_deps():
    """Check for dependencies and offer to install them."""
    if has_all_required_deps():
        return True

    msg = get_missing_deps_message()
    showWarning(msg)
    return False


def toggle_hands_free_mode():
    """Toggle hands-free review mode on/off."""
    global hands_free_reviewer

    # Check dependencies first
    if not has_all_required_deps():
        check_and_install_deps()
        return

    config = Config.load()

    if hands_free_reviewer is None or not hands_free_reviewer.is_active:
        # Start hands-free mode
        try:
            log_session_start()
            from .hands_free_reviewer import HandsFreeReviewer
            hands_free_reviewer = HandsFreeReviewer(config)

            # Check if we need to start a review first
            if mw.state != "review":
                # Try to start a review if a deck is selected
                if _start_review_if_possible():
                    hands_free_reviewer.start()
                    showInfo("Hands-Free mode enabled. Starting review...")
                else:
                    log_info("No deck selected or no cards to review")
                    showWarning(
                        "Please select a deck with cards to review first.")
                    hands_free_reviewer = None
                    return
            else:
                hands_free_reviewer.start()
                showInfo("Hands-Free mode enabled. Starting review...")

        except Exception as e:
            log_exception(e, "toggle_hands_free_mode - start")
            showWarning(
                f"Failed to start Hands-Free mode: {str(e)}\n\nPlease check your settings.")
            if hands_free_reviewer:
                hands_free_reviewer.stop()
                hands_free_reviewer = None
    else:
        # Stop hands-free mode
        try:
            hands_free_reviewer.stop()
            hands_free_reviewer = None
            log_session_end()
            showInfo("Hands-Free mode disabled.")
        except Exception as e:
            log_exception(e, "toggle_hands_free_mode - stop")
            hands_free_reviewer = None


def _start_review_if_possible() -> bool:
    """
    Try to start a review session if possible.
    Returns True if review was started or already in review.
    """
    try:
        log_info("Attempting to start review session...")

        # Check if already reviewing
        if mw.state == "review":
            log_info("Already in review state")
            return True

        # Check if there's a current deck selected
        deck_id = mw.col.decks.current()["id"]
        if not deck_id:
            log_info("No deck selected")
            return False

        deck_name = mw.col.decks.current()["name"]
        log_info(f"Current deck: {deck_name} (id={deck_id})")

        # Check if there are cards due
        counts = mw.col.sched.counts()
        total_due = sum(counts)
        log_info(
            f"Cards due: new={counts[0]}, learning={counts[1]}, review={counts[2]}")

        if total_due == 0:
            log_info("No cards due in current deck")
            return False

        # Start the review
        log_info("Starting review via moveToState")
        mw.moveToState("review")

        # Give Anki a moment to transition
        import time
        time.sleep(0.3)

        return mw.state == "review"

    except Exception as e:
        log_exception(e, "_start_review_if_possible")
        return False


def open_settings():
    """Open the settings dialog."""
    from .ui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(mw)
    dialog.exec()


def on_note_modified(col, note, deck_id):
    """Invalidate OCR cache when a note is modified."""
    global _ocr_service

    if _ocr_service is None:
        from .services.ocr import OCRService
        config = Config.load()
        _ocr_service = OCRService(config.ocr, config.llm.openai_api_key)

    # Invalidate cache for all cards of this note
    for card in note.cards():
        _ocr_service.invalidate_cache(card.id)


def install_dependencies():
    """Install missing dependencies."""
    missing_required, missing_optional = check_dependencies()

    if not missing_required:
        showInfo("All required dependencies are already installed!")
        return

    showInfo(
        f"Installing {len(missing_required)} packages. This may take a few minutes...")

    success, message = install_packages(missing_required)

    if success:
        showInfo("Dependencies installed successfully! Please restart Anki.")
    else:
        showWarning(
            f"Failed to install dependencies:\n\n{message}\n\nPlease install manually.")


def setup_hooks():
    """Set up hooks for cache invalidation."""
    # Hook for when notes are modified
    try:
        gui_hooks.add_cards_did_add_note.append(
            lambda col, note, deck_id: on_note_modified(col, note, deck_id)
        )
    except Exception:
        pass  # Hook may not be available in older Anki versions

    # Hook for handling pycmd from webview (for OCR help link)
    try:
        from aqt import gui_hooks as gh
        gh.webview_did_receive_js_message.append(_handle_pycmd)
    except Exception:
        pass  # Hook may not be available in older Anki versions


def _handle_pycmd(handled, message, context):
    """Handle custom pycmd messages from webview."""
    if message == "hf_show_ocr_help":
        _show_ocr_install_help()
        return (True, None)
    return handled


def _show_ocr_install_help():
    """Show OCR installation help dialog."""
    try:
        from .utils.system_deps import show_tesseract_install_dialog
        show_tesseract_install_dialog(mw)
    except Exception as e:
        showWarning(f"Could not show help: {e}")


def setup_menu():
    """Set up the addon menu."""
    menu = mw.form.menuTools.addMenu("Hands-Free Anki")

    # Toggle action
    toggle_action = QAction("Toggle Hands-Free Mode", mw)
    toggle_action.setShortcut("Ctrl+Shift+H")
    toggle_action.triggered.connect(toggle_hands_free_mode)
    menu.addAction(toggle_action)

    # Settings action
    settings_action = QAction("Settings...", mw)
    settings_action.triggered.connect(open_settings)
    menu.addAction(settings_action)

    # Separator
    menu.addSeparator()

    # View Logs action
    logs_action = QAction("View Logs...", mw)
    logs_action.triggered.connect(open_logs)
    menu.addAction(logs_action)

    # Install dependencies action
    install_action = QAction("Install Dependencies...", mw)
    install_action.triggered.connect(install_dependencies)
    menu.addAction(install_action)


def open_logs():
    """Open the logs folder or show log contents."""
    from .utils.logger import get_log_path, get_crash_log_path
    import subprocess
    import platform

    log_path = get_log_path()
    crash_log_path = get_crash_log_path()
    logs_dir = log_path.parent

    # Try to open the logs directory in file manager
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", str(logs_dir)])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(logs_dir)])
        else:
            subprocess.Popen(["xdg-open", str(logs_dir)])

        log_info(f"Opened logs directory: {logs_dir}")
    except Exception as e:
        log_error(f"Failed to open logs directory: {e}")
        # Show the path instead
        showInfo(
            f"Logs are located at:\n\n{logs_dir}\n\nMain log: {log_path.name}\nCrash log: {crash_log_path.name}")


# Initialize when Anki loads
setup_menu()
setup_hooks()
