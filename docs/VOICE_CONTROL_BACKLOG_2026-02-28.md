# Voice Control Backlog (Full Question Inventory)

Captured from your long voice note and follow-ups.  
Goal: make every question explicit, trackable, and explored.

Legend:
- `Status: done` = already implemented or measured
- `Status: partial` = started, needs deeper exploration
- `Status: todo` = not explored yet

## 1) Core workflow UX

- [x] One-hand flow: press once to start, press again to stop, then copy to clipboard.
  - Status: done (always-on marker start/stop flow exists).
  - Files: `always_on_mark_start.sh`, `always_on_mark_stop.sh`, `tools/always_on_capture.py`.
- [x] Distinct start/stop sounds.
  - Status: done (Ping on start, Pop on stop).
- [ ] Beep/sound feels slow; investigate and optimize sound latency.
  - Status: partial.
  - Next: measure command latency (`afplay`, notification, and script runtime breakdown) and select fastest cue chain.
- [ ] Final hotkey ergonomics for one-hand/baby-in-arms usage.
  - Status: todo.
  - Next: define 2-3 candidate key combos (French keyboard aware), run live test, keep winner.

## 2) Transcript format, timestamps, and clipboard behavior

- [x] Keep a raw timeline with timestamps for later search/retrieval.
  - Status: done.
  - File: `runtime/always_on/timeline.txt`.
- [ ] Ensure clipboard output is always clean text (no timestamp markers).
  - Status: partial.
  - Next: verify all stop/copy paths and add tests.
- [ ] Choose final storage design:
  - option A: one timestamped canonical file + derived clipboard/plain views
  - option B: dual-file pointer/index design
  - Status: todo.
  - Next: compare reliability and failure modes; pick one.
- [ ] Human-readable date/time markers for easy `Ctrl/Cmd+F` navigation.
  - Status: partial.
  - Next: finalize line schema (ISO timestamp + sentence + optional session headers).
- [ ] Very large-file robustness (append-only safety, corruption recovery, log rotation).
  - Status: todo.
  - Next: define retention + rotation policy and recovery script.

## 3) Realtime behavior and quality mode

- [ ] Sentence-level vs word-level streaming tradeoff (accuracy vs latency).
  - Status: todo.
  - Next: run controlled benchmark with different commit/silence settings and compare WER + latency.
- [ ] Live/semi-live text mode (sentence chunks) while keeping non-live clipboard mode.
  - Status: partial (live file exists).
  - Next: add selectable modes and tune defaults.

## 4) Local LLM integration

- [ ] What local LLM can run well on this laptop for transcript analysis/action routing?
  - Status: todo.
  - Next: hardware-aware shortlist + quick eval matrix (latency, memory, quality).
- [ ] Background watcher reading transcript and acting only on unseen text.
  - Status: todo.
  - Next: implement cursor/checkpoint file and dry-run action recommender.
- [ ] Voice-first computer control architecture (LLM + actions) with safety gates.
  - Status: todo.
  - Next: propose action policy (confirm/auto), tool permissions, and audit log format.

## 5) Hardware and remote microphone ideas

- [ ] Wearable mic options (clip-on, ring-button concepts, headset alternatives).
  - Status: todo.
  - Next: research concrete devices with push-to-talk and low-friction UX.
- [ ] Wireless streaming to laptop with button-first interaction.
  - Status: todo.
  - Next: define transport options (BLE trigger + local app, Wi-Fi stream, phone relay).
- [ ] Phone as microphone:
  - one-button trigger
  - no unlock/app friction
  - low latency and low battery usage
  - Status: todo.
  - Next: prototype simplest viable path and measure friction/latency.

## 6) Clamshell mode and audio input behavior

- [x] Why built-in mic failed with lid closed.
  - Status: done (documented: built-in mic disabled in clamshell; external mic required).
  - File: `docs/CLAMSHELL_MICROPHONE_NOTES_2026-02-28.md`.
- [ ] Validate stable external-mic workflow in clamshell for daily usage.
  - Status: todo.
  - Next: run repeatable checklist + fallback logic in scripts.

## 7) Energy and 24/7 operation

- [x] Compare power: baseline vs client-silent vs client-speaking.
  - Status: done.
  - File: `benchmarks/powermetrics_comparison_20260228.md`.
- [x] Estimate 24/7 cost.
  - Status: done.
  - File: `docs/ENERGY_COST_ESTIMATE_2026-02-28.md`.
- [ ] Quantify full-system wall power (not only CPU+GPU+ANE).
  - Status: todo.
  - Next: add wall-meter or battery discharge method and recompute cost.
- [ ] Laptop vs desktop Mac for 24/7 voice stack efficiency.
  - Status: todo.
  - Next: gather comparable measurements and normalize by workload.

## 8) “Is this already common?” research queue

- [ ] Existing local-first voice-control projects and architectures.
  - Status: todo.
  - Next: curated landscape doc with pros/cons and reuse opportunities.
- [ ] State-of-the-art speech stack options that could beat current setup for your use case.
  - Status: partial (some research done), needs refresh.
  - Next: update comparison table with current candidates and Apple-silicon compatibility.

## 9) Execution model (so nothing gets lost)

- [ ] Keep dual-track workflow:
  - Track A: stable daily driver
  - Track B: experimental branches
  - Status: partial.
- [ ] For every experiment, write:
  - hypothesis
  - exact commands
  - result
  - rollback
  - Status: partial.

## Suggested exploration order (next rounds)

1. Beep latency instrumentation + fix (fastest user-visible win).
2. Timestamp/clipboard contract hardening + log rotation.
3. Clamshell + external mic production checklist.
4. Local LLM shortlist + transcript-watcher dry run.
5. Wearable/phone input prototypes.
6. Full-system energy measurement and laptop-vs-desktop analysis.
