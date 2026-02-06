"""
Settings dialog for Hands-Free Anki.
"""

import threading

from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QGroupBox, QFormLayout, QMessageBox, QTextEdit, QTextBrowser,
    QProgressBar, QTimer, QListWidget, QListWidgetItem, Qt, QScrollArea,
    QSizePolicy, QTableWidget, QTableWidgetItem, QInputDialog
)

from ..config import Config


class CollapsibleSection(QWidget):
    """Simple expandable container with a toggle button header."""

    def __init__(self, title: str, parent: QWidget | None = None, expanded: bool = True):
        super().__init__(parent)
        self._title = title

        self._toggle = QPushButton()
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setFlat(True)
        self._toggle.setStyleSheet(
            "text-align:left; font-weight:bold; padding:6px;"
        )
        self._toggle.clicked.connect(self._on_toggled)

        self._content = QWidget()
        self._content.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 4, 12, 12)
        self._content_layout.setSpacing(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._toggle)
        layout.addWidget(self._content)

        self._apply_state(expanded)

    def _apply_state(self, expanded: bool):
        arrow = "▼" if expanded else "▶"
        self._toggle.setText(f"{arrow} {self._title}")
        self._content.setVisible(expanded)

    def _on_toggled(self, checked: bool):
        self._apply_state(checked)

    def content_layout(self) -> QVBoxLayout:
        """Expose the inner layout so callers can add widgets."""
        return self._content_layout


