@echo off
title Judo Dashboard — View + Edit
cd /d "%~dp0"
echo Stopping old dashboard processes on ports 5000 / 5001 ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000" ^| findstr LISTENING') do taskkill /F /PID %%p >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5001" ^| findstr LISTENING') do taskkill /F /PID %%p >nul 2>&1
timeout /t 2 /nobreak >nul
echo Starting VIEW on :5000 and EDIT on :5001 ...
start "Judo VIEW :5000" cmd /k "cd /d ""%~dp0"" && py app.py --mode view --port 5000"
timeout /t 2 /nobreak >nul
start "Judo EDIT :5001" cmd /k "cd /d ""%~dp0"" && py app.py --mode edit --port 5001"
echo.
echo VIEW (everyone):  http://localhost:5000
echo EDIT (ops desk):  http://localhost:5001
echo After code changes, run this batch again (or Ctrl+F5 in browser).
echo.
pause
