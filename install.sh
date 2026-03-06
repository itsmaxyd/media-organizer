#!/bin/bash
# Media Organizer - Installation Script
# This script installs system dependencies and Python packages

set -e

echo "========================================"
echo "Media Organizer - Installation"
echo "========================================"

# Detect package manager
if command -v pacman &> /dev/null; then
    echo "Detected: Arch Linux (pacman)"
    PACKAGE_MANAGER="pacman"
elif command -v apt &> /dev/null; then
    echo "Detected: Debian/Ubuntu (apt)"
    PACKAGE_MANAGER="apt"
elif command -v dnf &> /dev/null; then
    echo "Detected: Fedora (dnf)"
    PACKAGE_MANAGER="dnf"
elif command -v brew &> /dev/null; then
    echo "Detected: macOS (brew)"
    PACKAGE_MANAGER="brew"
else
    echo "Warning: Could not detect package manager"
    PACKAGE_MANAGER="unknown"
fi

# Install system dependencies
echo ""
echo "Installing system dependencies..."

case "$PACKAGE_MANAGER" in
    pacman)
        sudo pacman -Sy --noconfirm python python-pip ffmpeg tesseract
        ;;
    apt)
        sudo apt update
        sudo apt install -y python3 python3-pip ffmpeg tesseract-ocr
        ;;
    dnf)
        sudo dnf install -y python3 python3-pip ffmpeg tesseract
        ;;
    brew)
        brew install python3 ffmpeg tesseract
        ;;
    *)
        echo "Please install manually: Python 3, pip, ffmpeg, tesseract"
        ;;
esac

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Check for CUDA
echo ""
echo "Checking CUDA availability..."
python3 -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('CUDA device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"

echo ""
echo "========================================"
echo "Installation complete!"
echo "========================================"
echo ""
echo "To run the GUI:"
echo "  python main.py"
echo ""
echo "To run in CLI mode:"
echo "  python main.py --cli --source /path/to/media --output /path/out"
