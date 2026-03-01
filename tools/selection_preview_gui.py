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
    state_path: str = field(init=False)
    entries: list[DeltaEntry] = field(default_factory=list)
    file_pos: int = 0
    selections_file_pos: int = 0
    selected_ranges: list[tuple[float, float]] = field(default_factory=list)
    selected_spans: list[tuple[int, int]] = field(default_factory=list)
    pending_selection_texts: list[str] = field(default_factory=list)
    selection_search_cursor: int = 0
    marker_active: bool = False
    marker_start_epoch: float | None = None
    daemon_connected: bool = False

    def __post_init__(self) -> None:
        self.deltas_path = os.path.join(self.runtime_dir, "deltas.jsonl")
        self.selections_path = os.path.join(self.runtime_dir, "selections.jsonl")
        self.marker_path = os.path.join(self.runtime_dir, "selection_marker.json")
        self.state_path = os.path.join(self.runtime_dir, "state.json")


def read_marker(path: str) -> tuple[bool, float | None]:
    if not os.path.exists(path):
        return False, None


def read_daemon_connected(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return bool(obj.get("connected", False))
    except Exception:
        return False
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
    dropped = total_chars - sum(len(e.delta) for e in state.entries)
    if dropped > 0:
        shifted: list[tuple[int, int]] = []
        for s, e in state.selected_spans:
            ns = max(0, s - dropped)
            ne = max(0, e - dropped)
            if ne > ns:
                shifted.append((ns, ne))
        state.selected_spans = shifted
        state.selection_search_cursor = max(0, state.selection_search_cursor - dropped)


def full_text(state: AppState) -> str:
    return "".join(e.delta for e in state.entries)


def resolve_pending_selection_texts(state: AppState) -> None:
    if not state.pending_selection_texts:
        return
    hay = full_text(state)
    unresolved: list[str] = []
    start_local_hint = max(0, state.selection_search_cursor)
    for needle in state.pending_selection_texts:
        s = hay.find(needle, start_local_hint)
        if s < 0:
            s = hay.find(needle)
        if s < 0:
            unresolved.append(needle)
            continue
        e = s + len(needle)
        state.selected_spans.append((s, e))
        state.selection_search_cursor = max(state.selection_search_cursor, e)
        start_local_hint = max(0, e)
    state.pending_selection_texts = unresolved


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
            source = str(obj.get("source", ""))
            sel_text = str(obj.get("selection_text", "")).strip()
            if source == "voice_command" and sel_text:
                state.pending_selection_texts.append(sel_text)
                continue
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

    text = full_text(state)
    mask = [False] * len(text)
    for s, e in state.selected_spans:
        ls = max(0, min(len(mask), s))
        le = max(0, min(len(mask), e))
        for i in range(ls, le):
            mask[i] = True

    pos = 0
    for entry in state.entries:
        seg_start = pos
        seg_end = pos + len(entry.delta)
        if in_selected_ranges(state, entry.epoch) or (
            state.marker_active and state.marker_start_epoch is not None and entry.epoch >= state.marker_start_epoch
        ):
            for i in range(seg_start, seg_end):
                mask[i] = True
        pos = seg_end

    if text:
        run_sel = mask[0]
        run_start = 0
        for i in range(1, len(text)):
            if mask[i] != run_sel:
                text_widget.insert("end", text[run_start:i], ("selected" if run_sel else "normal",))
                run_start = i
                run_sel = mask[i]
        text_widget.insert("end", text[run_start:], ("selected" if run_sel else "normal",))

    text_widget.configure(state="disabled")
    text_widget.see("end")
    return len(text), sum(1 for x in mask if x)


def main() -> None:
    ap = argparse.ArgumentParser(description="Selection preview GUI")
    ap.add_argument("--runtime-dir", default="/Users/remi/voice2clipboard/runtime/always_on")
    ap.add_argument("--refresh-ms", type=int, default=180)
    args = ap.parse_args()

    state = AppState(runtime_dir=args.runtime_dir)
    # Session-only preview: start from current file end, ignore historical text/ranges.
    if os.path.exists(state.deltas_path):
        state.file_pos = os.path.getsize(state.deltas_path)
    if os.path.exists(state.selections_path):
        state.selections_file_pos = os.path.getsize(state.selections_path)

    root = tk.Tk()
    root.title("voice2clipboard selection preview (temporary)")
    root.geometry("1100x520")
    root.configure(bg="#101214")

    top = tk.Frame(root, bg="#101214")
    top.pack(fill="x", padx=12, pady=(10, 4))

    status_var = tk.StringVar(value="Daemon: disconnected | Marker: inactive")
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
        state.daemon_connected = read_daemon_connected(state.state_path)
        tail_new_deltas(state)
        tail_new_selections(state)
        resolve_pending_selection_texts(state)
        total_chars, selected_chars = rebuild_text(state, text)
        daemon = "Daemon: listening" if state.daemon_connected else "Daemon: disconnected"
        if state.marker_active:
            marker = (
                f"Marker: ACTIVE  start_epoch={state.marker_start_epoch:.3f}"
                if state.marker_start_epoch
                else "Marker: ACTIVE"
            )
        else:
            marker = "Marker: inactive"
        status_var.set(f"{daemon} | {marker}")
        stats_var.set(f"Chars: total={total_chars} selected={selected_chars}")
        root.after(args.refresh_ms, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    main()
