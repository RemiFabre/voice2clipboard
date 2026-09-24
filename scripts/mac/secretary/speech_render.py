#!/usr/bin/env python3
"""Renders speech to wav files through the warm Kokoro daemon, ahead of playback.

  speech_render.py render --lang en --voice af_heart --out file.wav "text"
  speech_render.py concat --out file.wav [--lead-in-ms 350] [--gap-ms 150] a.wav b.wav ...
  speech_render.py normalize a.wav b.wav ...      (in place: same speech level for every voice)

render applies the pronunciation dictionary and splits long texts into chunks of a few
sentences. The daemon serves one request at a time (measured 2026-09-19: a 600 word text takes
26 s, and a one-sentence request sent meanwhile waited 16 s), so chunking keeps an urgent
sentence from waiting behind a long report: it slips in between two chunks.
concat joins clips (same format) with a silent lead-in, because the earbuds swallow the first
fraction of a second of any audio. Standard library only: hooks call this with the system python."""
import argparse
import array
import math
import os
import re
import subprocess
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dictionary  # noqa: E402

KOKORO_SAY = os.getenv("KOKORO_SAY", "/Users/remi/local-tts-lab/.venv/bin/kokoro-say")
CHUNK_WORDS = int(os.getenv("SPEECH_RENDER_CHUNK_WORDS", "60"))


def chunks(text, max_words=CHUNK_WORDS):
    """Groups of whole sentences of at most max_words words (a longer single sentence stays whole)."""
    sentences = [s for s in re.split(r"(?<=[.!?:;])\s+", " ".join(text.split())) if s]
    out, current, count = [], [], 0
    for s in sentences:
        n = len(s.split())
        if current and count + n > max_words:
            out.append(" ".join(current)); current, count = [], 0
        current.append(s); count += n
    if current:
        out.append(" ".join(current))
    return out


