import sounddevice as sd
import soundfile as sf
import numpy as np
import os
import re
import platform
import threading
import queue
import time
import webbrowser
import pyperclip
import subprocess
import json
import signal
import socket
import uuid
from pynput import keyboard as pynput_keyboard
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
INPUT_LOSS_SECONDS = float(os.getenv("VOICE2CLIPBOARD_INPUT_LOSS_SECONDS", "3"))
# Headset mode (dictation started from an earbud press): nobody is at the screen, so the recorder
# has to notice by itself that the headset is gone. Measured 2026-09-19: pauses inside real
# dictations stay under 0.002 rms for 14 s at most; a recording made after the headset dropped
# (built-in mic, empty room) sits around 0.0003 for its whole length.
VOICE_MODE = os.getenv("VOICE2CLIPBOARD_VOICE_MODE", "manual")
HEADSET_INPUT_PATTERN = os.getenv("VOICE2CLIPBOARD_HEADSET_PATTERN", "Shokz|OpenFit")
SILENCE_STOP_RMS = float(os.getenv("VOICE2CLIPBOARD_SILENCE_STOP_RMS", "0.002"))
SILENCE_STOP_SECONDS = float(os.getenv("VOICE2CLIPBOARD_SILENCE_STOP_SECONDS", "60"))
# Presses while recording. One press stops and sends. A cancel (nothing sent, audio and transcript
# kept, recoverable) needs a gesture the Mac can see, and in call mode that is not a double
# press: tested with Remi on 2026-09-19, the Shokz firmware swallows it, the Mac receives nothing
# at all (no second hang-up, no other AT command, no AVRCP command). So the wait-for-a-second-
# press window is 0 by default (immediate stop, no added latency); a press that reaches the Mac
# already classified as "double" (recording not made through the headset microphone) still
# cancels, and a short recording with no speech in it is treated as a cancelled accident.
DOUBLE_PRESS_WINDOW_S = float(os.getenv("VOICE2CLIPBOARD_DOUBLE_PRESS_WINDOW_S", "0"))
ACCIDENTAL_MAX_S = float(os.getenv("VOICE2CLIPBOARD_ACCIDENTAL_MAX_S", "15"))
PRESS_FILE = os.getenv("VOICE2CLIPBOARD_PRESS_FILE", "/tmp/voice2clipboard_quick_autopaste.press")
CANCELLED_MARKER = "cancelled"
ROUTE_CONFIRM_TIMEOUT_S = float(os.getenv("VOICE2CLIPBOARD_ROUTE_CONFIRM_TIMEOUT_S", "10"))
ROUTE_LATE_S = float(os.getenv("VOICE2CLIPBOARD_ROUTE_LATE_S", "0.35"))  # the cues carry a 350 ms silent lead-in
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
SECRETARY_INBOX_POST = os.path.join(REPO_ROOT, "scripts", "mac", "secretary", "inbox_post.sh")
SECRETARY_LOG = os.path.join(REPO_ROOT, "runtime", "secretary", "secretary.log")
# Lazy rotation of the secretary (scripts/mac/secretary/lazy_rotate.sh): at the press a fresh
# secretary may be booting; when it is ready before the transcript, the transcript goes there.
ROTATION_DIR = os.getenv("VOICE2CLIPBOARD_ROTATION_DIR", os.path.join(REPO_ROOT, "runtime", "secretary", "lazy_rotation"))
ROTATION_WAIT_SECONDS = float(os.getenv("VOICE2CLIPBOARD_ROTATION_WAIT_S", "30"))
CHATGPT_ICON_IMAGE = "assets/chatgpt_plus.jpeg"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma:2b"
MLX_HELPER_SOCKET = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_SOCKET", "/tmp/voice2clipboard_mlx_helper.sock")
MLX_HELPER_STATE = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_STATE", "/tmp/voice2clipboard_mlx_helper_state.json")
MLX_HELPER_WAIT_TIMEOUT_S = float(os.getenv("VOICE2CLIPBOARD_MLX_HELPER_WAIT_TIMEOUT_S", "120"))
# Streaming: while recording, the helper decodes VAD-closed speech in the background so the
# stop-to-text delay no longer grows with dictation length. Set to 0 for whole-file decoding.
STREAMING_ENABLED = os.getenv("VOICE2CLIPBOARD_STREAMING", "1") != "0"
QUICK_SEND_TRACE_PATH = os.getenv("VOICE2CLIPBOARD_QUICK_SEND_TRACE", "/tmp/voice2clipboard_quick_send_trace.jsonl")
STOP_REQUEST_FILE = os.getenv("VOICE2CLIPBOARD_STOP_REQUEST_FILE", "/tmp/voice2clipboard_quick_autopaste.stop")
AUDIO_STATE_FILE = os.getenv("VOICE2CLIPBOARD_AUDIO_STATE_FILE", "/tmp/voice2clipboard_quick_autopaste.audio")
PHASE_FILE = os.getenv("VOICE2CLIPBOARD_PHASE_FILE", "/tmp/voice2clipboard_quick_autopaste.phase")


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
stream_session_id = None  # set when the helper accepted stream_begin for this recording


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


def write_phase_state(phase):
    if not PHASE_FILE:
        return
    with open(PHASE_FILE, "w") as f:
        f.write(phase)


def clear_phase_state():
    if PHASE_FILE and os.path.exists(PHASE_FILE):
        os.remove(PHASE_FILE)


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
    # Custom cues with a 350 ms silent lead-in: Bluetooth earbuds swallow the first fraction of a
    # second while the audio link wakes up, so the 0.1 s system "Pop" was often never heard.
    "record_start": "sounds/cue_start.aiff",
    "record_stop": "sounds/cue_stop.aiff",
    "record_lost": "sounds/cue_fail.aiff",
    "record_cancel": "sounds/cue_cancel.aiff",
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


GO_BANNER = """
\033[1;32m
  ██████╗  ██████╗
 ██╔════╝ ██╔═══██╗
 ██║  ███╗██║   ██║
 ██║   ██║██║   ██║
 ╚██████╔╝╚██████╔╝
  ╚═════╝  ╚═════╝
\033[0m\033[1m   SPEAK NOW — microphone is live\033[0m
"""


def go_banner():
    return GO_BANNER


