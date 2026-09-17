#!/bin/bash
# Builds EarbudButtons.app into runtime/earbuds/. The Swift 6.1 toolchain cannot compile against
# the macOS 26 SDK shipped with current Command Line Tools, so fall back to the newest 15.x SDK.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="/Users/remi/voice2clipboard/runtime/earbuds"
APP="$OUT/EarbudButtons.app"
mkdir -p "$APP/Contents/MacOS"
sdk_flag=()
if ! xcrun swiftc -O -o "$APP/Contents/MacOS/EarbudButtons" "$HERE/EarbudButtons.swift" >/dev/null 2>&1; then
  sdk="$(ls -d /Library/Developer/CommandLineTools/SDKs/MacOSX15.*.sdk 2>/dev/null | sort -V | tail -n 1)"
  [[ -n "$sdk" ]] || { echo "no usable SDK found"; exit 1; }
  sdk_flag=(-sdk "$sdk")
  xcrun swiftc "${sdk_flag[@]}" -O -o "$APP/Contents/MacOS/EarbudButtons" "$HERE/EarbudButtons.swift"
fi
cp "$HERE/Info.plist" "$APP/Contents/Info.plist"
codesign --force --sign - "$APP" >/dev/null 2>&1
echo "built $APP"
