# /// script
# dependencies = [
#   "easyocr",
#   "torch",
#   "torchvision",
# ]
# ///

import sys
from pathlib import Path

def process_images_cli():
    from src.config import load_settings
    from src.processor import BatchProcessor

    settings = load_settings()
    source_dir = Path(settings.get("source_dir", "source_images"))
    target_dir = Path(settings.get("target_dir", "processed_images"))
    move_files = settings.get("move_files", False)
    langs = settings.get("languages", ["en", "ch_tra"])
    exts = settings.get("supported_extensions", [".jpg", ".png", ".jpeg"])
    blacklist = [w.strip() for w in settings.get("blacklist", "").split("\n") if w.strip()]

    def cli_callback(msg, stats=None):
        if msg and msg != "PROCESS_DONE":
            print(msg)
        if stats:
            success, failed, total = stats
            print(f"進度: {success+failed}/{total} (成功: {success}, 失敗: {failed})")

    processor = BatchProcessor(cli_callback)
    print("啟動 CLI 批次處理模式...")
    processor.process(source_dir, target_dir, move_files, langs, exts, blacklist)

if __name__ == "__main__":
    # 若執行 `uv run main.py --gui` 或透過 bat 點擊，則啟動 GUI
    if "--gui" in sys.argv:
        from src import gui
        gui.launch_gui()
    else:
        process_images_cli()