VERIFIED_CUE_PLAYER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
                                   "scripts", "mac", "secretary", "play_cue_verified.sh")
# Cues that confirm to someone away from the screen that the dictation was taken. In headset mode
# they go through the verified player: macOS sometimes accepts a cue's stream on the headset
# without ever running it, and the player replays the cue when the audio daemon's log shows that.
VERIFIED_CUES = {"record_stop", "record_lost", "record_cancel", "done"}


def play_feedback(event, block=False):
    if IS_MAC:
        path = MAC_SOUNDS.get(event, "sounds/plop.mp3")
        if (not block and event in VERIFIED_CUES and os.getenv("VOICE2CLIPBOARD_VOICE_MODE") == "headset"
                and os.path.exists(VERIFIED_CUE_PLAYER)):
            try:
                subprocess.Popen([VERIFIED_CUE_PLAYER, os.path.abspath(path), event],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return
            except Exception:
                pass  # fall back to the plain player below
        playsound(path, block=block)
    else:
        playsound("sounds/plop.mp3", block=block)


def apply_word_dictionary(text):
    """Fix words the transcriber gets wrong (secretary/dictionary.json), e.g. product names."""
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "voice_dictionary", "/Users/remi/voice2clipboard/scripts/mac/secretary/dictionary.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.apply(text, "transcribe")
    except Exception:
        return text


def format_quick_text(text):
    return f"{QUICK_MODE_PREFIX}{apply_word_dictionary(text.strip())}"


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


class PressArbiter:
    """Tells one press (stop and send) from two (cancel) while recording.

    Presses come from two places: hang-up lines in the Bluetooth log (headset in call mode), and
    the press file written by on_gesture.sh when a press reaches the Mac as a media command
    (a gesture the headset classified itself: 'single', 'double', 'triple'). A 'double' cancels
    at once. Otherwise the first press opens a window: a second press inside it cancels at once,
    and when it closes with a single press the recording stops and is sent."""
    DUPLICATE_S = 0.08   # the log can repeat a line; one physical press is not two

    def __init__(self, window_s):
        self.window_s = window_s
        self.first_at = None
        self.last_at = None
        self.count = 0
        self.cancel = False

    def press(self, kind="hangup", now=None):
        now = time.time() if now is None else now
        if kind == "double":
            self.cancel = True
        if self.last_at is not None and now - self.last_at < self.DUPLICATE_S:
            return
        self.last_at = now
        if self.first_at is None:
            self.first_at = now
        self.count += 1

    def decision(self, now=None):
        now = time.time() if now is None else now
        if self.cancel or (self.window_s > 0 and self.count >= 2):
            return "cancel"
        if self.first_at is None:
            return None
        if self.window_s <= 0 or now - self.first_at >= self.window_s:
            return "stop"
        return None


press_arbiter = PressArbiter(DOUBLE_PRESS_WINDOW_S)
cancel_requested = False


class SilenceTracker:
    """Trips once the input has stayed under rms_threshold for limit_seconds (0 disables it)."""

    def __init__(self, rms_threshold, limit_seconds):
        self.rms_threshold = rms_threshold
        self.limit_seconds = limit_seconds
        self.quiet_since = None
        self.heard_sound = False   # anything above the threshold, ever

    def update(self, rms, now=None):
        now = time.time() if now is None else now
        if rms >= self.rms_threshold:
            self.heard_sound = True
        if self.limit_seconds <= 0 or rms >= self.rms_threshold:
            self.quiet_since = None
            return False
        if self.quiet_since is None:
            self.quiet_since = now
        return now - self.quiet_since >= self.limit_seconds


def headset_mode():
    return IS_MAC and VOICE_MODE == "headset"


def input_is_headset(name):
    return bool(name) and re.search(HEADSET_INPUT_PATTERN, name, re.IGNORECASE) is not None


def default_input_name():
    try:
        return sd.query_devices(kind="input")["name"]
    except Exception:
        return ""


def secretary_log(message):
    try:
        with open(SECRETARY_LOG, "a") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} recorder: {message}\n")
    except OSError:
        pass


def notify_secretary_inbox(text):
    """Queue a spoken note for the earbuds (headset mode only): a failure must never be silent."""
    if not headset_mode() or not os.path.exists(SECRETARY_INBOX_POST):
        return
    try:
        subprocess.Popen([SECRETARY_INBOX_POST, "--from", "secretary", text],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"ℹ️ Could not queue the spoken note ({e}).")


def parse_log_timestamp(line):
    """Epoch seconds of a `log show --style compact` line, or None."""
    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.(\d{3})", line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp() + int(m.group(2)) / 1000.0


def headset_audio_connected_at(since):
    """When the hands-free audio link to the headset last came up (epoch), None if not seen."""
    start = datetime.fromtimestamp(since).strftime("%Y-%m-%d %H:%M:%S")
    try:
        out = subprocess.run(
            ["/usr/bin/log", "show", "--style", "compact", "--info", "--debug", "--start", start,
             "--predicate", HEADSET_LOG_PREDICATE],
            capture_output=True, text=True, timeout=8,
        ).stdout
    except Exception:
        return None
    stamps = [parse_log_timestamp(l) for l in out.splitlines() if headset_event_from_log_line(l) == "audio_connected"]
    stamps = [t for t in stamps if t is not None and t >= since]
    return stamps[-1] if stamps else None


def confirm_headset_route(cue_started_at):
    """The start cue is played the moment the stream opens, but the headset only hears it once
    its hands-free audio link is up. At the edge of Bluetooth range that link comes up late and
    the cue is lost (2026-09-19: Remi waited for a cue that never came). Confirm the link from
    the Bluetooth log and replay the cue once if it came up after the cue had started."""
    time.sleep(1.0)
    deadline = cue_started_at + ROUTE_CONFIRM_TIMEOUT_S
    while recording and time.time() < deadline:
        connected_at = headset_audio_connected_at(cue_started_at - 3.0)
        if connected_at is not None:
            late = connected_at - cue_started_at
            if late > ROUTE_LATE_S:
                print(f"\n🔁 Headset audio link came up {late:.1f} s after the start cue — replaying it.")
                secretary_log(f"start cue replayed: audio link confirmed {late:.1f} s after the first cue")
                play_feedback("record_start", block=False)
            else:
                secretary_log(f"start cue route confirmed ({late:+.2f} s)")
            return
        time.sleep(1.0)
    if recording:
        secretary_log(f"headset audio link not confirmed within {ROUTE_CONFIRM_TIMEOUT_S:.0f} s of the start cue")


