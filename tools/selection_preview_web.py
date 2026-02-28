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
    marker_path: str = field(init=False)
    entries: list[DeltaEntry] = field(default_factory=list)
    file_pos: int = 0
    marker_active: bool = False
    marker_start_epoch: float | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.deltas_path = os.path.join(self.runtime_dir, "deltas.jsonl")
        self.marker_path = os.path.join(self.runtime_dir, "selection_marker.json")


def read_marker(path: str) -> tuple[bool, float | None]:
    if not os.path.exists(path):
        return False, None
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


def build_snapshot(state: SharedState) -> dict:
    with state.lock:
        active = state.marker_active
        start = state.marker_start_epoch
        chunks = []
        total = 0
        selected = 0
        for e in state.entries:
            total += len(e.delta)
            is_sel = bool(active and start is not None and e.epoch >= start)
            if is_sel:
                selected += len(e.delta)
            chunks.append({"t": e.delta, "s": is_sel})
    return {
        "marker_active": active,
        "marker_start_epoch": start,
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
<div class="top"><div class="status" id="status">Marker: inactive</div><div class="stats" id="stats"></div></div>
<div id="text"></div>
<script>
async function tick(){
  const r = await fetch('/snapshot');
  const d = await r.json();
  const s = document.getElementById('status');
  const st = document.getElementById('stats');
  const t = document.getElementById('text');
  s.textContent = d.marker_active ? `Marker: ACTIVE start_epoch=${(d.marker_start_epoch||0).toFixed(3)}` : 'Marker: inactive';
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

    def updater() -> None:
        while True:
            with state.lock:
                state.marker_active, state.marker_start_epoch = read_marker(state.marker_path)
                tail_new_deltas(state)
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
