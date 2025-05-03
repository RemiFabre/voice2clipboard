# 🎙️ Voice2ChatGPT

**Instant voice capture for transcription, clipboard, and ChatGPT interaction – all in one keypress.**

## 🚀 Main Use Case

This tool makes it **effortless** to capture voice notes or ideas during your workflow. You hit a single key, talk, and it:

- records your voice;
- transcribes it using a local Whisper model;
- copies the text to your clipboard;
- optionally pastes it directly into ChatGPT;
- saves the audio and transcript into a clean, timestamped folder.

This is ideal for:

- code commentary,
- journaling,
- bug reporting,
- voice-based chat prompting,
- hands-free idea dumps.

---

## ✨ Features

- 🎤 Voice recording from a keypress (with visual feedback).
- 🔠 Local Whisper transcription (via `faster-whisper`).
- 📋 Automatically copies text to clipboard.
- 🧠 [Optional] Local LLM cleanup & smart filename generation (via Ollama).
- 💬 Paste directly into ChatGPT (existing or new tab).
- 🗂️ Saved as daily folders with time-based subfolders (`recordings/YYYY-MM-DD/HH-MM-SS/`).
- ⌨️ Can be launched with a **global keyboard shortcut**.

---

## 🧰 Requirements

Tested on **Ubuntu 22.04** with:

- Python 3.10+
- `faster-whisper` (for transcription)
- `ollama` with a small model (e.g. `gemma:2b`) [optional]
- `xdotool`, `ffmpeg`, `playsound`, `pyautogui`, `pyperclip`, `pynput`, `requests`

---

## 📦 Installation

Create a fresh Python virtual environment:

```bash
python3 -m venv ~/.virtualenvs/voice2chatgpt
source ~/.virtualenvs/voice2chatgpt/bin/activate
pip install -r requirements.txt
````

You may also need system packages:

```bash
sudo apt install portaudio19-dev xdotool ffmpeg scrot
```

> Tip: If `playsound` gives warnings, ignore them or switch to a custom sound player.

---

## 🧠 Optional: Local LLM setup

To enable the text improvement and filename suggestion feature (mode 4):

1. [Install Ollama](https://ollama.com/)
2. Run:

   ```bash
   ollama run gemma:2b
   ```
3. Make sure `OLLAMA_URL` and `OLLAMA_MODEL` are configured in `voice_transcriber.py`.

If Ollama is not available, the script will still function normally (just without smart cleanup).

---

## 🖱️ Launch with a Global Shortcut (Ubuntu only)

You can launch the tool with a single shortcut from anywhere:

1. Use the `run_transcriber.sh` file in this repo as a launcher.

2. Edit the paths inside it:

   ```bash
   #!/bin/bash
   source /home/YOUR_USER/.virtualenvs/voice2chatgpt/bin/activate
   cd /home/YOUR_USER/path/to/voice2chatgpt
   gnome-terminal -- bash -c 'python3 voice_transcriber.py; exec bash'
   ```

3. Make it executable:

   ```bash
   chmod +x run_transcriber.sh
   ```

4. Go to **Settings > Keyboard > Shortcuts**, add a **custom shortcut**:

   * Name: `Voice2ChatGPT`
   * Command: `/full/path/to/run_transcriber.sh`
   * Shortcut: for example `Ctrl + Alt + U`

That's it! From now on, pressing your chosen shortcut will open a terminal, start recording, and you can begin speaking immediately.

> 🧠 Similar shortcut systems can be set up on other OSes using AutoHotKey (Windows) or Automator (macOS), but are not included in this guide.

---

## 🗃️ Folder Structure

Each session is stored in:

```
recordings/
  └── 2025-05-03/
        └── 14-38-12/
              ├── audio.wav
              └── transcript.txt
```

If mode 4 is used, the folder will be renamed to include the suggested topic (e.g., `14-38-12_MercuryDashboardFix`).

---

## 🧪 Modes (choose after recording)

| Key | Action                               |
| --- | ------------------------------------ |
| 1   | Show transcription (default)         |
| 2   | Paste into existing ChatGPT tab      |
| 3   | Open ChatGPT and paste               |
| 4   | Use local LLM to clean text & rename |
| 5   | Cancel (discard all)                 |

> Text is always copied to clipboard automatically.

---

## 🛠️ TODO / Known Limitations

* Local LLM punctuation is optional, and may be slow on GPUs with limited VRAM.
* Visual ChatGPT field detection relies on screenshots (may be fragile).
* Currently Linux-only for automation features (xdotool, pyautogui).

---

## 🧡 Credits

* Whisper transcription by [faster-whisper](https://github.com/guillaumekln/faster-whisper)
* Optional LLM via [Ollama](https://ollama.com/)
* ChatGPT integration via Firefox + xdotool
