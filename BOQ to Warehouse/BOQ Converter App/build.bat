@echo off
title Building BOQ to Warehouse Form Converter (.exe)
echo ============================================
echo   BOQ to Warehouse Form Converter - Builder
echo   TodayStyle 2100
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Install dependencies
echo [1/3] Installing dependencies...
pip install openpyxl>=3.1.0 pyinstaller>=6.0 --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

:: Build the exe
echo [2/3] Building executable... (this may take 1-2 minutes)
cd /d "%~dp0"
pyinstaller --noconfirm --onefile --windowed --noupx ^
    --name "BOQ Converter (v1.2.0)" ^
    --icon "logos\app_icon.ico" ^
    --version-file "version_info.txt" ^
    --add-data "boq_parser.py;." ^
    --add-data "boq_config.py;." ^
    --add-data "warehouse_generator.py;." ^
    --add-data "cell_selector.py;." ^
    --add-data "i18n.py;." ^
    --add-data "version.py;." ^
    --add-data "theme.py;." ^
    --add-data "logos;logos" ^
    --add-data "fonts;fonts" ^
    --add-data "user_guide.html;." ^
    --add-data "pictures;pictures" ^
    --hidden-import "openpyxl" ^
    --hidden-import "tkinter" ^
    app.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Check the output above for details.
    pause
    exit /b 1
)

:: Copy to output
echo [3/3] Done!
echo.
echo ============================================
echo   SUCCESS! Your .exe is ready at:
echo   %~dp0dist\BOQ Converter (v1.2.0).exe
echo ============================================
echo.
echo You can move "BOQ Converter.exe" anywhere you like.
echo Double-click it to run - no Python needed on the target PC.
echo.

:: Open the dist folder
explorer "%~dp0dist"

pause
