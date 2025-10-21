@echo off
title Build GolfQuotaApp EXE
setlocal

echo.
echo =====================================
echo   Building GolfQuotaApp executable...
echo =====================================
echo.

REM --- Move to the project folder (this .bat's location)
cd /d "%~dp0"

REM --- Kill any running instance (CMD-safe)
taskkill /f /im GolfQuotaApp.exe >nul 2>nul

REM --- Clean previous build artifacts
echo Cleaning old build files...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q GolfQuotaApp.spec 2>nul

REM --- Build EXE (include streamlit metadata, package data, and app file)
echo.
echo Building new EXE...
"%~dp0\.venv\Scripts\python.exe" -m PyInstaller ^
  --onefile ^
  --name GolfQuotaApp ^
  --copy-metadata streamlit ^
  --collect-all streamlit ^
  --add-data "app_single.py;." ^
  --exclude-module streamlit.external.langchain ^
  run_app.py

IF ERRORLEVEL 1 (
  echo.
  echo Build failed. Check the output above for errors.
  pause
  exit /b 1
)

REM --- Copy data file next to the EXE (if you keep one in the project root)
if exist "%~dp0golf_data.json" (
  copy /y "%~dp0golf_data.json" "%~dp0dist\golf_data.json" >nul
)

echo.
echo =====================================
echo   Build complete!
echo   EXE: %~dp0dist\GolfQuotaApp.exe
echo =====================================
echo.

REM --- Launch the new EXE (will auto-open browser to http://localhost:8502)
start "" "%~dp0dist\GolfQuotaApp.exe"

echo (Close this window or press any key to exit.)
pause>nul
endlocal
