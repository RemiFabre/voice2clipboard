import sounddevice as sd
import soundfile as sf
import numpy as np
import os
import threading
import queue
import time
import webbrowser
import pyperclip
import pyautogui
import subprocess
import requests
import json
from pynput import keyboard as pynput_keyboard
from faster_whisper import WhisperModel
from playsound import playsound
import sys
from datetime import datetime

# === CONFIG ===
SAMPLE_RATE = 16000
CHANNELS = 1
MODEL_SIZE = "medium"
DEVICE = "cuda"
COMPUTE_TYPE = "float16"
MIC_BAR_WIDTH = 30
CHATGPT_ICON_IMAGE = "assets/chatgpt_plus.jpeg"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma:2b"

# === Globals ===
recording = True
duration_sec = 0
start_time = None
action_chosen = None
callback_enabled = True
RECORDING_FILENAME = "recorded.wav"  # fallback only
TRANSCRIPTION_FILENAME = "transcription.txt"
current_audio_path = None
current_transcript_path = None


def generate_paths():
    now = datetime.now()
    base_folder = os.path.join("recordings", now.strftime("%Y-%m-%d"), now.strftime("%H-%M-%S"))
    os.makedirs(base_folder, exist_ok=True)
    global current_audio_path, current_transcript_path
    current_audio_path = os.path.join(base_folder, "audio.wav")
    current_transcript_path = os.path.join(base_folder, "transcript.txt")
    return current_audio_path


SUPPORTED_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.ogg', '.m4a', '.flac', '.opus'}
QUICK_MODE_DISCLAIMER = f"[Transcribed with Whisper {MODEL_SIZE} - may contain errors] "


def print_help():
    print("""
🎙️ voice_transcriber.py - Record or transcribe voice audio using Whisper

USAGE:
  python3 voice_transcriber.py                   # Start recording interactively
  python3 voice_transcriber.py --quick           # Quick mode: record, transcribe, paste at cursor + Enter
  python3 voice_transcriber.py <audio_file>      # Transcribe existing file (no recording)
  python3 voice_transcriber.py --help            # Show this help message

SUPPORTED FORMATS:
  .wav, .mp3, .ogg, .m4a, .flac, .opus (WhatsApp voice messages work!)

MODES:
  Default mode: Press 1–5 during recording to choose action
    1: Show transcription
    2: Paste into ChatGPT (existing tab)
    3: Open ChatGPT and paste
    4: Improve and rename with local LLM
    5: Cancel

  Quick mode (--quick): Press Escape to stop recording.
    Transcribes and pastes text at cursor position with disclaimer, then presses Enter.

- 📋 Text will always be copied to clipboard automatically.
""")


def audio_callback(indata, frames, time_info, status):
    global callback_enabled
    if not callback_enabled:
        return
    volume_norm = np.linalg.norm(indata) / len(indata)
    level = min(int(volume_norm * 100 * MIC_BAR_WIDTH), MIC_BAR_WIDTH)
    bar = "█" * level + " " * (MIC_BAR_WIDTH - level)
    elapsed = time.time() - start_time if start_time else 0
    print(f"\r🎤 {elapsed:5.1f}s [{bar}]", end="", flush=True)


def record_audio(filename, quick_mode=False):
    global duration_sec, recording, callback_enabled, start_time
    q = queue.Queue()

    def _callback(indata, frames, time_info, status):
        q.put(indata.copy())
        audio_callback(indata, frames, time_info, status)

    with sf.SoundFile(filename, mode='w', samplerate=SAMPLE_RATE, channels=CHANNELS) as file:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=_callback):
            playsound("sounds/plop.wav")
            print("\n🎤 Recording started.")
            if quick_mode:
                print("Press Escape to stop recording.\n")
            else:
                print("Press:")
                print("  1 – Show transcription")
                print("  2 – Paste into ChatGPT (existing tab)")
                print("  3 – Open ChatGPT and paste")
                print("  4 – Improve and rename with local LLM")
                print("  5 – Cancel (discard and stop immediately)")
                print("📋 Text will always be copied to clipboard.\n")

            start_time = time.time()
            try:
                while recording:
                    try:
                        file.write(q.get(timeout=0.1))
                    except queue.Empty:
                        continue
            finally:
                duration_sec = time.time() - start_time
                callback_enabled = False
                print("\r" + " " * (MIC_BAR_WIDTH + 20), end="\r", flush=True)
                print("\n🎤 Recording stopped.")