def concat(paths, out, lead_in_ms=0, gap_ms=0):
    params, frames = None, []
    for p in paths:
        with wave.open(p, "rb") as w:
            if params is None:
                params = w.getparams()
            elif (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (params.nchannels, params.sampwidth, params.framerate):
                raise SystemExit(f"format mismatch: {p}")
            frames.append(w.readframes(w.getnframes()))
    if params is None:
        raise SystemExit("nothing to join")
    silence = lambda ms: b"\0" * (params.nchannels * params.sampwidth * int(params.framerate * ms / 1000))
    tmp = out + ".part"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(params.nchannels); w.setsampwidth(params.sampwidth); w.setframerate(params.framerate)
        w.writeframes(silence(lead_in_ms))
        for i, f in enumerate(frames):
            if i:
                w.writeframes(silence(gap_ms))
            w.writeframes(f)
    os.replace(tmp, out)   # readers never see a half-written file


# Loudness (Remi, 2026-09-21: the voices did not sound equally loud to him). Measured on the
# cached clips that day: the speech level of the voices in use spread over 10 dB (-28.5 dBFS for
# the quietest, -17.8 for the loudest). Every rendered file is therefore brought to one speech
# level: the RMS of the frames that carry speech (50 ms frames above a gate, so pauses do not
# count), moved to SPEECH_TARGET_DBFS, with the gain kept within +/-15 dB and peaks rounded off
# softly instead of clipping. Standard library only, like the rest of this file.
TARGET_DBFS = float(os.getenv("SPEECH_TARGET_DBFS", "-20"))
NORMALIZE = os.getenv("SPEECH_NORMALIZE", "1") != "0"
_GATE, _KNEE, _CEIL = 0.01, 0.80, 0.98


def speech_level_dbfs(samples, rate):
    """Level of the frames that carry speech, in dBFS; None when there is no speech."""
    n = max(1, int(rate * 0.05))
    total, count = 0.0, 0
    for i in range(0, len(samples) - n + 1, n):
        fr = samples[i:i + n]
        e = sum(map(lambda x: x * x, fr)) / n / (32768.0 ** 2)
        if e > _GATE * _GATE:
            total += e; count += 1
    if count < 3:
        return None
    return 10 * math.log10(total / count)


def normalize(path):
    """Bring a 16-bit wav to the target speech level, in place. Returns the gain in dB (0 when untouched)."""
    with wave.open(path, "rb") as w:
        params = w.getparams()
        raw = w.readframes(w.getnframes())
    if params.sampwidth != 2:
        return 0.0
    samples = array.array("h"); samples.frombytes(raw)
    mono = samples if params.nchannels == 1 else samples[::params.nchannels]
    level = speech_level_dbfs(mono, params.framerate)
    if level is None:
        return 0.0
    gain_db = max(-15.0, min(15.0, TARGET_DBFS - level))
    if abs(gain_db) < 0.5:
        return 0.0
    g = 10 ** (gain_db / 20)
    knee, span = _KNEE * 32767, (_CEIL - _KNEE) * 32767

    def shape(x):
        y = x * g
        a = abs(y)
        if a <= knee:
            return int(y)
        a = knee + span * math.tanh((a - knee) / span)   # rounds a peak off instead of clipping it
        return int(a if y > 0 else -a)

    out = array.array("h", map(shape, samples))
    tmp = path + ".norm"
    with wave.open(tmp, "wb") as w:
        w.setparams(params); w.writeframes(out.tobytes())
    os.replace(tmp, path)
    return gain_db


def render(text, lang, voice, out):
    text = dictionary.apply(text, "pronounce")
    parts = chunks(text)
    if not parts:
        raise SystemExit("empty text")
    env = dict(os.environ, PYTORCH_ENABLE_MPS_FALLBACK="1")
    with tempfile.TemporaryDirectory() as d:
        files = []
        for i, part in enumerate(parts):
            f = os.path.join(d, f"{i:04d}.wav")
            r = subprocess.run([KOKORO_SAY, "--lang", lang, "--voice", voice, "--no-play", "--output", f, part],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode != 0 or not os.path.exists(f):
                raise SystemExit(f"kokoro failed on chunk {i}")
            files.append(f)
        concat(files, out, gap_ms=120 if len(files) > 1 else 0)
    if NORMALIZE:
        try:
            normalize(out)
        except Exception as e:      # a voice at its own level is better than no voice
            print(f"speech_render: not normalised ({e})", file=sys.stderr)


def tail(path, out, from_s, lead_in_ms=350):
    """The rest of a wav from `from_s` seconds on, after a silent lead-in: what a resumed message plays."""
    with wave.open(path, "rb") as w:
        params = w.getparams()
        w.setpos(min(max(0, int(from_s * params.framerate)), w.getnframes()))
        rest = w.readframes(w.getnframes())
    tmp = out + ".part"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(params.nchannels); w.setsampwidth(params.sampwidth); w.setframerate(params.framerate)
        w.writeframes(b"\0" * (params.nchannels * params.sampwidth * int(params.framerate * lead_in_ms / 1000)))
        w.writeframes(rest)
    os.replace(tmp, out)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render"); r.add_argument("--lang", default="en"); r.add_argument("--voice", required=True)
    r.add_argument("--out", required=True); r.add_argument("text", nargs="+")
    c = sub.add_parser("concat"); c.add_argument("--out", required=True); c.add_argument("--lead-in-ms", type=int, default=350)
    c.add_argument("--gap-ms", type=int, default=150); c.add_argument("files", nargs="+")
    n = sub.add_parser("normalize"); n.add_argument("files", nargs="+")
    t = sub.add_parser("tail"); t.add_argument("--out", required=True); t.add_argument("--from-s", type=float, required=True)
    t.add_argument("--lead-in-ms", type=int, default=350); t.add_argument("file")
    a = ap.parse_args()
    if a.cmd == "render":
        render(" ".join(a.text), a.lang, a.voice, a.out)
    elif a.cmd == "normalize":
        for f in a.files:
            print("%+5.1f dB  %s" % (normalize(f), f))
    elif a.cmd == "tail":
        tail(a.file, a.out, a.from_s, a.lead_in_ms)
    else:
        concat(a.files, a.out, a.lead_in_ms, a.gap_ms)


if __name__ == "__main__":
    main()
