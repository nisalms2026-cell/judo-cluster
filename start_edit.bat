@echo off
title Judo Dashboard — EDIT (port 5001)
cd /d "%~dp0"
echo Starting EDIT server on port 5001 (full access)...
py app.py --mode edit --port 5001
pause
