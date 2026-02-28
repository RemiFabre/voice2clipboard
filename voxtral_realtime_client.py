#!/usr/bin/env python3
"""Voxtral realtime websocket microphone client.

Usage:
  python voxtral_realtime_client.py

Controls:
  - Press Enter to toggle capture start/stop
  - Type 'q' + Enter to quit

Output:
  - runtime/voxtral_live_events.jsonl
  - runtime/voxtral_live_text.txt
"""

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pyperclip
import sounddevice as sd
import websockets


@dataclass
class RuntimeState:
    capturing: bool = False
    current_delta: str = ""
    committed_text: str = ""
    capture_started_at: float = 0.0


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def append_jsonl(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


async def send_session_update(ws, model, temperature):
    event = {
        "type": "session.update",
        "model": model,
        "temperature": temperature,
    }
    await ws.send(json.dumps(event))


async def sender_loop(ws, queue, state):
    while True:
        item = await queue.get()
        if item is None:
            return
        if not state.capturing:
            continue

        payload = {
            "type": "input_audio_buffer.append",
            "audio": item,
        }
        await ws.send(json.dumps(payload))


async def receiver_loop(ws, state, events_path, text_path, copy_on_commit=False):
    try:
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            event_type = data.get("type", "unknown")

            append_jsonl(events_path, {
                "ts": now_iso(),
                "event": data,
            })

            if event_type in {"transcription.delta", "response.audio_transcript.delta"}:
                delta = data.get("delta", "")
                if delta:
                    state.current_delta += delta
                    sys.stdout.write(delta)
                    sys.stdout.flush()
                    # Keep a continuously readable snapshot for debugging/live usage.
                    live_text = (state.committed_text + state.current_delta).strip()
                    if live_text:
                        write_text(text_path, live_text + "\n")
            elif event_type in {"transcription.done", "transcription.final"}:
                full = data.get("text", "").strip()
                if not full:
                    full = state.current_delta.strip()
                if full:
                    state.committed_text = (state.committed_text + "\n" + full).strip()
                    write_text(text_path, state.committed_text + "\n")
                    if copy_on_commit:
                        pyperclip.copy(full)
                state.current_delta = ""
                print("\n[commit]")
            elif event_type == "error":
                print(f"\n[server-error] {data}")
    except websockets.exceptions.ConnectionClosed:
        return


async def user_loop(ws, state):
    print("Connected. Controls: Enter=start/stop capture, q + Enter=quit")
    while True:
        cmd = await asyncio.to_thread(input, "")
        cmd = cmd.strip().lower()

        if cmd == "q":
            if state.capturing:
                state.capturing = False
                await ws.send(json.dumps({"type": "input_audio_buffer.commit", "final": True}))
            await ws.close()
            return

        if not state.capturing:
            state.capturing = True
            state.capture_started_at = time.time()
            state.current_delta = ""
            print("[capture started]")
            # Commit boundary start (model-card pattern)
            await ws.send(json.dumps({"type": "input_audio_buffer.commit", "final": False}))
        else:
            state.capturing = False
            elapsed = time.time() - state.capture_started_at
            print(f"\n[capture stopped] {elapsed:.1f}s")
            # Commit boundary end
            await ws.send(json.dumps({"type": "input_audio_buffer.commit", "final": True}))
            # Some servers only stream deltas and never emit a final event type.
            full = state.current_delta.strip()
            if full:
                state.committed_text = (state.committed_text + "\n" + full).strip()
                state.current_delta = ""
                print("\n[commit]")


def make_audio_callback(loop, queue, samplerate, channels):
    def callback(indata, _frames, _time_info, status):
        if status:
            return

        pcm16 = np.clip(indata[:, 0], -1.0, 1.0)
        pcm16 = (pcm16 * 32767.0).astype(np.int16)
        b = pcm16.tobytes()
        b64 = __import__("base64").b64encode(b).decode("ascii")
        loop.call_soon_threadsafe(queue.put_nowait, b64)

    return callback


async def main():
    parser = argparse.ArgumentParser(description="Voxtral realtime websocket mic client")
    parser.add_argument("--url", default="ws://127.0.0.1:8000/v1/realtime")
    parser.add_argument("--model", default="mistralai/Voxtral-Mini-4B-Realtime-2602")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--samplerate", type=int, default=16000)
    parser.add_argument("--channels", type=int, default=1)
    parser.add_argument("--blocksize", type=int, default=2048)
    parser.add_argument("--runtime-dir", default="runtime")
    parser.add_argument("--copy-on-commit", action="store_true")
    args = parser.parse_args()

    os.makedirs(args.runtime_dir, exist_ok=True)
    events_path = os.path.join(args.runtime_dir, "voxtral_live_events.jsonl")
    text_path = os.path.join(args.runtime_dir, "voxtral_live_text.txt")

    state = RuntimeState()
    audio_queue = asyncio.Queue(maxsize=64)

    async with websockets.connect(args.url, max_size=10 * 1024 * 1024) as ws:
        await send_session_update(ws, args.model, args.temperature)

        loop = asyncio.get_running_loop()
        callback = make_audio_callback(loop, audio_queue, args.samplerate, args.channels)

        with sd.InputStream(
            samplerate=args.samplerate,
            channels=args.channels,
            dtype="float32",
            blocksize=args.blocksize,
            callback=callback,
        ):
            sender = asyncio.create_task(sender_loop(ws, audio_queue, state))
            receiver = asyncio.create_task(receiver_loop(ws, state, events_path, text_path, args.copy_on_commit))
            user = asyncio.create_task(user_loop(ws, state))

            done, pending = await asyncio.wait(
                {sender, receiver, user},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            await audio_queue.put(None)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
