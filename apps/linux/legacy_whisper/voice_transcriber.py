import sounddevice as sd
import soundfile as sf
import numpy as np
import os
import platform
import threading
import queue
import time
import webbrowser
import pyperclip
import pyautogui
import subprocess
import requests
import json
import signal
import socket
import uuid
from pynput import keyboard as pynput_keyboard
from faster_whisper import WhisperModel
import sys
from datetime import datetime

# === CONFIG ===
SAMPLE_RATE = 16000
CHANNELS = 1
MODEL_SIZE = "medium"
IS_MAC = platform.system() == "Darwin"
DEVICE = "cpu" if IS_MAC else "cuda"
COMPUTE_TYPE = "int8" if IS_MAC else "float16"
TRANSCRIBE_BACKEND = os.getenv("VOICE2CLIPBOARD_BACKEND", "auto")  # auto|faster|mlx
MIC_BAR_WIDTH = 30
CHATGPT_ICON_IMAGE = "assets/chatgpt_plus.jpeg"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma:2b"
MLX_HELPER_SOCKET = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_SOCKET", "/tmp/voice2clipboard_mlx_helper.sock")
MLX_HELPER_STATE = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_STATE", "/tmp/voice2clipboard_mlx_helper_state.json")
MLX_HELPER_WAIT_TIMEOUT_S = float(os.getenv("VOICE2CLIPBOARD_MLX_HELPER_WAIT_TIMEOUT_S", "120"))
QUICK_SEND_TRACE_PATH = os.getenv("VOICE2CLIPBOARD_QUICK_SEND_TRACE", "/tmp/voice2clipboard_quick_send_trace.jsonl")
STOP_REQUEST_FILE = os.getenv("VOICE2CLIPBOARD_STOP_REQUEST_FILE", "/tmp/voice2clipboard_quick_autopaste.stop")
AUDIO_STATE_FILE = os.getenv("VOICE2CLIPBOARD_AUDIO_STATE_FILE", "/tmp/voice2clipboard_quick_autopaste.audio")


def playsound(path, block=False):
    if IS_MAC:
        p = subprocess.Popen(['afplay', path])
        if block:
            p.wait()
    else:
        from playsound import playsound as _playsound
        _playsound(path)


# === Globals ===
whisper_model = None  # loaded once on first transcription
recording = True
duration_sec = 0
start_time = None
action_chosen = None
callback_enabled = True
stop_requested_by_signal = False
quick_stop_source = None
stop_event = threading.Event()
active_input_stream = None
RECORDING_FILENAME = "recorded.wav"  # fallback only
TRANSCRIPTION_FILENAME = "transcription.txt"
STATS_FILENAME = "stats.json"
current_audio_path = None
current_transcript_path = None
current_stats_path = None
last_backend_info = {}


def generate_paths():
    now = datetime.now()
    base_folder = os.path.join("recordings", now.strftime("%Y-%m-%d"), now.strftime("%H-%M-%S"))
    os.makedirs(base_folder, exist_ok=True)
    global current_audio_path, current_transcript_path, current_stats_path
    current_audio_path = os.path.join(base_folder, "audio.wav")
    current_transcript_path = os.path.join(base_folder, "transcript.txt")
    current_stats_path = os.path.join(base_folder, STATS_FILENAME)
    return current_audio_path


def current_quick_send_marker_path():
    if current_audio_path:
        return os.path.join(os.path.dirname(current_audio_path), ".sent")
    return None


def write_quick_send_marker(marker_path, value):
    if not marker_path:
        return
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    with open(marker_path, "w") as f:
        f.write(value)


def claim_quick_send_marker(marker_path, value):
    if not marker_path:
        return True
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(marker_path, flags)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        f.write(value)
    return True


def clear_quick_send_marker(marker_path):
    if marker_path and os.path.exists(marker_path):
        os.remove(marker_path)


def append_quick_send_trace(event, **fields):
    payload = {
        "ts": datetime.now().isoformat(),
        "event": event,
        "pid": os.getpid(),
        "recording_dir": os.path.dirname(current_audio_path) if current_audio_path else None,
    }
    payload.update(fields)
    with open(QUICK_SEND_TRACE_PATH, "a") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def stop_request_active():
    return bool(STOP_REQUEST_FILE) and os.path.exists(STOP_REQUEST_FILE)


