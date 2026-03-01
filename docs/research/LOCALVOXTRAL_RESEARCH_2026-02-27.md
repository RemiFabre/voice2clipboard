# localvoxtral Research Notes (2026-02-27)

## Repo Cloned
- Source: `https://github.com/T0mSIlver/localvoxtral`
- Local path: `/Users/remi/voice2clipboard/external/localvoxtral`

## Key Finding
`localvoxtral` does **not** rely on `vllm-metal + mlx-vlm` for Apple-local realtime inference.

Its recommended local Apple path is:
- `localvoxtral` app (Swift client)
- `voxmlx` server (OpenAI Realtime-compatible websocket)

This is important because our current blocker is precisely in the `vllm-metal/mlx-vlm` stack for `voxtral_realtime`.

## Evidence in Code/README
- README explicitly recommends `voxmlx` for Apple Silicon local inference.
- Default realtime endpoint for main provider:
  - `ws://127.0.0.1:8000/v1/realtime`
- Provider label in settings:
  - `vLLM/voxmlx`
- `mlx-audio` is present but marked deprecated for true incremental realtime behavior.

## Why This Helps Us
Our current failure is:
- `mlx_vlm.models.voxtral_realtime` missing on current `mlx-vlm`
- plus unstable CPU fallback in `vllm` runtime path

`voxmlx` may bypass both blockers by using a different local serving stack with an OpenAI Realtime-compatible interface.

## Practical Adaptation Path for This Repo
1. Keep existing client-side websocket flow (`voxtral_realtime_client.py`).
2. Replace local server command from `vllm serve ...` to `voxmlx-serve ...`.
3. Keep endpoint as `ws://127.0.0.1:8000/v1/realtime`.
4. Re-test latency and transcript quality against current MLX Whisper baseline.

## Risks / Notes
- localvoxtral currently references a fork for websocket/server extras:
  - `T0mSIlver/voxmlx`
- This is more experimental than stable package-manager installs.
- Need to validate memory use and long-session stability on this machine.

## Immediate Next Experiment
Run local `voxmlx` server for Voxtral quant model and connect current client:

```bash
cd /Users/remi/voice2clipboard
./run_voxmlx_server.sh
```

Then in another terminal:

```bash
cd /Users/remi/voice2clipboard
./run_voxtral_realtime_client.sh
```