def record_audio(filename, quick_mode=False):
    global duration_sec, recording, callback_enabled, start_time, stop_requested_by_signal, active_input_stream
    q = queue.Queue()

    last_audio = {"t": time.time()}

    def _callback(indata, frames, time_info, status):
        last_audio["t"] = time.time()
        q.put(indata.copy())
        audio_callback(indata, frames, time_info, status)

    pcm_path = os.path.splitext(filename)[0] + ".pcm"
    pcm_file = open(pcm_path, "wb") if quick_mode and STREAMING_ENABLED else None
    with sf.SoundFile(filename, mode='w', samplerate=SAMPLE_RATE, channels=CHANNELS) as file:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=_callback) as stream:
            active_input_stream = stream
            # The stream is capturing from here: tell the user immediately. The sound is
            # only a secondary cue and must not block (afplay takes ~2.3 s to exit).
            start_time = time.time()
            if quick_mode:
                write_phase_state("recording")
            if pcm_file is not None:
                mlx_helper_stream_begin(pcm_path)
            print(go_banner(), flush=True)
            play_feedback("record_start", block=False)
            if quick_mode and headset_mode():
                threading.Thread(target=confirm_headset_route, args=(time.time(),), daemon=True).start()
            print("🎤 Recording started.")
            if quick_mode:
                print("Press Escape or the shortcut again to stop recording.\n")
            else:
                print("Press:")
                print("  1 – Show transcription")
                print("  2 – Paste into ChatGPT (existing tab)")
                print("  3 – Open ChatGPT and paste")
                print("  4 – Improve and rename with local LLM")
                print("  5 – Cancel (discard and stop immediately)")
                print("📋 Text will always be copied to clipboard.\n")

            silence = SilenceTracker(SILENCE_STOP_RMS, SILENCE_STOP_SECONDS if quick_mode and headset_mode() else 0)
            try:
                input_lost = False
                while recording:
                    if quick_mode and stop_request_active():
                        request_recording_stop("stop_file_loop")
                        continue
                    if quick_mode and time.time() - last_audio["t"] > INPUT_LOSS_SECONDS:
                        # The input device stopped delivering (Bluetooth headset dropped its
                        # audio link, device removed): keep what we have and finish normally.
                        input_lost = True
                        print("\n⚠️ Microphone stopped delivering audio (headset disconnected?) — finishing with what was recorded.")
                        play_feedback("record_lost", block=False)
                        request_recording_stop("input_lost")
                        continue
                    try:
                        block = q.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    file.write(block)
                    if silence.update(float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))):
                        # Frames keep coming but carry nothing: the headset is gone and another
                        # microphone took over, or the link is dead. Do not record for minutes.
                        print(f"\n⚠️ No sound for {SILENCE_STOP_SECONDS:.0f} s (headset gone?) — finishing with what was recorded.")
                        secretary_log(f"recording stopped after {SILENCE_STOP_SECONDS:.0f} s of near-silence")
                        if silence.heard_sound:   # never a sound at all: a phantom start, stay silent
                            play_feedback("record_lost", block=False)
                        request_recording_stop("silence")
                        continue
                    if pcm_file is not None:
                        pcm_file.write((np.clip(block[:, 0], -1.0, 1.0) * 32767).astype(np.int16).tobytes())
                        pcm_file.flush()
            finally:
                active_input_stream = None
                if pcm_file is not None:
                    pcm_file.close()
                duration_sec = time.time() - start_time
                callback_enabled = False
                print("\r" + " " * (MIC_BAR_WIDTH + 20), end="\r", flush=True)
                play_feedback("record_cancel" if cancel_requested else "record_stop", block=False)
                print("\n🎤 Recording cancelled." if cancel_requested else "\n🎤 Recording stopped.")


def focus_and_click_chatgpt_input(timeout=5):
    import pyautogui  # lazy: not needed to start recording

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


NO_SPEECH_MARKER = "[no speech detected]"


def write_no_speech_result(reason):
    """A recording without speech is a result, not a crash: leave an explicit transcript and stats
    so the folder explains itself and the orphan recovery does not pick it up again."""
    if current_transcript_path:
        with open(current_transcript_path, "w") as f:
            f.write(f"{NO_SPEECH_MARKER} {reason}\n")
    if current_stats_path:
        with open(current_stats_path, "w") as f:
            json.dump({
                "no_speech": True,
                "reason": reason,
                "input_duration_seconds": round(duration_sec, 4),
                "audio_path": current_audio_path,
                "transcript_path": current_transcript_path,
                "transcribed_at": datetime.now().isoformat(),
                "stop_source": quick_stop_source,
            }, f, indent=2)


def finish_cancelled_recording(filename):
    """A cancelled dictation is kept, not sent: the folder is marked, and the text is prepared
    quietly (no sounds, no clipboard, no paste) so recover_cancelled.sh can hand it over at once."""
    global last_backend_info
    folder = os.path.dirname(filename)
    with open(os.path.join(folder, CANCELLED_MARKER), "w") as f:
        how = {"hold:cancel": "press and hold", "press:cancel": "double press"}.get(quick_stop_source, quick_stop_source or "recorder window closed")
        f.write(f"cancelled ({how}) at {datetime.now().isoformat()}\n")
    secretary_log(f"dictation cancelled ({how}); kept in {folder} (recover_cancelled.sh)")
    write_phase_state("transcribing")
    try:
        text = transcribe_with_best_backend(filename)
    except Exception as e:   # no speech, helper gone: the audio is still there for later
        print(f"ℹ️ Cancelled recording not transcribed now ({e}); the audio is kept.")
        return
    with open(current_transcript_path, "w") as f:
        f.write(text)
    stats = {"cancelled": True, "input_duration_seconds": round(duration_sec, 4), "output_text_length_chars": len(text),
             "audio_path": current_audio_path, "transcript_path": current_transcript_path,
             "transcribed_at": datetime.now().isoformat()}
    stats.update(last_backend_info or {})
    with open(current_stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"🗑️ Cancelled. Text kept in {current_transcript_path}; nothing was sent.")


