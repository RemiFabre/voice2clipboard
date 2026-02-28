# Clamshell Microphone Notes (2026-02-28)

## What is likely happening
- On modern Mac laptops with Apple silicon, the internal microphone is hardware-disconnected when the lid is closed.
- This is independent of app-level microphone permissions.

## Practical consequence
- In clamshell mode (lid closed + external display), your built-in Mac mic will typically not capture audio.
- To capture audio with lid closed, use an external input device (USB mic, audio interface, headset mic, etc.).

## How to test quickly
1. Open `System Settings -> Sound -> Input`.
2. With lid open, confirm built-in mic is available and receiving level.
3. Connect external mic and select it as input.
4. Close lid (clamshell on external display), then re-check:
   - built-in mic should be unavailable/inactive
   - external mic should still show input activity
5. Run realtime client and verify transcript updates while lid remains closed.

## If audio still fails in clamshell
- Re-select external input in Sound settings after closing lid.
- Disconnect/reconnect mic once.
- Restart the client process so it rebinds to the current default input device.

## Current recommendation for your setup
- Use clamshell mode + external mic as the production path for lower display waste.
- Keep this as a dedicated test track in the energy benchmark matrix.
