# /// script
# dependencies = [
#   "easyocr",
#   "torch",
#   "torchvision",
# ]
# ///

import hashlib
import json
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.config import SOURCE_DIR, TARGET_DIR, MOVE_FILES, SUPPORTED_EXTENSIONS
from src.utils import clean_filename, get_unique_path, move_or_copy_file
from src.ocr import OCREngine

HASH_FILE = TARGET_DIR / ".hash_history.json"

def load_hashes():
    if HASH_FILE.exists():
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_hashes(hashes):
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(list(hashes), f)

def get_file_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def process_single_image(img_path, ocr_engine, log_file_path, recognized_dir, unrecognized_dir, log_lock, processed_hashes_lock, processed_hashes):
    # 計算檔案 MD5 (防呆：避免重複處理)
    file_md5 = get_file_md5(img_path)
    with processed_hashes_lock:
        if file_md5 in processed_hashes:
            return f"[跳過] {img_path.name} 已處理過 (MD5重複)"

    try:
        recognized_text = ocr_engine.extract_text(str(img_path))
        new_stem = clean_filename(recognized_text)

        if not new_stem:
            new_stem = f"未辨識_{img_path.stem}"
            current_target_dir = unrecognized_dir
            status_msg = "狀態: 未辨識到任何有效文字"
        else:
            current_target_dir = recognized_dir
            status_msg = f"辨識結果: 「{new_stem}」"

            # 寫入文字檔紀錄 (加鎖確保執行緒安全)
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with log_lock:
                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"[{now_str}] 原檔名: {img_path.name}\n")
                    f.write(f"辨識文字: {recognized_text}\n")
                    f.write("-" * 40 + "\n")

        ext = img_path.suffix.lower()
        
        # 處理檔名衝突與複製移動 (加鎖避免檔名競爭)
        with log_lock:
            dest_path = get_unique_path(current_target_dir, new_stem, ext)
            move_or_copy_file(img_path, dest_path, MOVE_FILES)

        action_name = "移動" if MOVE_FILES else "複製"
        
        # 加入歷史紀錄
        with processed_hashes_lock:
            processed_hashes.add(file_md5)
            
        return f"[成功] {img_path.name} -> {status_msg} (已{action_name}至 {dest_path.name})"
        
    except Exception as e:
        return f"[錯誤] {img_path.name} 發生異常: {e}"

def process_images():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    recognized_dir = TARGET_DIR / "已辨識"
    unrecognized_dir = TARGET_DIR / "未辨識"
    recognized_dir.mkdir(parents=True, exist_ok=True)
    unrecognized_dir.mkdir(parents=True, exist_ok=True)

    run_time_str = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    log_file_path = TARGET_DIR / f"{run_time_str}-辨識紀錄.txt"

    image_paths = [p for p in SOURCE_DIR.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not image_paths:
        print(f"提示：來源資料夾【{SOURCE_DIR.resolve()}】中沒有找到支援的圖片檔 ({', '.join(SUPPORTED_EXTENSIONS)})。")
        print("請放入圖片後再次執行此腳本！")
        return

    ocr_engine = OCREngine()
    processed_hashes = load_hashes()
    
    log_lock = threading.Lock()
    processed_hashes_lock = threading.Lock()

    print(f"開始多執行緒平行處理 {len(image_paths)} 張圖片...\n")

    # 使用多執行緒平行處理 (預設 4 個執行緒)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(
                process_single_image, 
                img_path, ocr_engine, log_file_path, recognized_dir, unrecognized_dir, 
                log_lock, processed_hashes_lock, processed_hashes
            ): img_path for img_path in image_paths
        }
        
        for future in as_completed(futures):
            print(future.result())

    # 儲存雜湊歷史紀錄
    save_hashes(processed_hashes)
    print("\n所有圖片批次處理完畢！")

if __name__ == "__main__":
    import sys
    # 若執行 `uv run main.py --gui` 則啟動 GUI，否則預設跑 CLI 批次
    if "--gui" in sys.argv:
        import gui
        gui.launch_gui()
    else:
        process_images()
