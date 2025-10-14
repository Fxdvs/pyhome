@echo off
cd /d "%~dp0"

py server/app.py
py client/led/app.py

pause