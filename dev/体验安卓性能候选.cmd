@echo off
setlocal
cd /d "%~dp0"
python -X utf8 tools/pvp744_android_manual.py --arm metadata
pause
