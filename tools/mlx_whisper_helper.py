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
from mlx_whisper.transcribe import ModelHolder

SOCKET_PATH = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_SOCKET", "/tmp/voice2clipboard_mlx_helper.sock")
STATE_PATH = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_STATE", "/tmp/voice2clipboard_mlx_helper_state.json")
PID_PATH = os.getenv("VOICE2CLIPBOARD_MLX_HELPER_PID", "/tmp/voice2clipboard_mlx_helper.pid")
MODEL_SIZE = os.getenv("VOICE2CLIPBOARD_MLX_MODEL_SIZE", "medium")


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


def transcribe(audio_path):
    start = time.time()
    result = mlx_whisper.transcribe(audio_path, path_or_hf_repo=MODEL_REPO)
    text = result.get("text", "").strip() if isinstance(result, dict) else str(result).strip()
    elapsed = time.time() - start
    return text, elapsed


def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    write_state(status="loading", load_started_at=datetime.now().isoformat())
    load_start = time.time()
    dtype = mx.float16
    ModelHolder.get_model(MODEL_REPO, dtype)
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
                    text, elapsed = transcribe(audio_path)
                    write_state(
                        status="ready",
                        last_request_completed_at=datetime.now().isoformat(),
                        last_transcription_seconds=round(elapsed, 4),
                        last_output_chars=len(text),
                    )
                    send_response(
                        conn,
                        {
                            "ok": True,
                            "text": text,
                            "transcription_time_seconds": round(elapsed, 4),
                            "helper_state": STATE,
                        },
                    )
                except Exception as e:
                    write_state(status="ready", last_error=str(e))
                    send_response(conn, {"ok": False, "error": str(e), "helper_state": STATE})


if __name__ == "__main__":
    main()
