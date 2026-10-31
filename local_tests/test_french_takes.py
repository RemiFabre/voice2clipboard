"""French voice, sentence by sentence (2026-10-31): each sentence rendered alone, a bad take (nothing
said, too short for its letters, a long pause or a mumble inside) rendered again, every sentence at
the same level, even pauses between them. Stub voice whose takes follow a script; no audio.
Run: python3 local_tests/test_french_takes.py   (TEST_SEC=<dir> tests an undeployed speech_render.py)"""
import array, math, os, shutil, subprocess, sys, tempfile, wave
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEC = os.environ.get("TEST_SEC") or os.path.join(ROOT, "scripts", "mac", "secretary")
sys.path.insert(0, SEC); sys.path.insert(1, os.path.join(ROOT, "scripts", "mac", "secretary"))   # dictionary.py
import speech_render as sr

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

tmp = tempfile.mkdtemp(); RATE = 24000
# The stub voice: each call takes the next line of the script ("good 0.3", "silent", "short 0.3",
# "pause 0.3", "quiet 0.3"; the number is the amplitude) and speaks tone bursts at 16 letters/s.
STUB = os.path.join(tmp, "say")
with open(STUB, "w") as f:
    f.write('''#!/usr/bin/env python3
import array, math, re, sys, wave
args = sys.argv[1:]; out = args[args.index("--output") + 1]; text = args[-1]
script, calls = sys.argv[0] + ".script", sys.argv[0] + ".calls"
lines = open(script).read().split("\\n"); line = lines.pop(0).split() or ["good", "0.3"]
open(script, "w").write("\\n".join(lines)); open(calls, "a").write(text + "\\n")
mode, amp = line[0], float(line[1]) if len(line) > 1 else 0.3
RATE = 24000; speech = len(re.findall(r"\\w", text)) / 16.0
if mode == "short": speech /= 3
a = array.array("h", [0] * int(RATE * 0.3))          # leading silence, trimmed by the renderer
def burst(seconds, amp):
    for i in range(int(RATE * seconds)):
        t = i / RATE; a.append(int(amp * 32767 * math.sin(2 * math.pi * 220 * t)) if (t % 0.25) < 0.2 else 0)
if mode == "pause": burst(speech / 2, amp); a.extend([0] * int(RATE * 2.0)); burst(speech / 2, amp)
elif mode == "quiet": burst(speech / 2, amp); burst(1.5, amp / 20); burst(speech / 2, amp)
elif mode != "silent": burst(speech, amp)
a.extend([0] * int(RATE * 0.5))
w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(a.tobytes()); w.close()
''')
os.chmod(STUB, 0o755)

def run(text, script, lang="fr"):
    open(STUB + ".script", "w").write("\n".join(script)); open(STUB + ".calls", "w").close()
    out = os.path.join(tmp, "out.wav")
    if os.path.exists(out): os.remove(out)
    p = subprocess.run([sys.executable, os.path.join(SEC, "speech_render.py"), "render", "--lang", lang, "--voice", "estelle",
                        "--out", out, text], env=dict(os.environ, KOKORO_SAY=STUB), capture_output=True, text=True)
    calls = open(STUB + ".calls").read().splitlines()
    return p, out, calls
def read(path):
    with wave.open(path) as w:
        a = array.array("h"); a.frombytes(w.readframes(w.getnframes())); return a
def silences(a, min_s):
    """Lengths of the silent stretches of at least min_s seconds between the first and last sound."""
    n = int(RATE * 0.02); loud = [max(map(abs, a[i:i + n])) > 300 for i in range(0, len(a) - n + 1, n)]
    first = loud.index(True); last = len(loud) - loud[::-1].index(True); out = []; run_ = 0
    for v in loud[first:last] + [True]:
        if v:
            if run_ * 0.02 >= min_s: out.append(round(run_ * 0.02, 2))
            run_ = 0
        else: run_ += 1
    return out