PHANTOM_STOP_SOURCES = ("silence", "input_lost", "headset:disconnected")


def phantom_start(stop_source):
    """A recording without speech that ended by itself (silence, lost input, headset gone) rather
    than by a press, in headset mode."""
    return headset_mode() and stop_source in PHANTOM_STOP_SOURCES


def transcribe_audio(filename):
    """Returns the text, or "" when the recording holds no speech (explicit transcript written)."""
    global last_backend_info, duration_sec, current_transcript_path
    if not phantom_start(quick_stop_source):   # nobody may be there to hear it, see below
        play_feedback("transcribe_start")
    print("🧠 Transcribing...")
    start = time.time()
    try:
        if audio_is_effectively_silent(filename):
            raise EmptyTranscription(
                "the recorded audio is digitally silent (on macOS this usually means the recorder "
                "was launched from a process without microphone access)"
            )
        text = transcribe_with_best_backend(filename)
    except EmptyTranscription as e:
        print(f"⚠️ No speech in this recording ({e}). Nothing to send; the audio is kept.")
        write_no_speech_result(str(e))
        if phantom_start(quick_stop_source):
            # Putting an earbud into its charger makes the headset send "pause", which is exactly
            # what a single press sends (confirmed with Remi on 2026-09-21 21:46; nothing in the
            # Bluetooth log tells the two apart). When nobody ends such a dictation and it holds no
            # speech, no cue is played (the headset is in its charger: it would come out of the
            # Mac's speakers). Nothing is deleted, ever, and Remi is told (his rule, the same
            # evening: no silent decisions about his recordings; flag it, he decides): the audio
            # and the explicit no-speech transcript stay in the recordings folder, and a note
            # waits in the inbox.
            secretary_log(f"dictation of {duration_sec:.0f} s that nobody ended ({quick_stop_source}) and without speech: "
                          "a phantom start (headset put away?); nothing deleted, note queued")
            notify_secretary_inbox(f"A dictation that started at {time.strftime('%H:%M', time.localtime(time.time() - duration_sec))} ended by itself after "
                                   f"{duration_sec:.0f} seconds with no speech in it, probably the charger. "
                                   "Nothing was sent and the audio is kept.")
            return ""
        if 0 < duration_sec <= ACCIDENTAL_MAX_S:
            # Started by mistake and stopped without a word: that is a cancel, not a problem.
            play_feedback("record_cancel")
            secretary_log(f"dictation of {duration_sec:.0f} s without speech: treated as cancelled, nothing sent")
            return ""
        play_feedback("record_lost")
        secretary_log(f"no speech in {os.path.dirname(current_transcript_path or filename)}: nothing sent")
        notify_secretary_inbox("Your last dictation had no speech in it, so nothing was sent. The audio is kept.")
        return ""
    end = time.time()

    pyperclip.copy(text)
    print("📋 Copied to clipboard.")
    play_feedback("done")

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
        "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
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

# condition_on_previous_text=False avoids repetition loops after silent windows
# (same setting as tools/mlx_whisper_helper.py).
try:
    result = mlx_whisper.transcribe(audio, path_or_hf_repo=repo, condition_on_previous_text=False)
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


class EmptyTranscription(RuntimeError):
    """The helper decoded the audio and found no speech."""


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
                        # Final answer, not a transient failure: retrying until the
                        # timeout used to hang the stop path for two minutes.
                        raise EmptyTranscription("helper returned empty transcription (no speech detected)")
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
                        "helper_model_size": helper_state.get("model_size"),
                        "helper_model_repo": helper_state.get("model_repo"),
                        "helper_vad": data.get("vad"),
                    }
                    if helper_ready_at_start:
                        print("✅ MLX helper was warm for this run.")
                    else:
                        print(f"✅ MLX helper became ready after {waited_for_ready_s:.2f}s.")
                    return text, info
            except EmptyTranscription:
                raise
            except Exception as e:
                last_error = str(e)
        time.sleep(0.1)

    raise RuntimeError(f"Timed out waiting for MLX helper: {last_error}")


def mlx_helper_request(payload, timeout_s=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        if timeout_s is not None:
            client.settimeout(timeout_s)
        client.connect(MLX_HELPER_SOCKET)
        client.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        response = b""
        while not response.endswith(b"\n"):
            chunk = client.recv(65536)
            if not chunk:
                break
            response += chunk
    if not response:
        raise RuntimeError("empty helper response")
    data = json.loads(response.decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "helper request failed"))
    return data


def mlx_helper_stream_begin(pcm_path):
    """Ask a warm helper to transcribe the growing PCM file while we record.
    Silently skipped when the helper is not ready yet: the stop path then decodes the whole file."""
    global stream_session_id
    stream_session_id = None
    if os.getenv("VOICE2CLIPBOARD_MLX_HELPER") != "1":
        return
    # The helper is usually still loading its model when the microphone opens (the hotkey
    # starts both at once), so keep trying for a while in the background: the stream session
    # reads the PCM file from its beginning, so a late start loses nothing.
    threading.Thread(target=_stream_begin_retry_loop, args=(pcm_path,), daemon=True).start()


def _stream_begin_retry_loop(pcm_path, timeout_s=30.0):
    global stream_session_id
    session_id = str(uuid.uuid4())
    deadline = time.time() + timeout_s
    last_error = "helper socket not present"
    while time.time() < deadline and recording:
        if os.path.exists(MLX_HELPER_SOCKET):
            try:
                _stream_begin_once(session_id, pcm_path)
                stream_session_id = session_id
                print("🛰️  Streaming transcription active (text is decoded while you speak).")
                return
            except Exception as e:
                last_error = str(e)
        time.sleep(0.5)
    print(f"ℹ️ Streaming not available ({last_error}); will transcribe the whole file at stop.")


def _stream_begin_once(session_id, pcm_path):
    mlx_helper_request(
        {
            "command": "stream_begin",
            "session_id": session_id,
            "pcm_path": os.path.abspath(pcm_path),
            # lets the helper end the recording when the spoken stop phrase is heard
            "stop_file": STOP_REQUEST_FILE or None,
        },
        timeout_s=2.0,
    )


