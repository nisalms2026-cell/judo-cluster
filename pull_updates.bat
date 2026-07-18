@echo off
title Judo Cluster — Pull updates from GitHub
cd /d "%~dp0"

echo ============================================================
echo  Pull latest from GitHub (ops push → this View PC)
echo ============================================================
echo.

git pull --ff-only origin main
if errorlevel 1 (
  echo.
  echo Pull failed. Common fixes:
  echo   - Commit or stash local changes on this PC first
  echo   - Or run:  git status
  echo.
  pause
  exit /b 1
)

echo.
echo Done. VIEW already reloads data every ~10s — no restart needed.
echo Keep VIEW + Cloudflare tunnel running.
echo.
pause
