@echo off
title BOQ to Warehouse Form Converter - TodayStyle 2100

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Install dependencies if needed
echo Checking dependencies...
pip install -r "%~dp0requirements.txt" --quiet 2>nul

:: Run the application
echo Starting BOQ to Warehouse Form Converter...
python "%~dp0app.py"

if errorlevel 1 (
    echo.
    echo An error occurred. Press any key to close.
    pause
)