def transcribe_with_mlx_helper_stream_end():
    """Finish the streaming session; raises so the caller can fall back to whole-file decoding."""
    global stream_session_id
    session_id, stream_session_id = stream_session_id, None
    if not session_id:
        raise RuntimeError("no streaming session")
    data = mlx_helper_request({"command": "stream_end", "session_id": session_id}, timeout_s=120.0)
    text = (data.get("text") or "").strip()
    if not text:
        raise RuntimeError("streaming returned empty transcription")
    helper_state = data.get("helper_state", {})
    stats = data.get("stream_stats", {})
    info = {
        "resolved_backend": "mlx_helper_stream",
        "helper_rss_mb": helper_state.get("rss_mb"),
        "helper_model_load_seconds": helper_state.get("model_load_seconds"),
        "helper_transcription_time_seconds": stats.get("end_seconds"),
        "helper_model_size": helper_state.get("model_size"),
        "helper_model_repo": helper_state.get("model_repo"),
        "helper_stream": stats,
    }
    print(
        f"✅ Streamed: {stats.get('chunks')} chunks decoded while recording, "
        f"final {stats.get('final_chunk_seconds')} s of speech in {stats.get('final_wait_seconds')} s."
    )
    return text, info


def transcribe_with_faster_whisper(filename):
    global whisper_model
    if whisper_model is None:
        from faster_whisper import WhisperModel  # lazy: 0.7 s import, fallback path only

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
                if stream_session_id:
                    try:
                        text, info = transcribe_with_mlx_helper_stream_end()
                    except Exception as e:
                        print(f"⚠️ Streaming finish failed ({e}); transcribing the whole file instead.")
                        text, info = transcribe_with_mlx_helper(filename)
                        info["stream_fallback_error"] = str(e)
                else:
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
    import pyautogui  # lazy

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
    import pyautogui  # lazy

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
        import requests  # lazy

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


def own_iterm_session_id():
    """Unique id of the iTerm session this recorder runs in (the worker window), or ""."""
    v = os.getenv("ITERM_SESSION_ID", "")
    return v.split(":")[-1] if v else ""


def recorder_window_is_frontmost(own_id=None):
    """True when iTerm is the frontmost app and its current session is this recorder's window.
    Any failure to tell counts as "not in front": a lost dictation costs more than an ignored key."""
    own_id = own_id or own_iterm_session_id()
    if not own_id:
        return False
    script = '''
tell application "System Events" to set front to name of first application process whose frontmost is true
if front is not "iTerm2" then return "other:" & front
tell application "iTerm2" to return (unique id of current session of current window) as text
'''.strip()
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=3)
    except Exception:
        return False
    return (result.stdout or "").strip() == own_id


def escape_counts(own_id=None):
    """Whether an Escape key event may stop this recording. In headset mode Remi is on the earbuds,
    and a key event can come from any app or from another agent's keystroke automation (pynput sees
    them all, wherever they were aimed): only an Escape typed into the recorder's own window counts.
    Keyboard-driven manual mode keeps the old rule, Escape anywhere.
    Remi's decision the same day: Escape anywhere is what he wants (he starts talking, goes back
    to something else and presses the key from there), so the window rule is OFF unless
    VOICE2CLIPBOARD_ESCAPE_ANYWHERE=0; the guard stays available for a day it is needed."""
    if os.getenv("VOICE2CLIPBOARD_ESCAPE_ANYWHERE", "1") != "0" or not headset_mode():
        return True
    return recorder_window_is_frontmost(own_id)


def handle_escape_during_recording():
    """Wait for Escape key to stop recording in quick mode."""
    global quick_stop_source

    def on_press(key):
        global quick_stop_source
        if key == pynput_keyboard.Key.esc:
            if not escape_counts():
                secretary_log("Escape key seen while the recorder window is not in front (another app, or "
                              "another agent's keystrokes): ignored, still recording")
                return
            if quick_stop_source is None:
                quick_stop_source = "escape"
            touch_stop_request_file()
            request_recording_stop("escape")

    listener = pynput_keyboard.Listener(on_press=on_press)
    listener.start()
    while recording:
        time.sleep(0.05)
    listener.stop()


def handle_external_stop_during_recording():
    """Watch for launcher stop-file requests, and arbitrate presses (one = stop, two = cancel)."""
    global cancel_requested
    press_offset = 0
    while recording:
        if stop_request_active():
            request_recording_stop("external_stop")
            return
        try:   # presses that reached the Mac as media commands (written by on_gesture.sh)
            with open(PRESS_FILE) as f:
                f.seek(press_offset)
                for kind in f.read().split():
                    press_arbiter.press(kind)
                press_offset = f.tell()
        except OSError:
            pass
        verdict = press_arbiter.decision()
        if verdict:
            gap = (press_arbiter.last_at - press_arbiter.first_at) if press_arbiter.first_at and press_arbiter.last_at else 0.0
            secretary_log(f"press decision: {verdict} ({press_arbiter.count} press(es), {gap:.2f} s apart, window {DOUBLE_PRESS_WINDOW_S} s)")
        if verdict == "cancel":
            cancel_requested = True
            print("\n🗑️ Second press — cancelling this dictation (audio kept, nothing sent).")
            request_recording_stop("press:cancel")
            return
        if verdict == "stop":
            request_recording_stop("press:stop")
            return
        time.sleep(0.03)


# --- Headset buttons while recording -------------------------------------------------------
# With a Bluetooth headset the microphone runs over the hands-free profile and macOS sets up a
# "virtual call" with it. Its buttons then send call commands (hang-up, speaker gain) instead
# of media commands, so the Now Playing app never sees them; bluetoothd logs them though.
HEADSET_STOP_ENABLED = IS_MAC and os.getenv("VOICE2CLIPBOARD_HEADSET_STOP", "1") != "0"
HEADSET_LOG_PREDICATE = 'process == "bluetoothd" AND category == "Server.Handsfree"'


def headset_event_from_log_line(line):
    """Map a bluetoothd hands-free log line to 'hangup', 'disconnected', 'audio_connected',
    'gain_up', 'gain_down', 'gain_change' or None."""
    if "Received call hangup event" in line or "AT+CHUP" in line:
        return "hangup"
    if "handsfree disconnection event" in line or ("Handsfree device handle" in line and "disconnected" in line):
        return "disconnected"
    if "voice audio connected event" in line:
        return "audio_connected"
    m = re.search(r"Received speaker gain event .* new gain is (\d+)", line)
    if m:
        gain = int(m.group(1))
        prev = headset_event_from_log_line.last_gain
        headset_event_from_log_line.last_gain = gain
        if prev is None:
            return "gain_change"
        return "gain_up" if gain > prev else "gain_down" if gain < prev else "gain_change"
    return None


