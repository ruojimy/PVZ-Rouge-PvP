@echo off
setlocal
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -I -X utf8 "%~dp0tools\pvz_tools.py" %*
  exit /b
)
python -I -X utf8 "%~dp0tools\pvz_tools.py" %*
exit /b %errorlevel%
