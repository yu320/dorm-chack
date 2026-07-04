@echo off
chcp 65001 >nul
title 圖片文字辨識工具 (GPU 版本)
echo ==========================================
echo    圖片文字辨識工具 - 系統初始化
echo ==========================================
echo.
if not exist ".bin\uv.exe" (
    echo [系統] 環境未就緒。正在下載核心元件...
    mkdir .bin >nul 2>&1
    curl.exe -L -o uv_installer.zip https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip
    tar.exe -xf uv_installer.zip -C .bin
    del "uv_installer.zip" >nul 2>&1
    echo [系統] 下載完成！
    echo.
)
if not exist ".venv" (
    echo [系統] 正在建立虛擬環境 - 若有需要將自動下載 Python 3.11...
    .bin\uv.exe venv --python 3.11
)
echo [系統] 正在安裝 CUDA AI 套件與圖形介面...
.bin\uv.exe pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
.bin\uv.exe pip install easyocr pypdfium2 customtkinter windnd
echo [系統] 正在啟動圖形介面...
".venv\Scripts\python.exe" main.py --gui
pause
exit