def focus_and_click_chatgpt_input(timeout=5):
    try:
        print("🔍 Looking for '+' icon to focus input...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try :
                location = pyautogui.locateOnScreen(CHATGPT_ICON_IMAGE, confidence=0.85)
            except pyautogui.ImageNotFoundException:
                time.sleep(0.2)
                continue
            if location:
                center = pyautogui.center(location)
                pyautogui.click(center.x, center.y - 40)
                print("✅ Focused input box.")
                return True
        print("❌ '+' icon not found.")
        return False
    except Exception as e:
        print(f"⚠️ Input focus failed: {e}")
        return False


def transcribe_audio(filename):
    playsound("sounds/beep.wav")
    print("🧠 Transcribing...")
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    start = time.time()
    segments, info = model.transcribe(filename, beam_size=1, best_of=1)
    end = time.time()
    text = " ".join([seg.text for seg in segments])

    pyperclip.copy(text)
    print("📋 Copied to clipboard.")
    playsound("sounds/plop.wav")

    global duration_sec, current_transcript_path
    if duration_sec == 0:
        # For pre-recorded files, try to get duration via ffprobe (handles all formats)
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', filename],
                capture_output=True, text=True
            )
            file_duration = float(result.stdout.strip())
        except (ValueError, FileNotFoundError):
            # Fallback: try soundfile (works for WAV)
            try:
                with sf.SoundFile(filename) as f:
                    file_duration = len(f) / f.samplerate
            except Exception:
                file_duration = end - start  # Last resort: use transcription time
        rtf = (end - start) / file_duration if file_duration > 0 else 0
        duration_sec = file_duration
    else:
        rtf = (end - start) / duration_sec

    print("\n📊 Stats:")
    print(f" - Input duration       : {duration_sec:.2f} seconds")
    print(f" - Real-time factor     : {rtf:.2f}x")
    print(f" - Transcription time   : {end - start:.2f} seconds")
    print(f" - Output text length   : {len(text)} characters")
    print(f" - Saved to             : {current_transcript_path}")
    with open(current_transcript_path, "w") as f:
        f.write(text)
    return text


def send_to_existing_chatgpt(text):
    print("📨 Focusing Firefox window...")
    try:
        subprocess.call(['xdotool', 'search', '--onlyvisible', '--class', 'firefox', 'windowactivate'])
        time.sleep(0.2)
        if focus_and_click_chatgpt_input(timeout=5):
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)
            pyautogui.press("enter")
        else:
            print("⚠️ Could not find ChatGPT input box. Message not sent.")
    except Exception as e:
        print(f"❌ Failed to interact with Firefox: {e}")


def send_to_new_chatgpt(text):
    print("🌐 Opening ChatGPT...")
    webbrowser.get("firefox").open_new_tab("https://chat.openai.com/")
    found = focus_and_click_chatgpt_input(timeout=5)
    if found:
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)
        pyautogui.press("enter")
    else:
        print("⚠️ Input box not detected, you can paste manually.")


def call_llm(text):
    prompt = f"""You are a helpful assistant. Please:
1. Re-punctuate the text below correctly.
2. Suggest a short filename based on the content (in CamelCase).
3. Return both in JSON with 'punctuated_text' and 'suggested_filename'.

Text:
{text}
"""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    print("🤖 Calling local LLM...")
    try:
        res = requests.post(OLLAMA_URL, json=payload)
        raw = res.json().get("response", "{}")
        data = json.loads(raw.split("```json")[-1].split("```")[0].strip()) if "```" in raw else json.loads(raw)
        return data.get("punctuated_text", text), data.get("suggested_filename")
    except Exception as e:
        print(f"⚠️ LLM error: {e}")
        return text, None


def handle_key_input_during_recording():
    global action_chosen, recording

    def on_press(key):
        global action_chosen, recording
        key_map = {'1': 1, '2': 2, '3': 3, '4': 4, '5': 5}
        if hasattr(key, 'char') and key.char in key_map:
            action_chosen = key_map[key.char]
            recording = False
        elif hasattr(key, 'vk') and key.vk in {97: 1, 98: 2, 99: 3, 100: 4, 101: 5, 53: 5, 229: 5}:
            action_chosen = {97: 1, 98: 2, 99: 3, 100: 4, 101: 5, 53: 5, 229: 5}[key.vk]
            recording = False

    listener = pynput_keyboard.Listener(on_press=on_press)
    listener.start()
    while recording:
        time.sleep(0.05)
    listener.stop()


def handle_escape_during_recording():
    """Wait for Escape key to stop recording in quick mode."""
    global recording

    def on_press(key):
        global recording
        if key == pynput_keyboard.Key.esc:
            recording = False

    listener = pynput_keyboard.Listener(on_press=on_press)
    listener.start()
    while recording:
        time.sleep(0.05)
    listener.stop()


