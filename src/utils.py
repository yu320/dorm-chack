import re
import shutil
from pathlib import Path

def clean_filename(text: str) -> str:
    """清理 OCR 辨識出的文字，使其符合作業系統的檔名規範。"""
    # 移除 Windows/Linux 不允許的字元 \ / : * ? " < > | 換行符與定位符
    cleaned = re.sub(r'[\/*?:"<>|\\\t\r\n]', "", text)

    # 將連續的空格替換為單一空格，並去除首尾空白
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 限制檔名長度，避免 Windows 的路徑長度限制（預設 255 字元，此處限制 100 字元）
    if len(cleaned) > 100:
        cleaned = cleaned[:100]

    return cleaned

def get_unique_path(target_dir: Path, base_name: str, ext: str) -> Path:
    """處理檔名衝突：若目的資料夾已有同名檔案，自動加上數字後綴。"""
    dest_path = target_dir / f"{base_name}{ext}"
    counter = 1
    while dest_path.exists():
        dest_path = target_dir / f"{base_name}_{counter}{ext}"
        counter += 1
    return dest_path

def move_or_copy_file(src_path: Path, dest_path: Path, move_files: bool):
    """移動或複製檔案到目的路徑。"""
    if move_files:
        shutil.move(str(src_path), str(dest_path))
    else:
        shutil.copy2(str(src_path), str(dest_path))
