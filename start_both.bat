@echo off
title Judo Dashboard — View + Edit
cd /d "%~dp0"
echo Starting VIEW on :5000 and EDIT on :5001 ...
start "Judo VIEW :5000" cmd /k "cd /d ""%~dp0"" && py app.py --mode view --port 5000"
timeout /t 2 /nobreak >nul
start "Judo EDIT :5001" cmd /k "cd /d ""%~dp0"" && py app.py --mode edit --port 5001"
echo.
echo VIEW (everyone):  http://localhost:5000
echo EDIT (ops desk):  http://localhost:5001
echo.
pause
