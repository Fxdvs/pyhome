@echo off
cd /d "%~dp0"

start "server" py server/app.py
start "client" py client/app.py
start "led" py client/led/app.py

pause