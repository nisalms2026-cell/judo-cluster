@echo off
title Judo Dashboard - Internet VIEW (free tunnel)
cd /d "%~dp0"

echo ============================================================
echo  FREE internet VIEW  (Cloudflare Tunnel)
echo  Edit stays LOCAL on :5001 - do NOT tunnel Edit.
echo ============================================================
echo.
echo Make sure VIEW is running on this PC first:
echo   start_view.bat   OR   start_both.bat
echo   (http://localhost:5000)
echo.

REM Prefer local copy in this folder (most reliable on Windows)
set "CF=%~dp0cloudflared.exe"
if exist "%CF%" goto RUN

REM Fallback: installed on PATH (new Command Prompt after winget install)
where cloudflared >nul 2>&1
if not errorlevel 1 (
  set "CF=cloudflared"
  goto RUN
)

echo cloudflared.exe not found in this folder or on PATH.
echo.
echo Fix: download cloudflared-windows-amd64.exe from
echo   https://github.com/cloudflare/cloudflared/releases
echo Rename it to cloudflared.exe and put it in:
echo   %~dp0
echo Then run this file again.
echo.
pause
exit /b 1

:RUN
echo Starting free tunnel to http://localhost:5000 ...
echo Leave this window OPEN. Copy the https://....trycloudflare.com link below.
echo Close this window to stop the public link.
echo.
"%CF%" tunnel --url http://127.0.0.1:5000
echo.
echo Tunnel stopped. (If it failed, start VIEW on port 5000 first, then retry.)
pause
