@echo off
cd /d "%~dp0"

REM 
for %%f in (*.py) do (
    echo Spúšťam: %%f
    start py "%%f"
)

pause