class SettingsDialog(QDialog):
    """Settings dialog for configuring Hands-Free Anki."""

    TTS_PROVIDER_CHOICES = [
        ("elevenlabs", "ElevenLabs (studio neural, recommended)"),
        ("google_cloud", "Google Cloud TTS"),
        ("amazon_polly", "Amazon Polly"),
        ("gtts", "Google Translate (gTTS)"),
        ("offline", "Offline pyttsx3")
    ]
    DEFAULT_TTS_PROVIDER_ORDER = [
        "elevenlabs",
        "google_cloud",
        "amazon_polly",
        "gtts",
        "offline",
    ]

    STT_PROVIDER_CHOICES = [
        ("elevenlabs", "ElevenLabs Scribe (online, recommended)"),
        ("whisper", "OpenAI Whisper Large V3 (online)"),
        ("google", "Google Speech Recognition (online)"),
        ("sphinx", "CMU Sphinx (offline, English)")
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = Config.load()
        self._audio_monitor_active = False
        self._audio_monitor_thread: threading.Thread | None = None
        self._audio_monitor_error_reported = False
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle("Hands-Free Anki Settings")

        # Match Anki's main window width (typically ~800px)
        self.setMinimumWidth(750)
        self.setMinimumHeight(650)
        self.resize(800, 700)

        # Apply nicer styling
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                font-weight: bold;
            }
            QPushButton {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                padding: 4px;
                border-radius: 3px;
            }
        """)

        layout = QVBoxLayout(self)

        # Tab widget - reorganized for better flow
        tabs = QTabWidget()
        self._add_tab(tabs, self._create_general_tab(), "⚙️ General")
        self._add_tab(tabs, self._create_display_tab(), "🖥️ Display")
        self._add_tab(tabs, self._create_tts_tab(), "🔊 Text-to-Speech")
        self._add_tab(tabs, self._create_stt_tab(), "🎤 Speech Recognition")
        self._add_tab(tabs, self._create_scoring_tab(), "📊 Scoring")
        self._add_tab(tabs, self._create_llm_tab(), "🤖 AI / LLM")
        self._add_tab(tabs, self._create_advanced_tab(), "🔧 Advanced")

        layout.addWidget(tabs)

        # Buttons
        buttons = QHBoxLayout()

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.clicked.connect(self.save_config)
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        self.test_btn = QPushButton("🧪 Test Services")
        self.test_btn.clicked.connect(self.test_services)
        buttons.addWidget(self.test_btn)
        buttons.addStretch()
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.save_btn)

        layout.addLayout(buttons)

    def _add_tab(self, tabs: QTabWidget, widget: QWidget, title: str):
        """Wrap tab contents in a scroll area for better readability."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        tabs.addTab(scroll, title)

    def _wrap_section(self, title: str, inner_widget: QWidget, expanded: bool = True) -> CollapsibleSection:
        section = CollapsibleSection(title, expanded=expanded)
        section.content_layout().addWidget(inner_widget)
        return section

    def _create_general_tab(self) -> QWidget:
        """Create the general settings tab - simplified for core settings."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Welcome / Quick Start
        welcome_group = QGroupBox("Welcome to Hands-Free Anki")
        welcome_layout = QVBoxLayout(welcome_group)
        welcome_text = QLabel(
            "<b>Review your Anki cards hands-free using voice!</b><br><br>"
            "• Press <b>Ctrl+Shift+H</b> to toggle hands-free mode<br>"
            "• Cards are read aloud automatically<br>"
            "• Speak your answer and get instant feedback<br>"
            "• Say a rating (1-4) or let AI grade your answer"
        )
        welcome_text.setWordWrap(True)
        welcome_layout.addWidget(welcome_text)
        layout.addWidget(welcome_group)

        # Language group
        lang_group = QGroupBox("Language")
        lang_layout = QFormLayout(lang_group)

        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("German (Deutsch)", "de")
        self.language_combo.addItem("French (Français)", "fr")
        self.language_combo.addItem("Spanish (Español)", "es")
        lang_layout.addRow("Default language:", self.language_combo)

        lang_note = QLabel("<i>This affects TTS voice and prompts. Override per-deck in Deck Settings.</i>")
        lang_note.setStyleSheet("color: #666;")
        lang_layout.addRow(lang_note)

        layout.addWidget(lang_group)

        # Voice Commands group
        voice_cmd_group = QGroupBox("Voice Commands")
        voice_cmd_layout = QFormLayout(voice_cmd_group)

        voice_info = QLabel("Words that trigger actions (comma-separated):")
        voice_info.setStyleSheet("color: #666; font-style: italic;")
        voice_cmd_layout.addRow(voice_info)

        self.cmd_stop = QLineEdit()
        self.cmd_stop.setPlaceholderText("stop,halt,stopp,beenden")
        self.cmd_stop.setToolTip("Stop hands-free mode but keep it enabled")
        voice_cmd_layout.addRow("🛑 Stop:", self.cmd_stop)

        self.cmd_skip = QLineEdit()
        self.cmd_skip.setPlaceholderText("skip,überspringen")
        self.cmd_skip.setToolTip("Skip current card without rating")
        voice_cmd_layout.addRow("⏭️ Skip:", self.cmd_skip)

        self.cmd_next = QLineEdit()
        self.cmd_next.setPlaceholderText("next,weiter")
        self.cmd_next.setToolTip("Move to next card")
        voice_cmd_layout.addRow("➡️ Next:", self.cmd_next)

        self.cmd_disable = QLineEdit()
        self.cmd_disable.setPlaceholderText("disable,deaktivieren")
        self.cmd_disable.setToolTip("Completely disable the addon")
        voice_cmd_layout.addRow("⛔ Disable:", self.cmd_disable)

        layout.addWidget(voice_cmd_group)

        # Deck Settings group
        deck_settings_group = QGroupBox("Per-Deck Settings")
        deck_settings_layout = QVBoxLayout(deck_settings_group)

        deck_settings_info = QLabel(
            "Configure language and which fields to read for each deck."
        )
        deck_settings_info.setWordWrap(True)
        deck_settings_layout.addWidget(deck_settings_info)

        # Table for deck settings
        self.deck_settings_table = QTableWidget()
        self.deck_settings_table.setColumnCount(3)
        self.deck_settings_table.setHorizontalHeaderLabels(
            ["Deck Name", "Language", "Fields to Read"])
        self.deck_settings_table.horizontalHeader().setStretchLastSection(True)
        self.deck_settings_table.setMaximumHeight(150)
        self.deck_settings_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        deck_settings_layout.addWidget(self.deck_settings_table)

        # Add/Edit/Remove buttons
        deck_btn_layout = QHBoxLayout()
        self.add_deck_btn = QPushButton("➕ Add Deck")
        self.add_deck_btn.clicked.connect(self._add_deck_settings)
        self.edit_deck_btn = QPushButton("✏️ Edit")
        self.edit_deck_btn.clicked.connect(self._edit_deck_settings)
        self.remove_deck_btn = QPushButton("🗑️ Remove")
        self.remove_deck_btn.clicked.connect(self._remove_deck_settings)
        deck_btn_layout.addWidget(self.add_deck_btn)
        deck_btn_layout.addWidget(self.edit_deck_btn)
        deck_btn_layout.addWidget(self.remove_deck_btn)
        deck_btn_layout.addStretch()
        deck_settings_layout.addLayout(deck_btn_layout)

        # Default skip fields
        skip_layout = QFormLayout()
        self.default_skip_fields = QLineEdit()
        self.default_skip_fields.setPlaceholderText(
            "ID,Audio,Sound,Comments,...")
        self.default_skip_fields.setToolTip(
            "Fields to skip when no deck-specific settings.\n"
            "Comma-separated, case-insensitive."
        )
        skip_layout.addRow("Default skip fields:", self.default_skip_fields)
        deck_settings_layout.addLayout(skip_layout)

        layout.addWidget(deck_settings_group)

        layout.addStretch()

        return widget

    def _get_fields_for_deck(self, deck_name: str) -> list[str]:
        """Get all field names for notes in a deck."""
        from aqt import mw
        if not mw or not mw.col:
            return []

        try:
            # Get deck ID
            deck = mw.col.decks.by_name(deck_name)
            if not deck:
                return []

            deck_id = deck["id"]

            # Get all note types used in this deck
            note_types = set()
            for cid in mw.col.decks.cids(deck_id, children=True):
                card = mw.col.get_card(cid)
                note_types.add(card.note().mid)

            # Collect all field names from these note types
            all_fields = set()
            for mid in note_types:
                model = mw.col.models.get(mid)
                if model:
                    for fld in model["flds"]:
                        all_fields.add(fld["name"])

            return sorted(all_fields)
        except Exception as e:
            print(f"Error getting fields for deck: {e}")
            return []

    def _add_deck_settings(self):
        """Add or edit deck settings with language and field selection."""
        self._show_deck_settings_dialog(None)

    def _edit_deck_settings(self):
        """Edit the selected deck settings."""
        row = self.deck_settings_table.currentRow()
        if row < 0:
            return
        deck_item = self.deck_settings_table.item(row, 0)
        if deck_item:
            self._show_deck_settings_dialog(deck_item.text(), row)

    def _show_deck_settings_dialog(self, existing_deck: str | None = None, edit_row: int = -1):
        """Show dialog to add/edit deck settings."""
        from aqt import mw

        if not mw or not mw.col:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(
            "Deck Settings" if existing_deck else "Add Deck Settings")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        # Deck selector
        deck_combo = QComboBox()
        decks = [d["name"] for d in mw.col.decks.all()]
        deck_combo.addItems(decks)
        if existing_deck:
            idx = deck_combo.findText(existing_deck)
            if idx >= 0:
                deck_combo.setCurrentIndex(idx)
            deck_combo.setEnabled(False)
        form.addRow("Deck:", deck_combo)

        # Language selector
        languages = [
            ("(Use default)", ""),
            ("English", "en"),
            ("German", "de"),
            ("French", "fr"),
            ("Spanish", "es"),
            ("Italian", "it"),
            ("Portuguese", "pt"),
            ("Dutch", "nl"),
            ("Polish", "pl"),
            ("Russian", "ru"),
            ("Japanese", "ja"),
            ("Chinese", "zh"),
            ("Korean", "ko"),
        ]
        lang_combo = QComboBox()
        for name, code in languages:
            lang_combo.addItem(name, code)
        form.addRow("Language:", lang_combo)

        layout.addLayout(form)

        # Fields section
        fields_label = QLabel(
            "Select fields to read (leave unchecked to use defaults):")
        layout.addWidget(fields_label)

        fields_scroll = QScrollArea()
        fields_scroll.setWidgetResizable(True)
        fields_scroll.setMaximumHeight(200)
        fields_widget = QWidget()
        fields_layout = QVBoxLayout(fields_widget)
        fields_scroll.setWidget(fields_widget)

        field_checkboxes = []

        def populate_fields(deck_name: str):
            """Populate field checkboxes for the selected deck."""
            # Clear existing
            for cb in field_checkboxes:
                fields_layout.removeWidget(cb)
                cb.deleteLater()
            field_checkboxes.clear()

            fields = self._get_fields_for_deck(deck_name)
            if not fields:
                no_fields = QLabel(
                    "(No fields found - select a deck with cards)")
                fields_layout.addWidget(no_fields)
                field_checkboxes.append(no_fields)
                return

            for field_name in fields:
                cb = QCheckBox(field_name)
                fields_layout.addWidget(cb)
                field_checkboxes.append(cb)

        # Connect deck change to field population
        deck_combo.currentTextChanged.connect(populate_fields)

        layout.addWidget(fields_scroll)

        # Load existing settings if editing
        if existing_deck:
            populate_fields(existing_deck)
            # Find existing row data
            if edit_row >= 0:
                lang_item = self.deck_settings_table.item(edit_row, 1)
                fields_item = self.deck_settings_table.item(edit_row, 2)
                if lang_item:
                    idx = lang_combo.findData(lang_item.text())
                    if idx >= 0:
                        lang_combo.setCurrentIndex(idx)
                if fields_item and fields_item.text():
                    selected_fields = [f.strip()
                                       for f in fields_item.text().split(",")]
                    for cb in field_checkboxes:
                        if isinstance(cb, QCheckBox) and cb.text() in selected_fields:
                            cb.setChecked(True)
        else:
            populate_fields(deck_combo.currentText())

        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        def accept():
            deck_name = deck_combo.currentText()
            lang_code = lang_combo.currentData()
            selected_fields = [cb.text() for cb in field_checkboxes
                               if isinstance(cb, QCheckBox) and cb.isChecked()]

            # Update or add to table
            if edit_row >= 0:
                row = edit_row
            else:
                # Check if deck already exists
                for r in range(self.deck_settings_table.rowCount()):
                    if self.deck_settings_table.item(r, 0).text() == deck_name:
                        row = r
                        break
                else:
                    row = self.deck_settings_table.rowCount()
                    self.deck_settings_table.insertRow(row)

            self.deck_settings_table.setItem(
                row, 0, QTableWidgetItem(deck_name))
            self.deck_settings_table.setItem(
                row, 1, QTableWidgetItem(lang_code))
            self.deck_settings_table.setItem(
                row, 2, QTableWidgetItem(", ".join(selected_fields)))
            dialog.accept()

        ok_btn.clicked.connect(accept)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def _remove_deck_settings(self):
        """Remove selected deck settings."""
        row = self.deck_settings_table.currentRow()
        if row >= 0:
            self.deck_settings_table.removeRow(row)

    def _show_deps_help(self):
        """Show system dependencies installation help dialog."""
        try:
            from ..utils.system_deps import (
                get_tesseract_install_instructions,
                get_espeak_install_instructions,
                check_tesseract,
                check_espeak,
                get_platform
            )

            dialog = QDialog(self)
            dialog.setWindowTitle("System Dependencies Installation")
            dialog.setMinimumWidth(650)
            dialog.setMinimumHeight(500)

            layout = QVBoxLayout(dialog)

            header = QLabel("<h2>📦 System Dependencies</h2>")
            layout.addWidget(header)

            instructions = QTextBrowser()
            instructions.setOpenExternalLinks(True)

            html_content = "<p>The following system packages are needed for full functionality:</p>"

            # Tesseract
            tess_ok, _ = check_tesseract()
            if not tess_ok:
                html_content += get_tesseract_install_instructions()
            else:
                html_content += "<p>✅ <b>Tesseract OCR</b> is already installed.</p>"

            # espeak (Linux)
            if get_platform() == "linux":
                espeak_ok, _ = check_espeak()
                if not espeak_ok:
                    html_content += get_espeak_install_instructions()
                else:
                    html_content += "<p>✅ <b>espeak</b> is already installed.</p>"

            html_content += "<hr><p><b>After installing:</b> Restart Anki for changes to take effect.</p>"

            instructions.setHtml(html_content)
            layout.addWidget(instructions)

            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            dialog.exec()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not show help: {e}")

    def _create_display_tab(self) -> QWidget:
        """Create the display settings tab for visual overlays and indicators."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Visual Overlays group
        overlays_group = QGroupBox("On-Screen Overlays")
        overlays_layout = QVBoxLayout(overlays_group)

        overlays_info = QLabel(
            "<i>Control what visual feedback appears during review:</i>"
        )
        overlays_info.setStyleSheet("color: #666;")
        overlays_layout.addWidget(overlays_info)

        self.show_user_answer = QCheckBox("Show recognized speech bubble")
        self.show_user_answer.setToolTip(
            "Shows what you said in a speech bubble on screen.\n"
            "Useful to verify your spoken answer was heard correctly."
        )
        overlays_layout.addWidget(self.show_user_answer)

        self.show_rating_indicator = QCheckBox("Show rating indicator")
        self.show_rating_indicator.setToolTip(
            "Shows a colored indicator (✓ or ✗) with the rating\n"
            "after your answer is scored."
        )
        overlays_layout.addWidget(self.show_rating_indicator)

        self.show_recording_indicator = QCheckBox("Show recording indicator")
        self.show_recording_indicator.setToolTip(
            "Shows a pulsing red dot when recording your voice.\n"
            "Helps you know when to speak."
        )
        overlays_layout.addWidget(self.show_recording_indicator)

        layout.addWidget(overlays_group)

        # Debug Panels group
        debug_group = QGroupBox("Developer / Debug Panels")
        debug_layout = QVBoxLayout(debug_group)

        debug_info = QLabel(
            "<i>Diagnostic panels for troubleshooting:</i>"
        )
        debug_info.setStyleSheet("color: #666;")
        debug_layout.addWidget(debug_info)

        self.show_debug_console = QCheckBox("Show debug console panel")
        self.show_debug_console.setToolTip(
            "Shows a terminal panel on the left side displaying\n"
            "real-time logs of TTS, STT, scoring, and errors.\n\n"
            "Useful for troubleshooting API issues."
        )
        debug_layout.addWidget(self.show_debug_console)

        self.show_audio_level_monitor = QCheckBox("Show audio level monitor")
        self.show_audio_level_monitor.setToolTip(
            "Shows a real-time audio level graph during recording\n"
            "to help diagnose microphone issues.\n\n"
            "Shows: current level, threshold line, history graph."
        )
        debug_layout.addWidget(self.show_audio_level_monitor)

        layout.addWidget(debug_group)

        # Preview group
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        preview_label = QLabel(
            "Toggle options above and start a hands-free session\n"
            "to see the changes in action."
        )
        preview_label.setStyleSheet("color: #888; font-style: italic;")
        preview_layout.addWidget(preview_label)

        layout.addWidget(preview_group)

        layout.addStretch()
        return widget

    def _create_tts_tab(self) -> QWidget:
        """Create the TTS settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        provider_group = QGroupBox("Voice Provider Priority")
        provider_layout = QVBoxLayout(provider_group)

        provider_info = QLabel(
            "Enable or disable providers and reorder them to control fallback order.\n"
            "The addon will try providers from top to bottom until audio is generated."
        )
        provider_info.setWordWrap(True)
        provider_layout.addWidget(provider_info)

        self.tts_provider_list = QListWidget()
        self.tts_provider_list.setAlternatingRowColors(True)
        provider_layout.addWidget(self.tts_provider_list)

        move_layout = QHBoxLayout()
        move_up = QPushButton("⬆ Move Up")
        move_up.clicked.connect(lambda: self._move_tts_provider(-1))
        move_layout.addWidget(move_up)

        move_down = QPushButton("⬇ Move Down")
        move_down.clicked.connect(lambda: self._move_tts_provider(1))
        move_layout.addWidget(move_down)

        provider_layout.addLayout(move_layout)

        reset_btn = QPushButton("Reset to recommended order")
        reset_btn.clicked.connect(lambda: self._set_tts_providers(
            self.DEFAULT_TTS_PROVIDER_ORDER))
        provider_layout.addWidget(reset_btn)

        layout.addWidget(self._wrap_section(
            "Provider Priority", provider_group))

        credentials_group = QGroupBox("Provider Credentials")
        credentials_layout = QFormLayout(credentials_group)

        self.elevenlabs_key = QLineEdit()
        self.elevenlabs_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.elevenlabs_key.setPlaceholderText("xi-api-key...")
        credentials_layout.addRow("ElevenLabs API Key:", self.elevenlabs_key)

        self.elevenlabs_voice = QComboBox()
        self.elevenlabs_voice.setEditable(True)
        self.elevenlabs_voice.addItem("Rachel", "21m00Tcm4TlvDq8ikWAM")
        self.elevenlabs_voice.addItem("Domi", "AZnzlk1XvdvUeBnXmlld")
        self.elevenlabs_voice.addItem("Bella", "EXAVITQu4vr4xnSDxMaL")
        self.elevenlabs_voice.addItem("Antoni", "ErXwobaYiN019PkySvjV")
        self.elevenlabs_voice.addItem("Elli", "MF3mGyEYCl7XYWbV9V6O")
        self.elevenlabs_voice.addItem("Josh", "TxGEqnHWrfWFTfGW9XjX")
        self.elevenlabs_voice.addItem("Arnold", "VR6AewLTigWG4xSOukaG")
        self.elevenlabs_voice.addItem("Adam", "pNInz6obpgDQGcFmaJgB")
        self.elevenlabs_voice.addItem("Sam", "yoZ06aMxZJJ28mfd3POQ")
        self.elevenlabs_voice.setToolTip(
            "Select a voice or enter a custom voice ID.\n"
            "You can find more voices at elevenlabs.io/voice-library"
        )
        credentials_layout.addRow(
            "ElevenLabs Voice:", self.elevenlabs_voice)

        self.elevenlabs_model = QComboBox()
        self.elevenlabs_model.setEditable(True)
        self.elevenlabs_model.addItem(
            "eleven_multilingual_v2", "eleven_multilingual_v2")
        self.elevenlabs_model.addItem("eleven_turbo_v2_5", "eleven_turbo_v2_5")
        self.elevenlabs_model.addItem("eleven_turbo_v2", "eleven_turbo_v2")
        self.elevenlabs_model.addItem(
            "eleven_monolingual_v1", "eleven_monolingual_v1")
        self.elevenlabs_model.addItem(
            "eleven_multilingual_v1", "eleven_multilingual_v1")
        self.elevenlabs_model.setToolTip(
            "ElevenLabs TTS model. Recommended:\n"
            "• eleven_multilingual_v2 - Best quality, multilingual\n"
            "• eleven_turbo_v2_5 - Fast, good quality\n"
        )
        credentials_layout.addRow("ElevenLabs Model:", self.elevenlabs_model)

        self.google_tts_key = QLineEdit()
        self.google_tts_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.google_tts_key.setPlaceholderText("AIza...")
        credentials_layout.addRow("Google Cloud API Key:", self.google_tts_key)

        self.google_tts_voice = QLineEdit()
        self.google_tts_voice.setPlaceholderText("en-US-Standard-B (optional)")
        credentials_layout.addRow("Google Cloud Voice:", self.google_tts_voice)

        self.polly_access_key = QLineEdit()
        self.polly_access_key.setEchoMode(QLineEdit.EchoMode.Password)
        credentials_layout.addRow("Amazon Access Key:", self.polly_access_key)

        self.polly_secret_key = QLineEdit()
        self.polly_secret_key.setEchoMode(QLineEdit.EchoMode.Password)
        credentials_layout.addRow("Amazon Secret Key:", self.polly_secret_key)

        self.polly_region = QLineEdit()
        self.polly_region.setPlaceholderText("us-east-1")
        credentials_layout.addRow("Amazon Region:", self.polly_region)

        self.polly_voice = QLineEdit()
        self.polly_voice.setPlaceholderText("Joanna")
        credentials_layout.addRow("Amazon Voice:", self.polly_voice)

        layout.addWidget(self._wrap_section(
            "API Credentials", credentials_group))

        playback_group = QGroupBox("Playback Preferences")
        playback_layout = QFormLayout(playback_group)

        self.tts_rate = QSpinBox()
        self.tts_rate.setRange(50, 400)
        self.tts_rate.setSuffix(" (default)")
        self.tts_rate.setToolTip(
            "Default speech rate (150 = normal, 300 = 2x speed)")
        playback_layout.addRow("Default rate:", self.tts_rate)

        self.tts_front_rate = QSpinBox()
        self.tts_front_rate.setRange(50, 400)
        self.tts_front_rate.setToolTip(
            "Speed for reading the question/front of card")
        playback_layout.addRow("Front (question) rate:", self.tts_front_rate)

        self.tts_back_rate = QSpinBox()
        self.tts_back_rate.setRange(50, 400)
        self.tts_back_rate.setToolTip(
            "Speed for reading the answer/back of card")
        playback_layout.addRow("Back (answer) rate:", self.tts_back_rate)

        self.tts_read_ease = QCheckBox("Announce card status before reading")
        self.tts_read_ease.setToolTip(
            "When enabled, announces the card type before reading the question.\n"
            "Examples:\n"
            "• 'Wiederholungskarte' (Review card)\n"
            "• 'Neue Karte' (New card)\n"
            "• 'Gut bekannte Karte' (Well-known card)\n\n"
            "Disable this for a faster, more streamlined experience."
        )
        playback_layout.addRow(self.tts_read_ease)

        layout.addWidget(self._wrap_section(
            "Playback Preferences", playback_group))

        info_label = QLabel(
            "ElevenLabs offers the highest naturalness. Google Cloud and Amazon Polly"
            " provide neural voices with your own API keys. gTTS and offline pyttsx3"
            " remain as fallbacks when premium services are unavailable."
        )
        info_label.setWordWrap(True)
        tips_wrapper = QWidget()
        tips_layout = QVBoxLayout(tips_wrapper)
        tips_layout.setContentsMargins(0, 0, 0, 0)
        tips_layout.addWidget(info_label)
        layout.addWidget(self._wrap_section(
            "Tips", tips_wrapper, expanded=False))

        layout.addStretch()

        self._set_tts_providers(
            self.config.tts.providers or self.DEFAULT_TTS_PROVIDER_ORDER)
        return widget

    def _set_tts_providers(self, order: list[str]):
        """Populate the provider list with the given order and check states."""
        if not hasattr(self, "tts_provider_list"):
            return

        labels = dict(self.TTS_PROVIDER_CHOICES)
        valid_keys = list(labels.keys())
        selected = [p for p in (
            order or self.DEFAULT_TTS_PROVIDER_ORDER) if p in valid_keys]
        for key in valid_keys:
            if key not in selected:
                selected.append(key)

        self.tts_provider_list.clear()

        for key in selected:
            item = QListWidgetItem(labels.get(key, key))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            if key in (order or self.DEFAULT_TTS_PROVIDER_ORDER):
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            self.tts_provider_list.addItem(item)

        if self.tts_provider_list.count() > 0:
            self.tts_provider_list.setCurrentRow(0)

    def _move_tts_provider(self, direction: int):
        """Move the selected provider up or down."""
        if not hasattr(self, "tts_provider_list"):
            return

        current_row = self.tts_provider_list.currentRow()
        if current_row < 0:
            return

        target_row = current_row + direction
        if target_row < 0 or target_row >= self.tts_provider_list.count():
            return

        item = self.tts_provider_list.takeItem(current_row)
        self.tts_provider_list.insertItem(target_row, item)
        self.tts_provider_list.setCurrentRow(target_row)

    def _collect_tts_providers(self) -> list[str]:
        """Return enabled providers in the current list order."""
        if not hasattr(self, "tts_provider_list"):
            return list(self.DEFAULT_TTS_PROVIDER_ORDER)

        providers: list[str] = []
        for i in range(self.tts_provider_list.count()):
            item = self.tts_provider_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                key = item.data(Qt.ItemDataRole.UserRole)
                if key and key not in providers:
                    providers.append(key)

        if not providers:
            providers = ["offline"]

        return providers

    def _create_stt_tab(self) -> QWidget:
        """Create the STT settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Microphone selection group
        mic_group = QGroupBox("Microphone")
        mic_layout = QVBoxLayout(mic_group)

        mic_form = QFormLayout()
        self.microphone_combo = QComboBox()
        self.microphone_combo.addItem("System Default", None)

        # Try to list available microphones
        try:
            from ..services.stt import STTService
            mics = STTService.list_microphones()
            for idx, name in mics:
                # Truncate long names
                display_name = name[:50] + "..." if len(name) > 50 else name
                self.microphone_combo.addItem(f"{idx}: {display_name}", idx)
        except Exception as e:
            print(f"Could not list microphones: {e}")

        mic_form.addRow("Input device:", self.microphone_combo)
        mic_layout.addLayout(mic_form)

        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh Microphone List")
        refresh_btn.clicked.connect(self._refresh_microphones)
        mic_layout.addWidget(refresh_btn)

        # Test button
        test_btn = QPushButton("🎤 Test Microphone")
        test_btn.clicked.connect(self._test_microphone)
        mic_layout.addWidget(test_btn)

        layout.addWidget(self._wrap_section("Microphone", mic_group))

        # Noise Threshold Group
        noise_group = QGroupBox("Noise Threshold (Pegel)")
        noise_layout = QVBoxLayout(noise_group)

        # Threshold controls
        threshold_form = QFormLayout()

        self.energy_threshold = QSpinBox()
        self.energy_threshold.setRange(0, 4000)
        self.energy_threshold.setSingleStep(50)
        self.energy_threshold.setToolTip(
            "Minimum audio energy level to be recognized as speech.\n"
            "Higher = ignores more background noise but may miss quiet speech.\n"
            "Lower = more sensitive but may pick up background noise.\n\n"
            "Typical values:\n"
            "• 100-200: Very quiet environment\n"
            "• 300-500: Normal room (default)\n"
            "• 500-1000: Some background noise\n"
            "• 1000-2000: Noisy environment\n"
            "• 2000+: Very noisy (TV, music, etc.)"
        )
        threshold_form.addRow("Energy threshold:", self.energy_threshold)

        self.dynamic_threshold = QCheckBox(
            "Auto-adjust based on ambient noise")
        self.dynamic_threshold.setToolTip(
            "When enabled, the threshold automatically adjusts\n"
            "based on the current background noise level.\n\n"
            "Disable this if you want a fixed threshold."
        )
        threshold_form.addRow(self.dynamic_threshold)
        noise_layout.addLayout(threshold_form)

        # Live Audio Level Monitor
        level_group_layout = QHBoxLayout()
        level_label = QLabel("Audio Level:")
        self.audio_level_bar = QProgressBar()
        self.audio_level_bar.setRange(0, 4000)
        self.audio_level_bar.setValue(0)
        self.audio_level_bar.setTextVisible(True)
        self.audio_level_bar.setFormat("%v")
        self.audio_level_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid gray;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
            }
        """)
        level_group_layout.addWidget(level_label)
        level_group_layout.addWidget(self.audio_level_bar)
        noise_layout.addLayout(level_group_layout)

        # Threshold line indicator
        self.threshold_indicator_label = QLabel("Threshold: ---")
        self.threshold_indicator_label.setStyleSheet(
            "color: #e74c3c; font-weight: bold;")
        noise_layout.addWidget(self.threshold_indicator_label)

        # Monitor buttons
        monitor_layout = QHBoxLayout()

        self.monitor_btn = QPushButton("📊 Start Level Monitor")
        self.monitor_btn.setCheckable(True)
        self.monitor_btn.clicked.connect(self._toggle_audio_monitor)
        monitor_layout.addWidget(self.monitor_btn)

        calibrate_btn = QPushButton("🎚️ Auto-Calibrate")
        calibrate_btn.setToolTip(
            "Automatically set threshold based on your voice")
        calibrate_btn.clicked.connect(self._run_calibration)
        monitor_layout.addWidget(calibrate_btn)

        noise_layout.addLayout(monitor_layout)

        # Visual indicator for threshold
        threshold_info = QLabel(
            "💡 Use 'Start Level Monitor' to see your current audio levels.\n"
            "Use 'Auto-Calibrate' to automatically set the threshold."
        )
        threshold_info.setWordWrap(True)
        threshold_info.setStyleSheet("color: gray; font-size: 11px;")
        noise_layout.addWidget(threshold_info)

        layout.addWidget(self._wrap_section("Noise Threshold", noise_group))

        # STT API Credentials Group
        stt_creds_group = QGroupBox("API Credentials")
        stt_creds_layout = QFormLayout(stt_creds_group)

        self.stt_openai_key = QLineEdit()
        self.stt_openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.stt_openai_key.setPlaceholderText("sk-...")
        self.stt_openai_key.setToolTip(
            "OpenAI API key for Whisper speech recognition.\n"
            "Get one at: https://platform.openai.com/api-keys"
        )
        stt_creds_layout.addRow(
            "OpenAI API Key (Whisper):", self.stt_openai_key)

        self.stt_elevenlabs_key = QLineEdit()
        self.stt_elevenlabs_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.stt_elevenlabs_key.setPlaceholderText(
            "xi-api-key... (or use TTS key)")
        self.stt_elevenlabs_key.setToolTip(
            "ElevenLabs API key for Scribe speech recognition.\n"
            "If left empty, the TTS ElevenLabs key will be used."
        )
        stt_creds_layout.addRow("ElevenLabs API Key:", self.stt_elevenlabs_key)

        self.stt_elevenlabs_model = QComboBox()
        self.stt_elevenlabs_model.setEditable(True)
        self.stt_elevenlabs_model.addItem("scribe_v1", "scribe_v1")
        self.stt_elevenlabs_model.setToolTip("ElevenLabs STT model")
        stt_creds_layout.addRow("ElevenLabs STT Model:",
                                self.stt_elevenlabs_model)

        stt_creds_note = QLabel(
            "💡 Whisper requires an OpenAI API key. ElevenLabs can share the TTS key."
        )
        stt_creds_note.setWordWrap(True)
        stt_creds_note.setStyleSheet("color: gray; font-size: 11px;")
        stt_creds_layout.addRow(stt_creds_note)

        layout.addWidget(self._wrap_section(
            "API Credentials", stt_creds_group))

        # STT Settings
        stt_group = QGroupBox("Speech Recognition Settings")
        stt_layout = QFormLayout(stt_group)

        self.stt_primary_provider = QComboBox()
        for value, label in self.STT_PROVIDER_CHOICES:
            self.stt_primary_provider.addItem(label, value)
        stt_layout.addRow("Primary engine:", self.stt_primary_provider)

        self.stt_whisper_model = QLineEdit()
        self.stt_whisper_model.setPlaceholderText("whisper-large-v3")
        stt_layout.addRow("Whisper model:", self.stt_whisper_model)

        self.stt_google_fallback = QCheckBox(
            "Enable Google Speech fallback when online")
        stt_layout.addRow(self.stt_google_fallback)

        self.stt_sphinx_fallback = QCheckBox(
            "Enable offline CMU Sphinx fallback (English only)")
        stt_layout.addRow(self.stt_sphinx_fallback)

        self.stt_silence_timeout = QDoubleSpinBox()
        self.stt_silence_timeout.setRange(0.5, 10.0)
        self.stt_silence_timeout.setSingleStep(0.5)
        self.stt_silence_timeout.setSuffix(" seconds")
        stt_layout.addRow("Silence timeout:", self.stt_silence_timeout)

        self.stt_min_time = QDoubleSpinBox()
        self.stt_min_time.setRange(0.5, 10.0)
        self.stt_min_time.setSingleStep(0.5)
        self.stt_min_time.setSuffix(" seconds")
        stt_layout.addRow("Min recording time:", self.stt_min_time)

        self.stt_max_time = QDoubleSpinBox()
        self.stt_max_time.setRange(5.0, 120.0)
        self.stt_max_time.setSingleStep(5.0)
        self.stt_max_time.setSuffix(" seconds")
        stt_layout.addRow("Max recording time:", self.stt_max_time)

        layout.addWidget(self._wrap_section("Recognition Engine", stt_group))

        info_label = QLabel(
            "Primary recognition now uses Whisper Large V3 with automatic fallbacks to"
            " Google Speech and offline CMU Sphinx when enabled."
        )
        info_label.setWordWrap(True)
        info_wrapper = QWidget()
        info_wrapper_layout = QVBoxLayout(info_wrapper)
        info_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        info_wrapper_layout.addWidget(info_label)
        layout.addWidget(self._wrap_section(
            "How it works", info_wrapper, expanded=False))

        layout.addStretch()
        return widget

    def _toggle_audio_monitor(self, checked: bool | None = None):
        """Handle the Start/Stop monitor button toggle."""
        if not hasattr(self, "monitor_btn"):
            return

        if checked is None:
            checked = self.monitor_btn.isChecked()

        if checked:
            self._start_audio_monitor()
        else:
            self._stop_audio_monitor()

    def _start_audio_monitor(self):
        """Start monitoring microphone levels in a background thread."""
        if self._audio_monitor_active:
            return

        self._audio_monitor_active = True
        self._audio_monitor_error_reported = False

        if hasattr(self, "monitor_btn"):
            self.monitor_btn.setChecked(True)
            self.monitor_btn.setText("⏹ Stop Level Monitor")

        self._audio_monitor_thread = threading.Thread(
            target=self._run_audio_monitor,
            daemon=True,
        )
        self._audio_monitor_thread.start()

    def _stop_audio_monitor(self):
        """Stop the live audio level monitor."""
        if not self._audio_monitor_active:
            return

        self._audio_monitor_active = False
        self._reset_monitor_button()

    def _reset_monitor_button(self):
        """Reset monitor UI elements to their idle state."""
        if hasattr(self, "monitor_btn"):
            self.monitor_btn.setChecked(False)
            self.monitor_btn.setText("📊 Start Level Monitor")

        if hasattr(self, "audio_level_bar") and self.audio_level_bar:
            self.audio_level_bar.setValue(0)
            self.audio_level_bar.setStyleSheet(
                """
                QProgressBar {
                    border: 1px solid gray;
                    border-radius: 3px;
                    text-align: center;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background-color: #27ae60;
                }
                """
            )

        if hasattr(self, "threshold_indicator_label"):
            threshold = self.energy_threshold.value()
            self.threshold_indicator_label.setText(
                f"Threshold: {threshold} | Current: ---"
            )
            self.threshold_indicator_label.setStyleSheet(
                "color: #e74c3c; font-weight: bold;"
            )

    def _run_audio_monitor(self):
        """Continuously sample microphone levels and update the UI."""
        try:
            import audioop
            import time

            from ..config import STTConfig
            from ..services.stt import STTService

            config = STTConfig()
            config.microphone_index = self.microphone_combo.currentData()
            config.energy_threshold = self.energy_threshold.value()
            config.dynamic_threshold = self.dynamic_threshold.isChecked()

            stt = STTService(config)

            with stt._get_microphone() as source:
                while self._audio_monitor_active:
                    try:
                        buffer = source.stream.read(source.CHUNK)
                        if not buffer:
                            continue

                        level = audioop.rms(buffer, source.SAMPLE_WIDTH)
                        QTimer.singleShot(
                            0, lambda level=level: self._update_audio_level(
                                level)
                        )
                    except Exception as exc:
                        QTimer.singleShot(
                            0,
                            lambda msg=str(
                                exc): self._handle_audio_monitor_error(msg),
                        )
                        break

                    time.sleep(0.05)
        except Exception as e:
            QTimer.singleShot(
                0, lambda msg=str(e): self._handle_audio_monitor_error(msg)
            )
        finally:
            self._audio_monitor_active = False
            self._audio_monitor_thread = None
            QTimer.singleShot(0, self._reset_monitor_button)

    def _update_audio_level(self, level: int):
        """Update UI elements with the latest sampled level."""
        if not hasattr(self, "audio_level_bar"):
            return

        level_value = max(0, int(level))
        capped = min(level_value, 4000)
        self.audio_level_bar.setValue(capped)

        threshold = self.energy_threshold.value()
        self.threshold_indicator_label.setText(
            f"Threshold: {threshold} | Current: {level_value}"
        )

        color = "#27ae60" if level_value > threshold else "#e74c3c"
        self.audio_level_bar.setStyleSheet(
            f"""
            QProgressBar {{
                border: 1px solid gray;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
            }}
            """
        )
        self.threshold_indicator_label.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )

    def _handle_audio_monitor_error(self, message: str):
        """Notify the user if the monitor encounters an error."""
        if self._audio_monitor_error_reported:
            return

        self._audio_monitor_error_reported = True
        self._audio_monitor_active = False
        self._reset_monitor_button()

        if not self.isVisible():
            return

        QMessageBox.warning(
            self,
            "Audio Monitor Error",
            f"Could not read microphone levels: {message}",
        )

    def _run_calibration(self):
        """Run the auto-calibration wizard."""
        from aqt.qt import QTimer, QProgressDialog

        # Create calibration dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Audio Calibration Wizard")
        dialog.setMinimumWidth(450)
        dialog.setMinimumHeight(300)

        layout = QVBoxLayout(dialog)

        # Instructions
        instructions = QLabel(
            "<h3>🎚️ Audio Calibration</h3>"
            "<p>This wizard will help set the optimal threshold for your environment.</p>"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Status label
        status_label = QLabel("Click 'Start' to begin calibration...")
        status_label.setWordWrap(True)
        status_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(status_label)

        # Level bar
        level_bar = QProgressBar()
        level_bar.setRange(0, 4000)
        level_bar.setValue(0)
        level_bar.setTextVisible(True)
        level_bar.setFormat("Level: %v")
        level_bar.setMinimumHeight(30)
        layout.addWidget(level_bar)

        # Results
        results_label = QLabel("")
        results_label.setWordWrap(True)
        layout.addWidget(results_label)

        # Buttons
        btn_layout = QHBoxLayout()
        start_btn = QPushButton("▶️ Start Calibration")
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Calibration state
        calibration_data = {
            'ambient_samples': [],
            'speech_samples': [],
            'phase': 'idle',
            'timer': None
        }

        def update_level(level):
            level_bar.setValue(int(level * 4000))

        def run_calibration():
            import threading

            start_btn.setEnabled(False)
            calibration_data['phase'] = 'ambient'
            status_label.setText(
                "📢 Phase 1/2: Measuring ambient noise...\n\nPlease stay quiet for 2 seconds.")

            def calibrate_thread():
                try:
                    from ..services.stt import STTService
                    from ..config import STTConfig
                    import time
                    import audioop

                    config = STTConfig()
                    config.microphone_index = self.microphone_combo.currentData()
                    stt = STTService(config)

                    # Phase 1: Measure ambient noise
                    ambient_levels = []
                    start = time.time()

                    with stt._get_microphone() as source:
                        while time.time() - start < 2.0:
                            try:
                                buffer = source.stream.read(source.CHUNK)
                                if buffer:
                                    energy = audioop.rms(
                                        buffer, source.SAMPLE_WIDTH)
                                    ambient_levels.append(energy)
                                    # Update UI from main thread
                                    from aqt import mw
                                    mw.taskman.run_on_main(
                                        lambda e=energy: level_bar.setValue(min(e, 4000)))
                            except:
                                break

                    ambient_avg = sum(ambient_levels) / \
                        len(ambient_levels) if ambient_levels else 300
                    ambient_max = max(
                        ambient_levels) if ambient_levels else 300

                    # Phase 2: Measure speech
                    from aqt import mw
                    mw.taskman.run_on_main(lambda: status_label.setText(
                        "📢 Phase 2/2: Speak normally for 3 seconds...\n\n"
                        "Say something like: 'Testing one two three, this is my normal speaking voice.'"
                    ))

                    time.sleep(0.5)  # Brief pause

                    speech_levels = []
                    start = time.time()

                    with stt._get_microphone() as source:
                        while time.time() - start < 3.0:
                            try:
                                buffer = source.stream.read(source.CHUNK)
                                if buffer:
                                    energy = audioop.rms(
                                        buffer, source.SAMPLE_WIDTH)
                                    speech_levels.append(energy)
                                    mw.taskman.run_on_main(
                                        lambda e=energy: level_bar.setValue(min(e, 4000)))
                            except:
                                break

                    speech_avg = sum(speech_levels) / \
                        len(speech_levels) if speech_levels else 500
                    speech_max = max(speech_levels) if speech_levels else 1000

                    # Calculate recommended threshold
                    # Should be above ambient max but below speech average
                    recommended = int((ambient_max + speech_avg) / 2)
                    # At least 50 above ambient
                    recommended = max(recommended, ambient_max + 50)
                    # At least 50 below speech
                    recommended = min(recommended, speech_avg - 50)
                    # Clamp to reasonable range
                    recommended = max(100, min(recommended, 3000))

                    # Update UI
                    def show_results():
                        results_label.setText(
                            f"<b>Results:</b><br>"
                            f"• Ambient noise: avg {int(ambient_avg)}, max {int(ambient_max)}<br>"
                            f"• Speech level: avg {int(speech_avg)}, max {int(speech_max)}<br>"
                            f"• <span style='color: #27ae60;'><b>Recommended threshold: {recommended}</b></span>"
                        )
                        status_label.setText(
                            "✅ Calibration complete! Click 'Apply' to use the recommended threshold.")

                        # Add apply button
                        apply_btn = QPushButton(
                            f"✅ Apply Threshold ({recommended})")
                        apply_btn.setStyleSheet(
                            "background-color: #27ae60; color: white; font-weight: bold;")
                        apply_btn.clicked.connect(
                            lambda: self._apply_calibration(recommended, dialog))
                        btn_layout.insertWidget(0, apply_btn)

                        start_btn.setText("🔄 Re-calibrate")
                        start_btn.setEnabled(True)

                    mw.taskman.run_on_main(show_results)

                except Exception as e:
                    from aqt import mw
                    mw.taskman.run_on_main(lambda: status_label.setText(
                        f"❌ Calibration failed: {e}"))
                    mw.taskman.run_on_main(lambda: start_btn.setEnabled(True))

            thread = threading.Thread(target=calibrate_thread, daemon=True)
            thread.start()

        start_btn.clicked.connect(run_calibration)

        dialog.exec()

    def _apply_calibration(self, threshold: int, dialog: QDialog):
        """Apply the calibrated threshold."""
        self.energy_threshold.setValue(int(threshold))
        # Use fixed threshold after calibration
        self.dynamic_threshold.setChecked(False)
        dialog.accept()
        QMessageBox.information(
            self, "Applied",
            f"Threshold set to {int(threshold)}.\n\n"
            "Auto-adjust has been disabled to use this fixed value."
        )

    def closeEvent(self, event):
        """Handle dialog close - stop any running monitors."""
        self._stop_audio_monitor()
        super().closeEvent(event)

    def _create_scoring_tab(self) -> QWidget:
        """Create the scoring settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Scoring Method
        method_group = QGroupBox("Scoring Method")
        method_layout = QFormLayout(method_group)

        self.scoring_method = QComboBox()
        self.scoring_method.addItem("Embedding Similarity", "embedding")
        self.scoring_method.addItem("LLM Grading", "llm")
        self.scoring_method.addItem("Hybrid (Both)", "hybrid")
        method_layout.addRow("Method:", self.scoring_method)

        self.embedding_provider = QComboBox()
        self.embedding_provider.addItem("Local (MiniLM)", "local")
        self.embedding_provider.addItem("spaCy", "spacy")
        self.embedding_provider.addItem("OpenAI", "openai")
        method_layout.addRow("Embedding Provider:", self.embedding_provider)

        self.embedding_weight = QDoubleSpinBox()
        self.embedding_weight.setRange(0.0, 1.0)
        self.embedding_weight.setSingleStep(0.1)
        self.embedding_weight.setToolTip(
            "For hybrid mode: weight given to embedding score.\n"
            "0.0 = LLM only, 1.0 = Embedding only, 0.5 = equal weight"
        )
        method_layout.addRow("Embedding Weight (hybrid):",
                             self.embedding_weight)

        layout.addWidget(self._wrap_section("Scoring Method", method_group))

        # Rating Thresholds
        threshold_group = QGroupBox("Rating Thresholds")
        threshold_layout = QFormLayout(threshold_group)

        self.threshold_4 = QDoubleSpinBox()
        self.threshold_4.setRange(0.0, 1.0)
        self.threshold_4.setSingleStep(0.05)
        threshold_layout.addRow("Easy (4) - score ≥:", self.threshold_4)

        self.threshold_3 = QDoubleSpinBox()
        self.threshold_3.setRange(0.0, 1.0)
        self.threshold_3.setSingleStep(0.05)
        threshold_layout.addRow("Good (3) - score ≥:", self.threshold_3)

        self.threshold_2 = QDoubleSpinBox()
        self.threshold_2.setRange(0.0, 1.0)
        self.threshold_2.setSingleStep(0.05)
        threshold_layout.addRow("Hard (2) - score ≥:", self.threshold_2)

        info = QLabel("Scores below Hard threshold result in 'Again' (1)")
        threshold_layout.addRow(info)

        layout.addWidget(self._wrap_section(
            "Rating Thresholds", threshold_group))
        layout.addStretch()

        return widget

    def _create_llm_tab(self) -> QWidget:
        """Create the LLM settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Provider
        provider_group = QGroupBox("LLM Provider")
        provider_layout = QFormLayout(provider_group)

        self.llm_provider = QComboBox()
        self.llm_provider.addItem("OpenAI", "openai")
        self.llm_provider.addItem("Anthropic (Claude)", "anthropic")
        self.llm_provider.addItem("Mistral AI", "mistral")
        self.llm_provider.addItem("Ollama (Local)", "ollama")
        self.llm_provider.addItem("None (embedding only)", "none")
        provider_layout.addRow("Provider:", self.llm_provider)

        layout.addWidget(provider_group)

        # API Keys
        keys_group = QGroupBox("API Keys")
        keys_layout = QFormLayout(keys_group)

        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setPlaceholderText("sk-...")
        keys_layout.addRow("OpenAI API Key:", self.openai_key)

        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key.setPlaceholderText("sk-ant-...")
        keys_layout.addRow("Anthropic API Key:", self.anthropic_key)

        self.mistral_key = QLineEdit()
        self.mistral_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.mistral_key.setPlaceholderText("mistral-...")
        keys_layout.addRow("Mistral API Key:", self.mistral_key)

        layout.addWidget(keys_group)

        # Models
        models_group = QGroupBox("Model Settings")
        models_layout = QFormLayout(models_group)

        self.openai_model = QComboBox()
        self.openai_model.setEditable(True)
        self.openai_model.addItems(
            ["gpt-3.5-turbo", "gpt-4o-mini", "gpt-4o", "gpt-4-turbo"])
        models_layout.addRow("OpenAI Model:", self.openai_model)

        self.anthropic_model = QComboBox()
        self.anthropic_model.setEditable(True)
        self.anthropic_model.addItems([
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229"
        ])
        models_layout.addRow("Anthropic Model:", self.anthropic_model)

        self.mistral_model = QComboBox()
        self.mistral_model.setEditable(True)
        self.mistral_model.addItems([
            "mistral-small-latest",
            "mistral-medium-latest",
            "mistral-large-latest"
        ])
        models_layout.addRow("Mistral Model:", self.mistral_model)

        self.ollama_model = QLineEdit()
        self.ollama_model.setPlaceholderText("llama3.2")
        models_layout.addRow("Ollama Model:", self.ollama_model)

        self.ollama_url = QLineEdit()
        self.ollama_url.setPlaceholderText("http://localhost:11434")
        models_layout.addRow("Ollama URL:", self.ollama_url)

        layout.addWidget(models_group)

        # Prompt
        prompt_group = QGroupBox("Custom Scoring Prompt")
        prompt_layout = QVBoxLayout(prompt_group)

        self.scoring_prompt = QTextEdit()
        self.scoring_prompt.setMaximumHeight(150)
        prompt_layout.addWidget(self.scoring_prompt)

        prompt_info = QLabel(
            "Use {front}, {back}, {user_answer} as placeholders.\n"
            "The LLM should respond with a number 0.0-1.0."
        )
        prompt_info.setWordWrap(True)
        prompt_layout.addWidget(prompt_info)

        layout.addWidget(prompt_group)

        return widget

    def _create_advanced_tab(self) -> QWidget:
        """Create the advanced settings tab - OCR, Announcements, System Dependencies."""
        from aqt.qt import QScrollArea

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # ============ System Dependencies ============
        deps_group = QGroupBox("System Dependencies")
        deps_layout = QVBoxLayout(deps_group)

        try:
            from ..utils.system_deps import check_all_system_deps, get_platform

            deps = check_all_system_deps()
            platform_name = get_platform().capitalize()

            platform_label = QLabel(f"<b>Platform:</b> {platform_name}")
            deps_layout.addWidget(platform_label)

            # Tesseract status
            tess_status = deps["tesseract"]
            if tess_status["installed"]:
                tess_label = QLabel(
                    f"✅ <b>Tesseract OCR:</b> Installed ({tess_status['path']})")
                tess_label.setStyleSheet("color: green;")
            else:
                tess_label = QLabel("❌ <b>Tesseract OCR:</b> Not installed")
                tess_label.setStyleSheet("color: red;")
            deps_layout.addWidget(tess_label)

            # espeak status (Linux only)
            espeak_status = deps["espeak"]
            if espeak_status["required"]:
                if espeak_status["installed"]:
                    espeak_label = QLabel(
                        f"✅ <b>espeak:</b> Installed ({espeak_status['path']})")
                    espeak_label.setStyleSheet("color: green;")
                else:
                    espeak_label = QLabel(
                        "❌ <b>espeak:</b> Not installed (required for offline TTS)")
                    espeak_label.setStyleSheet("color: orange;")
                deps_layout.addWidget(espeak_label)

            # Help button
            if not tess_status["installed"] or (espeak_status["required"] and not espeak_status["installed"]):
                help_btn = QPushButton("Show Installation Instructions")
                help_btn.clicked.connect(self._show_deps_help)
                deps_layout.addWidget(help_btn)

        except Exception as e:
            error_label = QLabel(f"Could not check dependencies: {e}")
            deps_layout.addWidget(error_label)

        layout.addWidget(deps_group)

        # ============ OCR Settings ============
        ocr_group = QGroupBox("OCR (Image Text Recognition)")
        ocr_layout = QFormLayout(ocr_group)

        self.ocr_enabled = QCheckBox("Enable OCR for images")
        self.ocr_enabled.setToolTip("Extract text from images in cards to read aloud")
        ocr_layout.addRow(self.ocr_enabled)

        self.ocr_engine = QComboBox()
        self.ocr_engine.addItem("GPT-4 Vision (recommended)", "gpt4_vision")
        self.ocr_engine.addItem("Tesseract (local)", "tesseract")
        self.ocr_engine.addItem("EasyOCR (local)", "easyocr")
        self.ocr_engine.currentIndexChanged.connect(self._update_ocr_engine_ui)
        ocr_layout.addRow("OCR Engine:", self.ocr_engine)

        self.ocr_vision_note = QLabel(
            "ℹ️ GPT-4 Vision uses your OpenAI API key (from AI/LLM settings)."
        )
        self.ocr_vision_note.setWordWrap(True)
        self.ocr_vision_note.setStyleSheet("color: #666; font-style: italic;")
        ocr_layout.addRow(self.ocr_vision_note)

        self.clear_cache_btn = QPushButton("Clear OCR Cache")
        self.clear_cache_btn.clicked.connect(self.clear_ocr_cache)
        ocr_layout.addRow(self.clear_cache_btn)

        layout.addWidget(ocr_group)

        # ============ Announcements ============
        ann_group = QGroupBox("Rating Announcements")
        ann_layout = QVBoxLayout(ann_group)

        self.announcements_enabled = QCheckBox("Enable rating announcements")
        self.announcements_enabled.setToolTip(
            "Speak a phrase after each rating (e.g., 'Correct!' or 'Let's try again.')"
        )
        ann_layout.addWidget(self.announcements_enabled)

        ann_info = QLabel(
            "<i>Customize phrases in the text boxes below (one per line).</i>"
        )
        ann_info.setStyleSheet("color: #666;")
        ann_layout.addWidget(ann_info)

        # English phrases (collapsed by default)
        en_group = QGroupBox("English Phrases")
        en_layout = QFormLayout(en_group)

        self.phrases_again_en = QTextEdit()
        self.phrases_again_en.setMaximumHeight(60)
        self.phrases_again_en.setPlaceholderText("Again. Let's review this.")
        en_layout.addRow("Again (1):", self.phrases_again_en)

        self.phrases_hard_en = QTextEdit()
        self.phrases_hard_en.setMaximumHeight(60)
        self.phrases_hard_en.setPlaceholderText("Hard. Almost there.")
        en_layout.addRow("Hard (2):", self.phrases_hard_en)

        self.phrases_good_en = QTextEdit()
        self.phrases_good_en.setMaximumHeight(60)
        self.phrases_good_en.setPlaceholderText("Good! Correct!")
        en_layout.addRow("Good (3):", self.phrases_good_en)

        self.phrases_easy_en = QTextEdit()
        self.phrases_easy_en.setMaximumHeight(60)
        self.phrases_easy_en.setPlaceholderText("Easy! Perfect!")
        en_layout.addRow("Easy (4):", self.phrases_easy_en)

        ann_layout.addWidget(en_group)

        # German phrases
        de_group = QGroupBox("German Phrases")
        de_layout = QFormLayout(de_group)

        self.phrases_again_de = QTextEdit()
        self.phrases_again_de.setMaximumHeight(60)
        self.phrases_again_de.setPlaceholderText("Nochmal. Das üben wir nochmal.")
        de_layout.addRow("Nochmal (1):", self.phrases_again_de)

        self.phrases_hard_de = QTextEdit()
        self.phrases_hard_de.setMaximumHeight(60)
        self.phrases_hard_de.setPlaceholderText("Schwer. Fast richtig.")
        de_layout.addRow("Schwer (2):", self.phrases_hard_de)

        self.phrases_good_de = QTextEdit()
        self.phrases_good_de.setMaximumHeight(60)
        self.phrases_good_de.setPlaceholderText("Gut! Richtig!")
        de_layout.addRow("Gut (3):", self.phrases_good_de)

        self.phrases_easy_de = QTextEdit()
        self.phrases_easy_de.setMaximumHeight(60)
        self.phrases_easy_de.setPlaceholderText("Leicht! Perfekt!")
        de_layout.addRow("Leicht (4):", self.phrases_easy_de)

        ann_layout.addWidget(de_group)

        layout.addWidget(ann_group)

        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

    def load_config(self):
        """Load configuration into UI elements."""
        # General
        lang_idx = self.language_combo.findData(self.config.tts.language)
        if lang_idx >= 0:
            self.language_combo.setCurrentIndex(lang_idx)

        # Display settings
        self.show_user_answer.setChecked(self.config.display.show_user_answer)
        self.show_rating_indicator.setChecked(self.config.display.show_rating_indicator)
        self.show_recording_indicator.setChecked(self.config.display.show_recording_indicator)
        self.show_debug_console.setChecked(self.config.display.show_debug_console)
        self.show_audio_level_monitor.setChecked(self.config.display.show_audio_level_monitor)

        # Voice Commands
        self.cmd_stop.setText(self.config.voice_commands.stop_words)
        self.cmd_skip.setText(self.config.voice_commands.skip_words)
        self.cmd_next.setText(self.config.voice_commands.next_words)
        self.cmd_disable.setText(self.config.voice_commands.disable_words)

        # Deck Settings
        self.deck_settings_table.setRowCount(0)
        for deck_name, settings in self.config.deck_settings.get_all().items():
            row = self.deck_settings_table.rowCount()
            self.deck_settings_table.insertRow(row)
            self.deck_settings_table.setItem(
                row, 0, QTableWidgetItem(deck_name))
            self.deck_settings_table.setItem(
                row, 1, QTableWidgetItem(settings.language))
            self.deck_settings_table.setItem(
                row, 2, QTableWidgetItem(", ".join(settings.include_fields)))
        self.default_skip_fields.setText(
            self.config.deck_settings.default_skip_fields)

        # TTS
        self._set_tts_providers(self.config.tts.providers)
        self.tts_rate.setValue(self.config.tts.rate)
        self.tts_front_rate.setValue(self.config.tts.front_rate)
        self.tts_back_rate.setValue(self.config.tts.back_rate)
        self.tts_read_ease.setChecked(self.config.tts.read_card_ease)
        # Use whichever ElevenLabs key is set (TTS or STT share the same key)
        elevenlabs_key = self.config.tts.elevenlabs_api_key or self.config.stt.elevenlabs_api_key
        self.elevenlabs_key.setText(elevenlabs_key)
        # ElevenLabs voice is a combo box - find by data (voice ID) or set custom text
        voice_id = self.config.tts.elevenlabs_voice_id or "21m00Tcm4TlvDq8ikWAM"
        voice_idx = self.elevenlabs_voice.findData(voice_id)
        if voice_idx >= 0:
            self.elevenlabs_voice.setCurrentIndex(voice_idx)
        else:
            self.elevenlabs_voice.setCurrentText(voice_id)
        # ElevenLabs model is a combo box
        model_id = self.config.tts.elevenlabs_model_id or "eleven_multilingual_v2"
        idx = self.elevenlabs_model.findData(model_id)
        if idx >= 0:
            self.elevenlabs_model.setCurrentIndex(idx)
        else:
            self.elevenlabs_model.setCurrentText(model_id)
        self.google_tts_key.setText(self.config.tts.google_tts_api_key)
        self.google_tts_voice.setText(self.config.tts.google_tts_voice)
        self.polly_access_key.setText(self.config.tts.amazon_polly_access_key)
        self.polly_secret_key.setText(self.config.tts.amazon_polly_secret_key)
        self.polly_region.setText(self.config.tts.amazon_polly_region)
        self.polly_voice.setText(self.config.tts.amazon_polly_voice_id)

        # STT
        stt_provider_idx = self.stt_primary_provider.findData(
            self.config.stt.provider)
        if stt_provider_idx >= 0:
            self.stt_primary_provider.setCurrentIndex(stt_provider_idx)
        self.stt_whisper_model.setText(self.config.stt.whisper_model)
        self.stt_google_fallback.setChecked(
            self.config.stt.enable_google_fallback)
        self.stt_sphinx_fallback.setChecked(
            self.config.stt.enable_sphinx_fallback)
        self.stt_silence_timeout.setValue(self.config.stt.silence_timeout)
        self.stt_min_time.setValue(self.config.stt.min_recording_time)
        self.stt_max_time.setValue(self.config.stt.max_recording_time)
        self.energy_threshold.setValue(self.config.stt.energy_threshold)
        self.dynamic_threshold.setChecked(self.config.stt.dynamic_threshold)

        # STT API credentials
        self.stt_openai_key.setText(self.config.llm.openai_api_key)
        self.stt_elevenlabs_key.setText(self.config.stt.elevenlabs_api_key)
        # ElevenLabs STT model
        stt_model_id = self.config.stt.elevenlabs_model_id or "scribe_v1"
        stt_model_idx = self.stt_elevenlabs_model.findData(stt_model_id)
        if stt_model_idx >= 0:
            self.stt_elevenlabs_model.setCurrentIndex(stt_model_idx)
        else:
            self.stt_elevenlabs_model.setCurrentText(stt_model_id)

        # Set microphone selection
        mic_index = self.config.stt.microphone_index
        for i in range(self.microphone_combo.count()):
            if self.microphone_combo.itemData(i) == mic_index:
                self.microphone_combo.setCurrentIndex(i)
                break

        # OCR
        self.ocr_enabled.setChecked(self.config.ocr.enabled)
        ocr_idx = self.ocr_engine.findData(self.config.ocr.engine)
        if ocr_idx >= 0:
            self.ocr_engine.setCurrentIndex(ocr_idx)
        self._update_ocr_engine_ui()

        # Scoring
        method_idx = self.scoring_method.findData(self.config.scoring.method)
        if method_idx >= 0:
            self.scoring_method.setCurrentIndex(method_idx)

        embed_idx = self.embedding_provider.findData(
            self.config.embedding.provider)
        if embed_idx >= 0:
            self.embedding_provider.setCurrentIndex(embed_idx)

        self.embedding_weight.setValue(self.config.scoring.embedding_weight)
        self.threshold_4.setValue(self.config.scoring.threshold_4)
        self.threshold_3.setValue(self.config.scoring.threshold_3)
        self.threshold_2.setValue(self.config.scoring.threshold_2)

        # Announcements
        self.announcements_enabled.setChecked(self.config.announcement.enabled)
        self.phrases_again_en.setPlainText(
            self.config.announcement.phrases_again_en)
        self.phrases_hard_en.setPlainText(
            self.config.announcement.phrases_hard_en)
        self.phrases_good_en.setPlainText(
            self.config.announcement.phrases_good_en)
        self.phrases_easy_en.setPlainText(
            self.config.announcement.phrases_easy_en)
        self.phrases_again_de.setPlainText(
            self.config.announcement.phrases_again_de)
        self.phrases_hard_de.setPlainText(
            self.config.announcement.phrases_hard_de)
        self.phrases_good_de.setPlainText(
            self.config.announcement.phrases_good_de)
        self.phrases_easy_de.setPlainText(
            self.config.announcement.phrases_easy_de)

        # LLM
        provider_idx = self.llm_provider.findData(self.config.llm.provider)
        if provider_idx >= 0:
            self.llm_provider.setCurrentIndex(provider_idx)
        self.openai_key.setText(self.config.llm.openai_api_key)
        self.anthropic_key.setText(self.config.llm.anthropic_api_key)
        self.mistral_key.setText(self.config.llm.mistral_api_key)
        self.openai_model.setCurrentText(self.config.llm.openai_model)
        self.anthropic_model.setCurrentText(self.config.llm.anthropic_model)
        self.mistral_model.setCurrentText(self.config.llm.mistral_model)
        self.ollama_model.setText(self.config.llm.ollama_model)
        self.ollama_url.setText(self.config.llm.ollama_base_url)
        self.scoring_prompt.setPlainText(self.config.llm.scoring_prompt)

    def save_config(self):
        """Save UI values to configuration."""
        # General / Language
        lang = self.language_combo.currentData()
        self.config.tts.language = lang
        self.config.stt.language = "de-DE" if lang == "de" else "en-US"

        # Display settings
        self.config.display.show_user_answer = self.show_user_answer.isChecked()
        self.config.display.show_rating_indicator = self.show_rating_indicator.isChecked()
        self.config.display.show_recording_indicator = self.show_recording_indicator.isChecked()
        self.config.display.show_debug_console = self.show_debug_console.isChecked()
        self.config.display.show_audio_level_monitor = self.show_audio_level_monitor.isChecked()

        # Voice Commands
        self.config.voice_commands.stop_words = self.cmd_stop.text().strip()
        self.config.voice_commands.skip_words = self.cmd_skip.text().strip()
        self.config.voice_commands.next_words = self.cmd_next.text().strip()
        self.config.voice_commands.disable_words = self.cmd_disable.text().strip()

        # Deck Settings
        import json
        deck_settings = {}
        for row in range(self.deck_settings_table.rowCount()):
            deck_item = self.deck_settings_table.item(row, 0)
            lang_item = self.deck_settings_table.item(row, 1)
            fields_item = self.deck_settings_table.item(row, 2)
            if deck_item:
                deck_name = deck_item.text()
                language = lang_item.text() if lang_item else ""
                fields_str = fields_item.text() if fields_item else ""
                include_fields = [f.strip()
                                  for f in fields_str.split(",") if f.strip()]
                deck_settings[deck_name] = {
                    "language": language,
                    "include_fields": include_fields
                }
        self.config.deck_settings.deck_settings = json.dumps(deck_settings)
        self.config.deck_settings.default_skip_fields = self.default_skip_fields.text().strip()

        # TTS
        self.config.tts.providers = self._collect_tts_providers()
        self.config.tts.rate = self.tts_rate.value()
        self.config.tts.front_rate = self.tts_front_rate.value()
        self.config.tts.back_rate = self.tts_back_rate.value()
        self.config.tts.read_card_ease = self.tts_read_ease.isChecked()
        self.config.tts.elevenlabs_api_key = self.elevenlabs_key.text().strip()
        # Get voice ID from combo box data or text (for custom IDs)
        voice_data = self.elevenlabs_voice.currentData()
        if voice_data:
            self.config.tts.elevenlabs_voice_id = voice_data
        else:
            self.config.tts.elevenlabs_voice_id = self.elevenlabs_voice.currentText(
            ).strip() or "21m00Tcm4TlvDq8ikWAM"
        self.config.tts.elevenlabs_model_id = self.elevenlabs_model.currentText(
        ).strip() or "eleven_multilingual_v2"
        self.config.tts.google_tts_api_key = self.google_tts_key.text().strip()
        self.config.tts.google_tts_voice = self.google_tts_voice.text().strip()
        self.config.tts.amazon_polly_access_key = self.polly_access_key.text().strip()
        self.config.tts.amazon_polly_secret_key = self.polly_secret_key.text().strip()
        self.config.tts.amazon_polly_region = self.polly_region.text().strip() or "us-east-1"
        self.config.tts.amazon_polly_voice_id = self.polly_voice.text().strip() or "Joanna"

        # STT
        self.config.stt.provider = self.stt_primary_provider.currentData()
        self.config.stt.whisper_model = self.stt_whisper_model.text().strip() or "whisper-large-v3"
        self.config.stt.enable_google_fallback = self.stt_google_fallback.isChecked()
        self.config.stt.enable_sphinx_fallback = self.stt_sphinx_fallback.isChecked()
        self.config.stt.silence_timeout = self.stt_silence_timeout.value()
        # STT ElevenLabs: use dedicated key if set, otherwise fall back to TTS key
        stt_elevenlabs_key = self.stt_elevenlabs_key.text().strip()
        self.config.stt.elevenlabs_api_key = stt_elevenlabs_key or self.elevenlabs_key.text().strip()
        self.config.stt.elevenlabs_model_id = self.stt_elevenlabs_model.currentText(
        ).strip() or "scribe_v1"
        # OpenAI key for Whisper (also save to LLM config)
        openai_key = self.stt_openai_key.text().strip()
        if openai_key:
            self.config.llm.openai_api_key = openai_key
        self.config.stt.min_recording_time = self.stt_min_time.value()
        self.config.stt.max_recording_time = self.stt_max_time.value()
        self.config.stt.microphone_index = self.microphone_combo.currentData()
        self.config.stt.energy_threshold = self.energy_threshold.value()
        self.config.stt.dynamic_threshold = self.dynamic_threshold.isChecked()

        # OCR
        self.config.ocr.enabled = self.ocr_enabled.isChecked()
        self.config.ocr.engine = self.ocr_engine.currentData()

        # Scoring
        self.config.scoring.method = self.scoring_method.currentData()
        self.config.embedding.provider = self.embedding_provider.currentData()
        self.config.scoring.embedding_weight = self.embedding_weight.value()
        self.config.scoring.threshold_4 = self.threshold_4.value()
        self.config.scoring.threshold_3 = self.threshold_3.value()
        self.config.scoring.threshold_2 = self.threshold_2.value()

        # Announcements
        self.config.announcement.enabled = self.announcements_enabled.isChecked()
        self.config.announcement.phrases_again_en = self.phrases_again_en.toPlainText()
        self.config.announcement.phrases_hard_en = self.phrases_hard_en.toPlainText()
        self.config.announcement.phrases_good_en = self.phrases_good_en.toPlainText()
        self.config.announcement.phrases_easy_en = self.phrases_easy_en.toPlainText()
        self.config.announcement.phrases_again_de = self.phrases_again_de.toPlainText()
        self.config.announcement.phrases_hard_de = self.phrases_hard_de.toPlainText()
        self.config.announcement.phrases_good_de = self.phrases_good_de.toPlainText()
        self.config.announcement.phrases_easy_de = self.phrases_easy_de.toPlainText()

        # LLM
        self.config.llm.provider = self.llm_provider.currentData()
        self.config.llm.openai_api_key = self.openai_key.text()
        self.config.llm.anthropic_api_key = self.anthropic_key.text()
        self.config.llm.mistral_api_key = self.mistral_key.text()
        self.config.llm.openai_model = self.openai_model.currentText()
        self.config.llm.anthropic_model = self.anthropic_model.currentText()
        self.config.llm.mistral_model = self.mistral_model.currentText()
        self.config.llm.ollama_model = self.ollama_model.text()
        self.config.llm.ollama_base_url = self.ollama_url.text()
        self.config.llm.scoring_prompt = self.scoring_prompt.toPlainText()

        # Save
        self.config.save()

        QMessageBox.information(self, "Settings Saved",
                                "Settings have been saved successfully.")
        self.accept()

    def test_services(self):
        """Test that all services are working."""
        results = []

        # Test TTS
        try:
            from ..services import TTSService
            tts = TTSService(self.config.tts)
            tts.speak("Testing text to speech.", blocking=True)
            results.append("✓ TTS: Working")
        except Exception as e:
            results.append(f"✗ TTS: {e}")

        # Test STT (just initialization)
        try:
            from ..services import STTService
            stt = STTService(self.config.stt, self.config.llm)
            stt._init_recognizer()
            results.append("✓ STT: Initialized")
        except Exception as e:
            results.append(f"✗ STT: {e}")

        # Test OCR
        try:
            if self.config.ocr.engine == "tesseract":
                import pytesseract
                pytesseract.get_tesseract_version()
                results.append("✓ OCR (Tesseract): Available")
            else:
                import easyocr
                results.append("✓ OCR (EasyOCR): Available")
        except Exception as e:
            results.append(f"✗ OCR: {e}")

        # Test embeddings (spaCy)
        try:
            from ..deps import check_spacy_model
            if check_spacy_model("en"):
                results.append("✓ spaCy (English): Available")
            else:
                results.append("⚠ spaCy (English): Model not installed")
            if check_spacy_model("de"):
                results.append("✓ spaCy (German): Available")
            else:
                results.append("⚠ spaCy (German): Model not installed")
        except Exception as e:
            results.append(f"⚠ spaCy: Not installed ({e})")

        # Test network
        from ..utils import is_online
        if is_online():
            results.append("✓ Network: Online")
        else:
            results.append("⚠ Network: Offline (limited features)")

        QMessageBox.information(
            self,
            "Service Test Results",
            "\n".join(results)
        )

    def clear_ocr_cache(self):
        """Clear the OCR cache."""
        from ..services import OCRService
        ocr = OCRService(self.config.ocr, self.config.llm.openai_api_key)
        ocr.invalidate_cache()
        QMessageBox.information(self, "Cache Cleared",
                                "OCR cache has been cleared.")

    def _update_ocr_engine_ui(self):
        """Update OCR UI based on selected engine."""
        engine = self.ocr_engine.currentData()
        is_vision = engine == "gpt4_vision"

        # Show/hide tesseract status based on engine
        if hasattr(self, 'tesseract_status_wrapper'):
            self.tesseract_status_wrapper.setVisible(not is_vision)

        # Update vision note visibility
        if hasattr(self, 'ocr_vision_note'):
            self.ocr_vision_note.setVisible(is_vision)

    def install_spacy_model(self, language: str):
        """Install spaCy model for the given language."""
        from ..deps import install_spacy_model, SPACY_MODELS, install_packages

        # First ensure spacy is installed
        try:
            import spacy
        except ImportError:
            QMessageBox.information(
                self, "Installing spaCy",
                "spaCy is not installed. Installing now...\nThis may take a moment."
            )
            success, msg = install_packages(["spacy"])
            if not success:
                QMessageBox.critical(self, "Installation Failed", msg)
                return

        model_name = SPACY_MODELS.get(language, "en_core_web_sm")
        QMessageBox.information(
            self, "Installing Model",
            f"Installing spaCy model '{model_name}'...\nThis may take a moment."
        )

        success, msg = install_spacy_model(language)

        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Installation Failed", msg)

    def _refresh_microphones(self):
        """Refresh the microphone list."""
        self.microphone_combo.clear()
        self.microphone_combo.addItem("System Default", None)
        try:
            from ..services.stt import STTService
            mics = STTService.list_microphones()
            for idx, name in mics:
                display_name = name[:50] + "..." if len(name) > 50 else name
                self.microphone_combo.addItem(f"{idx}: {display_name}", idx)
        except Exception as e:
            print(f"Could not list microphones: {e}")
        QMessageBox.information(self, "Microphones Refreshed",
                                "Microphone list has been refreshed.")

    def _test_microphone(self):
        """Test the selected microphone by recording a short sample."""
        try:
            from ..services.stt import STTService
            stt = STTService(self.config.stt, self.config.llm)

            QMessageBox.information(
                self, "Microphone Test",
                "Speak something now. Recording for 3 seconds..."
            )

            # Try to listen and recognize
            text = stt.listen_and_recognize()

            if text:
                QMessageBox.information(
                    self, "Microphone Test - Success",
                    f"Recognized: \"{text}\"\n\nMicrophone is working!"
                )
            else:
                QMessageBox.warning(
                    self, "Microphone Test - No Speech",
                    "No speech was detected. Please check:\n"
                    "• Microphone is connected\n"
                    "• Microphone permissions are granted\n"
                    "• Energy threshold may need adjustment"
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Microphone Test - Error",
                f"Microphone test failed:\n{e}"
            )
