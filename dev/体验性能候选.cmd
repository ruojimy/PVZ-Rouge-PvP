@echo off
setlocal
cd /d "%~dp0"
python -X utf8 tools/pvp744_scheduler_lab.py --exe "test_results/pvp744/metadata-20261116/candidate/PvP744MetadataCandidate.exe" --out auto --scenes grabber --arms metadata --interactive --seconds 180
pause
