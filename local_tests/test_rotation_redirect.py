"""Recorder side of the secretary's lazy rotation: where does the transcript go?
No audio, no iTerm: the rotation directory is a temp folder and "is that window alive" is a stub.
Run: python local_tests/test_rotation_redirect.py   (TEST_VT_DIR=<dir> tests an undeployed recorder)"""
import os, sys, tempfile, threading, time
sys.path.insert(0, os.environ.get("TEST_VT_DIR") or os.path.join(os.path.dirname(__file__), "..", "apps", "linux", "legacy_whisper"))
import voice_transcriber as vt

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name)
    fails += 0 if ok else 1

logged = []
vt.secretary_log = logged.append          # never write to the live log
alive = lambda sid: sid != "DEAD"
def fresh_dir():
    vt.ROTATION_DIR = tempfile.mkdtemp(); return vt.ROTATION_DIR
def put(name, text, age=0):
    path = os.path.join(vt.ROTATION_DIR, name)
    with open(path, "w") as f: f.write(text)
    if age: os.utime(path, (time.time() - age, time.time() - age))
def has(name): return os.path.exists(os.path.join(vt.ROTATION_DIR, name))

vt.ROTATION_WAIT_SECONDS = 1.0
fresh_dir()
t0 = time.time()
check("no rotation: original target, at once", vt.rotation_redirect("OLD", alive) == "OLD" and time.time() - t0 < 0.2)
check("no target: untouched", vt.rotation_redirect(None, alive) is None)
vt.ROTATION_DIR = "/nonexistent/dir"
check("missing directory: original target", vt.rotation_redirect("OLD", alive) == "OLD")

fresh_dir(); put("ready", "OLD NEW")
check("fresh secretary ready: redirected", vt.rotation_redirect("OLD", alive) == "NEW")
check("the hand-over is marked delivered", has("delivered") and not has("ready"))

fresh_dir(); put("ready", "OLD DEAD")
check("fresh window not alive: original target", vt.rotation_redirect("OLD", alive) == "OLD")
fresh_dir(); put("ready", "SOMEONE_ELSE NEW")
check("a rotation of another target is ignored", vt.rotation_redirect("OLD", alive) == "OLD")

fresh_dir(); put("pending", "OLD")
t0 = time.time()
check("not ready in time: original target after the wait", vt.rotation_redirect("OLD", alive) == "OLD" and 0.9 < time.time() - t0 < 2.5)
check("the rotation was aborted for the rotator to see", has("aborted") and not has("pending"))

fresh_dir(); put("pending", "OLD")
def rotator():
    time.sleep(0.4)
    put("ready.tmp", "OLD NEW")
    os.rename(os.path.join(vt.ROTATION_DIR, "pending"), os.path.join(vt.ROTATION_DIR, "publishing"))
    os.rename(os.path.join(vt.ROTATION_DIR, "ready.tmp"), os.path.join(vt.ROTATION_DIR, "ready"))
threading.Thread(target=rotator).start()
check("ready during the wait: redirected", vt.rotation_redirect("OLD", alive) == "NEW")

fresh_dir(); put("publishing", "OLD")     # rotator is between its two renames
def finish():
    time.sleep(0.3); put("ready", "OLD NEW")
threading.Thread(target=finish).start()
check("caught mid-publish: waits and is redirected", vt.rotation_redirect("OLD", alive) == "NEW")

fresh_dir(); put("publishing", "OLD", age=60); put("pending", "OLD", age=600)
t0 = time.time()
check("leftovers of a dead rotator cost no wait", vt.rotation_redirect("OLD", alive) == "OLD" and time.time() - t0 < 0.2)

fresh_dir(); put("pending", "OLD")
vt.get_iterm_session_tty = lambda sid: (_ for _ in ()).throw(RuntimeError("boom"))
put("ready", "OLD NEW")
check("an error inside never loses the dictation", vt.rotation_redirect("OLD") == "OLD")

print()
print("all passed" if fails == 0 else f"{fails} failed")
sys.exit(1 if fails else 0)
