@echo off
REM server
start "Server" cmd /k "cd /d %~dp0server && start.bat"

REM client
start "Client" cmd /k "cd /d %~dp0client && start.bat"

echo All instances started.
timeout /t 1 >nul

