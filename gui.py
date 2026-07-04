import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import queue
import datetime
import hashlib
import json
import os
import windnd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.ocr import OCREngine
from src.utils import clean_filename, get_unique_path, move_or_copy_file
from src.config import SUPPORTED_EXTENSIONS

APP_VERSION = "v1.1.0"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class OCRDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("圖片文字辨識與自動改名工具")
        self.geometry("950x700")
        self.minsize(900, 650)
        
        # 狀態與資源
        self.ocr_engine = None
        self.is_processing = False
        self.is_cancelled = False
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        
        # 數據統計
        self.stats = {"total": 0, "success": 0, "failed": 0}
        
        # 設定字型
        self.font_main = ("Microsoft JhengHei UI", 14)
        self.font_title = ("Microsoft JhengHei UI", 20, "bold")
        self.font_giant = ("Microsoft JhengHei UI", 36, "bold")
        self.font_log = ("Consolas", 12)

        self.create_sidebar()
        self.create_home_frame()
        self.create_settings_frame()
        self.create_logs_frame()
        
        # 預設顯示首頁
        self.select_frame_by_name("home")
        
        # 啟動佇列監聽
        self.after(100, self.process_queue)
        
        # 綁定拖曳功能到全視窗
        windnd.hook_dropfiles(self, func=self.on_drop)

    def create_sidebar(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        
        # 標題
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="✨ Auto Renamer", font=self.font_title)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 30))
        
        # 導覽按鈕
        self.btn_nav_home = ctk.CTkButton(self.sidebar_frame, corner_radius=0, height=50, border_spacing=10, text="🏠 控制中心",
                                          fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                          anchor="w", font=self.font_main, command=lambda: self.select_frame_by_name("home"))
        self.btn_nav_home.grid(row=1, column=0, sticky="ew")
        
        self.btn_nav_logs = ctk.CTkButton(self.sidebar_frame, corner_radius=0, height=50, border_spacing=10, text="📜 處理日誌",
                                          fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                          anchor="w", font=self.font_main, command=lambda: self.select_frame_by_name("logs"))
        self.btn_nav_logs.grid(row=2, column=0, sticky="ew")

        self.btn_nav_settings = ctk.CTkButton(self.sidebar_frame, corner_radius=0, height=50, border_spacing=10, text="⚙️ 進階設定",
                                              fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                              anchor="w", font=self.font_main, command=lambda: self.select_frame_by_name("settings"))
        self.btn_nav_settings.grid(row=3, column=0, sticky="ew")
        
        # 版本與版權
        self.version_label = ctk.CTkLabel(self.sidebar_frame, text=f"版本 {APP_VERSION}", font=("Microsoft JhengHei UI", 12), text_color="gray")
        self.version_label.grid(row=5, column=0, padx=20, pady=(10, 5))
        
        self.copyright_label = ctk.CTkLabel(self.sidebar_frame, text="© 2026 Youzih", font=("Microsoft JhengHei UI", 11), text_color="gray50")
        self.copyright_label.grid(row=6, column=0, padx=20, pady=(0, 20))

    def create_home_frame(self):
        self.home_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.home_frame.grid_columnconfigure(0, weight=1)
        self.home_frame.grid_rowconfigure(1, weight=1)

        # --- 頂部儀表板卡片 ---
        self.dashboard_frame = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        self.dashboard_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.dashboard_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        def create_card(parent, title, color):
            frame = ctk.CTkFrame(parent, corner_radius=15, fg_color="#2B2B2B")
            lbl_title = ctk.CTkLabel(frame, text=title, font=self.font_main, text_color="gray")
            lbl_title.pack(pady=(15, 0))
            lbl_value = ctk.CTkLabel(frame, text="0", font=self.font_giant, text_color=color)
            lbl_value.pack(pady=(0, 15))
            return frame, lbl_value

        self.card_total, self.val_total = create_card(self.dashboard_frame, "總計圖片", "#3498DB")
        self.card_total.grid(row=0, column=0, padx=10, sticky="ew")
        
        self.card_success, self.val_success = create_card(self.dashboard_frame, "成功辨識", "#2ECC71")
        self.card_success.grid(row=0, column=1, padx=10, sticky="ew")
        
        self.card_failed, self.val_failed = create_card(self.dashboard_frame, "未辨識/失敗", "#E74C3C")
        self.card_failed.grid(row=0, column=2, padx=10, sticky="ew")

        # --- 中央拖曳區 ---
        self.drop_zone = ctk.CTkFrame(self.home_frame, corner_radius=20, fg_color="#1E1E1E", border_width=2, border_color="#333333")
        self.drop_zone.grid(row=1, column=0, padx=30, pady=20, sticky="nsew")
        self.drop_zone.grid_rowconfigure(0, weight=1)
        self.drop_zone.grid_columnconfigure(0, weight=1)
        
        self.lbl_drop_icon = ctk.CTkLabel(self.drop_zone, text="📁", font=("Segoe UI Emoji", 72))
        self.lbl_drop_icon.grid(row=0, column=0, pady=(60, 0))
        self.lbl_drop_text = ctk.CTkLabel(self.drop_zone, text="將資料夾拖曳至此處", font=self.font_title, text_color="gray")
        self.lbl_drop_text.grid(row=1, column=0, pady=(10, 10))
        
        self.lbl_current_path = ctk.CTkLabel(self.drop_zone, text="尚未選擇來源", font=self.font_main, text_color="#3498DB")
        self.lbl_current_path.grid(row=2, column=0, pady=(0, 60))

        # --- 底部控制區 ---
        self.control_frame = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        self.control_frame.grid(row=2, column=0, padx=30, pady=(0, 30), sticky="ew")
        self.control_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_bar = ctk.CTkProgressBar(self.control_frame, height=12, corner_radius=6)
        self.progress_bar.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 20))
        self.progress_bar.set(0)
        
        self.btn_start = ctk.CTkButton(self.control_frame, text="🚀 開始執行批次改名", font=("Microsoft JhengHei UI", 16, "bold"), height=55, corner_radius=10, command=self.start_processing)
        self.btn_start.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        
        self.btn_cancel = ctk.CTkButton(self.control_frame, text="⛔ 停止", font=("Microsoft JhengHei UI", 16, "bold"), fg_color="#D9534F", hover_color="#C9302C", height=55, width=120, corner_radius=10, command=self.cancel_processing, state="disabled")
        self.btn_cancel.grid(row=1, column=1, padx=(0, 10))
        
        self.btn_open_folder = ctk.CTkButton(self.control_frame, text="📂 開啟輸出資料夾", font=("Microsoft JhengHei UI", 16, "bold"), fg_color="#5CB85C", hover_color="#4CAE4C", height=55, width=180, corner_radius=10, command=self.open_output_folder)
        self.btn_open_folder.grid(row=1, column=2)

    def create_logs_frame(self):
        self.logs_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.logs_frame.grid_rowconfigure(1, weight=1)
        self.logs_frame.grid_columnconfigure(0, weight=1)
        
        lbl_title = ctk.CTkLabel(self.logs_frame, text="📜 處理日誌", font=self.font_title)
        lbl_title.grid(row=0, column=0, padx=30, pady=(30, 10), sticky="w")
        
        self.log_text = ctk.CTkTextbox(self.logs_frame, font=self.font_log, state="disabled", wrap="word", fg_color="#1E1E1E", text_color="#2ECC71", corner_radius=10)
        self.log_text.grid(row=1, column=0, padx=30, pady=(10, 30), sticky="nsew")

    def create_settings_frame(self):
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        
        lbl_title = ctk.CTkLabel(self.settings_frame, text="⚙️ 進階設定", font=self.font_title)
        lbl_title.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        
        config_box = ctk.CTkFrame(self.settings_frame, corner_radius=15, fg_color="#2B2B2B")
        config_box.grid(row=1, column=0, padx=30, sticky="ew")
        config_box.grid_columnconfigure(1, weight=1)
        
        # 來源資料夾 (仍可手動選)
        lbl_source = ctk.CTkLabel(config_box, text="手動指定來源:", font=self.font_main)
        lbl_source.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        self.source_var = ctk.StringVar(value=str(Path("source_images").resolve()))
        entry_source = ctk.CTkEntry(config_box, textvariable=self.source_var, font=self.font_main, height=35)
        entry_source.grid(row=0, column=1, padx=(0, 10), pady=(20, 10), sticky="ew")
        
        btn_source = ctk.CTkButton(config_box, text="瀏覽", font=self.font_main, width=80, height=35, command=self.browse_source)
        btn_source.grid(row=0, column=2, padx=(0, 20), pady=(20, 10))

        # 輸出資料夾
        lbl_target = ctk.CTkLabel(config_box, text="指定輸出路徑:", font=self.font_main)
        lbl_target.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        
        self.target_var = ctk.StringVar(value=str(Path("processed_images").resolve()))
        entry_target = ctk.CTkEntry(config_box, textvariable=self.target_var, font=self.font_main, height=35)
        entry_target.grid(row=1, column=1, padx=(0, 10), pady=10, sticky="ew")
        
        btn_target = ctk.CTkButton(config_box, text="瀏覽", font=self.font_main, width=80, height=35, command=self.browse_target)
        btn_target.grid(row=1, column=2, padx=(0, 20), pady=10)

        # 處理模式
        lbl_mode = ctk.CTkLabel(config_box, text="檔案處理模式:", font=self.font_main)
        lbl_mode.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="w")
        
        self.mode_var = ctk.BooleanVar(value=False) # False=Copy, True=Move
        radio_frame = ctk.CTkFrame(config_box, fg_color="transparent")
        radio_frame.grid(row=2, column=1, columnspan=2, padx=(0, 20), pady=(10, 20), sticky="w")
        
        radio_copy = ctk.CTkRadioButton(radio_frame, text="複製 (保留原始檔案，安全)", variable=self.mode_var, value=False, font=self.font_main)
        radio_copy.pack(side="left", padx=(0, 20))
        
        radio_move = ctk.CTkRadioButton(radio_frame, text="移動 (處理後刪除原圖，節省空間)", variable=self.mode_var, value=True, font=self.font_main)
        radio_move.pack(side="left")

    def select_frame_by_name(self, name):
        # 更新按鈕顏色
        self.btn_nav_home.configure(fg_color=("gray75", "gray25") if name == "home" else "transparent")
        self.btn_nav_logs.configure(fg_color=("gray75", "gray25") if name == "logs" else "transparent")
        self.btn_nav_settings.configure(fg_color=("gray75", "gray25") if name == "settings" else "transparent")

        # 切換 Frame
        if name == "home":
            self.home_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.home_frame.grid_forget()
            
        if name == "logs":
            self.logs_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.logs_frame.grid_forget()
            
        if name == "settings":
            self.settings_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.settings_frame.grid_forget()

    def on_drop(self, files):
        if not files: return
        try:
            path = files[0].decode('gbk')
        except:
            try:
                path = files[0].decode('utf-8')
            except:
                path = ""
                
        if os.path.isdir(path):
            self.source_var.set(path)
            suggested_target = os.path.join(path, "processed_images")
            self.target_var.set(suggested_target)
            self.lbl_current_path.configure(text=f"已選取: {path}", text_color="#2ECC71")
            self.drop_zone.configure(border_color="#2ECC71")
            self.log(f"[系統] 透過拖曳設定了來源資料夾: {path}")

    def browse_source(self):
        d = filedialog.askdirectory(initialdir=self.source_var.get())
        if d: 
            self.source_var.set(d)
            self.lbl_current_path.configure(text=f"已選取: {d}", text_color="#2ECC71")
            self.drop_zone.configure(border_color="#2ECC71")

    def browse_target(self):
        d = filedialog.askdirectory(initialdir=self.target_var.get())
        if d: self.target_var.set(d)

    def log(self, message):
        self.log_queue.put(message)
        
    def update_stats(self, success, failed, total):
        self.progress_queue.put(("stats", success, failed, total))

    def process_queue(self):
        # 處理日誌
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
            
        # 處理進度條與儀表板
        try:
            while True:
                msg_type, *args = self.progress_queue.get_nowait()
                if msg_type == "stats":
                    success, failed, total = args
                    if total > 0:
                        pct = (success + failed) / total
                        self.progress_bar.set(pct)
                    self.val_total.configure(text=str(total))
                    self.val_success.configure(text=str(success))
                    self.val_failed.configure(text=str(failed))
        except queue.Empty:
            pass
            
        self.after(100, self.process_queue)

    def open_output_folder(self):
        path = self.target_var.get()
        if os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showwarning("提示", "輸出資料夾尚未建立！")

    def cancel_processing(self):
        if self.is_processing:
            self.is_cancelled = True
            self.btn_cancel.configure(state="disabled", text="正在停止...")
            self.log("⚠️ 已觸發緊急停止，等待當前任務結束後中止...")

    def start_processing(self):
        if self.is_processing: return
        self.is_processing = True
        self.is_cancelled = False
        
        self.btn_start.configure(state="disabled", text="處理中，請稍候...")
        self.btn_cancel.configure(state="normal", text="⛔ 停止")
        self.progress_bar.set(0)
        self.update_stats(0, 0, 0)
        
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        
        source_dir = Path(self.source_var.get())
        target_dir = Path(self.target_var.get())
        move_files = self.mode_var.get()
        
        threading.Thread(target=self.run_batch_job, args=(source_dir, target_dir, move_files), daemon=True).start()

    def run_batch_job(self, source_dir, target_dir, move_files):
        try:
            if not source_dir.exists():
                self.log(f"[錯誤] 來源資料夾不存在: {source_dir}")
                return
            
            image_paths = [p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
            total_images = len(image_paths)
            
            if total_images == 0:
                self.log(f"[提示] 找不到支援的圖片檔 ({', '.join(SUPPORTED_EXTENSIONS)})")
                return

            self.log("正在初始化 AI OCR 引擎 (首次啟動可能需要幾秒鐘)...")
            if not self.ocr_engine:
                self.ocr_engine = OCREngine()
                
            self.log(f"成功載入！共找到 {total_images} 張圖片，開始處理...")
            self.update_stats(0, 0, total_images)
            
            max_workers = 1 if hasattr(self.ocr_engine, 'use_gpu') and self.ocr_engine.use_gpu else 4
            self.log(f"已啟用效能最佳化：執行緒數量為 {max_workers}")
            
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
                with open(hash_file, "r", encoding="utf-8") as f:
                    processed_hashes = set(json.load(f))
                    
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
                    new_stem = clean_filename(text)
                    
                    is_failed = False
                    if not new_stem:
                        new_stem = f"未辨識_{img_path.stem}"
                        out_dir = unrec_dir
                        status_msg = "未辨識到有效文字"
                        is_failed = True
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
                        self.log(res)
                    self.update_stats(current_success, current_failed, total_images)

            with open(hash_file, "w", encoding="utf-8") as f:
                json.dump(list(processed_hashes), f)
                
            if self.is_cancelled:
                self.log("====== 🚫 處理已終止 ======")
            else:
                self.log("====== 🎉 所有圖片處理完畢！ ======")
            
        except Exception as e:
            self.log(f"[嚴重錯誤] {e}")
        finally:
            self.is_processing = False
            self.after(0, self.reset_ui_state)

    def reset_ui_state(self):
        self.btn_start.configure(state="normal", text="🚀 開始執行批次改名")
        self.btn_cancel.configure(state="disabled", text="⛔ 停止")

def launch_gui():
    app = OCRDesktopApp()
    app.mainloop()

if __name__ == "__main__":
    launch_gui()
