@echo off
chcp 65001 >nul
title 圖片文字辨識與改名工具
echo ==========================================
echo    圖片文字辨識與自動重新命名工具
echo ==========================================
echo.

:: 檢查當前目錄是否有 uv.exe
if not exist "uv.exe" (
    echo [系統提示] 尚未準備好環境，正在為您自動下載核心元件...
    echo 請保持網路連線，稍候片刻...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile 'uv.zip'"
    powershell -Command "Expand-Archive -Path 'uv.zip' -DestinationPath '.' -Force"
    move "uv-x86_64-pc-windows-msvc\uv.exe" . >nul
    rmdir /S /Q "uv-x86_64-pc-windows-msvc" >nul
    del "uv.zip" >nul
    echo [系統提示] 核心元件下載完成！
    echo.
)

echo [系統提示] 開始執行辨識腳本...
echo (註: 若是首次執行，系統將自動下載 Python 與 AI 模型檔，這可能需要幾分鐘的時間)
echo.

:: 使用當前目錄的 uv.exe 執行 Python 腳本
:: uv 會自動偵測並下載 Python 免安裝版，完全不需要使用者手動安裝 Python
uv.exe run main.py

echo.
echo ==========================================
echo 處理完畢！請按任意鍵關閉視窗...
pause >nul
