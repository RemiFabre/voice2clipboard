# Voxtral Realtime Deep Dive (Apple Silicon)

## Is this the right model?
Yes: `mistralai/Voxtral-Mini-4B-Realtime-2602` is the realtime ASR model card you linked.

## What is vLLM?
`vLLM` is an inference engine/runtime for serving LLMs efficiently.

In practice, it gives you:
- a high-performance model server,
- OpenAI-compatible APIs,
- streaming/realtime protocol support,
- batching/scheduling optimizations for low latency under load.

For this project, vLLM is useful because Voxtral Realtime's recommended production path is the vLLM server with `/v1/realtime` websocket API.

## Why not just Transformers directly?
You can. The model card includes Transformers support, but it explicitly recommends vLLM for realtime deployment quality and performance.

## Apple Silicon specifics
- vLLM on macOS is still evolving.
- For Apple GPU acceleration, the path is `vllm-metal` (plugin backend using MLX).
- This is powerful, but still more bleeding-edge than your current MLX-Whisper path.

## Defaults we use
- Model: `mistralai/Voxtral-Mini-4B-Realtime-2602`
- Temperature: `0.0`
- Delay: model-card default behavior (commonly 480ms via config)
- API: websocket `ws://127.0.0.1:8000/v1/realtime`

## Files added
- `run_voxtral_realtime_server.sh`: launch vLLM server for Voxtral
- `run_voxtral_realtime_client.sh`: run local microphone websocket client
- `voxtral_realtime_client.py`: push-to-talk-ish local client
- `stop_voxtral_realtime_server.sh`: stop server
- `requirements_voxtral.txt`: extra client deps (`websockets`)

## Quick start
1. One-shot runtime setup (installs vllm-metal and client deps):
```bash
cd /Users/remi/voice2clipboard
./setup_voxtral_runtime.sh
```

2. Start server (new terminal):
```bash
cd /Users/remi/voice2clipboard
./run_voxtral_realtime_server.sh
```

3. Start client (another terminal):
```bash
cd /Users/remi/voice2clipboard
./run_voxtral_realtime_client.sh
```

Controls:
- `Enter`: start capture
- `Enter`: stop capture (commit)
- `q` + `Enter`: quit

Live outputs:
- `runtime/voxtral_live_events.jsonl`
- `runtime/voxtral_live_text.txt`

## Notes
- This PoC is isolated and does not replace your stable Whisper hotkeys.
- If server startup fails, first verify your vLLM/vllm-metal installation.

## Sources
- Model card: https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602
- vLLM realtime architecture post: https://blog.vllm.ai/2026/01/31/streaming-realtime.html
- vLLM docs (CPU/macOS): https://docs.vllm.ai/en/latest/getting_started/installation/cpu/
- vllm-metal: https://github.com/vllm-project/vllm-metal

## Common terminal gotcha
If you type a URL directly in zsh, shell tries to execute it as a command.
Use one of these instead:
```bash
open "https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602"
# or copy/paste in your browser
```

## First-run startup delay (important)
On first run, vLLM may download and initialize model files before opening API routes.
During this period, client may fail with `ConnectionRefusedError`.

Recommended flow:
```bash
cd /Users/remi/voice2clipboard
./run_voxtral_realtime_server.sh
# in another terminal, wait until API is ready:
./wait_voxtral_server_ready.sh
# then start client:
./run_voxtral_realtime_client.sh
```

Useful log tail:
```bash
tail -f /Users/remi/voice2clipboard/logs/voxtral_vllm_server.log
```

## Known failure: "Model type voxtral_realtime not supported"
If server logs show:
- `No module named 'mlx_vlm.models.voxtral_realtime'`
- `Model type voxtral_realtime not supported`

your `mlx-vlm` in `~/.venv-vllm-metal` is too old for this model type.

Fix:
```bash
cd /Users/remi/voice2clipboard
./fix_voxtral_runtime.sh
./run_voxtral_realtime_server.sh
```

This does not re-download full model weights from scratch (cached files are reused).

If this still fails on the metal path, test CPU fallback:
```bash
cd /Users/remi/voice2clipboard
VOXTRAL_DISABLE_METAL=1 ./run_voxtral_realtime_server.sh
```
