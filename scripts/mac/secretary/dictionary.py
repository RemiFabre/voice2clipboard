#!/usr/bin/env python3
"""Word dictionary for the voice layer (secretary/dictionary.json).
  dictionary.py transcribe  < text   -> fixes mis-transcribed words in a dictation
  dictionary.py pronounce   < text   -> rewrites words so Kokoro pronounces them right
  dictionary.py pronounce_fr < text  -> same for the French voice, from "pronounce_fr" only: the
                                        English respellings ("Clawed") are wrong in French
Importable: apply(text, mode)."""
import json
import os
import re
import sys

DICT_PATH = os.getenv("VOICE2CLIPBOARD_DICTIONARY", "/Users/remi/voice2clipboard/secretary/dictionary.json")
_cache = {"mtime": None, "rules": None}


def _load():
    try:
        mtime = os.path.getmtime(DICT_PATH)
    except OSError:
        return []
    if _cache["mtime"] != mtime:
        with open(DICT_PATH) as f:
            entries = json.load(f).get("entries", [])
        transcribe, pronounce, pronounce_fr = [], [], []
        for e in entries:
            say = e.get("say", "")
            for h in sorted(e.get("hear", []), key=len, reverse=True):  # longest first
                transcribe.append((re.compile(r"\b" + re.escape(h) + r"\b", re.I), say))
            for field, rules in (("pronounce", pronounce), ("pronounce_fr", pronounce_fr)):
                if e.get(field) and e[field] != say:
                    rules.append((re.compile(r"\b" + re.escape(say) + r"\b", re.I), e[field]))
        _cache.update(mtime=mtime, rules={"transcribe": transcribe, "pronounce": pronounce, "pronounce_fr": pronounce_fr})
    return _cache["rules"]


def apply(text, mode="transcribe"):
    rules = _load()
    if not rules or not text:
        return text
    for pattern, repl in rules.get(mode, []):
        text = pattern.sub(repl, text)
    return text


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "transcribe"
    sys.stdout.write(apply(sys.stdin.read(), mode))
