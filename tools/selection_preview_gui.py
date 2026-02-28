#!/usr/bin/env python3
"""Temporary GUI to visualize marker selection over live transcript deltas.

- Gray text: outside current marker window.
- Highlight text: inside current marker window.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import tkinter as tk
from dataclasses import dataclass, field


@dataclass
class DeltaEntry:
    epoch: float
    delta: str


@dataclass
class AppState:
    runtime_dir: str
    max_chars: int = 30000
    deltas_path: str = field(init=False)
    selections_path: str = field(init=False)
    marker_path: str = field(init=False)
    entries: list[DeltaEntry] = field(default_factory=list)
    file_pos: int = 0
    selections_file_pos: int = 0
    selected_ranges: list[tuple[float, float]] = field(default_factory=list)
    marker_active: bool = False
    marker_start_epoch: float | None = None

    def __post_init__(self) -> None:
        self.deltas_path = os.path.join(self.runtime_dir, "deltas.jsonl")
        self.selections_path = os.path.join(self.runtime_dir, "selections.jsonl")
        self.marker_path = os.path.join(self.runtime_dir, "selection_marker.json")


def read_marker(path: str) -> tuple[bool, float | None]:
    if not os.path.exists(path):
        return False, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        start = obj.get("selection_start_epoch")
        if start is None:
            start = obj.get("started_epoch")
        return True, float(start) if start is not None else None
    except Exception:
        return False, None


def tail_new_deltas(state: AppState) -> None:
    if not os.path.exists(state.deltas_path):
        return
    size = os.path.getsize(state.deltas_path)
    if size < state.file_pos:
        state.file_pos = 0
    with open(state.deltas_path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(state.file_pos)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            delta = obj.get("delta")
            epoch = obj.get("epoch")
            if not delta or epoch is None:
                continue
            try:
                state.entries.append(DeltaEntry(float(epoch), str(delta)))
            except Exception:
                continue
        state.file_pos = f.tell()

    # Prune old text to keep UI responsive.
    total_chars = sum(len(e.delta) for e in state.entries)
    if total_chars <= state.max_chars:
        return
    keep_chars = int(state.max_chars * 0.8)
    acc = 0
    kept: list[DeltaEntry] = []
    for e in reversed(state.entries):
        kept.append(e)
        acc += len(e.delta)
        if acc >= keep_chars:
            break
    state.entries = list(reversed(kept))


def tail_new_selections(state: AppState) -> None:
    if not os.path.exists(state.selections_path):
        return
    size = os.path.getsize(state.selections_path)
    if size < state.selections_file_pos:
        state.selections_file_pos = 0
    with open(state.selections_path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(state.selections_file_pos)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            start = obj.get("selection_start_epoch")
            end = obj.get("selection_end_epoch")
            if start is None or end is None:
                continue
            try:
                state.selected_ranges.append((float(start), float(end)))
            except Exception:
                continue
        state.selections_file_pos = f.tell()


def in_selected_ranges(state: AppState, epoch: float) -> bool:
    for start, end in state.selected_ranges:
        if start <= epoch <= end:
            return True
    return False


def rebuild_text(state: AppState, text_widget: tk.Text) -> None:
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")

    selected_chars = 0
    total_chars = 0
    for entry in state.entries:
        total_chars += len(entry.delta)
        tag = "normal"
        if in_selected_ranges(state, entry.epoch):
            tag = "selected"
            selected_chars += len(entry.delta)
        elif state.marker_active and state.marker_start_epoch is not None and entry.epoch >= state.marker_start_epoch:
            tag = "selected"
            selected_chars += len(entry.delta)
        text_widget.insert("end", entry.delta, (tag,))

    text_widget.configure(state="disabled")
    text_widget.see("end")
    return total_chars, selected_chars


def main() -> None:
    ap = argparse.ArgumentParser(description="Selection preview GUI")
    ap.add_argument("--runtime-dir", default="/Users/remi/voice2clipboard/runtime/always_on")
    ap.add_argument("--refresh-ms", type=int, default=180)
    args = ap.parse_args()

    state = AppState(runtime_dir=args.runtime_dir)

    root = tk.Tk()
    root.title("voice2clipboard selection preview (temporary)")
    root.geometry("1100x520")
    root.configure(bg="#101214")

    top = tk.Frame(root, bg="#101214")
    top.pack(fill="x", padx=12, pady=(10, 4))

    status_var = tk.StringVar(value="Marker: inactive")
    stats_var = tk.StringVar(value="Chars: total=0 selected=0")

    status_label = tk.Label(top, textvariable=status_var, fg="#D0D7DE", bg="#101214", font=("Menlo", 12, "bold"))
    status_label.pack(side="left")
    stats_label = tk.Label(top, textvariable=stats_var, fg="#9AA0A6", bg="#101214", font=("Menlo", 11))
    stats_label.pack(side="right")

    text = tk.Text(
        root,
        wrap="word",
        bg="#14171A",
        fg="#9AA0A6",
        insertbackground="#D0D7DE",
        relief="flat",
        font=("Menlo", 13),
        padx=10,
        pady=10,
    )
    text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    text.tag_configure("normal", foreground="#8B949E")
    text.tag_configure("selected", foreground="#00D084")
    text.configure(state="disabled")

    def tick() -> None:
        state.marker_active, state.marker_start_epoch = read_marker(state.marker_path)
        tail_new_deltas(state)
        tail_new_selections(state)
        total_chars, selected_chars = rebuild_text(state, text)
        if state.marker_active:
            status_var.set(
                f"Marker: ACTIVE  start_epoch={state.marker_start_epoch:.3f}" if state.marker_start_epoch else "Marker: ACTIVE"
            )
        else:
            status_var.set("Marker: inactive")
        stats_var.set(f"Chars: total={total_chars} selected={selected_chars}")
        root.after(args.refresh_ms, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
