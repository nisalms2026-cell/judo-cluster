@echo off
title Judo Cluster — Push ops updates to GitHub
cd /d "%~dp0"

echo ============================================================
echo  Push data updates to GitHub
echo  (LAN ops + GitHub Pages permanent View)
echo ============================================================
echo.

echo Building data\bundle.json for GitHub Pages ...
py export_static.py
if errorlevel 1 (
  echo export_static.py failed.
  pause
  exit /b 1
)
echo.

git status -sb
echo.

set /p MSG=Commit message (Enter = "ops: update data"): 
if "%MSG%"=="" set "MSG=ops: update data"

git add data
git status -sb
echo.

set /p GO=Commit and push data\ now? [Y/N]: 
if /i not "%GO%"=="Y" (
  echo Cancelled.
  pause
  exit /b 0
)

git commit -m "%MSG%"
if errorlevel 1 (
  echo.
  echo Nothing to commit in data\ — or commit failed.
  pause
  exit /b 1
)

git push origin main
if errorlevel 1 (
  echo.
  echo Push failed. Check GitHub login / network, then retry.
  pause
  exit /b 1
)

echo.
echo Pushed.
echo   - Public PC: run pull_updates.bat if using Cloudflare View
echo   - GitHub Pages View updates in ~1-2 minutes after first enable:
echo     https://nisalms2026-cell.github.io/judo-cluster/
echo.
pause
