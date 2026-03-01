# Voxtral + Streaming Research Plan (macOS Apple Silicon)

Date: 2026-02-27

## 1) Research Summary

### Confirmed from source docs
- `mistralai/Voxtral-Mini-4B-Realtime-2602` is designed for realtime ASR with configurable delay and streaming architecture.
- The model card documents:
  - configurable delay (80ms multiples, commonly 480ms),
  - websocket/realtime usage with `/v1/realtime`,
  - strong recommendation to use vLLM for production-grade streaming.
- The same card also documents Transformers usage (`transformers >= 5.2.0`) with `VoxtralRealtimeForConditionalGeneration`.

### Apple Silicon implications
- vLLM official docs state macOS Apple Silicon support is still experimental on CPU.
- For Apple GPU acceleration, vLLM docs point to `vllm-metal` as the plugin backend using MLX.
- `vllm-metal` README states:
  - it is community-maintained,
  - it integrates with vLLM API server/OpenAI-compatible flows,
  - it targets Apple Silicon and MLX acceleration.

### Whisper ecosystem status (realtime)
- `mlx-whisper` is excellent for local Whisper speed on Apple Silicon, but its public API is basic transcribe-oriented; streaming policy must be layered externally.
- Whisper realtime wrappers exist:
  - `whisper_streaming` (explicitly marked as being replaced),
  - `SimulStreaming` (newer successor, claims better quality/speed for simultaneous use cases).
- `whisper.cpp` remains a strong low-latency local option and has realtime input examples.

## 2) Strategic Decision

For your setup, we should run two tracks in parallel:

- Track A (primary): Keep and evolve MLX-Whisper daemon path now, because it is already proven fast and reliable on your machine.
- Track B (exploratory): Prototype Voxtral Realtime path on Apple Silicon through vLLM + vllm-metal (or Transformers fallback if needed), then compare against Track A.

Reasoning:
- Track A minimizes risk and keeps your workflow moving.
- Track B captures upside from native realtime architecture if deployment friction is manageable.

## 3) Full Build Plan

### Phase 0: Freeze Stable Baseline (done)
- Keep current hotkeys working:
  - `cmd+shift+v`: headless copy-only
  - `cmd+shift+b`: headless autopaste
- Keep a rollback snapshot of launcher scripts and key Python flow.

### Phase 1: Always-On Whisper Daemon (implement first)
- Build local daemon process with MLX backend loaded once.
- Add client commands:
  - `start_capture` (mark selection start)
  - `stop_capture` (mark selection end and copy committed text to clipboard)
  - `status`, `reset`
- Write incremental transcript stream to disk (JSONL), e.g.:
  - `runtime/live_transcript.jsonl`
  - `runtime/live_committed.txt`
- Commit policy:
  - do not publish word-by-word raw tokens,
  - publish segment/sentence-stable updates only.
- Keep this daemon on a dedicated hotkey profile, without replacing current stable flow.

Deliverables:
- `daemon_server.py`, `daemon_client.py`, `run_daemon.sh`, `stop_daemon.sh`
- small README with protocol and hotkey mappings.

### Phase 2: Streaming Quality Layer (still on Whisper backend)
- Add smarter stability heuristics:
  - LocalAgreement-style prefix confirmation over consecutive updates,
  - optional VAD gating,
  - configurable latency/quality knob (`fast`, `balanced`, `accurate`).
- Add a minimal overlay/log view (optional initial terminal tail mode).

Success criteria:
- perceived latency below current one-shot flow,
- low correction churn (few rewritten words/segments),
- robust for 1h continuous run.

### Phase 3: Voxtral Realtime Spike
- Environment spike:
  - Option A: vLLM + vllm-metal + `/v1/realtime` websocket.
  - Option B: Transformers `VoxtralRealtimeForConditionalGeneration` as fallback.
- Build isolated PoC script:
  - `poc_voxtral_realtime_ws.py`
  - mic chunk in -> partial/final transcript out.
- Integrate only if metrics beat or match Track A with acceptable complexity.

Go/No-Go criteria:
- setup complexity acceptable,
- runtime stability >= Track A,
- latency/accuracy materially better or at least equivalent with new capabilities.

### Phase 4: Unified Runtime Profiles
- Maintain multiple modes in parallel:
  - `safe_copy` (current one-shot),
  - `daemon_select` (always-on selection model),
  - `realtime_overlay` (if adopted),
  - `autopaste` (opt-in).
- Each mode gets independent script + hotkey, no destructive switching.

## 4) Benchmark & Evaluation Protocol

Measure for each mode:
- TTFT (time to first readable text),
- final transcript delay,
- correction churn (how often text is revised),
- WER proxy on repeated standard test clips,
- memory footprint over 1h,
- subjective usability score (1-5).

Test corpus:
- short commands (<5s),
- medium dictation (20-60s),
- noisy environment clip,
- multilingual sample (EN/FR at minimum).

## 5) Risk Register

- vLLM/vllm-metal compatibility drift on macOS.
- Streaming instability (word churn) harming usability.
- Hotkey manager fragility (`skhd`) if config parsing breaks.
- Long-running memory growth in streaming mode.

Mitigation:
- keep stable fallback hotkey path untouched,
- run every new mode behind separate launcher/hotkey,
- log-based monitoring and kill-switch scripts.

## 6) Immediate Next Actions

1. Implement Phase 1 (Always-On Whisper Daemon) now.
2. Add transcript JSONL file output and selection-based clipboard command.
3. Run 1-hour trial.
4. Only then start Phase 3 Voxtral spike.

## Sources
- Voxtral model card: https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602
- vLLM streaming/realtime blog: https://blog.vllm.ai/2026/01/31/streaming-realtime.html
- vLLM CPU/macOS docs: https://docs.vllm.ai/en/latest/getting_started/installation/cpu/
- vllm-metal repo: https://github.com/vllm-project/vllm-metal
- mlx-whisper package docs: https://pypi.org/project/mlx-whisper/
- whisper_streaming repo: https://github.com/ufal/whisper_streaming
- SimulStreaming repo: https://github.com/ufal/SimulStreaming
- whisper.cpp repo/docs: https://github.com/ggml-org/whisper.cpp
