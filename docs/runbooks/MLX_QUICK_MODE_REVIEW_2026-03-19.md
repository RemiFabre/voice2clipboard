# MLX Quick Mode Review (2026-03-19)

This note captures the review of the macOS MLX quick dictation workflow after a series of robustness fixes regressed normal behavior.

## What regressed
- Terminal delivery in `iTerm2` became unreliable:
  - transcript text arrived,
  - but Enter often did not submit the command,
  - and the failure rate was higher on long messages.
- `VS Code` picked up an app-specific terminal focus path that is not part of the main workflow and made editor tests noisy.
- The stop path accumulated multiple overlapping mechanisms:
  - local Escape stop,
  - stop-file polling,
  - immediate `SIGTERM`,
  - worker-side reinforcement,
  - forced recovery from audio snapshots.

The combined effect was that rare recovery logic leaked into normal operation and made the system harder to reason about.

## Key finding from history review
- The special `iTerm2` direct-send path (`write text` to a session by unique id) was introduced later as an enhancement.
- The original quick dictation flow was simpler:
  - refocus target,
  - paste,
  - press Enter.

This matters because the unstable terminal behavior appeared on the later specialized path, not on the original simple model.

## Simplification applied

### 1. iTerm2 delivery
Removed the special `write text` submit path for the normal workflow.

New behavior:
- find the original `iTerm2` session by unique id,
- select its tab/session/window,
- bring `iTerm2` to the front,
- perform a normal terminal paste (`Cmd+Shift+V`),
- wait based on transcript length,
- press Enter.

Rationale:
- this is closer to the Linux workflow that has been stable,
- it uses a real paste + Enter instead of a special AppleScript text insertion path,
- it preserves the good part of the newer design: targeting the original `iTerm2` session.

### 2. Stop path
Simplified the normal stop flow:
- second shortcut press now creates the stop file only,
- it does not immediately send `SIGTERM`.

Recorder behavior:
- quick recording loop notices the stop file and stops locally,
- Escape remains a local stop,
- worker recovery stays in place only if the recorder does not exit in time.

Rationale:
- normal stop should not mix local stop and external signal injection,
- recovery should stay a fallback, not a routine part of stopping.

### 3. VS Code-specific behavior
Removed the special `View > Terminal` path for `Code`.

Rationale:
- it was introduced to chase a side effect in a non-primary workflow,
- it made simple editor tests confusing,
- the main target workflow is terminal dictation and Codex/Cursor-style app dictation.

## Current design intent
- `Escape`: local in-process stop.
- second hotkey press: external stop request.
- forced recovery: emergency only.
- `iTerm2`: focus exact session, paste, then Enter.
- other macOS apps: activate app, paste, then Enter.

## If instability remains
The next debugging step should be observation-only:
- inspect `/tmp/voice2clipboard_quick_send_trace.jsonl`
- inspect `/tmp/voice2clipboard_quick_autopaste.log`
- avoid adding more parallel stop/send paths before proving where the failure occurs.