# Nobody has yet seen what this headset sends for a second press in call mode (another hang-up,
# a media command, or some other call command). Anything unknown it sends while we record is
# logged and counted as a press, so the first real double press documents itself.
_KNOWN_HANDSFREE_CHATTER = ("voice audio", "disconnection", "connection", "gain", "SLC", "subscriber", "call waiting", "EC/NR", "indicator")


def headset_other_command(line):
    if "Received" in line and " event" in line and "from device" in line and headset_event_from_log_line(line) is None:
        if not any(k in line for k in _KNOWN_HANDSFREE_CHATTER):
            return re.sub(r".*Received ", "", line).split(" from device")[0].strip()
    return None


headset_event_from_log_line.last_gain = None

# Cancel gesture (2026-09-21). In call mode the headset keeps a double press to itself, so the
# double press Remi reaches for can never cancel a dictation started by mistake. The only other
# gesture that arrives is press-and-hold, as a speaker gain event (one volume step of the call
# volume as a side effect). It now cancels: cancel cue, nothing sent, audio kept and transcribed
# quietly, recover_cancelled.sh brings it back. In about forty dictations logged before this
# change the headset never sent a gain event on its own; the first second of a recording is
# ignored all the same, in case it reports its volume when the call link comes up.
HOLD_CANCELS = os.getenv("VOICE2CLIPBOARD_HOLD_CANCELS", "1") != "0"
HOLD_CANCEL_GRACE_S = float(os.getenv("VOICE2CLIPBOARD_HOLD_CANCEL_GRACE_S", "1.0"))


def hold_cancels(event, started_at, now=None):
    """True when this headset event is a press-and-hold that should cancel the dictation."""
    if not HOLD_CANCELS or event not in ("gain_up", "gain_down", "gain_change"):
        return False
    now = time.time() if now is None else now
    return started_at is not None and now - started_at >= HOLD_CANCEL_GRACE_S


def handle_headset_buttons_during_recording():
    """Stop the recording when the headset sends its hands-free hang-up (a press); cancel it on
    a press-and-hold (speaker gain event)."""
    global cancel_requested
    if not HEADSET_STOP_ENABLED:
        return
    cmd = ["/usr/bin/log", "stream", "--style", "compact", "--info", "--debug", "--predicate", HEADSET_LOG_PREDICATE]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    except Exception as e:
        print(f"ℹ️ Headset button watcher unavailable ({e}).")
        return

    def _reaper():
        while recording and proc.poll() is None:
            time.sleep(0.1)
        if proc.poll() is None:
            proc.terminate()

    threading.Thread(target=_reaper, daemon=True).start()
    headset_event_from_log_line.last_gain = None
    try:
        for line in proc.stdout:
            if not recording:
                break
            event = headset_event_from_log_line(line)
            if event == "hangup":
                # A press. Volume changes (long presses) are deliberately not an action. The
                # watcher thread decides between stop and cancel once it knows if a second follows.
                print(f"\n🎧 Headset button ({event}).")
                press_arbiter.press("hangup")
                continue
            if event in ("gain_up", "gain_down", "gain_change"):
                if hold_cancels(event, start_time):
                    cancel_requested = True
                    print("\n🗑️ Press-and-hold — cancelling this dictation (audio kept, nothing sent).")
                    secretary_log(f"press-and-hold ({event}): dictation cancelled, nothing sent, audio kept")
                    request_recording_stop("hold:cancel")
                    break
                secretary_log(f"headset volume event while recording ({event}): ignored (first second, or VOICE2CLIPBOARD_HOLD_CANCELS=0)")
                continue
            other = headset_other_command(line)
            if other:
                secretary_log(f"headset sent an unknown command while recording: {other} (counted as a press)")
                press_arbiter.press("other")
                continue
            if event == "disconnected":
                # Out of range or switched off: nothing more will come. Keep what was said.
                print("\n⚠️ Headset disconnected — finishing with what was recorded.")
                secretary_log("headset disconnected during a recording: stopping and delivering what was said")
                play_feedback("record_lost", block=False)
                request_recording_stop("headset:disconnected")
                break
    finally:
        if proc.poll() is None:
            proc.terminate()


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


def iterm_write_text_action(text, bracketed):
    """AppleScript `write text` clause; bracketed wraps text in bracketed-paste markers.

    Claude Code (>= 2.1.248) drops the first 1022-byte chunk of un-bracketed
    input when more input follows and Enter arrives within ~1 s (the macOS pty
    input queue splits anything longer than 1022 bytes). Bracketed paste makes
    Claude Code treat the whole text as one paste, so nothing is lost.
    """
    escaped_text = _escape_applescript_string(text)
    if bracketed:
        return (
            'write text (ASCII character 27) & "[200~" & '
            f'"{escaped_text}" & (ASCII character 27) & "[201~" newline NO'
        )
    return f'write text "{escaped_text}" newline NO'


def _foreground_comms_from_ps(ps_output):
    """Full command paths of the foreground ('+' state) processes in `ps -o stat=,comm=` output."""
    comms = []
    for line in ps_output.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and "+" in parts[0]:
            comms.append(parts[1].strip())
    return comms


def foreground_commands_from_ps(ps_output):
    return [os.path.basename(comm) for comm in _foreground_comms_from_ps(ps_output)]


def tty_foreground_is_claude(ps_output):
    return any(
        os.path.basename(comm) == "claude" or "/claude/versions/" in comm
        for comm in _foreground_comms_from_ps(ps_output)
    )


def get_iterm_session_tty(session_id):
    escaped_session = _escape_applescript_string(session_id)
    script = f'''
tell application "iTerm2"
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if (unique id of s as text) is "{escaped_session}" then
                    return tty of s
                end if
            end repeat
        end repeat
    end repeat
end tell
return ""
'''.strip()
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return (result.stdout or "").strip() if result.returncode == 0 else ""


