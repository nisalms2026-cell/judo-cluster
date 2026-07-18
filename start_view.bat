@echo off
title Judo Dashboard — VIEW (port 5000)
cd /d "%~dp0"
echo Starting VIEW server on port 5000 (read-only)...
py app.py --mode view --port 5000
pause
