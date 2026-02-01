# Voice2Clipboard

**Voice capture for transcription and clipboard – all in one keypress.**

## Main Use Case

Capture voice notes during your workflow. Hit a key, talk, and it:

- Records your voice
- Transcribes it using a local Whisper model
- Copies the text to your clipboard
- Optionally pastes it directly into ChatGPT or Claude Code
- Saves the audio and transcript with timestamps

Ideal for code commentary, journaling, bug reporting, voice-based chat prompting, and hands-free idea dumps.

---

## Features

- **Voice recording** with visual feedback
- **Local Whisper transcription** via `faster-whisper` (no cloud API needed)
- **Automatic clipboard copy**
- **Quick mode** for Claude Code and terminals (`--quick`)
- **ChatGPT integration** - paste into existing or new tab
- **Multiple audio formats**: WAV, MP3, OGG, M4A, FLAC, OPUS (WhatsApp voice messages work)
- **Local LLM cleanup** (optional) - smart filename generation via Ollama
- **Organized storage**: `recordings/YYYY-MM-DD/HH-MM-SS/`
- **Global keyboard shortcut** support

---

## Requirements

Tested on **Ubuntu 22.04** with:

- Python 3.10+
- `faster-whisper` (transcription)
- `ollama` with a small model like `gemma:2b` (optional, for text cleanup)
- System packages: `xdotool`, `ffmpeg`, `portaudio19-dev`, `scrot`

---

## Installation

```bash
# Create virtual environment
python3 -m venv ~/.virtualenvs/voice2clipboard
source ~/.virtualenvs/voice2clipboard/bin/activate
pip install -r requirements.txt

# Install system dependencies
sudo apt install portaudio19-dev xdotool ffmpeg scrot
```

---

## Usage

### Standard Mode

```bash
python voice_transcriber.py
```

After recording, choose an action:

| Key | Action |
|-----|--------|
| 1 | Show transcription (default) |
| 2 | Paste into existing ChatGPT tab |
| 3 | Open ChatGPT and paste |
| 4 | Use local LLM to clean text & rename folder |
| 5 | Cancel (discard all) |

Text is always copied to clipboard automatically.

### Quick Mode (for Claude Code)

Designed for fast dictation directly into Claude Code or any terminal:

```bash
python voice_transcriber.py --quick
```

1. Press hotkey to start recording
2. Speak your message
3. Press **Escape** to stop
4. Text is transcribed, prefixed with a disclaimer, and pasted at cursor
5. Enter is pressed automatically

The disclaimer helps LLMs understand potential errors:
`[Transcribed with Whisper medium - may contain errors]`

---

## Global Shortcut Setup (Ubuntu)

1. Edit `run_transcriber.sh` with your paths:

```bash
#!/bin/bash
source /home/YOUR_USER/.virtualenvs/voice2clipboard/bin/activate
cd /home/YOUR_USER/path/to/voice2clipboard
gnome-terminal -- bash -c 'python3 voice_transcriber.py; exec bash'
```

2. Make executable: `chmod +x run_transcriber.sh`

3. In **Settings > Keyboard > Shortcuts**, add a custom shortcut pointing to the script (e.g., `Ctrl+Alt+U`)

For quick mode, use `run_transcriber_quick.sh` instead.

---

## Performance Benchmarks

Tested on RTX A2000 (4GB VRAM) with an 83-second audio file:

| Model | Precision | Beam | Load | Transcribe | Total | Notes |
|-------|-----------|------|------|------------|-------|-------|
| medium | float16 | 5 | 1.3s | 6.0s | 7.3s | Reference |
| **medium** | **float16** | **1** | **1.3s** | **3.0s** | **4.3s** | **Default - best balance** |
| small | int8 | 1 | 0.9s | 1.4s | 2.3s | Minor errors |
| base | int8 | 1 | 0.4s | 0.6s | 1.0s | Some errors |
| tiny | int8 | 1 | 0.3s | 0.5s | 0.8s | More errors |

**Key finding**: `beam_size=1` is 2x faster than `beam_size=5` with no quality loss for most audio.

Run your own benchmarks:
```bash
python benchmark_whisper.py
python compare_transcriptions.py
```

---

## Folder Structure

```
recordings/
  └── 2025-05-03/
        └── 14-38-12/
              ├── audio.wav
              └── transcript.txt
```

With LLM mode (4), folders are renamed to include the topic: `14-38-12_MercuryDashboardFix`

---

## Optional: Local LLM Setup

For text cleanup and smart filename generation:

1. [Install Ollama](https://ollama.com/)
2. Run `ollama serve` (if needed)
3. Pull a model: `ollama run gemma:2b`
4. Configure `OLLAMA_URL` and `OLLAMA_MODEL` in `voice_transcriber.py`

The script works without Ollama – this just disables mode 4.

---

## Known Limitations

- Local LLM punctuation may be slow on GPUs with limited VRAM
- ChatGPT field detection relies on screenshots (may be fragile)
- Linux-only for automation features (xdotool, pyautogui)

---

## Credits

- Transcription: [faster-whisper](https://github.com/guillaumekln/faster-whisper)
- LLM: [Ollama](https://ollama.com/)
- ChatGPT integration: Firefox + xdotool
