import hashlib
import json
import threading
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.ocr import OCREngine
from src.utils import clean_filename, get_unique_path, move_or_copy_file

class BatchProcessor:
    """負責處理批次 OCR 改名的業務邏輯，達成與 GUI 的解耦 (Low Coupling)"""
    def __init__(self, callback):
        self.callback = callback
        self.ocr_engine = None
        self.is_cancelled = False
        
    def cancel(self):
        self.is_cancelled = True

    def process(self, source_dir: Path, target_dir: Path, move_files: bool, 
                langs: list, allowed_exts: list, blacklist: list):
        self.is_cancelled = False
        
        try:
            if not source_dir.exists():
                self.callback(f"[錯誤] 來源資料夾不存在: {source_dir}", None)
                return
            
            image_paths = [p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed_exts]
            total_images = len(image_paths)
            
            if total_images == 0:
                self.callback(f"[提示] 找不到指定的檔案格式 ({', '.join(allowed_exts)})", None)
                return

            self.callback("正在初始化 AI OCR 引擎 (首次啟動可能需要幾秒鐘)...", None)
            if not self.ocr_engine or getattr(self.ocr_engine, 'current_langs', []) != langs:
                self.ocr_engine = OCREngine(languages=langs)
                self.ocr_engine.current_langs = langs
                
            self.callback(f"成功載入！共找到 {total_images} 個檔案，開始處理...", (0, 0, total_images))
            
            max_workers = 1 if getattr(self.ocr_engine, 'use_gpu', False) else 4
            self.callback(f"已啟用效能最佳化：執行緒數量為 {max_workers}", None)
            
            target_dir.mkdir(parents=True, exist_ok=True)
            rec_dir = target_dir / "已辨識"
            unrec_dir = target_dir / "未辨識"
            rec_dir.mkdir(exist_ok=True)
            unrec_dir.mkdir(exist_ok=True)
            
            run_time = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            log_file_path = target_dir / f"{run_time}-辨識紀錄.txt"
            
            hash_file = target_dir / ".hash_history.json"
            processed_hashes = set()
            if hash_file.exists():
                try:
                    with open(hash_file, "r", encoding="utf-8") as f:
                        processed_hashes = set(json.load(f))
                except Exception:
                    self.callback("⚠️ [系統] 發現歷史快取損毀，已自動為您重置", None)
                    processed_hashes = set()
                    
            log_lock = threading.Lock()
            hash_lock = threading.Lock()
            stats_lock = threading.Lock()
            
            current_success = 0
            current_failed = 0

            def process_image(img_path):
                nonlocal current_success, current_failed
                if self.is_cancelled:
                    return None
                    
                h_md5 = hashlib.md5()
                with open(img_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""): h_md5.update(chunk)
                file_md5 = h_md5.hexdigest()
                
                with hash_lock:
                    if file_md5 in processed_hashes:
                        with stats_lock:
                            current_success += 1
                        return f"[跳過] {img_path.name} 已處理過"
                        
                try:
                    text = self.ocr_engine.extract_text(str(img_path))
                    new_stem = clean_filename(text, blacklist=blacklist)
                    
                    is_failed = False
                    if not new_stem:
                        new_stem = f"未辨識_{img_path.stem}"
                        out_dir = unrec_dir
                        status_msg = "未辨識到有效文字或觸發過濾條件"
                        is_failed = True
                    else:
                        out_dir = rec_dir
                        status_msg = f"成功辨識「{new_stem}」"
                        
                        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        with log_lock:
                            with open(log_file_path, "a", encoding="utf-8") as f:
                                f.write(f"[{now_str}] 原檔名: {img_path.name}\n辨識文字: {text}\n過濾後檔名: {new_stem}\n{'-'*40}\n")
                                
                    ext = img_path.suffix.lower()
                    with log_lock:
                        dest_path = get_unique_path(out_dir, new_stem, ext)
                        move_or_copy_file(img_path, dest_path, move_files)
                        
                    with hash_lock:
                        processed_hashes.add(file_md5)
                        
                    with stats_lock:
                        if is_failed:
                            current_failed += 1
                        else:
                            current_success += 1
                            
                    return f"[{'成功' if not is_failed else '失敗'}] {img_path.name} -> {status_msg}"
                except Exception as e:
                    with stats_lock:
                        current_failed += 1
                    return f"[錯誤] {img_path.name} -> {e}"

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(process_image, p) for p in image_paths]
                for future in as_completed(futures):
                    if self.is_cancelled:
                        break
                    res = future.result()
                    if res:
                        self.callback(res, (current_success, current_failed, total_images))

            with open(hash_file, "w", encoding="utf-8") as f:
                json.dump(list(processed_hashes), f)
                
            if self.is_cancelled:
                self.callback("====== 🚫 處理已終止 ======", None)
            else:
                self.callback("====== 🎉 所有檔案處理完畢！ ======", None)
            
        except Exception as e:
            self.callback(f"[嚴重錯誤] {e}", None)
        finally:
            self.callback("PROCESS_DONE", None)
