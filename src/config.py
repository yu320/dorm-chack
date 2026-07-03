import json
from pathlib import Path

# 設定檔路徑
SETTINGS_FILE = Path("settings.json")

# 預設設定
default_settings = {
    "source_dir": "./source_images",
    "target_dir": "./processed_images",
    "move_files": False,
    "supported_extensions": [".jpg", ".jpeg", ".png"]
}

# 讀取或建立設定檔
if not SETTINGS_FILE.exists():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(default_settings, f, indent=4, ensure_ascii=False)
    settings = default_settings
else:
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)

# 匯出變數供其他模組使用
SOURCE_DIR = Path(settings.get("source_dir", "./source_images"))
TARGET_DIR = Path(settings.get("target_dir", "./processed_images"))
MOVE_FILES = settings.get("move_files", False)
SUPPORTED_EXTENSIONS = set(settings.get("supported_extensions", [".jpg", ".jpeg", ".png"]))