def paste_at_cursor_and_send(text, target_window=None):
    """Paste text at current cursor position and press Enter."""
    text_with_disclaimer = QUICK_MODE_DISCLAIMER + text
    pyperclip.copy(text_with_disclaimer)

    # Refocus original window if provided
    if target_window:
        print(f"🔄 Refocusing original window ({target_window})...")
        subprocess.call(['xdotool', 'windowactivate', '--sync', target_window])
        time.sleep(0.2)

    # Use Ctrl+Shift+V (works in terminals like Claude Code)
    pyautogui.hotkey("ctrl", "shift", "v")
    time.sleep(0.1)
    pyautogui.press("enter")
    print("📨 Pasted and sent.")


def post_transcription_menu(text):
    global action_chosen, current_audio_path, current_transcript_path
    print("\n📄 Transcription:\n")
    print(text)
    print()
    if action_chosen is None:
        print("\nWhat would you like to do?")
        print("1. Show transcription (default)")
        print("2. Paste into ChatGPT (existing tab)")
        print("3. Open ChatGPT and paste")
        print("4. Improve and rename with local LLM")
        print("5. Cancel (discard)")
        choice = input("Choose (1–5): ").strip()
        action_chosen = int(choice) if choice in '12345' else 1

    if action_chosen == 2:
        send_to_existing_chatgpt(text)
    elif action_chosen == 3:
        send_to_new_chatgpt(text)
    elif action_chosen == 4:
        new_text, new_name = call_llm(text)
        print("\n✨ Enhanced Text:\n")
        print(new_text)
        pyperclip.copy(new_text)
        print("📋 Copied enhanced version to clipboard.")
        playsound("sounds/plop.wav")
        if new_name:
            folder = os.path.dirname(current_audio_path)
            base = os.path.dirname(folder)
            renamed = os.path.join(base, f"{os.path.basename(folder)}_{new_name}")
            os.rename(folder, renamed)
            print(f"📁 Folder renamed to: {renamed}")
    elif action_chosen == 5:
        print("❌ Discarded.")
        try:
            os.remove(current_audio_path)
            os.remove(current_transcript_path)
        except FileNotFoundError:
            pass
    else:
        pass  # Default action is to show transcription and exit


def main():
    global recording

    # Parse arguments
    quick_mode = "--quick" in sys.argv
    target_window = None
    if "--target-window" in sys.argv:
        idx = sys.argv.index("--target-window")
        if idx + 1 < len(sys.argv):
            target_window = sys.argv[idx + 1]

    args = [a for a in sys.argv[1:] if a not in ["--quick", "--target-window", target_window or ""]]

    if len(args) > 1 or (len(args) == 1 and args[0] in ["--help", "-h"]):
        print_help()
        return

    # File transcription mode
    if len(args) == 1:
        input_file = args[0]
        if not os.path.isfile(input_file):
            print(f"❌ File not found: {input_file}")
            return
        ext = os.path.splitext(input_file)[1].lower()
        if ext not in SUPPORTED_AUDIO_EXTENSIONS:
            print(f"❌ Unsupported format: {ext}")
            print(f"   Supported: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}")
            return
        print(f"📂 Transcribing {ext} file...")
        generate_paths()
        text = transcribe_audio(input_file)
        if quick_mode:
            paste_at_cursor_and_send(text, target_window)
        else:
            post_transcription_menu(text)
        return

    # Recording mode
    filename = generate_paths()

    if quick_mode:
        # Quick mode: Escape to stop, then paste at cursor
        recording = True
        recorder = threading.Thread(target=record_audio, args=(filename, True))
        escape_listener = threading.Thread(target=handle_escape_during_recording)
        recorder.start()
        escape_listener.start()
        recorder.join()
        escape_listener.join()

        if os.path.exists(filename):
            text = transcribe_audio(filename)
            paste_at_cursor_and_send(text, target_window)
    else:
        # Default mode: 1-5 keys to choose action
        recorder = threading.Thread(target=record_audio, args=(filename,))
        hotkeys = threading.Thread(target=handle_key_input_during_recording)
        recorder.start()
        hotkeys.start()
        recorder.join()
        hotkeys.join()

        if os.path.exists(filename):
            if action_chosen == 5:
                print("❌ Aborted before transcription.")
                return
            text = transcribe_audio(filename)
            post_transcription_menu(text)


if __name__ == "__main__":
    main()
