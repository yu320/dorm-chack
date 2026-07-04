@echo off
title Image Text Recognition Tool (GPU Version)
echo ==========================================
echo    Image Text Recognition Tool - Initialization
echo ==========================================
echo.
if not exist ".bin\uv.exe" (
    echo [System] Environment not ready. Downloading core components...
    mkdir .bin >nul 2>&1
    curl.exe -L -o uv_installer.zip https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip
    tar.exe -xf uv_installer.zip -C .bin
    del "uv_installer.zip" >nul 2>&1
    echo [System] Download complete!
    echo.
)
if not exist ".venv" (
    echo [System] Creating virtual environment (Auto-downloading Python 3.11 if needed)...
    .bin\uv.exe venv --python 3.11
)
echo [System] Installing CUDA AI packages and GUI...
.bin\uv.exe pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
.bin\uv.exe pip install easyocr pypdfium2 customtkinter windnd
echo [System] Starting GUI...
".venv\Scripts\python.exe" main.py --gui
pause
exit
