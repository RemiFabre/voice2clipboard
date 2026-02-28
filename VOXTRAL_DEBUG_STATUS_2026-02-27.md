# Voxtral Debug Status (2026-02-27)

## Scope
This file is a persistent record of what was implemented, tested, and concluded for local Voxtral realtime integration on this Mac.

## Machine and Runtime Context
- Host: Apple Silicon Mac (36 GB unified memory)
- Project: `/Users/remi/voice2clipboard`
- Dedicated runtime env: `~/.venv-vllm-metal`

## What Was Added
- Voxtral client/server scripts:
  - `run_voxtral_realtime_server.sh`
  - `run_voxtral_realtime_client.sh`
  - `stop_voxtral_realtime_server.sh`
  - `wait_voxtral_server_ready.sh`
  - `setup_voxtral_runtime.sh`
  - `fix_voxtral_runtime.sh`
  - `voxtral_realtime_client.py`
  - `requirements_voxtral.txt`
- Documentation:
  - `VOXTRAL_REALTIME_DEEP_DIVE.md`
  - `RESEARCH_VOXTRAL_PLAN.md`
  - `VOICE_CONTROL_ROADMAP.md`

## Current Script Hardening
### `run_voxtral_realtime_server.sh`
- Added runtime version logging at startup.
- Added strict preflight check for `mlx_vlm.models.voxtral_realtime`.
- Fails fast with explicit message when support is missing.
- Added optional bypass flag:
  - `VOXTRAL_ALLOW_UNSUPPORTED=1` (diagnostics only, not recommended).

### `fix_voxtral_runtime.sh`
- Updated to pin core vLLM-compatible stack during repair attempts:
  - `vllm==0.16.0`
  - `vllm-metal==0.1.0`
  - `torch==2.10.0`
  - `transformers<5`
  - `setuptools==77.0.3`
  - `mistral-common==1.9.1`
- If Voxtral support is still missing after upgrade attempts, script now restores core pins before exiting.

## Tested Failure Modes (Observed in Logs)
1. Metal path failure:
   - `ValueError: Model type voxtral_realtime not supported`
   - `No module named 'mlx_vlm.models.voxtral_realtime'`
2. CPU fallback failure:
   - `AttributeError: '_OpNamespace' '_C_utils' object has no attribute 'init_cpu_threads_env'`
3. Additional warning seen repeatedly:
   - `Failed to import from vllm._C ... Symbol not found ... libc10.dylib`

## Verified Runtime Snapshot (after repair)
- `vllm 0.16.0`
- `vllm-metal 0.1.0`
- `torch 2.10.0`
- `transformers 4.57.6`
- `mlx-vlm 0.3.12`
- `setuptools 77.0.3`

## Main Technical Blocker
`mlx-vlm` (release and GitHub main tested) still does not expose:
- `mlx_vlm.models.voxtral_realtime`

Without this adapter in the current macOS/vllm-metal stack, local serving of
`mistralai/Voxtral-Mini-4B-Realtime-2602` does not come up cleanly.

## Important Conclusion
At this timestamp, Voxtral realtime local inference is blocked by upstream runtime support alignment, not by project script wiring.

## Additional Research Update (localvoxtral)
- Cloned: `/Users/remi/voice2clipboard/external/localvoxtral`
- Key insight: their recommended Apple-local path is `voxmlx`, not `vllm-metal`.
- New local helper added in this repo:
  - `run_voxmlx_server.sh`
- Detailed notes:
  - `LOCALVOXTRAL_RESEARCH_2026-02-27.md`

## Follow-up Result: voxmlx Path Works
Validated working path:
- `./run_voxmlx_server.sh`
- `./run_voxtral_realtime_client.sh`

Observed behavior:
- websocket handshake returns `session.created`
- realtime deltas arrive as `response.audio_transcript.delta`

Client compatibility updates made:
- `voxtral_realtime_client.py` now handles `response.audio_transcript.delta`
- normal websocket closure no longer emits traceback

## Production Scaffold Added
- Always-on daemon + marker selection workflow:
  - `run_always_on_voxtral_daemon.sh`
  - `tools/always_on_voxtral_daemon.py`
  - `always_on_mark_start.sh`
  - `always_on_mark_stop.sh`
  - `always_on_status.sh`
  - `tools/always_on_capture.py`
- LaunchAgent setup + service control:
  - `install_always_on_launchagents.sh`
  - `service_always_on.sh`

## Recommended Interim Strategy
1. Keep Whisper/MLX local path as production baseline.
2. Keep Voxtral scripts as experimental branch with preflight checks.
3. Re-test Voxtral when either:
   - `mlx-vlm` adds `voxtral_realtime`, or
   - an alternative runtime path demonstrates stable Apple support.

## Quick Validation Commands
```bash
cd /Users/remi/voice2clipboard
./run_voxtral_realtime_server.sh
```
Expected current output:
- Fast exit with missing `voxtral_realtime` support message.

```bash
cd /Users/remi/voice2clipboard
./fix_voxtral_runtime.sh
```
Expected current output:
- Attempts upgrade paths, then exits with upstream support missing; core pins restored.
