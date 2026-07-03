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

# 為了讓 Docker image 容量維持在合理範圍 (從 3GB 縮減到 300MB)，我們強制指定安裝 CPU 版本的 PyTorch 引擎
RUN uv pip install --system torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN uv pip install --system easyocr opencv-python-headless sv-ttk

# 建立預設掛載資料夾
RUN mkdir -p source_images processed_images

# 在 Docker 中執行時，我們呼叫沒有 --gui 參數的 main.py，啟動無介面的「背景批次處理模式」
CMD ["python", "main.py"]
