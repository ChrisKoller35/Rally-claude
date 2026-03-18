@echo off
echo ============================================
echo   Rally PTZ Kamera Controller - Installation
echo ============================================
echo.

REM Prüfe ob Python installiert ist
python --version >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Python ist nicht installiert!
    echo.
    echo Bitte lade Python herunter von: https://www.python.org/downloads/
    echo WICHTIG: Beim Installieren "Add Python to PATH" ankreuzen!
    echo.
    pause
    exit /b 1
)

echo Python gefunden:
python --version
echo.

echo Installiere benoetigte Pakete...
echo.
python -m pip install opencv-python
echo.

if errorlevel 1 (
    echo.
    echo Erster Versuch fehlgeschlagen. Versuche mit --user Flag...
    python -m pip install --user opencv-python
)

echo.
echo ============================================
echo   Installation abgeschlossen!
echo ============================================
echo.
echo Starte das Programm mit: start.bat
echo Oder mit: python rally_controller.py
echo.
pause