def levels(a, cut_s):
    """Speech level before and after cut_s seconds."""
    c = int(RATE * cut_s); return sr.speech_level_dbfs(a[:c], RATE), sr.speech_level_dbfs(a[c:], RATE)

S1 = "Le salon est à dix-neuf degrés et la consigne reste à vingt et un."
S2 = "Le chauffage repart demain matin à six heures pour la chambre de Léo."

# 1. how a text is cut
check("a short piece before a colon stays with what follows",
      sr.sentences("Seule piste : un boîtier domotique. Rien n'a été modifié ici.") == ["Seule piste : un boîtier domotique.", "Rien n'a été modifié ici."])
check("a long clause before a colon is its own piece",
      sr.sentences("Ta génération était déjà sur la pente : le même test avait perdu des points.") == ["Ta génération était déjà sur la pente :", "le même test avait perdu des points."])
check("a sentence of three words or fewer goes with the next, with a comma",
      sr.sentences("Pas encore prêt. Il reste deux messages en attente.") == ["Pas encore prêt, il reste deux messages en attente."])
check("an acronym keeps its capitals", sr.sentences("Bien reçu. VMC éteinte ce soir.") == ["Bien reçu. VMC éteinte ce soir."])
check("a short last sentence goes with the one before",
      sr.sentences("Il reste deux messages en attente. Rien d'autre.") == ["Il reste deux messages en attente. Rien d'autre."])
check("a piece cut at a colon is said as a sentence", sr.spoken_form("Seule piste :") == "Seule piste.")
check("times are read as hours",
      sr.spoken_form("à 9 h 12, à 1 h 05, à 14h, à 10 h 00, et 3 hommes") == "à 9 heures 12, à une heure 5, à 14 heures, à 10 heures, et 3 hommes")
check("a one-word message stays one piece", sr.sentences("D'accord.") == ["D'accord."])

# 2. good takes: one call per sentence, the same level whatever each take's level, even pauses
p, out, calls = run(S1 + " " + S2, ["good 0.05", "good 0.6"])
a = read(out)
check("one take per sentence when both are good", p.returncode == 0 and calls == [S1, S2])
l1, l2 = levels(a, len(S1) / 16.0)
check("a quiet take and a loud take come out at the same level (%.1f / %.1f dB)" % (l1, l2), abs(l1 - l2) < 1.5)
gaps = silences(a, 0.3); expected = sr.SENTENCE_PAUSE_MS / 1000 + 2 * sr._EDGE_S   # the pause plus each take's kept edge
check("the takes' own silences are trimmed: one even pause between sentences (%s s)" % gaps, len(gaps) == 1 and abs(gaps[0] - expected) < 0.08)

# 3. bad takes are rendered again
for mode in ("silent", "short", "pause", "quiet"):
    p, out, calls = run(S1, [mode, "good"])
    check(f"a {mode} take is rendered again", p.returncode == 0 and calls == [S1, S1] and f"{'no speech' if mode == 'silent' else ('too short' if mode == 'short' else mode)}" in p.stderr)
p, out, calls = run(S1, ["pause", "pause", "pause"])
check("three takes with a pause: the least bad is kept, nothing lost", p.returncode == 0 and len(calls) == 3 and len(read(out)) > RATE)
p, out, calls = run(S1, ["silent", "pause", "short"])
check("silence beaten by any take with speech", p.returncode == 0 and max(silences(read(out), 1.0) or [0]) >= 1.5)
p, out, calls = run(S1, ["silent", "silent", "silent"])
check("a sentence never said fails the render (the Kokoro fallback speaks the message)", p.returncode != 0 and len(calls) == 3)

# 4. English keeps the chunked path: one call for several sentences
p, out, calls = run("The salon is warm now. The bedroom heats up tomorrow morning.", ["good", "good"], lang="en")
check("English is not split per sentence", p.returncode == 0 and len(calls) == 1)

shutil.rmtree(tmp)
print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
