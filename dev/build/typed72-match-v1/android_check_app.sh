#!/usr/bin/env bash
# Compile only the typed app library with the Android NDK toolchain, keep going after
# errors, and print every compiler error (fast check before a full native build).
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
B=$HOME/pvz-native-android/build-arm64-v8a
cmake --build "$B" ${1:+--target $1} -- -k 0 -j1 > /tmp/pvz-app-check.log 2>&1
rc=$?
grep -E "error:|FAILED:" /tmp/pvz-app-check.log | head -60
echo "rc=$rc"
