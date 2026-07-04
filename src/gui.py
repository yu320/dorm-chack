import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import queue
import os
import windnd
from pathlib import Path

from src.config import load_settings, save_settings
from src.processor import BatchProcessor

APP_VERSION = "v1.5.1"

class OCRDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("圖片文字辨識與自動改名工具")
        self.geometry("1000x800")
        self.minsize(950, 750)
        
        # 載入設定檔
        self.app_settings = load_settings()
        
        # 設定主題
        theme = self.app_settings.get("theme", "Dark")
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")
        
        # 狀態與資源 (引入解耦的處理器)
        self.processor = BatchProcessor(self.on_processor_update)
        self.is_processing = False
        
        # UI 佇列
        self.update_queue = queue.Queue()
        
        # 設定字型
        self.font_main = ("Microsoft JhengHei UI", 14)
        self.font_title = ("Microsoft JhengHei UI", 20, "bold")
        self.font_giant = ("Microsoft JhengHei UI", 36, "bold")
        self.font_log = ("Consolas", 12)

        self.create_sidebar()
        self.create_home_frame()
        self.create_settings_frame()
        self.create_logs_frame()
        self.create_guide_frame()
        
        # 預設顯示首頁
        self.select_frame_by_name("home")
        
        # 啟動佇列監聽
        self.after(100, self.process_queue)
        
        # 綁定拖曳功能到全視窗
        windnd.hook_dropfiles(self, func=self.on_drop)
        
        # 綁定關閉事件儲存設定
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.save_current_settings()
        self.destroy()

    def save_current_settings(self):
        self.app_settings["source_dir"] = self.source_var.get()
        self.app_settings["target_dir"] = self.target_var.get()
        self.app_settings["move_files"] = self.mode_var.get()
        self.app_settings["blacklist"] = self.entry_blacklist.get("1.0", "end").strip()
        self.app_settings["theme"] = self.theme_var.get()
        
        selected_langs = [k for k, v in self.lang_vars.items() if v.get()]
        self.app_settings["languages"] = selected_langs if selected_langs else ["en"]
        
        selected_exts = [k for k, v in self.ext_vars.items() if v.get()]
        self.app_settings["supported_extensions"] = selected_exts if selected_exts else [".jpg"]
        
        save_settings(self.app_settings)

    def create_sidebar(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="✨ Auto Renamer", font=self.font_title)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 30))
        
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
        
        self.btn_nav_guide = ctk.CTkButton(self.sidebar_frame, corner_radius=0, height=50, border_spacing=10, text="📖 使用說明",
                                              fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                              anchor="w", font=self.font_main, command=lambda: self.select_frame_by_name("guide"))
        self.btn_nav_guide.grid(row=4, column=0, sticky="ew")
        
        self.version_label = ctk.CTkLabel(self.sidebar_frame, text=f"版本 {APP_VERSION}", font=("Microsoft JhengHei UI", 12), text_color="gray")
        self.version_label.grid(row=6, column=0, padx=20, pady=(10, 5))

    def create_home_frame(self):
        self.home_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.home_frame.grid_columnconfigure(0, weight=1)
        self.home_frame.grid_rowconfigure(1, weight=1)

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

        self.card_total, self.val_total = create_card(self.dashboard_frame, "總計圖片與文件", "#3498DB")
        self.card_total.grid(row=0, column=0, padx=10, sticky="ew")
        
        self.card_success, self.val_success = create_card(self.dashboard_frame, "成功辨識", "#2ECC71")
        self.card_success.grid(row=0, column=1, padx=10, sticky="ew")
        
        self.card_failed, self.val_failed = create_card(self.dashboard_frame, "未辨識/失敗", "#E74C3C")
        self.card_failed.grid(row=0, column=2, padx=10, sticky="ew")

        self.drop_zone = ctk.CTkFrame(self.home_frame, corner_radius=20, border_width=2, border_color="#333333")
        self.drop_zone.grid(row=1, column=0, padx=30, pady=20, sticky="nsew")
        self.drop_zone.grid_rowconfigure(0, weight=1)
        self.drop_zone.grid_columnconfigure(0, weight=1)
        
        self.lbl_drop_icon = ctk.CTkLabel(self.drop_zone, text="📁", font=("Segoe UI Emoji", 72))
        self.lbl_drop_icon.grid(row=0, column=0, pady=(60, 0))
        self.lbl_drop_text = ctk.CTkLabel(self.drop_zone, text="將資料夾或檔案拖曳至此處", font=self.font_title, text_color="gray")
        self.lbl_drop_text.grid(row=1, column=0, pady=(10, 10))
        
        source_text = self.app_settings.get("source_dir", "尚未選擇來源")
        self.lbl_current_path = ctk.CTkLabel(self.drop_zone, text=f"當前來源: {source_text}", font=self.font_main, text_color="#3498DB")
        self.lbl_current_path.grid(row=2, column=0, pady=(0, 60))

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
        self.settings_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        
        lbl_title = ctk.CTkLabel(self.settings_frame, text="⚙️ 進階設定", font=self.font_title)
        lbl_title.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        
        # 基本設定
        config_box = ctk.CTkFrame(self.settings_frame, corner_radius=15)
        config_box.grid(row=1, column=0, padx=30, pady=(0, 20), sticky="ew")
        config_box.grid_columnconfigure(1, weight=1)
        
        lbl_source = ctk.CTkLabel(config_box, text="手動指定來源:", font=self.font_main)
        lbl_source.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.source_var = ctk.StringVar(value=self.app_settings.get("source_dir", ""))
        entry_source = ctk.CTkEntry(config_box, textvariable=self.source_var, font=self.font_main, height=35)
        entry_source.grid(row=0, column=1, padx=(0, 10), pady=(20, 10), sticky="ew")
        btn_source = ctk.CTkButton(config_box, text="瀏覽", font=self.font_main, width=80, height=35, command=self.browse_source)
        btn_source.grid(row=0, column=2, padx=(0, 20), pady=(20, 10))

        lbl_target = ctk.CTkLabel(config_box, text="指定輸出路徑:", font=self.font_main)
        lbl_target.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        self.target_var = ctk.StringVar(value=self.app_settings.get("target_dir", ""))
        entry_target = ctk.CTkEntry(config_box, textvariable=self.target_var, font=self.font_main, height=35)
        entry_target.grid(row=1, column=1, padx=(0, 10), pady=10, sticky="ew")
        btn_target = ctk.CTkButton(config_box, text="瀏覽", font=self.font_main, width=80, height=35, command=self.browse_target)
        btn_target.grid(row=1, column=2, padx=(0, 20), pady=10)

        lbl_mode = ctk.CTkLabel(config_box, text="檔案處理模式:", font=self.font_main)
        lbl_mode.grid(row=2, column=0, padx=20, pady=(10, 20), sticky="w")
        self.mode_var = ctk.BooleanVar(value=self.app_settings.get("move_files", False))
        radio_frame = ctk.CTkFrame(config_box, fg_color="transparent")
        radio_frame.grid(row=2, column=1, columnspan=2, padx=(0, 20), pady=(10, 20), sticky="w")
        radio_copy = ctk.CTkRadioButton(radio_frame, text="複製 (安全)", variable=self.mode_var, value=False, font=self.font_main, command=self.save_current_settings)
        radio_copy.pack(side="left", padx=(0, 20))
        radio_move = ctk.CTkRadioButton(radio_frame, text="移動 (省空間)", variable=self.mode_var, value=True, font=self.font_main, command=self.save_current_settings)
        radio_move.pack(side="left")

        # 辨識格式與語言設定
        adv_box = ctk.CTkFrame(self.settings_frame, corner_radius=15)
        adv_box.grid(row=2, column=0, padx=30, pady=(0, 30), sticky="ew")
        adv_box.grid_columnconfigure(1, weight=1)
        
        lbl_ext = ctk.CTkLabel(adv_box, text="辨識檔案格式:", font=self.font_main)
        lbl_ext.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nw")
        ext_frame = ctk.CTkFrame(adv_box, fg_color="transparent")
        ext_frame.grid(row=0, column=1, padx=(0, 20), pady=(20, 10), sticky="w")
        self.ext_vars = {}
        for i, ext in enumerate([".jpg", ".jpeg", ".png", ".bmp", ".webp", ".pdf"]):
            var = ctk.BooleanVar(value=(ext in self.app_settings.get("supported_extensions", [])))
            self.ext_vars[ext] = var
            chk = ctk.CTkCheckBox(ext_frame, text=ext.upper(), variable=var, font=self.font_main, command=self.save_current_settings)
            chk.grid(row=i//3, column=i%3, padx=10, pady=5, sticky="w")

        lbl_lang = ctk.CTkLabel(adv_box, text="AI 辨識語言:", font=self.font_main)
        lbl_lang.grid(row=1, column=0, padx=20, pady=(10, 10), sticky="nw")
        lang_frame = ctk.CTkFrame(adv_box, fg_color="transparent")
        lang_frame.grid(row=1, column=1, padx=(0, 20), pady=(10, 10), sticky="w")
        self.lang_vars = {}
        for i, (code, name) in enumerate({"ch_tra":"繁體中文", "ch_sim":"簡體中文", "en":"英文", "ja":"日文", "ko":"韓文"}.items()):
            var = ctk.BooleanVar(value=(code in self.app_settings.get("languages", [])))
            self.lang_vars[code] = var
            chk = ctk.CTkCheckBox(lang_frame, text=name, variable=var, font=self.font_main, command=self.save_current_settings)
            chk.grid(row=i//3, column=i%3, padx=10, pady=5, sticky="w")

        lbl_black = ctk.CTkLabel(adv_box, text="過濾關鍵字:", font=self.font_main)
        lbl_black.grid(row=2, column=0, padx=20, pady=(10, 10), sticky="nw")
        self.entry_blacklist = ctk.CTkTextbox(adv_box, font=self.font_main, height=80)
        self.entry_blacklist.grid(row=2, column=1, padx=(0, 20), pady=(10, 5), sticky="ew")
        self.entry_blacklist.insert("1.0", self.app_settings.get("blacklist", ""))
        self.entry_blacklist.bind("<KeyRelease>", lambda e: self.save_current_settings())

        # 系統操作
        sys_box = ctk.CTkFrame(self.settings_frame, corner_radius=15)
        sys_box.grid(row=3, column=0, padx=30, pady=(0, 30), sticky="ew")
        sys_box.grid_columnconfigure(1, weight=1)
        lbl_theme = ctk.CTkLabel(sys_box, text="介面主題:", font=self.font_main)
        lbl_theme.grid(row=0, column=0, padx=20, pady=(20, 20), sticky="w")
        self.theme_var = ctk.StringVar(value=self.app_settings.get("theme", "Dark"))
        theme_menu = ctk.CTkOptionMenu(sys_box, values=["Dark", "Light", "System"], variable=self.theme_var, font=self.font_main, command=self.change_theme)
        theme_menu.grid(row=0, column=1, padx=0, pady=(20, 20), sticky="w")
        btn_clear_cache = ctk.CTkButton(sys_box, text="🗑️ 清除快取", font=self.font_main, fg_color="#E74C3C", hover_color="#C0392B", command=self.clear_cache)
        btn_clear_cache.grid(row=0, column=2, padx=20, pady=(20, 20), sticky="e")

    def create_guide_frame(self):
        self.guide_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.guide_frame.grid_columnconfigure(0, weight=1)
        lbl_title = ctk.CTkLabel(self.guide_frame, text="📖 使用說明", font=self.font_title)
        lbl_title.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        guide_box = ctk.CTkFrame(self.guide_frame, corner_radius=15)
        guide_box.grid(row=1, column=0, padx=30, pady=(0, 30), sticky="ew")
        guide_text = "操作說明已整合，這是一個與介面解耦的版本，擁有更強的擴充性與穩定性。"
        lbl_content = ctk.CTkLabel(guide_box, text=guide_text, font=("Microsoft JhengHei UI", 15), justify="left")
        lbl_content.grid(row=0, column=0, padx=30, pady=30, sticky="w")

    def select_frame_by_name(self, name):
        self.btn_nav_home.configure(fg_color=("gray75", "gray25") if name == "home" else "transparent")
        self.btn_nav_logs.configure(fg_color=("gray75", "gray25") if name == "logs" else "transparent")
        self.btn_nav_settings.configure(fg_color=("gray75", "gray25") if name == "settings" else "transparent")
        self.btn_nav_guide.configure(fg_color=("gray75", "gray25") if name == "guide" else "transparent")
        for f, n in [(self.home_frame, "home"), (self.logs_frame, "logs"), (self.settings_frame, "settings"), (self.guide_frame, "guide")]:
            f.grid(row=0, column=1, sticky="nsew") if n == name else f.grid_forget()

    def change_theme(self, new_theme):
        ctk.set_appearance_mode(new_theme)
        self.save_current_settings()

    def clear_cache(self):
        target_dir = Path(self.target_var.get())
        hash_file = target_dir / ".hash_history.json"
        if hash_file.exists():
            hash_file.unlink()
            messagebox.showinfo("成功", "已成功清除處理記憶！")

    def on_drop(self, files):
        if not files: return
        path = files[0].decode('gbk') if 'gbk' else files[0].decode('utf-8')
        if os.path.isdir(path):
            self.source_var.set(path)
            self.target_var.set(os.path.join(path, "processed_images"))
            self.lbl_current_path.configure(text=f"已選取: {path}", text_color="#2ECC71")
            self.update_log(f"[系統] 拖曳設定了來源: {path}")

    def browse_source(self):
        d = filedialog.askdirectory(initialdir=self.source_var.get())
        if d: self.source_var.set(d)

    def browse_target(self):
        d = filedialog.askdirectory(initialdir=self.target_var.get())
        if d: self.target_var.set(d)

    def open_output_folder(self):
        path = self.target_var.get()
        if os.path.exists(path): os.startfile(path)

    # --- 佇列機制與回呼函式 ---
    def on_processor_update(self, msg, stats=None):
        self.update_queue.put((msg, stats))

    def update_log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def process_queue(self):
        try:
            while True:
                msg, stats = self.update_queue.get_nowait()
                if msg == "PROCESS_DONE":
                    self.is_processing = False
                    self.btn_start.configure(state="normal", text="🚀 開始執行批次改名")
                    self.btn_cancel.configure(state="disabled", text="⛔ 停止")
                elif msg:
                    self.update_log(msg)
                
                if stats:
                    success, failed, total = stats
                    if total > 0: self.progress_bar.set((success + failed) / total)
                    self.val_total.configure(text=str(total))
                    self.val_success.configure(text=str(success))
                    self.val_failed.configure(text=str(failed))
        except queue.Empty:
            pass
        self.after(100, self.process_queue)

    def cancel_processing(self):
        if self.is_processing:
            self.processor.cancel()
            self.btn_cancel.configure(state="disabled", text="正在停止...")
            self.update_log("⚠️ 觸發停止，等待當前任務結束...")

    def start_processing(self):
        if self.is_processing: return
        self.is_processing = True
        
        self.save_current_settings()
        self.btn_start.configure(state="disabled", text="處理中，請稍候...")
        self.btn_cancel.configure(state="normal", text="⛔ 停止")
        self.progress_bar.set(0)
        self.update_log("--------------------------------")
        
        source = Path(self.source_var.get())
        target = Path(self.target_var.get())
        move = self.mode_var.get()
        langs = self.app_settings.get("languages", ["en"])
        exts = self.app_settings.get("supported_extensions", [".jpg"])
        bl = [w.strip() for w in self.app_settings.get("blacklist", "").split('\n') if w.strip()]
        
        threading.Thread(target=self.processor.process, args=(source, target, move, langs, exts, bl), daemon=True).start()

def launch_gui():
    app = OCRDesktopApp()
    app.mainloop()

if __name__ == "__main__":
    launch_gui()
