@echo off
REM ============================================================================
REM  MedienDL — Windows-Build
REM
REM  WICHTIG: Dieser Build laeuft NUR auf Windows. PyInstaller kann nicht
REM  plattformuebergreifend kompilieren, ein Bau auf dem Mac liefert daher
REM  keine Windows-Datei. Diese Skripte sind auf macOS NICHT getestet.
REM
REM  Voraussetzungen auf dem Windows-Rechner:
REM    - Python 3.11+ von python.org (mit "Add to PATH")
REM    - winget install Gyan.FFmpeg     (oder ffmpeg manuell in PATH)
REM ============================================================================
setlocal
cd /d "%~dp0"

echo.
echo ===> Python pruefen
python --version || goto :nopython

echo.
echo ===> Venv anlegen
if not exist ".venv" (
    python -m venv .venv || goto :error
)

echo.
echo ===> Abhaengigkeiten installieren
call .venv\Scripts\python.exe -m pip install --quiet --upgrade pip || goto :error
call .venv\Scripts\python.exe -m pip install --quiet pyinstaller yt-dlp certifi imageio-ffmpeg fastapi "uvicorn[standard]" || goto :error

echo.
echo ===> Icons erzeugen
call .venv\Scripts\python.exe backend\make_icons.py || goto :error

echo.
echo ===> ffmpeg suchen
where ffmpeg >nul 2>&1 || echo   WARNUNG: ffmpeg nicht im PATH. Bitte "winget install Gyan.FFmpeg" ausfuehren.
where ffprobe >nul 2>&1 || echo   WARNUNG: ffprobe nicht im PATH - MP3-Export wird fehlschlagen.

echo.
echo ===> Build (dauert einige Minuten)
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
call .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean MedienDL_win.spec || goto :error

echo.
echo ===> Fertig: dist\MedienDL\MedienDL.exe
echo.
echo Zum Verteilen den ganzen Ordner "dist\MedienDL" als ZIP packen —
echo die EXE allein reicht nicht, daneben liegen Python, yt-dlp und ffmpeg.
echo.
echo Testen: dist\MedienDL\MedienDL.exe
start "" "dist\MedienDL\MedienDL.exe"
goto :eof

:nopython
echo FEHLER: Python nicht gefunden. Bitte Python von python.org installieren
echo und bei der Installation "Add Python to PATH" waehlen.
exit /b 1

:error
echo.
echo FEHLER: Build abgebrochen — siehe Meldungen oben.
exit /b 1