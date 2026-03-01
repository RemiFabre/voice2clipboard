#!/usr/bin/env python3
"""No-dependency web preview for marker-selected transcript deltas."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class DeltaEntry:
    epoch: float
    delta: str


@dataclass
class SharedState:
    runtime_dir: str
    max_chars: int = 40000
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
    lock: threading.Lock = field(default_factory=threading.Lock)

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
        start = obj.get("selection_start_epoch", obj.get("started_epoch"))
        return True, float(start) if start is not None else None
    except Exception:
        return False, None


def tail_new_deltas(state: SharedState) -> None:
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


def full_text(state: SharedState) -> str:
    return "".join(e.delta for e in state.entries)


def resolve_pending_selection_texts(state: SharedState) -> None:
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


def tail_new_selections(state: SharedState) -> None:
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


def in_selected_ranges(state: SharedState, epoch: float) -> bool:
    for start, end in state.selected_ranges:
        if start <= epoch <= end:
            return True
    return False


def build_snapshot(state: SharedState) -> dict:
    with state.lock:
        active = state.marker_active
        start = state.marker_start_epoch
        text = full_text(state)
        mask = [False] * len(text)

        for s, e in state.selected_spans:
            ls = max(0, min(len(mask), s))
            le = max(0, min(len(mask), e))
            for i in range(ls, le):
                mask[i] = True

        pos = 0
        for e in state.entries:
            seg_start = pos
            seg_end = pos + len(e.delta)
            if in_selected_ranges(state, e.epoch) or bool(active and start is not None and e.epoch >= start):
                for i in range(seg_start, seg_end):
                    mask[i] = True
            pos = seg_end

        chunks = []
        if text:
            run_sel = mask[0]
            run_start = 0
            for i in range(1, len(text)):
                if mask[i] != run_sel:
                    chunks.append({"t": text[run_start:i], "s": run_sel})
                    run_start = i
                    run_sel = mask[i]
            chunks.append({"t": text[run_start:], "s": run_sel})
        total = len(text)
        selected = sum(1 for x in mask if x)
    return {
        "marker_active": active,
        "marker_start_epoch": start,
        "daemon_connected": state.daemon_connected,
        "total_chars": total,
        "selected_chars": selected,
        "chunks": chunks,
        "ts": time.time(),
    }


HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>voice2clipboard preview</title>
<style>
body { background:#101214; color:#d0d7de; font-family:Menlo, monospace; margin:0; }
.top { padding:10px 14px; display:flex; justify-content:space-between; border-bottom:1px solid #2a2f35; }
.status { font-weight:700; }
.stats { color:#9aa0a6; }
#text { white-space:pre-wrap; padding:12px 14px; line-height:1.45; font-size:15px; }
.n { color:#8b949e; }
.s { color:#00d084; }
</style></head>
<body>
<div class="top"><div class="status" id="status">Daemon: disconnected | Marker: inactive</div><div class="stats" id="stats"></div></div>
<div id="text"></div>
<script>
async function tick(){
  const r = await fetch('/snapshot');
  const d = await r.json();
  const s = document.getElementById('status');
  const st = document.getElementById('stats');
  const t = document.getElementById('text');
  const daemon = d.daemon_connected ? 'Daemon: listening' : 'Daemon: disconnected';
  const marker = d.marker_active ? `Marker: ACTIVE start_epoch=${(d.marker_start_epoch||0).toFixed(3)}` : 'Marker: inactive';
  s.textContent = `${daemon} | ${marker}`;
  st.textContent = `Chars: total=${d.total_chars} selected=${d.selected_chars}`;
  let html = '';
  for (const c of d.chunks) {
    const cls = c.s ? 's' : 'n';
    const safe = c.t.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    html += `<span class="${cls}">${safe}</span>`;
  }
  t.innerHTML = html;
  window.scrollTo(0, document.body.scrollHeight);
}
setInterval(tick, 180); tick();
</script></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Selection preview web server")
    ap.add_argument("--runtime-dir", default="/Users/remi/voice2clipboard/runtime/always_on")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    state = SharedState(runtime_dir=args.runtime_dir)
    # Session-only preview: ignore historical content before startup.
    if os.path.exists(state.deltas_path):
        state.file_pos = os.path.getsize(state.deltas_path)
    if os.path.exists(state.selections_path):
        state.selections_file_pos = os.path.getsize(state.selections_path)

    def updater() -> None:
        while True:
            with state.lock:
                state.marker_active, state.marker_start_epoch = read_marker(state.marker_path)
                state.daemon_connected = read_daemon_connected(state.state_path)
                tail_new_deltas(state)
                tail_new_selections(state)
                resolve_pending_selection_texts(state)
            time.sleep(0.12)

    threading.Thread(target=updater, daemon=True).start()

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/" or self.path.startswith("/index"):
                body = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/snapshot":
                body = json.dumps(build_snapshot(state)).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, fmt, *args):  # noqa: D401, N802
            return

    srv = ThreadingHTTPServer((args.host, args.port), H)
    print(f"Preview server: http://{args.host}:{args.port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
