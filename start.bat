@echo off
echo Starte Rally Kamera Stopper...
pythonw "%~dp0rally_stopper.py"
if errorlevel 1 (
    echo.
    echo FEHLER: Programm konnte nicht gestartet werden.
    echo Hast du install.bat schon ausgefuehrt?
    echo.
    pause
)
