import re
import shutil
from pathlib import Path

def clean_filename(text: str, blacklist: list[str] = None) -> str:
    """清理 OCR 辨識出的文字，使其符合作業系統的檔名規範，並智慧過濾雜訊。"""
    # 過濾黑名單
    if blacklist:
        for word in blacklist:
            word = word.strip()
            if word:
                text = text.replace(word, "")
                
    # 移除 Windows/Linux 不允許的字元 \ / : * ? " < > | 換行符與定位符
    cleaned = re.sub(r'[\/*?:"<>|\\\t\r\n]', "", text)

    # 將連續的空格替換為單一空格，並去除首尾空白
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 智慧過濾：若完全沒有英數或中文字（純符號雜訊），視為未辨識
    if not re.search(r'[A-Za-z0-9\u4e00-\u9fff]', cleaned):
        return ""
        
    # 智慧過濾：如果長度只有 1 且非中文字（單一英數字或符號經常是雜訊），視為未辨識
    if len(cleaned) == 1 and not re.match(r'[\u4e00-\u9fff]', cleaned):
        return ""

    # 限制檔名長度，避免 Windows 的路徑長度限制（預設 255 字元，此處限制 100 字元）
    if len(cleaned) > 100:
        cleaned = cleaned[:100]

    return cleaned

def get_unique_path(target_dir: Path, base_name: str, ext: str) -> Path:
    """處理檔名衝突：若目的資料夾已有同名檔案，自動加上時間標籤。"""
    dest_path = target_dir / f"{base_name}{ext}"
    if not dest_path.exists():
        return dest_path
        
    import datetime
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_path = target_dir / f"{base_name}_{now_str}{ext}"
    
    counter = 1
    while dest_path.exists():
        dest_path = target_dir / f"{base_name}_{now_str}_{counter}{ext}"
        counter += 1
    return dest_path

def move_or_copy_file(src_path: Path, dest_path: Path, move_files: bool):
    """移動或複製檔案到目的路徑。"""
    if move_files:
        shutil.move(str(src_path), str(dest_path))
    else:
        shutil.copy2(str(src_path), str(dest_path))
