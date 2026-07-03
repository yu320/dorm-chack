# /// script
# dependencies = [
#   "easyocr",
#   "torch",
#   "torchvision",
# ]
# ///

from src.config import SOURCE_DIR, TARGET_DIR, MOVE_FILES, SUPPORTED_EXTENSIONS
from src.utils import clean_filename, get_unique_path, move_or_copy_file
from src.ocr import OCREngine

def process_images():
    # 自動建立主要資料夾
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    # 建立分類子資料夾
    recognized_dir = TARGET_DIR / "已辨識"
    unrecognized_dir = TARGET_DIR / "未辨識"
    recognized_dir.mkdir(parents=True, exist_ok=True)
    unrecognized_dir.mkdir(parents=True, exist_ok=True)

    # 準備紀錄檔 (依據每次執行時間產生新檔案，注意 Windows 檔名不允許使用冒號 :)
    import datetime
    run_time_str = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    log_file_path = TARGET_DIR / f"{run_time_str}-辨識紀錄.txt"

    # 檢查來源資料夾是否有檔案
    image_paths = [
        p
        for p in SOURCE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not image_paths:
        print(f"提示：來源資料夾【{SOURCE_DIR.resolve()}】中沒有找到支援的圖片檔 ({', '.join(SUPPORTED_EXTENSIONS)})。")
        print("請放入圖片後再次執行此腳本！")
        return

    # 初始化 OCR 引擎
    ocr_engine = OCREngine()
    print("開始處理圖片...\n")

    for index, img_path in enumerate(image_paths, start=1):
        print(f"[{index}/{len(image_paths)}] 正在處理: {img_path.name}")

        try:
            # 進行 OCR 辨識
            recognized_text = ocr_engine.extract_text(str(img_path))

            # 清理文字以作為合法檔名
            new_stem = clean_filename(recognized_text)

            # 依據辨識結果進行分類
            if not new_stem:
                # 未辨識
                new_stem = f"未辨識_{img_path.stem}"
                current_target_dir = unrecognized_dir
                print("  -> 狀態: 未辨識到任何文字")
            else:
                # 已辨識
                current_target_dir = recognized_dir
                print(f"  -> 辨識結果: 「{new_stem}」")

                # 寫入文字檔紀錄
                import datetime
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"[{now_str}] 原檔名: {img_path.name}\n")
                    f.write(f"辨識文字: {recognized_text}\n")
                    f.write("-" * 40 + "\n")

            # 處理檔名衝突：若該分類資料夾已有同名檔案，自動加上數字後綴
            ext = img_path.suffix.lower()
            dest_path = get_unique_path(current_target_dir, new_stem, ext)

            # 移動或複製檔案
            move_or_copy_file(img_path, dest_path, MOVE_FILES)

            action_name = "移動" if MOVE_FILES else "複製"
            print(f"  -> 已{action_name}至: {dest_path.relative_to(TARGET_DIR)}\n")

        except Exception as e:
            print(f"  -> [錯誤] 處理圖片時發生異常: {e}\n")

    print("所有圖片處理完畢！")


if __name__ == "__main__":
    process_images()
