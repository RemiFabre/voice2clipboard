#!/bin/bash
# recover_orphaned_recording.sh <audio.wav> [transcriber args...]
# A recorder ended without a transcript (crash, kill, headset gone). Rebuild the WAV from the raw
# PCM sidecar if its header is broken, then transcribe it with the normal quick-mode path.
set -uo pipefail
ROOT_DIR="/Users/remi/voice2clipboard"
audio="$1"; shift
[[ -f "$audio" ]] || { echo "no audio at $audio"; exit 1; }
source /Users/remi/.virtualenvs/voice2clipboard/bin/activate
cd "$ROOT_DIR"
python - "$audio" <<'PY'
import os, sys, soundfile as sf, numpy as np
wav = sys.argv[1]; pcm = os.path.splitext(wav)[0] + ".pcm"
ok = False
try:
    ok = sf.info(wav).duration > 0.5
except Exception:
    ok = False
if not ok and os.path.exists(pcm) and os.path.getsize(pcm) > 32000:
    data = np.frombuffer(open(pcm, "rb").read(), dtype=np.int16)
    sf.write(wav, data, 16000, subtype="PCM_16")
    print(f"rebuilt {wav} from {pcm}: {len(data)/16000:.1f} s")
elif ok:
    print(f"wav readable: {sf.info(wav).duration:.1f} s")
else:
    print("nothing usable to recover"); sys.exit(2)
PY
[[ $? -eq 0 ]] || exit 2
exec python apps/linux/legacy_whisper/voice_transcriber.py "$@" "$audio"
