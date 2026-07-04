@echo off
chcp 65001 >nul
title 圖片文字辨識與自動改名工具 (CPU版)
echo ==========================================
echo    圖片文字辨識與自動改名工具 - 環境初始化
echo ==========================================
echo.
if not exist ".bin\uv.exe" (
    echo [系統] 尚未準備好環境，正在自動下載必備核心...
    mkdir .bin >nul 2>&1
    curl.exe -L -o uv_installer.zip https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip
    tar.exe -xf uv_installer.zip -C .bin
    del "uv_installer.zip" >nul 2>&1
    echo [系統] 下載完畢！
    echo.
)
if not exist ".venv" (
    .bin\uv.exe venv
)
echo [系統] 正在安裝 AI 辨識套件與圖形介面...
.bin\uv.exe pip install torch torchvision easyocr pypdfium2 customtkinter windnd
echo [系統] 啟動中...
start "" ".venv\Scripts\pythonw.exe" main.py --gui
exit
