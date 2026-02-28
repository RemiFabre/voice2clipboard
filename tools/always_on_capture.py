#!/usr/bin/env python3
"""Marker-based capture selection over always-on transcript segments.

Commands:
  start  -> set selection start marker
  stop   -> copy transcript between marker and now to clipboard
  status -> print current marker + daemon status
  clear  -> clear marker
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

import pyperclip


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_segments(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def read_deltas(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            out.append(obj)
    return out


def parse_iso_to_epoch(s: str) -> float:
    return datetime.fromisoformat(s).timestamp()


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        # Process exists but this process cannot signal it.
        return True
    except Exception:
        return False


def cmd_start(runtime_dir: str) -> int:
    marker_path = os.path.join(runtime_dir, "selection_marker.json")
    boundary_pad_s = env_float("VOICE2CLIP_BOUNDARY_PAD_S", env_float("VOICE2CLIP_TRANSCRIPT_LAG_S", 0.66))
    started_epoch = time.time()
    payload = {
        "started_at": now_iso(),
        "started_epoch": started_epoch,
        # Use one symmetric pad at both boundaries for delta-emission latency.
        "selection_start_epoch": started_epoch + boundary_pad_s,
        "boundary_pad_s": boundary_pad_s,
    }
    write_json(marker_path, payload)
    print(f"Selection started at {payload['started_at']}")
    return 0


def cmd_stop(runtime_dir: str) -> int:
    marker_path = os.path.join(runtime_dir, "selection_marker.json")
    segments_path = os.path.join(runtime_dir, "segments.jsonl")
    deltas_path = os.path.join(runtime_dir, "deltas.jsonl")
    out_path = os.path.join(runtime_dir, "last_selection.txt")

    marker = read_json(marker_path)
    if not marker:
        print("No selection marker found. Run start first.")
        return 1

    boundary_pad_s = float(marker.get("boundary_pad_s", env_float("VOICE2CLIP_BOUNDARY_PAD_S", env_float("VOICE2CLIP_TRANSCRIPT_LAG_S", 0.66))))
    pressed_stop_epoch = time.time()

    # Symmetric boundary compensation: same pad for start and stop.
    selection_start_epoch = float(marker.get("selection_start_epoch", float(marker.get("started_epoch", 0.0)) + boundary_pad_s))
    selection_end_epoch = pressed_stop_epoch + boundary_pad_s

    wait_s = selection_end_epoch - time.time()
    if wait_s > 0:
        time.sleep(wait_s)

    picked_deltas: list[str] = []
    for d in read_deltas(deltas_path):
        delta = d.get("delta")
        if not delta:
            continue
        epoch = d.get("epoch")
        if epoch is None:
            ts = d.get("ts")
            if not ts:
                continue
            try:
                epoch = parse_iso_to_epoch(ts)
            except Exception:
                continue
        try:
            epoch = float(epoch)
        except Exception:
            continue
        if selection_start_epoch <= epoch <= selection_end_epoch:
            picked_deltas.append(str(delta))

    # Preferred path: fine-grained delta stream (more accurate than segment-level cut).
    selected_text = "".join(picked_deltas).strip()
    picked_segments: list[str] = []
    for seg in read_segments(segments_path):
        ts = seg.get("ts")
        text = (seg.get("text") or "").strip()
        if not ts or not text:
            continue
        try:
            seg_epoch = parse_iso_to_epoch(ts)
        except Exception:
            continue
        if selection_start_epoch <= seg_epoch <= selection_end_epoch:
            picked_segments.append(text)

    # Fallback for older runs with no deltas stream available.
    if not selected_text:
        selected_text = "\n".join(picked_segments).strip()
    if not selected_text:
        print("No transcript segments found in selected interval.")
        os.remove(marker_path)
        return 2

    pyperclip.copy(selected_text)
    os.makedirs(runtime_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(selected_text + "\n")

    if os.path.exists(marker_path):
        os.remove(marker_path)

    print(f"Copied {len(selected_text)} chars to clipboard.")
    print(f"Saved selection to {out_path}")
    return 0


def cmd_status(runtime_dir: str) -> int:
    state_path = os.path.join(runtime_dir, "state.json")
    marker_path = os.path.join(runtime_dir, "selection_marker.json")
    pid_path = os.path.join(runtime_dir, "daemon.pid")

    state = read_json(state_path)
    marker = read_json(marker_path)
    pid = None
    if os.path.exists(pid_path):
        try:
            pid = int(open(pid_path, "r", encoding="utf-8").read().strip())
        except Exception:
            pid = None

    if state:
        print("Daemon state:")
        print(json.dumps(state, ensure_ascii=False, indent=2))
        ts = state.get("ts")
        stale_s = None
        if ts:
            try:
                stale_s = time.time() - parse_iso_to_epoch(ts)
            except Exception:
                stale_s = None
        print("\nHealth:")
        print(f"- daemon pid: {pid if pid is not None else 'unknown'}")
        print(f"- pid running: {is_pid_running(pid or -1)}")
        if stale_s is not None:
            print(f"- state freshness: {round(stale_s, 1)}s old")
    else:
        print("Daemon state file not found.")

    if marker:
        print("\nActive selection marker:")
        print(json.dumps(marker, ensure_ascii=False, indent=2))
    else:
        print("\nNo active selection marker.")
    return 0


def cmd_clear(runtime_dir: str) -> int:
    marker_path = os.path.join(runtime_dir, "selection_marker.json")
    if os.path.exists(marker_path):
        os.remove(marker_path)
        print("Selection marker cleared.")
    else:
        print("No selection marker to clear.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Marker-based selection over always-on transcript")
    ap.add_argument("command", choices=["start", "stop", "status", "clear"])
    ap.add_argument("--runtime-dir", default="runtime/always_on")
    args = ap.parse_args()

    if args.command == "start":
        return cmd_start(args.runtime_dir)
    if args.command == "stop":
        return cmd_stop(args.runtime_dir)
    if args.command == "status":
        return cmd_status(args.runtime_dir)
    return cmd_clear(args.runtime_dir)


if __name__ == "__main__":
    raise SystemExit(main())
