from pathlib import Path

# ==================== 設定區 ====================
# 來源資料夾（放置原始圖片的資料夾）
SOURCE_DIR = Path("./source_images")

# 目的資料夾（放置處理並改名後圖片的資料夾）
TARGET_DIR = Path("./processed_images")

# 是否移動檔案？ True 為移動檔案，False 為複製檔案（保留原檔）
MOVE_FILES = False

# 支援的圖片格式
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
# ===============================================
