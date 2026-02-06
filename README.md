# Hands-Free Anki

🎤 **Review Anki cards completely hands-free using voice!**

Cards are read aloud, you answer verbally, and your answers are automatically scored and rated. Perfect for language learning, studying while commuting, or accessibility needs.

## ✨ Features

- **🔊 Text-to-Speech**: Cards read aloud automatically (ElevenLabs, Google TTS, Amazon Polly, or offline pyttsx3)
- **🎤 Speech Recognition**: Speak your answer (OpenAI Whisper, ElevenLabs, or Google Speech)
- **📊 Smart Scoring**: AI-powered answer evaluation (GPT-4, Claude, Mistral, or local semantic matching)
- **🖼️ OCR Support**: Text extracted from images in cards (GPT-4 Vision or Tesseract)
- **🌍 Multi-language**: English, German, French, Spanish support
- **⚙️ Highly Configurable**: Per-deck settings, custom voice commands, display toggles

## 🚀 Quick Start

1. Install from AnkiWeb or copy to your addons folder
2. Press **Ctrl+Shift+H** to start hands-free mode
3. Listen to the card, speak your answer
4. Get instant feedback and automatic rating!

## 📋 Requirements

### API Keys (for best experience)
- **OpenAI API Key**: For Whisper STT and GPT scoring
- **ElevenLabs API Key** (optional): For high-quality voices

### System Dependencies
```bash
# Linux (Ubuntu/Debian)
sudo apt install portaudio19-dev tesseract-ocr espeak

# macOS  
brew install portaudio tesseract espeak

# Windows
# Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
```

## ⚙️ Configuration

Access settings via **Tools → Hands-Free → Settings**

### Tabs Overview
| Tab | Description |
|-----|-------------|
| ⚙️ General | Language, voice commands, per-deck settings |
| 🖥️ Display | Toggle overlays: speech bubble, rating indicator, debug panels |
| 🔊 TTS | Voice provider priority, ElevenLabs voice selection, speech rate |
| 🎤 STT | Whisper/ElevenLabs setup, microphone settings, recording timeouts |
| 📊 Scoring | Grading thresholds, embedding vs LLM scoring |
| 🤖 AI/LLM | API keys and model selection |
| 🔧 Advanced | OCR settings, rating announcements, system dependencies |

## 🗣️ Voice Commands

During review, you can say:
- **"stop"** / **"halt"** - Pause hands-free mode
- **"skip"** - Skip current card
- **"next"** - Move to next card
- **"one"** / **"two"** / **"three"** / **"four"** - Rate card directly

## 🎯 Scoring Methods

| Method | Speed | Quality | Requires |
|--------|-------|---------|----------|
| Local (spaCy) | ⚡ Fast | Good | Nothing |
| GPT-4o-mini | Medium | Excellent | OpenAI key |
| Claude | Medium | Excellent | Anthropic key |
| Ollama | Varies | Good | Local Ollama |

## 🔒 Privacy & Security

⚠️ **Important Security Notice:**

- **API keys are stored locally** in plain text in your Anki addons folder (`user_config.json`)
- **Other Anki addons may have access** to these keys - only install addons you trust
- Consider using API keys with spending limits or usage restrictions
- Audio is only recorded during active review sessions
- Speech data is sent to your configured provider (OpenAI Whisper, ElevenLabs, etc.)
- No data is stored or shared by this addon itself

## 🔧 Building from Source

If you want to build/install the addon yourself:

### 1. Clone the repository
```bash
cd ~/.local/share/Anki2/addons21/
git clone https://github.com/fsch-ppi/hands-free-anki.git
cd hands-free-anki
```

### 2. Install Python dependencies
```bash
# Create vendor directory and install dependencies there
pip install -t vendor/ -r requirements.txt

# Or install manually:
pip install -t vendor/ openai anthropic elevenlabs SpeechRecognition gTTS pyttsx3 spacy pygame pytesseract pillow
```

### 3. Download spaCy language models
```bash
python -m spacy download en_core_web_sm
python -m spacy download de_core_news_sm
# Copy to vendor/spacy_models/
```

### 4. System dependencies
```bash
# Linux (Ubuntu/Debian)
sudo apt install portaudio19-dev tesseract-ocr espeak

# macOS
brew install portaudio tesseract espeak

# Windows - see Requirements section
```

### 5. Restart Anki
The addon will appear in your addons list.

## 🐛 Troubleshooting

**TTS not working?**
- Check the TTS provider order in settings
- Ensure espeak is installed (Linux)
- Try a different provider

**Microphone not detected?**
- Install portaudio: `sudo apt install portaudio19-dev`
- Check microphone selection in STT settings

**OCR not working?**
- Use GPT-4 Vision (requires OpenAI key)
- Or install Tesseract locally

**Rating seems wrong?**
- Adjust scoring thresholds in Scoring tab
- Try switching between embedding and LLM scoring

## 📝 License

MIT License - Free for personal and educational use.

## � Author

**Florian Schlösser** - [@fsch-ppi](https://github.com/fsch-ppi)

## �🙏 Credits

Built with ❤️ for the Anki community.

---

**Keyboard Shortcut**: `Ctrl+Shift+H` to toggle hands-free mode
