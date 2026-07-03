FROM python:3.11-slim

# 安裝 OpenCV 與 EasyOCR 系統相依套件 (Debian 12 Bookworm 適用)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 安裝超快速的 Python 套件管理工具 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 複製專案原始碼
COPY . /app/

# 為了讓 Docker image 容量維持在合理範圍，我們預設安裝 CPU 版本的引擎
# 透過 uv 安裝到系統環境 (Docker 內部不需 venv)
RUN uv pip install --system torch torchvision easyocr

# 建立預設掛載資料夾
RUN mkdir -p source_images processed_images

# 在 Docker 中執行時，我們呼叫沒有 --gui 參數的 main.py，啟動無介面的「背景批次處理模式」
CMD ["python", "main.py"]