def iterm_session_runs_claude(session_id):
    tty = get_iterm_session_tty(session_id)
    if not tty:
        return False
    try:
        ps_output = subprocess.check_output(
            ["ps", "-t", os.path.basename(tty), "-o", "stat=,comm="], text=True
        )
    except Exception:
        return False
    return tty_foreground_is_claude(ps_output)


def rotation_redirect(target_iterm_session, session_alive=None):
    """Where a dictation aimed at the secretary goes while lazy_rotate.sh may be replacing it.

    Files in ROTATION_DIR, each holding "<old id> <new id>" or "<old id>":
      pending  a fresh secretary is booting (written by the rotator at the press)
      ready    it is ready for input: deliver there
    The rotator publishes with rename(pending -> publishing) then rename(ready.tmp -> ready);
    this side gives up with rename(pending -> aborted), which makes the rotator close the new
    window. Whoever renames `pending` first wins, so both sides always agree on where the text
    went. Any doubt or error means the original target: a lost dictation is worse than a costly wake.
    """
    if not target_iterm_session:
        return target_iterm_session
    alive = session_alive or (lambda sid: bool(get_iterm_session_tty(sid)))
    pending, ready = os.path.join(ROTATION_DIR, "pending"), os.path.join(ROTATION_DIR, "ready")

    def read(path):
        try:
            with open(path) as f:
                return f.read().split()
        except OSError:
            return []

    def fresh(path, max_age):
        # leftovers of a rotator that died must not make every later dictation wait
        try:
            return time.time() - os.stat(path).st_mtime < max_age
        except OSError:
            return False

    def ready_target():
        parts = read(ready)
        if len(parts) == 2 and parts[0] == target_iterm_session and alive(parts[1]):
            return parts[1]
        return None

    try:
        deadline = time.time() + ROTATION_WAIT_SECONDS
        waited = False
        while True:
            new = ready_target()
            if new:
                secretary_log(f"dictation redirected to the fresh secretary {new} (was {target_iterm_session})")
                try:
                    os.rename(ready, os.path.join(ROTATION_DIR, "delivered"))
                except OSError:
                    pass
                return new
            parts = read(pending) if fresh(pending, 180) else []
            in_flight = fresh(os.path.join(ROTATION_DIR, "publishing"), 5)
            if not in_flight and (not parts or parts[0] != target_iterm_session):
                return target_iterm_session          # no rotation concerns this dictation
            if time.time() >= deadline:
                break
            if not waited:
                waited = True
                print("⏳ A fresh secretary is starting; waiting for it before sending...")
                secretary_log("transcript ready before the fresh secretary: waiting for it")
            time.sleep(0.25)
        try:
            os.rename(pending, os.path.join(ROTATION_DIR, "aborted"))
            secretary_log("fresh secretary not ready in time: rotation aborted, delivering to the current one")
        except OSError:
            new = ready_target()                     # the rotator published at the last instant
            if new:
                secretary_log(f"dictation redirected to the fresh secretary {new} (was {target_iterm_session})")
                return new
    except Exception as e:                           # never let this feature cost a dictation
        secretary_log(f"rotation redirect failed ({e}): delivering to the current secretary")
    return target_iterm_session


def send_text_to_iterm_session(text, session_id):
    one_line = " ".join(text.splitlines())
    bracketed = iterm_session_runs_claude(session_id)
    print(f"🧾 iTerm send mode: {'bracketed paste (Claude Code)' if bracketed else 'typed text'}")
    action_lines = "                        " + iterm_write_text_action(one_line, bracketed)
    _run_iterm_session_applescript(session_id, action_lines)


# --- Verified delivery to a Claude Code window ---------------------------------------------------
# On 2026-09-22 at 21:35 "/usage" had been submitted in the secretary's window (from its keyboard).
# That opens a full-screen dialog which stays until Escape; while it is open Claude Code reports
# itself "waiting", every keystroke goes to the dialog, and queued messages wait. Nobody closed it,
# so a dictation and two agent reports typed into that window vanished without a trace for two
# hours. Typing blindly is therefore not enough: before typing, the window must show its input
# prompt (Escape closes a dialog); after typing, the message must show up as a turn in the
# session's transcript, or, when that file cannot be found, must have left the input box.
DELIVERY_VERIFY_SECONDS = float(os.getenv("VOICE2CLIPBOARD_DELIVERY_VERIFY_S", "8"))
CLAUDE_SESSIONS_DIR = os.path.expanduser("~/.claude/sessions")
CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")


def get_iterm_session_contents(session_id):
    escaped_session = _escape_applescript_string(session_id)
    script = f'''
tell application "iTerm2"
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if (unique id of s as text) is "{escaped_session}" then
                    return contents of s
                end if
            end repeat
        end repeat
    end repeat
end tell
return ""
'''.strip()
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def claude_screen_has_prompt(screen):
    """True when the bottom of a Claude Code screen is its input prompt, not a dialog."""
    tail = "\n".join((screen or "").rstrip().splitlines()[-12:])
    return "bypass permissions" in tail or "\n❯" in "\n" + tail or "shift+tab to cycle" in tail


def claude_input_ready(session_id):
    return claude_screen_has_prompt(get_iterm_session_contents(session_id))


def send_escape_to_iterm_session(session_id):
    _run_iterm_session_applescript(session_id, "                        write text (ASCII character 27) newline NO")


def claude_transcript_for_iterm(session_id):
    """Path of the Claude Code transcript behind an iTerm session (tty -> claude pid -> session
    file -> project transcript), or None. Works for a fresh session that registered nothing yet."""
    tty = get_iterm_session_tty(session_id)
    if not tty:
        return None
    try:
        ps_output = subprocess.check_output(["ps", "-t", os.path.basename(tty), "-o", "pid=,stat=,comm="], text=True)
    except Exception:
        return None
    for line in ps_output.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and "+" in parts[1] and (os.path.basename(parts[2]) == "claude" or "/claude/versions/" in parts[2]):
            try:
                info = json.load(open(os.path.join(CLAUDE_SESSIONS_DIR, parts[0] + ".json")))
            except Exception:
                continue
            sid = info.get("sessionId")
            if not sid:
                continue
            import glob as _glob
            hits = _glob.glob(os.path.join(CLAUDE_PROJECTS_DIR, "*", sid + ".jsonl"))
            if hits:
                return hits[0]
    return None


