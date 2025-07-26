#!/bin/bash

echo " Installing system dependencies..."
# For Debian/Ubuntu
if [ "$(uname)" == "Linux" ]; then
    sudo apt update
    sudo apt install -y tesseract-ocr poppler-utils ffmpeg
fi

# For macOS
if [ "$(uname)" == "Darwin" ]; then
    brew install tesseract poppler ffmpeg
fi

echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo " Installing Python packages from req.txt..."
pip install --upgrade pip
pip install -r req.txt

echo "Setup complete."
#For Windows
@echo off
setlocal enabledelayedexpansion

echo 🔧 Windows Setup Script for GeminiTutor
echo ----------------------------------------

:: Check for Python
where python >nul 2>&1
if errorlevel 1 (
    echo  Python is not installed or not in PATH.
    echo Download from https://www.python.org/downloads/windows/
    exit /b
)

:: Check for pip
where pip >nul 2>&1
if errorlevel 1 (
    echo  pip is not installed or not in PATH.
    exit /b
)

:: Optional: Warn if tesseract, ffmpeg, or poppler aren't installed
echo  Make sure the following are installed and added to PATH:
echo   - Tesseract OCR:    https://github.com/tesseract-ocr/tesseract
echo   - FFmpeg:           https://ffmpeg.org/download.html
echo   - Poppler (for Windows): http://blog.alivate.com.au/poppler-windows/
pause

:: Create virtual environment
echo  Creating virtual environment...
python -m venv venv

:: Activate environment
call venv\Scripts\activate.bat

:: Upgrade pip and install requirements
echo  Installing Python packages from req.txt...
python -m pip install --upgrade pip
pip install -r req.txt

echo ✅ Setup complete. You can now run: python main.py
pause

 
