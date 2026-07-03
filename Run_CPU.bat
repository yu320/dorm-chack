@echo off
title 圖片文字辨識與改名工具 (一般CPU版)
echo ==========================================
echo    圖片文字辨識與自動重新命名工具 (一般版)
echo ==========================================
echo.
if not exist "uv.exe" (
    echo [系統提示] 尚未準備好環境，正在自動下載核心元件...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile 'uv.zip'"
    powershell -Command "Expand-Archive -Path 'uv.zip' -DestinationPath '.' -Force"
    move "uv-x86_64-pc-windows-msvc\uv.exe" . >nul
    rmdir /S /Q "uv-x86_64-pc-windows-msvc" >nul
    del "uv.zip" >nul
    echo [系統提示] 下載完成！
    echo.
)
if not exist ".venv" (
    uv.exe venv
)
echo [系統提示] 正在確認 CPU 版本 AI 引擎...
uv.exe pip install torch torchvision easyocr
echo [系統提示] 啟動視窗介面中...
uv.exe run main.py --gui
echo.
pause >nul
