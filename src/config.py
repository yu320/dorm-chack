import json
from pathlib import Path

SETTINGS_FILE = Path("settings.json")

def load_settings():
    default_settings = {
        "source_dir": str(Path("source_images").resolve()),
        "target_dir": str(Path("processed_images").resolve()),
        "move_files": False,
        "languages": ["ch_tra", "en"],
        "blacklist": "",
        "supported_extensions": [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".pdf"]
    }
    
    if not SETTINGS_FILE.exists():
        save_settings(default_settings)
        return default_settings
        
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # 更新可能缺少的欄位
            for key, val in default_settings.items():
                if key not in settings:
                    settings[key] = val
            return settings
    except Exception:
        return default_settings

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"無法儲存設定檔: {e}")

# 相容舊版
SUPPORTED_EXTENSIONS = load_settings().get("supported_extensions", [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".pdf"])