def touch_stop_request_file():
    if not STOP_REQUEST_FILE:
        return
    with open(STOP_REQUEST_FILE, "a"):
        pass


def write_audio_state(path):
    if not AUDIO_STATE_FILE:
        return
    with open(AUDIO_STATE_FILE, "w") as f:
        f.write(path)


def clear_audio_state():
    if AUDIO_STATE_FILE and os.path.exists(AUDIO_STATE_FILE):
        os.remove(AUDIO_STATE_FILE)


def request_recording_stop(source=None):
    global recording, stop_requested_by_signal, quick_stop_source
    if source and quick_stop_source is None:
        quick_stop_source = source
    stop_requested_by_signal = True
    recording = False
    stop_event.set()
    # Let the recording thread unwind its own InputStream context.
    # Stopping the PortAudio/CoreAudio stream from the listener thread can
    # deadlock on macOS inside AudioOutputUnitStop / FinishStoppingStream.


SUPPORTED_AUDIO_EXTENSIONS = {'.wav', '.mp3', '.ogg', '.m4a', '.flac', '.opus'}
QUICK_MODE_PREFIX = "[Voice] "
MAC_SOUNDS = {
    # Use system AIFF for lower startup latency than custom MP3 decode.
    "record_start": "/System/Library/Sounds/Pop.aiff",
    "transcribe_start": "/System/Library/Sounds/Tink.aiff",
    "done": "/System/Library/Sounds/Glass.aiff",
}
TERMINAL_LIKE_APPS = {
    "iterm",
    "iterm2",
    "terminal",
    "warp",
    "kitty",
    "alacritty",
    "wezterm",
    "ghostty",
}

SILENCE_RMS_THRESHOLD = 1e-6


