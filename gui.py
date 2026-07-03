import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import datetime
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import sv_ttk

from src.ocr import OCREngine
from src.utils import clean_filename, get_unique_path, move_or_copy_file
from src.config import SUPPORTED_EXTENSIONS

class OCRDesktopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("圖片文字辨識與自動改名工具 (專業版)")
        self.root.geometry("700x550")
        self.root.minsize(600, 500)
        
        # 狀態與資源
        self.ocr_engine = None
        self.is_processing = False
        self.log_queue = queue.Queue()
        
        # 介面建構
        self.create_widgets()
        
        # 啟動佇列監聽
        self.root.after(100, self.process_log_queue)

    def create_widgets(self):
        # --- 全局樣式設定 (適中字體) ---
        style = ttk.Style()
        style.configure(".", font=("微軟正黑體", 11))
        style.configure("TLabelframe.Label", font=("微軟正黑體", 11, "bold"))
        style.configure("TButton", font=("微軟正黑體", 12, "bold"))
        style.configure("TEntry", font=("微軟正黑體", 11))
        style.configure("TRadiobutton", font=("微軟正黑體", 11))
        
        # --- 設定區塊 ---
        frame_config = ttk.LabelFrame(self.root, text="資料夾設定", padding=10)
        frame_config.pack(fill=tk.X, padx=10, pady=10)
        
        # 來源資料夾
        ttk.Label(frame_config, text="來源資料夾:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.source_var = tk.StringVar(value=str(Path("source_images").resolve()))
        ttk.Entry(frame_config, textvariable=self.source_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame_config, text="瀏覽...", command=self.browse_source).grid(row=0, column=2, padx=5, pady=5)
        
        # 輸出資料夾
        ttk.Label(frame_config, text="輸出資料夾:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.target_var = tk.StringVar(value=str(Path("processed_images").resolve()))
        ttk.Entry(frame_config, textvariable=self.target_var, width=50).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame_config, text="瀏覽...", command=self.browse_target).grid(row=1, column=2, padx=5, pady=5)
        
        # 處理模式
        ttk.Label(frame_config, text="處理模式:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.mode_var = tk.BooleanVar(value=False) # False=Copy, True=Move
        frame_mode = ttk.Frame(frame_config)
        frame_mode.grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Radiobutton(frame_mode, text="複製 (保留原檔)", variable=self.mode_var, value=False).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(frame_mode, text="移動 (處理後刪除原檔)", variable=self.mode_var, value=True).pack(side=tk.LEFT, padx=5)
        
        # --- 執行區塊 ---
        frame_action = ttk.Frame(self.root, padding=10)
        frame_action.pack(fill=tk.X, padx=10)
        
        self.btn_start = ttk.Button(frame_action, text="🚀 開始執行辨識與改名", command=self.start_processing)
        self.btn_start.pack(fill=tk.X, ipady=10)
        
        # --- 紀錄區塊 ---
        frame_log = ttk.LabelFrame(self.root, text="處理紀錄", padding=10)
        frame_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_text = tk.Text(frame_log, wrap=tk.WORD, state=tk.DISABLED, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 11))
        scrollbar = ttk.Scrollbar(frame_log, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # --- 版權聲明 ---
        lbl_copyright = ttk.Label(self.root, text="Copyright © @youzih", foreground="gray")
        lbl_copyright.pack(side=tk.BOTTOM, pady=(0, 10))

    def browse_source(self):
        d = filedialog.askdirectory(initialdir=self.source_var.get())
        if d: self.source_var.set(d)

    def browse_target(self):
        d = filedialog.askdirectory(initialdir=self.target_var.get())
        if d: self.target_var.set(d)

    def log(self, message):
        self.log_queue.put(message)

    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.configure(state=tk.NORMAL)
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
                self.log_text.configure(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)

    def start_processing(self):
        if self.is_processing: return
        self.is_processing = True
        self.btn_start.configure(state=tk.DISABLED, text="處理中，請稍候...")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)
        
        source_dir = Path(self.source_var.get())
        target_dir = Path(self.target_var.get())
        move_files = self.mode_var.get()
        
        # 在背景執行緒中進行
        threading.Thread(target=self.run_batch_job, args=(source_dir, target_dir, move_files), daemon=True).start()

    def run_batch_job(self, source_dir, target_dir, move_files):
        try:
            if not source_dir.exists():
                self.log(f"[錯誤] 來源資料夾不存在: {source_dir}")
                return
            
            image_paths = [p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
            if not image_paths:
                self.log(f"[提示] 找不到支援的圖片檔 ({', '.join(SUPPORTED_EXTENSIONS)})")
                return

            self.log("正在初始化 AI OCR 引擎 (首次啟動可能需要幾秒鐘)...")
            if not self.ocr_engine:
                self.ocr_engine = OCREngine()
                
            self.log(f"成功載入！共找到 {len(image_paths)} 張圖片，開始平行處理...")
            
            # 建立目錄
            target_dir.mkdir(parents=True, exist_ok=True)
            rec_dir = target_dir / "已辨識"
            unrec_dir = target_dir / "未辨識"
            rec_dir.mkdir(exist_ok=True)
            unrec_dir.mkdir(exist_ok=True)
            
            # 紀錄檔
            run_time = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            log_file_path = target_dir / f"{run_time}-辨識紀錄.txt"
            
            # 讀取 Hash
            hash_file = target_dir / ".hash_history.json"
            processed_hashes = set()
            if hash_file.exists():
                with open(hash_file, "r", encoding="utf-8") as f:
                    processed_hashes = set(json.load(f))
                    
            log_lock = threading.Lock()
            hash_lock = threading.Lock()

            def process_image(img_path):
                # Hash check
                h_md5 = hashlib.md5()
                with open(img_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""): h_md5.update(chunk)
                file_md5 = h_md5.hexdigest()
                
                with hash_lock:
                    if file_md5 in processed_hashes:
                        return f"[跳過] {img_path.name} 已處理過"
                        
                try:
                    text = self.ocr_engine.extract_text(str(img_path))
                    new_stem = clean_filename(text)
                    
                    if not new_stem:
                        new_stem = f"未辨識_{img_path.stem}"
                        out_dir = unrec_dir
                        status_msg = "未辨識到有效文字"
                    else:
                        out_dir = rec_dir
                        status_msg = f"成功辨識「{new_stem}」"
                        
                        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        with log_lock:
                            with open(log_file_path, "a", encoding="utf-8") as f:
                                f.write(f"[{now_str}] 原檔名: {img_path.name}\n辨識文字: {text}\n{'-'*40}\n")
                                
                    ext = img_path.suffix.lower()
                    with log_lock:
                        dest_path = get_unique_path(out_dir, new_stem, ext)
                        move_or_copy_file(img_path, dest_path, move_files)
                        
                    with hash_lock:
                        processed_hashes.add(file_md5)
                        
                    return f"[成功] {img_path.name} -> {status_msg}"
                except Exception as e:
                    return f"[錯誤] {img_path.name} -> {e}"

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(process_image, p) for p in image_paths]
                for future in as_completed(futures):
                    self.log(future.result())

            with open(hash_file, "w", encoding="utf-8") as f:
                json.dump(list(processed_hashes), f)
                
            self.log("====== 所有圖片處理完畢！ ======")
            
        except Exception as e:
            self.log(f"[嚴重錯誤] {e}")
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.btn_start.configure(state=tk.NORMAL, text="🚀 開始執行辨識與改名"))

def launch_gui():
    root = tk.Tk()
    
    # 套用 Windows 11 現代化深色主題
    sv_ttk.set_theme("dark")
    
    app = OCRDesktopApp(root)
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
