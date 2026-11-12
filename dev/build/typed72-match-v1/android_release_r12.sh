#!/usr/bin/env bash
# Serial release: native library, then APK (signature/cert checks inside).
set -euo pipefail
D=/mnt/c/Users/xiech/Downloads/PVZ_rougePvP_native/build/typed72-match-v1
bash "$D/android_native_r12.sh"
echo "NATIVE_DONE"
bash "$D/android_apk_r12.sh"
echo "APK_DONE"
