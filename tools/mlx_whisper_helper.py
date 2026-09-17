#!/usr/bin/env python3
import json
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime

import mlx.core as mx
import mlx_whisper
import numpy as np
import soundfile as sf
from faster_whisper.vad import VadOptions, collect_chunks, get_speech_timestamps, get_vad_model
from mlx_whisper.transcribe import ModelHolder

SOCKET_PATH = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_SOCKET", "/tmp/voice2clipboard_mlx_helper.sock")
STATE_PATH = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_STATE", "/tmp/voice2clipboard_mlx_helper_state.json")
PID_PATH = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_PID", "/tmp/voice2clipboard_mlx_helper.pid")
MODEL_SIZE = os.getenv("VOICE2CLIPBOARD_MLX_MODEL_SIZE", "large-v3-turbo")
# Silero VAD trimming: pauses longer than this are cut before Whisper sees the audio.
# Silent 30 s windows are where every Whisper size hallucinates (loops, "Thank you.");
# removing them halved medium's WER and makes large-v3-turbo usable. Set to 0 to disable.
VAD_MIN_SILENCE_MS = int(os.getenv("VOICE2CLIPBOARD_VAD_MIN_SILENCE_MS", "1000"))
VAD_SPEECH_PAD_MS = int(os.getenv("VOICE2CLIPBOARD_VAD_SPEECH_PAD_MS", "300"))


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
    return mapping.get(model_size, "mlx-community/whisper-large-v3-turbo")


MODEL_REPO = mlx_repo_for_model(MODEL_SIZE)
STATE = {
    "status": "starting",
    "model_size": MODEL_SIZE,
    "model_repo": MODEL_REPO,
    "pid": os.getpid(),
    "started_at": datetime.now().isoformat(),
}


def rss_mb(pid=None):
    if pid is None:
        pid = os.getpid()
    try:
        out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True).strip()
        kb = int(out or "0")
        return round(kb / 1024.0, 1)
    except Exception:
        return None


def write_state(**kwargs):
    STATE.update(kwargs)
    STATE["pid"] = os.getpid()
    STATE["updated_at"] = datetime.now().isoformat()
    STATE["rss_mb"] = rss_mb()
    tmp = f"{STATE_PATH}.tmp"
    with open(tmp, "w") as f:
        json.dump(STATE, f, indent=2)
    os.replace(tmp, STATE_PATH)


def cleanup():
    for path in [SOCKET_PATH, PID_PATH]:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    write_state(status="stopped")


def handle_signal(signum, frame):
    cleanup()
    sys.exit(0)


def read_request(conn):
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
    if not data:
        return None
    return json.loads(data.decode("utf-8"))


def send_response(conn, payload):
    conn.sendall((json.dumps(payload) + "\n").encode("utf-8"))


def trim_silence(audio_path):
    """Return (speech-only float32 16 kHz audio, stats). Falls back to the raw file if
    the WAV is not 16 kHz mono; returns None audio when no speech is detected."""
    audio, sr = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    total_s = len(audio) / sr
    if sr != 16000 or VAD_MIN_SILENCE_MS <= 0:
        return audio_path, {"vad": "skipped", "input_seconds": round(total_s, 2)}
    regions = get_speech_timestamps(
        audio, VadOptions(min_silence_duration_ms=VAD_MIN_SILENCE_MS, speech_pad_ms=VAD_SPEECH_PAD_MS)
    )
    if not regions:
        return None, {"vad": "no_speech", "input_seconds": round(total_s, 2), "speech_seconds": 0.0}
    chunks, _meta = collect_chunks(audio, regions, sr)
    speech = np.concatenate(chunks)
    return speech, {
        "vad": "trimmed",
        "input_seconds": round(total_s, 2),
        "speech_seconds": round(len(speech) / sr, 2),
        "speech_regions": len(regions),
    }


def transcribe(audio_path):
    start = time.time()
    audio, vad_stats = trim_silence(audio_path)
    if audio is None:
        return "", time.time() - start, vad_stats
    vad_stats["vad_seconds"] = round(time.time() - start, 3)
    # condition_on_previous_text=False: with the default (True) a hallucinated
    # sentence in a silent 30 s window is fed back as the prompt for the next
    # window and Whisper loops it for minutes ("filed filed filed ...").
    # Whisper never falls back on such windows because no_speech_prob > 0.6
    # disables the compression-ratio check. See local_tests/test_mlx_helper_loops.py.
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=MODEL_REPO,
        condition_on_previous_text=False,
    )
    text = result.get("text", "").strip() if isinstance(result, dict) else str(result).strip()
    elapsed = time.time() - start
    return text, elapsed, vad_stats


def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    write_state(status="loading", load_started_at=datetime.now().isoformat())
    load_start = time.time()
    dtype = mx.float16
    ModelHolder.get_model(MODEL_REPO, dtype)
    if VAD_MIN_SILENCE_MS > 0:
        get_vad_model()
    load_elapsed = time.time() - load_start
    write_state(
        status="ready",
        load_completed_at=datetime.now().isoformat(),
        model_load_seconds=round(load_elapsed, 4),
    )

    try:
        os.remove(SOCKET_PATH)
    except FileNotFoundError:
        pass

    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))

    with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as server:
        server.bind(SOCKET_PATH)
        server.listen(5)

        while True:
            conn, _addr = server.accept()
            with closing(conn):
                try:
                    request = read_request(conn)
                    if not request:
                        continue
                    command = request.get("command", "transcribe")
                    if command == "status":
                        write_state(status=STATE.get("status", "ready"))
                        send_response(conn, {"ok": True, "state": STATE})
                        continue
                    if command != "transcribe":
                        send_response(conn, {"ok": False, "error": f"unsupported command: {command}"})
                        continue

                    audio_path = request["audio_path"]
                    write_state(
                        status="busy",
                        last_request_started_at=datetime.now().isoformat(),
                        last_audio_path=audio_path,
                    )
                    text, elapsed, vad_stats = transcribe(audio_path)
                    write_state(
                        status="ready",
                        last_request_completed_at=datetime.now().isoformat(),
                        last_transcription_seconds=round(elapsed, 4),
                        last_output_chars=len(text),
                        last_vad=vad_stats,
                    )
                    send_response(
                        conn,
                        {
                            "ok": True,
                            "text": text,
                            "transcription_time_seconds": round(elapsed, 4),
                            "vad": vad_stats,
                            "helper_state": STATE,
                        },
                    )
                except Exception as e:
                    write_state(status="ready", last_error=str(e))
                    send_response(conn, {"ok": False, "error": str(e), "helper_state": STATE})


if __name__ == "__main__":
    main()
