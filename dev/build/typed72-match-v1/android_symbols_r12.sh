#!/usr/bin/env bash
# Confirm the release libmain.so carries this round's typed AI code paths.
L=$HOME/pvz-native-android/candidates/20261112-typed72-ai3/jniLibs/arm64-v8a/libmain.so
for s in ai_tick typed_ai_control reset_ai_controller collect_locked_until ai_control_log "typed72] battle session started"; do
  printf '%s=%s\n' "$s" "$(strings "$L" | grep -c "$s")"
done
