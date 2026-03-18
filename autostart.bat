@echo off
echo === Rally Kamera Stopper - Autostart Setup ===
echo.

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SCRIPT=%~dp0start.bat"

if exist "%STARTUP%\Rally Stopper.lnk" (
    echo Autostart ist bereits eingerichtet.
    echo Entferne Autostart...
    del "%STARTUP%\Rally Stopper.lnk"
    echo Autostart entfernt.
) else (
    echo Erstelle Autostart-Verknuepfung...
    powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP%\Rally Stopper.lnk'); $s.TargetPath = '%SCRIPT%'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Description = 'Rally Kamera Stopper'; $s.Save()"
    if exist "%STARTUP%\Rally Stopper.lnk" (
        echo Autostart eingerichtet!
        echo Die App startet ab jetzt automatisch bei der Windows-Anmeldung.
    ) else (
        echo FEHLER: Konnte Verknuepfung nicht erstellen.
    )
)

echo.
pause
