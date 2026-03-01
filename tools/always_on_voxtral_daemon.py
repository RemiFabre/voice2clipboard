#!/usr/bin/env python3
"""Always-on local dictation daemon (voxmlx/OpenAI-realtime compatible).

- Continuously captures microphone audio.
- Streams to ws://.../v1/realtime.
- Writes rolling transcript + committed segments to files under runtime/always_on.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import signal
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

import numpy as np
import sounddevice as sd
import websockets


@dataclass
class State:
    current_delta: str = ""
    committed_text: str = ""
    connected: bool = False
    started_at: float = 0.0
    last_delta_at: float | None = None


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def append_jsonl(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def append_text_line(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")


def timeline_day_path(runtime_dir: str, dt: datetime | None = None) -> str:
    day = (dt or datetime.now()).strftime("%Y-%m-%d")
    return os.path.join(runtime_dir, "timeline", f"{day}.txt")


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def write_state(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def normalize_text(text: str) -> str:
    lowered = text.lower()
    deaccented = "".join(
        ch for ch in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(ch)
    )
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", deaccented)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_phrases(raw: str) -> list[str]:
    parts = [normalize_text(x) for x in raw.split(",")]
    return [p for p in parts if p]


def detect_voice_command(segment: str, start_phrases: list[str], stop_phrases: list[str]) -> str | None:
    norm = normalize_text(segment)
    for p in start_phrases:
        if norm.startswith(p):
            return "start"
    for p in stop_phrases:
        if norm.startswith(p):
            return "stop"
    return None


def read_pid(path: str) -> int | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return None
        return int(raw)
    except Exception:
        return None


def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def ws_host_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    return host, port


async def wait_for_server(url: str, timeout_s: float, interval_s: float) -> bool:
    if timeout_s <= 0:
        return True
    host, port = ws_host_port(url)
    deadline = time.time() + timeout_s
    while True:
        try:
            conn = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(conn, timeout=1.0)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            if time.time() >= deadline:
                return False
            await asyncio.sleep(max(0.05, interval_s))


async def run_daemon(args: argparse.Namespace) -> None:
    runtime_dir = args.runtime_dir
    events_path = os.path.join(runtime_dir, "events.jsonl")
    segments_path = os.path.join(runtime_dir, "segments.jsonl")
    deltas_path = os.path.join(runtime_dir, "deltas.jsonl")
    live_text_path = os.path.join(runtime_dir, "live_text.txt")
    state_path = os.path.join(runtime_dir, "state.json")
    pid_path = os.path.join(runtime_dir, "daemon.pid")

    os.makedirs(runtime_dir, exist_ok=True)
    existing_pid = read_pid(pid_path)
    if existing_pid and existing_pid != os.getpid() and is_pid_running(existing_pid):
        raise RuntimeError(
            f"Another daemon instance is already running (pid={existing_pid}, pid file={pid_path})"
        )

    write_text(live_text_path, "")
    append_text_line(timeline_day_path(runtime_dir), f"\n=== Session start {now_iso()} ===")
    with open(pid_path, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    state = State(started_at=time.time())
    start_phrases = parse_phrases(args.voice_start_phrases)
    stop_phrases = parse_phrases(args.voice_stop_phrases)
    marker_path = os.path.join(runtime_dir, "selection_marker.json")
    command_lock = asyncio.Lock()
    last_command_at = 0.0
    stop_event = asyncio.Event()
    audio_q: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _on_signal(_sig, _frame):
        stop_event_loop = asyncio.get_event_loop()
        stop_event_loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    loop = asyncio.get_running_loop()

    def audio_cb(indata, _frames, _time_info, status):
        if status:
            return
        mono = indata[:, 0] if indata.ndim == 2 else indata
        pcm16 = (np.clip(mono, -1.0, 1.0) * 32767.0).astype(np.int16)
        payload = base64.b64encode(pcm16.tobytes()).decode("ascii")
        try:
            loop.call_soon_threadsafe(audio_q.put_nowait, payload)
        except asyncio.QueueFull:
            pass

    async def run_marker_script(action: str, reason_text: str) -> None:
        nonlocal last_command_at
        if not args.voice_commands:
            return
        if action not in {"start", "stop"}:
            return

        now = time.time()
        if now - last_command_at < args.voice_command_cooldown:
            return

        marker_exists = os.path.exists(marker_path)
        if action == "start" and marker_exists:
            return
        if action == "stop" and not marker_exists:
            return

        script_name = "always_on_mark_start.sh" if action == "start" else "always_on_mark_stop.sh"
        script_path = os.path.join(repo_root, script_name)
        if not os.path.exists(script_path):
            append_jsonl(
                events_path,
                {
                    "ts": now_iso(),
                    "voice_command": action,
                    "status": "script_missing",
                    "script": script_path,
                },
            )
            return

        async with command_lock:
            last_command_at = time.time()
            proc = await asyncio.create_subprocess_exec(
                script_path,
                cwd=repo_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
            append_jsonl(
                events_path,
                {
                    "ts": now_iso(),
                    "voice_command": action,
                    "status": "ok" if proc.returncode == 0 else "error",
                    "rc": proc.returncode,
                    "trigger_text": reason_text,
                    "stdout": (out or b"").decode("utf-8", errors="ignore").strip(),
                    "stderr": (err or b"").decode("utf-8", errors="ignore").strip(),
                },
            )

    try:
        if not await wait_for_server(args.url, args.wait_server_s, args.wait_poll_s):
            host, port = ws_host_port(args.url)
            raise ConnectionError(
                f"Realtime server not reachable at {host}:{port} after {args.wait_server_s:.1f}s"
            )

        async with websockets.connect(args.url, max_size=10 * 1024 * 1024) as ws:
            state.connected = True
            await ws.send(json.dumps({"type": "session.update", "model": args.model, "temperature": 0.0}))

            async def sender_loop() -> None:
                while not stop_event.is_set():
                    try:
                        b64 = await asyncio.wait_for(audio_q.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        continue
                    await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": b64}))

            async def commit_loop() -> None:
                while not stop_event.is_set():
                    await asyncio.sleep(args.commit_every)
                    await ws.send(json.dumps({"type": "input_audio_buffer.commit", "final": False}))

            async def segment_flush_loop() -> None:
                while not stop_event.is_set():
                    await asyncio.sleep(0.2)
                    if not state.current_delta:
                        continue
                    if state.last_delta_at is None:
                        continue
                    if (time.time() - state.last_delta_at) < args.segment_silence:
                        continue
                    seg = state.current_delta.strip()
                    if not seg:
                        state.current_delta = ""
                        continue

                    state.committed_text = (state.committed_text + "\n" + seg).strip()
                    state.current_delta = ""
                    append_jsonl(
                        segments_path,
                        {
                            "ts": now_iso(),
                            "text": seg,
                        },
                    )
                    append_text_line(timeline_day_path(runtime_dir), f"[{now_iso()}] {seg}")
                    write_text(live_text_path, state.committed_text + "\n")

                    if args.voice_commands:
                        action = detect_voice_command(seg, start_phrases, stop_phrases)
                        if action:
                            asyncio.create_task(run_marker_script(action, seg))

            async def receiver_loop() -> None:
                while not stop_event.is_set():
                    raw = await ws.recv()
                    obj = json.loads(raw)
                    append_jsonl(events_path, {"ts": now_iso(), "event": obj})
                    evt = obj.get("type", "")

                    if evt in {"response.audio_transcript.delta", "transcription.delta"}:
                        delta = obj.get("delta", "")
                        if delta:
                            # High-resolution stream used for marker-based clipboard selection.
                            append_jsonl(
                                deltas_path,
                                {
                                    "ts": now_iso(),
                                    "epoch": time.time(),
                                    "delta": delta,
                                },
                            )
                            state.current_delta += delta
                            state.last_delta_at = time.time()
                            live = (state.committed_text + state.current_delta).strip()
                            if live:
                                write_text(live_text_path, live + "\n")
                    elif evt == "error":
                        append_jsonl(events_path, {"ts": now_iso(), "error": obj})

            async def heartbeat_loop() -> None:
                while not stop_event.is_set():
                    write_state(
                        state_path,
                        {
                            "connected": state.connected,
                            "started_at": state.started_at,
                            "uptime_s": round(time.time() - state.started_at, 2),
                            "committed_chars": len(state.committed_text),
                            "pending_chars": len(state.current_delta),
                            "ts": now_iso(),
                        },
                    )
                    await asyncio.sleep(1.0)

            with sd.InputStream(
                samplerate=args.samplerate,
                channels=1,
                dtype="float32",
                blocksize=args.blocksize,
                callback=audio_cb,
            ):
                tasks = [
                    asyncio.create_task(sender_loop()),
                    asyncio.create_task(receiver_loop()),
                    asyncio.create_task(commit_loop()),
                    asyncio.create_task(segment_flush_loop()),
                    asyncio.create_task(heartbeat_loop()),
                ]

                await stop_event.wait()

                # Final commit + short drain
                await ws.send(json.dumps({"type": "input_audio_buffer.commit", "final": True}))
                await asyncio.sleep(0.8)

                if state.current_delta.strip():
                    seg = state.current_delta.strip()
                    state.committed_text = (state.committed_text + "\n" + seg).strip()
                    append_jsonl(segments_path, {"ts": now_iso(), "text": seg})
                    append_text_line(timeline_day_path(runtime_dir), f"[{now_iso()}] {seg}")
                    state.current_delta = ""

                write_text(live_text_path, (state.committed_text + "\n") if state.committed_text else "")
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        state.connected = False
        write_state(
            state_path,
            {
                "connected": False,
                "stopped_at": now_iso(),
                "uptime_s": round(time.time() - state.started_at, 2),
                "committed_chars": len(state.committed_text),
                "pending_chars": len(state.current_delta),
            },
        )
        if os.path.exists(pid_path):
            try:
                os.remove(pid_path)
            except OSError:
                pass


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Always-on Voxtral dictation daemon")
    ap.add_argument("--url", default="ws://127.0.0.1:8000/v1/realtime")
    ap.add_argument("--model", default="voxtral-mini-latest")
    ap.add_argument("--runtime-dir", default="runtime/always_on")
    ap.add_argument("--samplerate", type=int, default=16000)
    ap.add_argument("--blocksize", type=int, default=2048)
    ap.add_argument("--commit-every", type=float, default=0.8)
    ap.add_argument("--segment-silence", type=float, default=0.9)
    ap.add_argument("--voice-commands", action="store_true", help="Enable start/stop by spoken keywords")
    ap.add_argument("--voice-start-phrases", default="roger start", help="Comma-separated start phrases")
    ap.add_argument("--voice-stop-phrases", default="roger stop", help="Comma-separated stop phrases")
    ap.add_argument("--voice-command-cooldown", type=float, default=1.0, help="Debounce between voice commands")
    ap.add_argument("--wait-server-s", type=float, default=15.0)
    ap.add_argument("--wait-poll-s", type=float, default=0.4)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    print("Always-on daemon starting...")
    print(f"URL: {args.url}")
    print(f"Model: {args.model}")
    print(f"Runtime dir: {args.runtime_dir}")
    asyncio.run(run_daemon(args))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"[daemon-error] {exc}", file=sys.stderr)
        raise SystemExit(3)
    except ConnectionError as exc:
        print(f"[daemon-error] {exc}", file=sys.stderr)
        print("Hint: start voxmlx first: ./voice_control.sh start", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        pass
