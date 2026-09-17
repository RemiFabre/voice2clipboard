#!/usr/bin/env python3
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
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
# Streaming: while the recorder is still capturing, speech regions that VAD has closed
# are decoded in the background so stream_end only has to decode the tail.
STREAM_POLL_S = 1.0
STREAM_CLOSE_MARGIN_S = 1.2       # a region is "closed" once the file extends this far past it
STREAM_MIN_CHUNK_SPEECH_S = 15.0  # accumulate closed regions until this much speech (15 s beat whole-file WER)
STREAM_MAX_CHUNK_WAIT_S = 20.0    # ...or the oldest closed region has waited this long
STREAM_IDLE_TIMEOUT_S = 60.0      # give up if the pcm file stops growing (recorder died)
# Spoken stop command: a short isolated utterance (<= STOP_PROBE_MAX_S of speech, i.e. said after a
# pause) is decoded on its own as soon as VAD closes it; if it is one of the stop phrases the
# helper touches the recorder's stop file and drops the phrase from the transcript. Needed because
# the headset buttons do not reach the Mac while its microphone is in hands-free mode.
STOP_PROBE_MAX_S = 4.0
STOP_TAIL_PROBE_S = 3.0           # longer regions: check whether their last seconds end with the phrase
STOP_PHRASES = [p.strip().lower() for p in os.getenv("VOICE2CLIPBOARD_STOP_PHRASES", "roger stop,over and out,stop dictation").split(",") if p.strip()]
SAMPLE_RATE = 16000


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


DECODE_LOCK = threading.Lock()  # never run two Whisper decodes at once


def vad_options():
    return VadOptions(min_silence_duration_ms=VAD_MIN_SILENCE_MS, speech_pad_ms=VAD_SPEECH_PAD_MS)


def decode_speech(speech):
    """Whisper on a float32 16 kHz array; returns stripped text ('' for empty input)."""
    if speech is None or len(speech) < SAMPLE_RATE // 4:
        return ""
    with DECODE_LOCK:
        result = mlx_whisper.transcribe(speech, path_or_hf_repo=MODEL_REPO, condition_on_previous_text=False)
    return result.get("text", "").strip() if isinstance(result, dict) else str(result).strip()


