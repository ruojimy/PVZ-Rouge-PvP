#!/bin/bash
# Regenerate the translated UI modules (src/ui/gen) and rename the dual-use ones (tools/ui_dual.py).
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." || exit 1
P=/c/Users/xiech/Downloads/PVZ-Rouge-v1.4.8/next-pvp71/modkit/tools/python38-embed/python.exe
rm -rf src/ui/gen
$P tools/pvp2cpp.py src/ui/gen $(cat tools/ui_modules.txt) 2>&1 | grep -v "todo=0" | tail -6
$P tools/ui_dual.py
$P tools/gen_modindex.py
