import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import queue
import datetime
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.ocr import OCREngine
from src.utils import clean_filename, get_unique_path, move_or_copy_file
from src.config import SUPPORTED_EXTENSIONS

# 設定主題與顏色
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class OCRDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("圖片文字辨識與自動改名工具")
        self.geometry("800x650")
        self.minsize(700, 600)
        
        # 狀態與資源
        self.ocr_engine = None
        self.is_processing = False
        self.log_queue = queue.Queue()
        
        # 設定字型
        self.font_main = ("Microsoft JhengHei UI", 14)
        self.font_title = ("Microsoft JhengHei UI", 24, "bold")
        self.font_log = ("Consolas", 12)

        self.create_widgets()
        
        # 啟動佇列監聽
        self.after(100, self.process_log_queue)

    def create_widgets(self):
        # 佈局設定
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # 讓日誌區塊自動延展

        # --- 標題區塊 ---
        self.title_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.title_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        self.title_label = ctk.CTkLabel(self.title_frame, text="✨ 圖片自動辨識改名工具", font=self.font_title)
        self.title_label.pack(side="left")

        # --- 設定區塊 ---
        self.config_frame = ctk.CTkFrame(self, corner_radius=10)
        self.config_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.config_frame.grid_columnconfigure(1, weight=1)

        # 來源資料夾
        self.lbl_source = ctk.CTkLabel(self.config_frame, text="來源資料夾:", font=self.font_main)
        self.lbl_source.grid(row=0, column=0, padx=15, pady=(20, 10), sticky="w")
        
        self.source_var = ctk.StringVar(value=str(Path("source_images").resolve()))
        self.entry_source = ctk.CTkEntry(self.config_frame, textvariable=self.source_var, font=self.font_main, height=35)
        self.entry_source.grid(row=0, column=1, padx=(0, 15), pady=(20, 10), sticky="ew")
        
        self.btn_source = ctk.CTkButton(self.config_frame, text="選擇資料夾", font=self.font_main, width=100, height=35, command=self.browse_source)
        self.btn_source.grid(row=0, column=2, padx=(0, 15), pady=(20, 10))

        # 輸出資料夾
        self.lbl_target = ctk.CTkLabel(self.config_frame, text="輸出資料夾:", font=self.font_main)
        self.lbl_target.grid(row=1, column=0, padx=15, pady=10, sticky="w")
        
        self.target_var = ctk.StringVar(value=str(Path("processed_images").resolve()))
        self.entry_target = ctk.CTkEntry(self.config_frame, textvariable=self.target_var, font=self.font_main, height=35)
        self.entry_target.grid(row=1, column=1, padx=(0, 15), pady=10, sticky="ew")
        
        self.btn_target = ctk.CTkButton(self.config_frame, text="選擇資料夾", font=self.font_main, width=100, height=35, command=self.browse_target)
        self.btn_target.grid(row=1, column=2, padx=(0, 15), pady=10)

        # 處理模式
        self.lbl_mode = ctk.CTkLabel(self.config_frame, text="處理模式:", font=self.font_main)
        self.lbl_mode.grid(row=2, column=0, padx=15, pady=(10, 20), sticky="w")
        
        self.mode_var = ctk.BooleanVar(value=False) # False=Copy, True=Move
        self.radio_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        self.radio_frame.grid(row=2, column=1, columnspan=2, padx=(0, 15), pady=(10, 20), sticky="w")
        
        self.radio_copy = ctk.CTkRadioButton(self.radio_frame, text="複製 (保留原始圖片)", variable=self.mode_var, value=False, font=self.font_main)
        self.radio_copy.pack(side="left", padx=(0, 20))
        
        self.radio_move = ctk.CTkRadioButton(self.radio_frame, text="移動 (處理後刪除原圖)", variable=self.mode_var, value=True, font=self.font_main)
        self.radio_move.pack(side="left")

        # --- 日誌區塊 ---
        self.log_frame = ctk.CTkFrame(self, corner_radius=10)
        self.log_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.log_frame.grid_rowconfigure(0, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)
        
        self.log_text = ctk.CTkTextbox(self.log_frame, font=self.font_log, state="disabled", wrap="word", fg_color="#1E1E1E", text_color="#00FF00")
        self.log_text.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        # --- 底部執行與版權區塊 ---
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="ew")
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        
        self.btn_start = ctk.CTkButton(self.bottom_frame, text="🚀 開始執行辨識與自動改名", font=("Microsoft JhengHei UI", 16, "bold"), height=50, corner_radius=8, command=self.start_processing)
        self.btn_start.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        current_year = datetime.datetime.now().year
        year_str = "2026" if current_year == 2026 else f"2026-{current_year}"
        self.lbl_copyright = ctk.CTkLabel(self.bottom_frame, text=f"Copyright © {year_str} Youzih | Made with ❤️", font=("Microsoft JhengHei UI", 12), text_color="gray")
        self.lbl_copyright.grid(row=1, column=0)

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
                self.log_text.configure(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self.process_log_queue)

    def start_processing(self):
        if self.is_processing: return
        self.is_processing = True
        self.btn_start.configure(state="disabled", text="處理中，請稍候...")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        
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
                
            self.log("====== 🎉 所有圖片處理完畢！ ======")
            
        except Exception as e:
            self.log(f"[嚴重錯誤] {e}")
        finally:
            self.is_processing = False
            self.after(0, lambda: self.btn_start.configure(state="normal", text="🚀 開始執行辨識與自動改名"))

def launch_gui():
    app = OCRDesktopApp()
    app.mainloop()

if __name__ == "__main__":
    launch_gui()