class StreamSession:
    """Incremental transcription of a growing raw int16 mono 16 kHz PCM file.

    A poll thread reads new samples, runs VAD on the audio not yet committed, and
    once the closed speech regions hold enough speech decodes them as one chunk.
    end() decodes whatever is left and returns the joined text.
    """

    def __init__(self, session_id, pcm_path, stop_file=None, stop_phrases=None):
        self.session_id = session_id
        self.pcm_path = pcm_path
        self.stop_file = stop_file
        self.stop_phrases = [p.lower() for p in (stop_phrases or STOP_PHRASES)]
        self.stop_hit = None                          # text that triggered the spoken stop
        self.probed_until = 0                         # sample offset up to which short regions were probed
        self.tail_probed_until = 0
        self.audio = np.zeros(0, dtype=np.float32)   # everything read so far
        self.committed = 0                            # samples already decoded
        self.pending_regions = []                     # closed regions waiting for enough speech
        self.pending_since = None
        self.texts = []
        self.chunk_stats = []
        self.error = None
        self.started_at = time.time()
        self.lock = threading.Lock()                  # guards audio/committed/texts
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"stream-{session_id}", daemon=True)

    def start(self):
        self.thread.start()

    def _read_new(self):
        size = os.path.getsize(self.pcm_path) if os.path.exists(self.pcm_path) else 0
        have = len(self.audio) * 2
        if size <= have:
            return False
        with open(self.pcm_path, "rb") as f:
            f.seek(have)
            raw = f.read((size - have) // 2 * 2)
        if not raw:
            return False
        new = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        with self.lock:
            self.audio = np.concatenate([self.audio, new])
        return True

    def _closed_regions(self):
        """VAD on the uncommitted tail; returns regions (absolute sample offsets) that are closed."""
        tail = self.audio[self.committed:]
        if len(tail) < SAMPLE_RATE:
            return []
        regions = get_speech_timestamps(tail, vad_options())
        limit = len(tail) - int(STREAM_CLOSE_MARGIN_S * SAMPLE_RATE)
        closed = [r for r in regions if r["end"] <= limit]
        return [{"start": r["start"] + self.committed, "end": r["end"] + self.committed} for r in closed]

    @staticmethod
    def _normalize(text):
        return " ".join(re.sub(r"[^\w\s']", " ", text.lower()).split())

    def _matches_stop_phrase(self, text):
        norm = self._normalize(text)
        if not norm:
            return False
        words = norm.split()
        for phrase in self.stop_phrases:
            if phrase in norm and len(words) <= len(phrase.split()) + 2:
                return True
        return False

    def _ends_with_stop_phrase(self, text):
        norm = self._normalize(text)
        return any(norm.endswith(p) for p in self.stop_phrases) if norm else False

    def _cut_point_before_phrase(self, region):
        """Word timestamps on the region; returns the absolute sample where the stop phrase starts."""
        audio = self.audio[region["start"]:region["end"]]
        with DECODE_LOCK:
            result = mlx_whisper.transcribe(audio, path_or_hf_repo=MODEL_REPO, condition_on_previous_text=False, word_timestamps=True)
        words = [w for seg in result.get("segments", []) for w in seg.get("words", [])]
        if not words:
            return None
        for phrase in self.stop_phrases:
            n = len(phrase.split())
            if n <= len(words) and self._normalize(" ".join(w["word"] for w in words[-n:])) == phrase:
                start_s = words[-n]["start"]
                return region["start"] + int(max(0.0, start_s - 0.15) * SAMPLE_RATE)
        return None

    def _probe_stop_phrase(self, closed):
        """Decode the newest short closed region alone; returns True when it is a stop command."""
        if not self.stop_file or not closed:
            return False
        region = closed[-1]
        if region["end"] <= self.probed_until:
            return False
        if (region["end"] - region["start"]) / SAMPLE_RATE > STOP_PROBE_MAX_S:
            self.probed_until = region["end"]
            return False
        self.probed_until = region["end"]
        text = decode_speech(self.audio[region["start"]:region["end"]])
        if not self._matches_stop_phrase(text):
            return False
        # Commit everything said before the command, drop the command itself, tell the recorder.
        self._decode_regions(closed[:-1])
        with self.lock:
            self.committed = region["end"]
            self.stop_hit = text
        self._touch_stop_file()
        return True

    def _probe_stop_phrase_at_tail(self, closed):
        """Longer closed region whose last seconds end with the phrase (said without a pause)."""
        if not self.stop_file or not closed:
            return False
        region = closed[-1]
        if region["end"] <= self.tail_probed_until:
            return False
        self.tail_probed_until = region["end"]
        if (region["end"] - region["start"]) / SAMPLE_RATE <= STOP_PROBE_MAX_S:
            return False
        tail_start = max(region["start"], region["end"] - int(STOP_TAIL_PROBE_S * SAMPLE_RATE))
        text = decode_speech(self.audio[tail_start:region["end"]])
        if not self._ends_with_stop_phrase(text):
            return False
        cut = self._cut_point_before_phrase(region)
        if cut is None or cut <= region["start"] + SAMPLE_RATE // 4:
            trimmed = []
        else:
            trimmed = [{"start": region["start"], "end": cut}]
        self._decode_regions(closed[:-1] + trimmed)
        with self.lock:
            self.committed = region["end"]
            self.stop_hit = text
        self._touch_stop_file()
        return True

    def _touch_stop_file(self):
        try:
            with open(self.stop_file, "a"):
                pass
        except OSError as e:
            self.error = f"could not touch stop file: {e}"

    def _decode_regions(self, regions, final=False):
        if not regions:
            return
        chunks, _meta = collect_chunks(self.audio, [dict(r) for r in regions], SAMPLE_RATE)
        speech = np.concatenate(chunks)
        t = time.time()
        text = decode_speech(speech)
        with self.lock:
            if text:
                self.texts.append(text)
            self.chunk_stats.append({"speech_s": round(len(speech) / SAMPLE_RATE, 2), "decode_s": round(time.time() - t, 3), "final": final})
            self.committed = regions[-1]["end"]

    def _run(self):
        last_growth = time.time()
        while not self.stop_event.is_set():
            try:
                if self._read_new():
                    last_growth = time.time()
                elif time.time() - last_growth > STREAM_IDLE_TIMEOUT_S:
                    self.error = "pcm file stopped growing"
                    break
                closed = self._closed_regions()
                if closed and (self._probe_stop_phrase(closed) or self._probe_stop_phrase_at_tail(closed)):
                    break
                if closed:
                    speech_s = sum(r["end"] - r["start"] for r in closed) / SAMPLE_RATE
                    if self.pending_since is None:
                        self.pending_since = time.time()
                    if speech_s >= STREAM_MIN_CHUNK_SPEECH_S or time.time() - self.pending_since >= STREAM_MAX_CHUNK_WAIT_S:
                        self._decode_regions(closed)
                        self.pending_since = None
            except Exception as e:  # keep the recorder path alive; end() falls back
                self.error = str(e)
                break
            self.stop_event.wait(STREAM_POLL_S)

    def end(self):
        """Stop polling, decode the remainder, return (text, stats)."""
        t0 = time.time()
        self.stop_event.set()
        self.thread.join()
        if self.error:
            raise RuntimeError(f"stream session failed: {self.error}")
        self._read_new()
        tail = self.audio[self.committed:]
        final_regions = []
        if self.stop_hit is None and len(tail) >= SAMPLE_RATE // 4:
            regions = get_speech_timestamps(tail, vad_options())
            final_regions = [{"start": r["start"] + self.committed, "end": r["end"] + self.committed} for r in regions]
        t_final = time.time()
        self._decode_regions(final_regions, final=True)
        final_wait = time.time() - t_final
        text = " ".join(t for t in self.texts if t).strip()
        stats = {
            "chunks": len(self.chunk_stats),
            "speech_seconds": round(sum(c["speech_s"] for c in self.chunk_stats), 2),
            "input_seconds": round(len(self.audio) / SAMPLE_RATE, 2),
            "final_chunk_seconds": round(sum(c["speech_s"] for c in self.chunk_stats if c["final"]), 2),
            "final_wait_seconds": round(final_wait, 3),
            "end_seconds": round(time.time() - t0, 3),
            "background_decode_seconds": round(sum(c["decode_s"] for c in self.chunk_stats if not c["final"]), 3),
            "stop_phrase_hit": self.stop_hit,
        }
        return text, stats


STREAMS = {}


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
    if isinstance(audio, str):
        audio, _sr = sf.read(audio, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
    text = decode_speech(audio)
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
                    if command == "stream_begin":
                        session_id = request["session_id"]
                        old = STREAMS.pop(session_id, None)
                        if old:
                            old.stop_event.set()
                        session = StreamSession(session_id, request["pcm_path"], stop_file=request.get("stop_file"), stop_phrases=request.get("stop_phrases"))
                        session.start()
                        STREAMS[session_id] = session
                        write_state(status="streaming", last_stream_session=session_id)
                        send_response(conn, {"ok": True, "session_id": session_id})
                        continue
                    if command == "stream_end":
                        session = STREAMS.pop(request["session_id"], None)
                        if session is None:
                            send_response(conn, {"ok": False, "error": "unknown stream session"})
                            continue
                        write_state(status="busy")
                        text, stream_stats = session.end()
                        write_state(status="ready", last_stream_stats=stream_stats, last_output_chars=len(text))
                        send_response(conn, {"ok": True, "text": text, "stream_stats": stream_stats, "helper_state": STATE})
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
