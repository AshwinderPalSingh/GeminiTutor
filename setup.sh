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

echo " Installing Python packages from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup complete."
