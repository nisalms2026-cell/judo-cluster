@echo off
title Judo Cluster — Push ops updates to GitHub
cd /d "%~dp0"

echo ============================================================
echo  Push data updates to GitHub (ops PC → public View PC)
echo ============================================================
echo.
echo This stages data\ (and shows other local changes).
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
echo Pushed. On the public PC run pull_updates.bat (or the auto-pull loop).
echo.
pause
