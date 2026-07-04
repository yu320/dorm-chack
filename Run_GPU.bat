@echo off
chcp 65001 >nul
title Auto Renamer (GPU Mode)
echo ==========================================
echo    Auto Renamer - Initialization (GPU)
echo ==========================================
echo.
if not exist ".bin\uv.exe" (
    echo [System] Downloading required tools (uv)...
    mkdir .bin >nul 2>&1
    powershell -Command "$ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile 'uv.zip'"
    powershell -Command "Expand-Archive -Path 'uv.zip' -DestinationPath '.' -Force"
    move "uv-x86_64-pc-windows-msvc\uv.exe" ".bin\" >nul
    rmdir /S /Q "uv-x86_64-pc-windows-msvc" >nul
    del "uv.zip" >nul
    echo [System] Download complete!
    echo.
)
if not exist ".venv" (
    .bin\uv.exe venv
)
echo [System] Installing packages (with CUDA support)...
.bin\uv.exe pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
.bin\uv.exe pip install easyocr pypdfium2 customtkinter windnd
echo [System] Starting application...
start "" ".venv\Scripts\pythonw.exe" main.py --gui
exit
