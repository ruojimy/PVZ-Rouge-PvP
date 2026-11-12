#!/usr/bin/env bash
# List adb devices (no proxy); optional $1 = host:port to connect first.
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
ADB=$(command -v adb || echo "$HOME/pvz-android/sdk/platform-tools/adb")
echo "adb=$ADB"
if [[ -n "${1:-}" ]]; then timeout 20 "$ADB" connect "$1"; fi
timeout 20 "$ADB" devices -l
