# Benchmark Diagnosis (2026-02-28)

## Ground truth input
- Manifest used: `benchmarks/groundtruth_edit_best.jsonl`
- Includes validated user-corrected references (EN + FR).

## Comparison set
- `faster-whisper`: `base`, `small`, `medium`, `large-v3`
- `voxmlx` realtime: `mistralai/Voxtral-Mini-4B-Realtime-2602`

## Key output files
- Raw JSON reports:
  - `benchmarks/realtime_backends_groundtruth_bestedit_base.json`
  - `benchmarks/realtime_backends_groundtruth_bestedit_small.json`
  - `benchmarks/realtime_backends_groundtruth_bestedit_medium_only.json`
  - `benchmarks/realtime_backends_groundtruth_bestedit_largev3.json`
  - `benchmarks/realtime_backends_groundtruth_bestedit_voxmlx_fixed.json`
- Human-readable summary:
  - `benchmarks/realtime_backends_groundtruth_bestedit_readable_clean.md`

## Main findings
- `faster-whisper-medium` quality is best on this dataset.
- `faster-whisper-small` is close in quality and much faster.
- `faster-whisper-large-v3` is slower than medium on this machine for this setup.
- `voxmlx` first-token latency is low, but transcript quality is poor in this benchmark path.

## Voxtral anomaly
`voxmlx` outputs are often truncated to the beginning of the utterance (e.g., first clause only), which inflates WER.

Examples from `realtime_backends_groundtruth_bestedit_voxmlx_fixed.json`:
- `recordings/2026-02-28/11-16-57/audio.wav` =>
  `"Ok, donc je refais un message vocal en français. J'aimerais qu'on utilise celui-ci pour le"`
- `recordings/2026-02-27/18-17-10/audio.wav` => `"Okay,"`

## Changes made in benchmark client during diagnosis
- Set explicit Voxtral model default to `mistralai/Voxtral-Mini-4B-Realtime-2602`
- Added initial `input_audio_buffer.commit(final=false)` boundary
- Added handling of final events:
  - `transcription.done`
  - `transcription.final`
  - `response.audio_transcript.done`
- Prefer final text when provided by server event

These changes improved protocol correctness but did not eliminate truncation.

## Most likely root cause candidates
1. Realtime websocket mode currently used in `voxmlx` server may not match the mode that produced high-quality live results in prior manual tests.
2. Additional server/session fields may be required for full-length transcription responses (transcription-only mode vs conversation mode semantics).
3. The high-quality live demo path likely includes extra client logic beyond current benchmark path.

## Next technical experiments
1. Capture and inspect full event stream for one benchmark sample in the current runtime (including `response.done` payloads).
2. Compare protocol with the known-good live app/repo (`external/localvoxtral`) for session creation and commit boundaries.
3. Add an alternate benchmark backend that shells out to known-good local app path if available, to compare model quality independently from websocket client implementation.

## Update (same day): client-like benchmark mode fixed the mismatch
- Added a benchmark mode that emulates the successful live client behavior:
  - realtime-paced audio replay
  - start/end commit boundaries only
  - larger chunk size (`128 ms`) matching live feel
  - longer idle/wait windows for final text settlement
- New report:
  - `benchmarks/realtime_backends_groundtruth_bestedit_readable_clientlike.md`
- Result: Voxtral quality jumped from poor (`~0.80 WER`) to good (`~0.067 WER`) on the same ground-truth set.

Conclusion: prior poor Voxtral scores were caused by benchmark ingestion/protocol mismatch, not model quality.
