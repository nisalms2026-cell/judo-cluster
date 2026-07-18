@echo off
title Judo Cluster — Auto-pull from GitHub (every 2 min)
cd /d "%~dp0"

echo ============================================================
echo  Auto-pull every 120 seconds. Leave this window OPEN.
echo  Ctrl+C to stop.
echo ============================================================
echo.

:LOOP
echo [%date% %time%] git pull --ff-only origin main
git pull --ff-only origin main
echo.
timeout /t 120 /nobreak >nul
goto LOOP