def transcript_has_user_turn(path, marker, offset):
    """True when a user turn containing `marker` was appended to `path` after byte `offset`."""
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            new = f.read().decode("utf-8", "ignore")
    except OSError:
        return False
    key = json.dumps(marker, ensure_ascii=False)[1:-1]
    for line in new.splitlines():
        if key not in line:
            continue
        if re.search(r'"type":\s*"user"', line) and "tool_result" not in line:
            return True
        # Typed while the session is busy with a turn, the message is queued. Claude Code appends
        # a {"type": "queue-operation", "operation": "enqueue", "content": ...} line the moment it
        # is queued; the "queued_command" attachment and the user turn come only when the running
        # turn reaches its next round, often after the wait here (2026-09-24 08:56 and 15:15: a
        # dictation and an agent report typed twice into the busy secretary, then reported as
        # undelivered, although both had been queued at the first attempt).
        if re.search(r'"operation":\s*"enqueue"', line) or '"queued_command"' in line:
            return True
    return False


def deliver_to_claude_session(text, session_id, log=None):
    """Type `text` into a Claude Code window and make sure it became a turn. Returns True when
    the message was seen in the transcript (or, without a transcript, has left the input box);
    False when it was typed twice and still not consumed. Never types a third time."""
    log = log or (lambda m: None)
    marker = " ".join(text.split())[:40]
    transcript = claude_transcript_for_iterm(session_id)
    for attempt in (1, 2):
        if not claude_input_ready(session_id):
            log(f"window {session_id} shows no input prompt (a dialog?): pressing Escape before typing")
            send_escape_to_iterm_session(session_id)
            time.sleep(0.6)
            if not claude_input_ready(session_id):
                log(f"window {session_id} still shows no input prompt after Escape")
        offset = os.path.getsize(transcript) if transcript and os.path.exists(transcript) else 0
        send_text_to_iterm_session(text, session_id)
        time.sleep(0.4)
        send_enter_to_iterm_session(session_id)
        deadline = time.time() + DELIVERY_VERIFY_SECONDS
        while time.time() < deadline:
            if transcript:
                if transcript_has_user_turn(transcript, marker, offset):
                    if attempt == 2:
                        log(f"delivered to {session_id} at the second attempt")
                    return True
            else:
                screen = get_iterm_session_contents(session_id)
                if claude_screen_has_prompt(screen) and marker not in "\n".join(screen.splitlines()[-6:]):
                    return True
            time.sleep(0.25)
        log(f"message typed into {session_id} was not consumed within {DELIVERY_VERIFY_SECONDS:.0f} s (attempt {attempt})")
    return False


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
            target_iterm_session = rotation_redirect(target_iterm_session)
            print("🔄 Sending text directly to original iTerm session...")
            try:
                append_quick_send_trace(
                    "iterm_direct_send_begin",
                    send_id=send_id,
                    target_iterm_session=target_iterm_session,
                    submit_mode="single_enter_400ms",
                )
                play_feedback("transcribe_start")
                if not deliver_to_claude_session(text_with_disclaimer, target_iterm_session, secretary_log):
                    raise RuntimeError("the window did not take the message (a dialog open in it?)")
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
                if headset_mode():
                    # The target is the secretary's window, whatever is frontmost. A blind paste
                    # would land in an arbitrary console (2026-09-19: two dictations lost).
                    print(f"⚠️ Direct iTerm send failed ({e}); not pasting blindly. Text kept in the clipboard and {current_transcript_path}.")
                    write_quick_send_marker(marker_path, f"undelivered\nsend_id={send_id}\npid={os.getpid()}\n")
                    secretary_log(f"dictation NOT delivered, secretary window unreachable ({e}); saved in {current_transcript_path}")
                    play_feedback("record_lost")
                    notify_secretary_inbox("Your last dictation could not be delivered because my window was unreachable. The text is saved in the recordings folder and in the clipboard.")
                    return
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
            import pyautogui  # lazy

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
    try:
        os.remove(PRESS_FILE)   # presses from a previous recording are not ours
    except OSError:
        pass
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
        if quick_mode and not text:
            return
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
    if quick_mode and headset_mode():
        input_name = default_input_name()
        if not input_is_headset(input_name):
            # Pressed at the edge of range: the headset dropped before the microphone opened, and
            # the Mac's own microphone would record an empty room (2026-09-19, 14 minutes).
            print(f"⚠️ Headset dictation, but the input device is '{input_name or 'unknown'}', not the headset. Not recording.")
            secretary_log(f"dictation refused: headset not connected (input device: {input_name or 'unknown'})")
            play_feedback("record_lost", block=True)
            notify_secretary_inbox("You pressed to dictate while the headset was disconnected, so nothing was recorded.")
            sys.exit(3)
    filename = generate_paths()
    write_audio_state(filename)
    clear_phase_state()

    if quick_mode:
        # Quick mode: Escape to stop, then paste at cursor
        recording = True
        recorder = threading.Thread(target=record_audio, args=(filename, True))
        escape_listener = threading.Thread(target=handle_escape_during_recording)
        external_stop_listener = threading.Thread(target=handle_external_stop_during_recording)
        headset_listener = threading.Thread(target=handle_headset_buttons_during_recording, daemon=True)
        recorder.start()
        escape_listener.start()
        external_stop_listener.start()
        headset_listener.start()
        recorder.join()
        escape_listener.join()
        external_stop_listener.join()

        try:
            if cancel_requested and os.path.exists(filename):
                finish_cancelled_recording(filename)
            elif os.path.exists(filename):
                if stop_requested_by_signal:
                    detail = f" via {quick_stop_source}" if quick_stop_source else ""
                    print(f"⏹️ Stop requested{detail}.")
                write_phase_state("transcribing")
                text = transcribe_audio(filename)
                if not text:
                    pass  # no speech: explicit transcript written, nothing to deliver
                elif copy_only:
                    pyperclip.copy(format_quick_text(text))
                    print("📋 Quick mode copy-only: transcription is in clipboard.")
                else:
                    paste_at_cursor_and_send(text, target_window, target_iterm_session)
                write_phase_state("done")
        finally:
            clear_audio_state()
            clear_phase_state()
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
