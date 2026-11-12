#!/usr/bin/env bash
set -euo pipefail
D=/mnt/c/Users/xiech/Downloads/PVZ_rougePvP_native/build/pvp73-tools
bash "$D/android_native_r73.sh"
echo NATIVE_DONE
bash "$D/android_apk_r73.sh"
echo APK_DONE
