# Long dictation benchmark (2026-09-17)

Recording: a 37 min (2219 s) English dictation through a Bluetooth headset mic, kept privately
under `recordings/` with its adjudicated reference in `benchmarks/private/` (not published).
Apple M3 Pro 36 GB, `mlx-whisper 0.4.3`, `mlx-audio 0.4.2`.

## Why the production transcript was garbled

The output had one sentence repeated 20x and a single word repeated 219x. Audio was clean;
the cause is Whisper decoding (fixed in commit "Stop Whisper repetition loops"):

- a fully silent 30 s window makes the model hallucinate a sentence (compression ratio 4.6-7.0);
- `no_speech_prob > 0.6` disables the compression-ratio fallback and `avg_logprob > -1.0` keeps it;
- `condition_on_previous_text=True` feeds it forward, so the following silent windows repeat it.

Fix: `condition_on_previous_text=False` in the MLX helper, with a full-file regression test. A
short slice does not reproduce the loop because the log-mel floor depends on the whole file's peak.

## Microphone (Bluetooth headset)

| Metric | Value |
|---|---|
| Format | 16 kHz mono 16-bit, no dropouts, 5 clipped samples in 37 min |
| Speech level | -26 dBFS (top 20% frames) |
| Background | -91 dBFS in pauses (headset noise suppression), no hard gating |
| Bandwidth | energy to ~6.5 kHz, 99% below 5 kHz |
| Speech density | ~31% speech (Silero VAD), 217 regions, several fully silent 30 s windows |

The mic is not the problem; silent windows are what trigger every Whisper hallucination.

## Reference

Adjudicated from five model outputs (medium, small, large-v3, large-v3-turbo, Parakeet) by
applying corrections where the others agreed. Not human-verified, and biased toward medium's
wording, so differences under ~1 WER point are noise.

## Results (WER vs reference; punctuation, case and fillers ignored)

| Setup | WER | time |
|---|---|---|
| production transcript (medium, default options) | 0.408 | ~100 s |
| medium, no conditioning (shipped fix) | 0.044 | 51 s |
| small, no conditioning | 0.066 | 22 s |
| large-v3-turbo, no conditioning | 0.049 | 49 s |
| large-v3, no conditioning | 0.047 | 89 s |
| Parakeet TDT 0.6b v3, raw file | 0.269 | 28 s |
| **VAD-trimmed audio (697 s of speech), then:** | | |
| medium | 0.025 | 38 s |
| small | 0.056 | 13 s |
| large-v3-turbo | 0.029 | 23 s |
| large-v3 | **0.019** | 55 s |
| Parakeet TDT 0.6b v3 | 0.086 | 9.5 s |
| medium + vocabulary prompt, no conditioning | 0.031 | 31 s |
| turbo + vocabulary prompt, conditioning on | 0.052 (loops again) | 36 s |

Notes:
- large-v3 and turbo on the raw file emit a stock two-word hallucination in every silent
  window; VAD trimming removes it.
- Parakeet drops whole sentences on the raw file and still loses words after trimming.
- Residual errors of the best setups are contractions and one multi-word product name that
  every model misspells; a vocabulary prompt did not fix it (with conditioning off Whisper only
  applies the prompt to the first window; with conditioning on the loops return).

## Streaming (chunks decoded while recording)

| Policy | WER | chunks | stream_end |
|---|---|---|---|
| whole file, turbo + VAD | 0.029 | 1 | 22.7 s decode |
| chunks of >= 4 s of speech | 0.034 | 45 | 1.6 s |
| chunks of >= 8 s | 0.033 | 41 | 1.4 s |
| chunks of >= 15 s (default) | 0.026 to 0.031 | 30 to 32 | 1.5 to 2.7 s |

A real 4 min dictation: 8 chunks, stop-to-text 2.9 s (was ~9 s). No loops in any run.

## Decisions

1. Default: large-v3-turbo with Silero VAD trimming and streaming (env overrides:
   `VOICE2CLIPBOARD_MLX_MODEL_SIZE`, `VOICE2CLIPBOARD_VAD_MIN_SILENCE_MS=0`,
   `VOICE2CLIPBOARD_STREAMING=0`).
2. Product-name spelling is a post-processing problem, not a prompt problem.
3. French was checked on one 100 s clip only; quality there is unverified.
