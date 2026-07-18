@echo off
title Judo Cluster — Push ops updates to GitHub
cd /d "%~dp0"

echo ============================================================
echo  Push data updates to GitHub
echo  (LAN ops + GitHub Pages permanent View)
echo ============================================================
echo.

echo Building static Pages site (data\bundle.json + docs\) ...
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

git add data docs
# Prefer not to miss login/export helpers when changed locally
git add -u login.html index.html export_static.py authutil.py app.py push_updates.bat README.md 2>nul
git status -sb
echo.

set /p GO=Commit and push now? [Y/N]: 
if /i not "%GO%"=="Y" (
  echo Cancelled.
  pause
  exit /b 0
)

git commit -m "%MSG%"
if errorlevel 1 (
  echo.
  echo Nothing to commit — or commit failed.
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
echo   Permanent View (after Pages /docs is enabled):
echo   https://nisalms2026-cell.github.io/judo-cluster/
echo.
pause