def print_help():
    print("""
🎙️ voice_transcriber.py - Record or transcribe voice audio using Whisper

USAGE:
  python3 voice_transcriber.py                   # Start recording interactively
  python3 voice_transcriber.py --quick           # Quick mode: record, transcribe, paste at cursor + Enter
  python3 voice_transcriber.py --quick --copy-only  # Quick mode: record, transcribe, copy to clipboard only
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
    Default: transcribes and pastes text at cursor position with voice prefix, then presses Enter.
    With --copy-only: transcribes and copies text to clipboard only (no paste, no Enter).

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


def play_feedback(event, block=False):
    if IS_MAC:
        path = MAC_SOUNDS.get(event, "sounds/plop.mp3")
        playsound(path, block=block)
    else:
        playsound("sounds/plop.mp3", block=block)


def format_quick_text(text):
    return f"{QUICK_MODE_PREFIX}{text.strip()}"


def audio_is_effectively_silent(filename):
    try:
        audio, _samplerate = sf.read(filename)
    except Exception:
        return False

    if getattr(audio, "ndim", 1) > 1:
        audio = audio[:, 0]
    if len(audio) == 0:
        return True

    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    return rms <= SILENCE_RMS_THRESHOLD


def record_audio(filename, quick_mode=False):
    global duration_sec, recording, callback_enabled, start_time, stop_requested_by_signal, active_input_stream
    q = queue.Queue()

    def _callback(indata, frames, time_info, status):
        q.put(indata.copy())
        audio_callback(indata, frames, time_info, status)

    with sf.SoundFile(filename, mode='w', samplerate=SAMPLE_RATE, channels=CHANNELS) as file:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=_callback) as stream:
            active_input_stream = stream
            play_feedback("record_start", block=True)  # wait for sound = go signal
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
                    if quick_mode and stop_request_active():
                        request_recording_stop("stop_file_loop")
                        continue
                    try:
                        file.write(q.get(timeout=0.1))
                    except queue.Empty:
                        continue
            finally:
                active_input_stream = None
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
    global last_backend_info
    play_feedback("transcribe_start")
    print("🧠 Transcribing...")
    start = time.time()
    if audio_is_effectively_silent(filename):
        raise RuntimeError(
            "Recorded audio is silent. On macOS this usually means the recorder "
            "was launched from a process without microphone access."
        )
    text = transcribe_with_best_backend(filename)
    end = time.time()

    pyperclip.copy(text)
    print("📋 Copied to clipboard.")
    play_feedback("done")

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
    stats = {
        "input_duration_seconds": round(duration_sec, 4),
        "real_time_factor": round(rtf, 4),
        "transcription_time_seconds": round(end - start, 4),
        "output_text_length_chars": len(text),
        "audio_path": current_audio_path,
        "transcript_path": current_transcript_path,
        "transcribed_at": datetime.now().isoformat(),
        "backend": TRANSCRIBE_BACKEND,
        "model_size": MODEL_SIZE,
        "helper_launch_state": os.getenv("VOICE2CLIPBOARD_HELPER_LAUNCH_STATE"),
    }
    stats.update(last_backend_info or {})
    if current_stats_path:
        with open(current_stats_path, "w") as f:
            json.dump(stats, f, indent=2)
    return text


def mlx_repo_for_model(model_size):
    mapping = {
        "tiny": "mlx-community/whisper-tiny-mlx",
        "base": "mlx-community/whisper-base-mlx",
        "small": "mlx-community/whisper-small-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
        "large-v2": "mlx-community/whisper-large-v2-mlx",
        "large-v3": "mlx-community/whisper-large-v3-mlx",
    }
    return mapping.get(model_size, "mlx-community/whisper-medium-mlx")


def transcribe_with_mlx_subprocess(filename):
    """Run mlx-whisper in a separate process so crashes don't kill this script."""
    repo = mlx_repo_for_model(MODEL_SIZE)
    payload = r"""
import json
import sys

audio = sys.argv[1]
repo = sys.argv[2]
import mlx_whisper

try:
    result = mlx_whisper.transcribe(audio, path_or_hf_repo=repo)
except TypeError:
    result = mlx_whisper.transcribe(audio, repo)

if isinstance(result, dict):
    text = result.get("text", "")
else:
    text = str(result)
print(json.dumps({"text": text.strip()}))
""".strip()
    cmd = [sys.executable, "-c", payload, filename, repo]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip().splitlines()
        reason = stderr[-1] if stderr else f"exit code {result.returncode}"
        raise RuntimeError(reason)
    output = (result.stdout or "").strip().splitlines()
    if not output:
        raise RuntimeError("mlx-whisper returned empty output")
    data = json.loads(output[-1])
    text = data.get("text", "").strip()
    if not text:
        raise RuntimeError("mlx-whisper returned empty transcription")
    return text


def read_mlx_helper_state():
    if not os.path.exists(MLX_HELPER_STATE):
        return {}
    try:
        with open(MLX_HELPER_STATE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def transcribe_with_mlx_helper(filename):
    helper_state_at_start = read_mlx_helper_state()
    helper_status_at_start = helper_state_at_start.get("status", "missing")
    helper_ready_at_start = helper_status_at_start == "ready"
    helper_wait_start = time.time()
    waited_for_ready_s = 0.0

    if helper_ready_at_start:
        rss_mb = helper_state_at_start.get("rss_mb")
        load_s = helper_state_at_start.get("model_load_seconds")
        detail = []
        if rss_mb is not None:
            detail.append(f"rss≈{rss_mb} MB")
        if load_s is not None:
            detail.append(f"initial load={load_s}s")
        suffix = f" ({', '.join(detail)})" if detail else ""
        print(f"⚡ MLX helper already loaded{suffix}.")
    else:
        print("⏳ MLX helper is still loading; recording is safe, waiting for model now...")

    last_error = "helper unavailable"
    while time.time() - helper_wait_start < MLX_HELPER_WAIT_TIMEOUT_S:
        if os.path.exists(MLX_HELPER_SOCKET):
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.connect(MLX_HELPER_SOCKET)
                    waited_for_ready_s = time.time() - helper_wait_start
                    payload = {"command": "transcribe", "audio_path": filename}
                    client.sendall((json.dumps(payload) + "\n").encode("utf-8"))
                    response = b""
                    while not response.endswith(b"\n"):
                        chunk = client.recv(65536)
                        if not chunk:
                            break
                        response += chunk
                if not response:
                    last_error = "empty helper response"
                else:
                    data = json.loads(response.decode("utf-8"))
                    if not data.get("ok"):
                        raise RuntimeError(data.get("error", "helper request failed"))
                    text = (data.get("text") or "").strip()
                    if not text:
                        raise RuntimeError("helper returned empty transcription")
                    helper_state = data.get("helper_state", {})
                    info = {
                        "resolved_backend": "mlx_helper",
                        "helper_status_at_request_start": helper_status_at_start,
                        "helper_ready_at_request_start": helper_ready_at_start,
                        "helper_waited_for_ready_seconds": round(waited_for_ready_s, 4),
                        "helper_waited_for_model_load": not helper_ready_at_start,
                        "helper_rss_mb": helper_state.get("rss_mb"),
                        "helper_model_load_seconds": helper_state.get("model_load_seconds"),
                        "helper_transcription_time_seconds": data.get("transcription_time_seconds"),
                    }
                    if helper_ready_at_start:
                        print("✅ MLX helper was warm for this run.")
                    else:
                        print(f"✅ MLX helper became ready after {waited_for_ready_s:.2f}s.")
                    return text, info
            except Exception as e:
                last_error = str(e)
        time.sleep(0.1)

    raise RuntimeError(f"Timed out waiting for MLX helper: {last_error}")


def transcribe_with_faster_whisper(filename):
    global whisper_model
    if whisper_model is None:
        print("⏳ Loading faster-whisper model...")
        whisper_model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    model = whisper_model
    segments, _info = model.transcribe(filename, beam_size=1, best_of=1)
    return " ".join([seg.text for seg in segments]).strip()


def transcribe_with_best_backend(filename):
    global last_backend_info
    backend = TRANSCRIBE_BACKEND.lower()
    if IS_MAC and backend in {"auto", "mlx"}:
        print("⚡ Trying mlx-whisper backend...")
        try:
            if os.getenv("VOICE2CLIPBOARD_MLX_HELPER") == "1":
                text, info = transcribe_with_mlx_helper(filename)
            else:
                text = transcribe_with_mlx_subprocess(filename)
                info = {"resolved_backend": "mlx_subprocess"}
            last_backend_info = info
            return text
        except Exception as e:
            if backend == "mlx":
                raise
            print(f"⚠️ mlx-whisper unavailable ({e}); falling back to faster-whisper.")

    last_backend_info = {"resolved_backend": "faster_whisper"}
    return transcribe_with_faster_whisper(filename)


def send_to_existing_chatgpt(text):
    print("📨 Focusing Firefox window...")
    try:
        if IS_MAC:
            subprocess.call(['osascript', '-e', 'tell application "Firefox" to activate'])
        else:
            subprocess.call(['xdotool', 'search', '--onlyvisible', '--class', 'firefox', 'windowactivate'])
        time.sleep(0.2)
        if focus_and_click_chatgpt_input(timeout=5):
            pyautogui.hotkey("command" if IS_MAC else "ctrl", "v")
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
    global quick_stop_source

    def on_press(key):
        global quick_stop_source
        if key == pynput_keyboard.Key.esc:
            if quick_stop_source is None:
                quick_stop_source = "escape"
            request_recording_stop("escape")

    listener = pynput_keyboard.Listener(on_press=on_press)
    listener.start()
    while recording:
        time.sleep(0.05)
    listener.stop()


def handle_external_stop_during_recording():
    """Watch for launcher stop-file requests in quick mode."""
    while recording:
        if stop_request_active():
            request_recording_stop("external_stop")
            return
        time.sleep(0.05)


def handle_stop_signal(signum, frame):
    """Gracefully stop active capture when receiving SIGINT/SIGTERM."""
    request_recording_stop(f"signal:{signum}")


def _escape_applescript_string(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def target_is_vscode(target_window):
    if not target_window:
        return False
    name = target_window.strip().lower()
    return name in {"code", "visual studio code"}


def mac_paste_and_submit(target_window, use_shift_paste=False):
    escaped_window = _escape_applescript_string(target_window) if target_window else ""
    if target_window:
        activate_clause = f'tell application "{escaped_window}" to activate\n    delay 0.5\n'
    else:
        activate_clause = ""
    if use_shift_paste:
        script = f'''
{activate_clause}tell application "System Events"
    keystroke "v" using {{command down, shift down}}
    delay 0.3
    key code 36
end tell
'''.strip()
        submit_mode = "keystroke_shift_paste"
    elif target_is_vscode(target_window):
        script = f'''
{activate_clause}tell application "System Events"
    tell process "{escaped_window}"
        click menu item "Terminal" of menu "View" of menu bar item "View" of menu bar 1
    end tell
    delay 0.25
    keystroke "v" using command down
    delay 0.45
    key code 36
end tell
'''.strip()
        submit_mode = "vscode_terminal_paste"
    elif target_window:
        script = f'''
{activate_clause}tell application "System Events"
    tell process "{escaped_window}"
        click menu item "Paste" of menu "Edit" of menu bar 1
    end tell
end tell
delay 0.35
tell application "{escaped_window}" to activate
delay 0.2
tell application "System Events"
    key code 36
end tell
'''.strip()
        submit_mode = "menu_paste"
    else:
        script = '''
tell application "System Events"
    keystroke "v" using command down
    delay 0.3
    key code 36
end tell
'''.strip()
        submit_mode = "keystroke_paste"
    append_quick_send_trace(
        "mac_submit_begin",
        target_window=target_window,
        use_shift_paste=use_shift_paste,
        submit_mode=submit_mode,
    )
    subprocess.check_call(["osascript", "-e", script])
    append_quick_send_trace(
        "mac_submit_end",
        target_window=target_window,
        use_shift_paste=use_shift_paste,
        submit_mode=submit_mode,
    )


def _run_iterm_session_applescript(session_id, action_lines):
    escaped_session = _escape_applescript_string(session_id)
    script = f'''
tell application "iTerm2"
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if (unique id of s as text) is "{escaped_session}" then
                    tell s
{action_lines}
                    end tell
                    return "ok"
                end if
            end repeat
        end repeat
    end repeat
end tell
return "not_found"
'''.strip()
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    status = (result.stdout or "").strip().lower()
    if result.returncode != 0 or status != "ok":
        detail = (result.stderr or result.stdout or f"status={status}").strip()
        raise RuntimeError(detail)


def send_text_to_iterm_session(text, session_id):
    one_line = " ".join(text.splitlines())
    escaped_text = _escape_applescript_string(one_line)
    action_lines = f'                        write text "{escaped_text}" newline NO'
    _run_iterm_session_applescript(session_id, action_lines)


def send_enter_to_iterm_session(session_id):
    action_lines = '                        write text (ASCII character 13) newline NO'
    _run_iterm_session_applescript(session_id, action_lines)


def target_uses_shift_paste(target_window):
    if not target_window:
        return False
    name = target_window.strip().lower()
    return any(app in name for app in TERMINAL_LIKE_APPS)


def paste_at_cursor_and_send(text, target_window=None, target_iterm_session=None):
    """Paste text at current cursor position and press Enter."""
    marker_path = current_quick_send_marker_path()
    send_id = str(uuid.uuid4())
    append_quick_send_trace(
        "send_attempt",
        send_id=send_id,
        marker_path=marker_path,
        target_window=target_window,
        target_iterm_session=target_iterm_session,
    )
    if not claim_quick_send_marker(
        marker_path,
        f"claimed\nsend_id={send_id}\npid={os.getpid()}\n",
    ):
        append_quick_send_trace(
            "send_skipped_marker_exists",
            send_id=send_id,
            marker_path=marker_path,
            target_window=target_window,
            target_iterm_session=target_iterm_session,
        )
        print("⚠️ Quick-send already completed for this recording; skipping duplicate send.")
        return

    try:
        text_with_disclaimer = format_quick_text(text)
        pyperclip.copy(text_with_disclaimer)
        append_quick_send_trace(
            "clipboard_copied",
            send_id=send_id,
            text_length=len(text_with_disclaimer),
        )

        if IS_MAC and target_iterm_session:
            print("🔄 Sending text directly to original iTerm session...")
            try:
                append_quick_send_trace(
                    "iterm_direct_send_begin",
                    send_id=send_id,
                    target_iterm_session=target_iterm_session,
                    submit_mode="single_enter_400ms",
                )
                send_text_to_iterm_session(text_with_disclaimer, target_iterm_session)
                play_feedback("transcribe_start")
                time.sleep(0.4)
                send_enter_to_iterm_session(target_iterm_session)
                append_quick_send_trace(
                    "iterm_direct_enter",
                    send_id=send_id,
                    target_iterm_session=target_iterm_session,
                    submit_mode="single_enter_400ms",
                    delay_s=0.4,
                )
                write_quick_send_marker(
                    marker_path,
                    f"iterm_session\nsend_id={send_id}\npid={os.getpid()}\n",
                )
                append_quick_send_trace(
                    "iterm_direct_send_end",
                    send_id=send_id,
                    target_iterm_session=target_iterm_session,
                    submit_mode="single_enter_400ms",
                )
                print("📨 Sent to iTerm session.")
                return
            except Exception as e:
                append_quick_send_trace(
                    "iterm_direct_send_failed",
                    send_id=send_id,
                    target_iterm_session=target_iterm_session,
                    submit_mode="single_enter_400ms",
                    error=str(e),
                )
                print(f"⚠️ Direct iTerm send failed ({e}); falling back to clipboard paste.")

        if IS_MAC:
            if target_window:
                print(f"🔄 Refocusing original window ({target_window})...")
            mac_paste_and_submit(
                target_window,
                use_shift_paste=target_uses_shift_paste(target_window),
            )
        else:
            if target_window:
                print(f"🔄 Refocusing original window ({target_window})...")
                subprocess.call(['xdotool', 'windowactivate', '--sync', target_window])
                time.sleep(0.5)
            pyautogui.hotkey("ctrl", "shift", "v")
            time.sleep(0.3)
            pyautogui.press("enter")
        write_quick_send_marker(
            marker_path,
            f"clipboard_paste\nsend_id={send_id}\npid={os.getpid()}\n",
        )
        append_quick_send_trace(
            "generic_send_complete",
            send_id=send_id,
            target_window=target_window,
            target_iterm_session=target_iterm_session,
        )
        print("📨 Pasted and sent.")
    except Exception as e:
        clear_quick_send_marker(marker_path)
        append_quick_send_trace(
            "send_failed",
            send_id=send_id,
            target_window=target_window,
            target_iterm_session=target_iterm_session,
            error=str(e),
        )
        raise


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
        playsound("sounds/plop.mp3")
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
    global recording, stop_requested_by_signal, quick_stop_source, callback_enabled

    # Parse arguments
    quick_mode = "--quick" in sys.argv
    copy_only = "--copy-only" in sys.argv
    recording = True
    callback_enabled = True
    stop_requested_by_signal = False
    quick_stop_source = None
    stop_event.clear()
    target_window = None
    target_iterm_session = None
    if "--target-window" in sys.argv:
        idx = sys.argv.index("--target-window")
        if idx + 1 < len(sys.argv):
            target_window = sys.argv[idx + 1]
    if "--target-iterm-session" in sys.argv:
        idx = sys.argv.index("--target-iterm-session")
        if idx + 1 < len(sys.argv):
            target_iterm_session = sys.argv[idx + 1]

    args = [
        a for a in sys.argv[1:]
        if a not in [
            "--quick",
            "--target-window",
            target_window or "",
            "--target-iterm-session",
            target_iterm_session or "",
            "--copy-only",
        ]
    ]

    if len(args) > 1 or (len(args) == 1 and args[0] in ["--help", "-h"]):
        print_help()
        return

    signal.signal(signal.SIGINT, handle_stop_signal)
    signal.signal(signal.SIGTERM, handle_stop_signal)

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
        clear_audio_state()
        text = transcribe_audio(input_file)
        if quick_mode:
            if copy_only:
                pyperclip.copy(format_quick_text(text))
                print("📋 Quick mode copy-only: transcription is in clipboard.")
            else:
                paste_at_cursor_and_send(text, target_window, target_iterm_session)
        else:
            post_transcription_menu(text)
        return

    # Recording mode
    filename = generate_paths()
    write_audio_state(filename)

    if quick_mode:
        # Quick mode: Escape to stop, then paste at cursor
        recording = True
        recorder = threading.Thread(target=record_audio, args=(filename, True))
        escape_listener = threading.Thread(target=handle_escape_during_recording)
        external_stop_listener = threading.Thread(target=handle_external_stop_during_recording)
        recorder.start()
        escape_listener.start()
        external_stop_listener.start()
        recorder.join()
        escape_listener.join()
        external_stop_listener.join()

        if os.path.exists(filename):
            if stop_requested_by_signal:
                detail = f" via {quick_stop_source}" if quick_stop_source else ""
                print(f"⏹️ Stop requested{detail}.")
            text = transcribe_audio(filename)
            if copy_only:
                pyperclip.copy(format_quick_text(text))
                print("📋 Quick mode copy-only: transcription is in clipboard.")
            else:
                paste_at_cursor_and_send(text, target_window, target_iterm_session)
        clear_audio_state()
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
                clear_audio_state()
                return
            text = transcribe_audio(filename)
            post_transcription_menu(text)
        clear_audio_state()


if __name__ == "__main__":
    main()
