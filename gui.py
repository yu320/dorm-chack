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
from src.config import load_settings, save_settings

APP_VERSION = "v1.5.0"

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
        
        # 狀態與資源
        self.ocr_engine = None
        self.is_processing = False
        self.is_cancelled = False
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        
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
        
        # 收集打勾的語言
        selected_langs = []
        for lang_code, var in self.lang_vars.items():
            if var.get():
                selected_langs.append(lang_code)
        if not selected_langs:
            selected_langs = ["en"] # 至少要有英文
        self.app_settings["languages"] = selected_langs
        
        # 收集打勾的副檔名
        selected_exts = []
        for ext, var in self.ext_vars.items():
            if var.get():
                selected_exts.append(ext)
        if not selected_exts:
            selected_exts = [".jpg"]
        self.app_settings["supported_extensions"] = selected_exts
        
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
        
        self.copyright_label = ctk.CTkLabel(self.sidebar_frame, text="© 2026 Youzih", font=("Microsoft JhengHei UI", 11), text_color="gray50")
        self.copyright_label.grid(row=7, column=0, padx=20, pady=(0, 20))

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

        self.card_total, self.val_total = create_card(self.dashboard_frame, "總計圖片與文件", "#3498DB")
        self.card_total.grid(row=0, column=0, padx=10, sticky="ew")
        
        self.card_success, self.val_success = create_card(self.dashboard_frame, "成功辨識", "#2ECC71")
        self.card_success.grid(row=0, column=1, padx=10, sticky="ew")
        
        self.card_failed, self.val_failed = create_card(self.dashboard_frame, "未辨識/失敗", "#E74C3C")
        self.card_failed.grid(row=0, column=2, padx=10, sticky="ew")

        # --- 中央拖曳區 ---
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
        self.settings_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.settings_frame.grid_columnconfigure(0, weight=1)
        
        lbl_title = ctk.CTkLabel(self.settings_frame, text="⚙️ 進階設定", font=self.font_title)
        lbl_title.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        
        # --- 基本設定區塊 ---
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
        radio_copy = ctk.CTkRadioButton(radio_frame, text="複製 (保留原始檔案，安全)", variable=self.mode_var, value=False, font=self.font_main, command=self.save_current_settings)
        radio_copy.pack(side="left", padx=(0, 20))
        radio_move = ctk.CTkRadioButton(radio_frame, text="移動 (處理後刪除原檔，省空間)", variable=self.mode_var, value=True, font=self.font_main, command=self.save_current_settings)
        radio_move.pack(side="left")

        # --- 辨識格式與語言設定區塊 ---
        adv_box = ctk.CTkFrame(self.settings_frame, corner_radius=15)
        adv_box.grid(row=2, column=0, padx=30, pady=(0, 30), sticky="ew")
        adv_box.grid_columnconfigure(1, weight=1)
        
        # 副檔名選擇
        lbl_ext = ctk.CTkLabel(adv_box, text="辨識檔案格式:", font=self.font_main)
        lbl_ext.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nw")
        
        ext_frame = ctk.CTkFrame(adv_box, fg_color="transparent")
        ext_frame.grid(row=0, column=1, padx=(0, 20), pady=(20, 10), sticky="w")
        
        self.available_exts = [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".pdf"]
        self.ext_vars = {}
        saved_exts = self.app_settings.get("supported_extensions", self.available_exts)
        
        for i, ext in enumerate(self.available_exts):
            var = ctk.BooleanVar(value=(ext in saved_exts))
            self.ext_vars[ext] = var
            chk = ctk.CTkCheckBox(ext_frame, text=ext.upper(), variable=var, font=self.font_main, command=self.save_current_settings)
            chk.grid(row=i//3, column=i%3, padx=10, pady=5, sticky="w")

        # 語言設定
        lbl_lang = ctk.CTkLabel(adv_box, text="AI 辨識語言:", font=self.font_main)
        lbl_lang.grid(row=1, column=0, padx=20, pady=(10, 10), sticky="nw")
        
        lang_frame = ctk.CTkFrame(adv_box, fg_color="transparent")
        lang_frame.grid(row=1, column=1, padx=(0, 20), pady=(10, 10), sticky="w")
        
        self.available_langs = {
            "ch_tra": "繁體中文", "ch_sim": "簡體中文", "en": "英文", "ja": "日文", "ko": "韓文"
        }
        self.lang_vars = {}
        saved_langs = self.app_settings.get("languages", ["ch_tra", "en"])
        
        for i, (code, name) in enumerate(self.available_langs.items()):
            var = ctk.BooleanVar(value=(code in saved_langs))
            self.lang_vars[code] = var
            chk = ctk.CTkCheckBox(lang_frame, text=name, variable=var, font=self.font_main, command=self.save_current_settings)
            chk.grid(row=i//3, column=i%3, padx=10, pady=5, sticky="w")

        # 雜訊過濾黑名單
        lbl_black = ctk.CTkLabel(adv_box, text="過濾關鍵字:", font=self.font_main)
        lbl_black.grid(row=2, column=0, padx=20, pady=(10, 10), sticky="nw")
        
        self.entry_blacklist = ctk.CTkTextbox(adv_box, font=self.font_main, height=80)
        self.entry_blacklist.grid(row=2, column=1, padx=(0, 20), pady=(10, 5), sticky="ew")
        self.entry_blacklist.insert("1.0", self.app_settings.get("blacklist", ""))
        self.entry_blacklist.bind("<KeyRelease>", lambda e: self.save_current_settings())
        
        lbl_black_hint = ctk.CTkLabel(adv_box, text="每行一個想過濾的字（如公司名），這些字將不會出現在改名後的檔名中", font=("Microsoft JhengHei UI", 12), text_color="gray")
        lbl_black_hint.grid(row=3, column=1, padx=(0, 20), pady=(0, 20), sticky="w")
        
        # --- 介面外觀與系統操作 ---
        sys_box = ctk.CTkFrame(self.settings_frame, corner_radius=15)
        sys_box.grid(row=3, column=0, padx=30, pady=(0, 30), sticky="ew")
        sys_box.grid_columnconfigure(1, weight=1)
        
        lbl_theme = ctk.CTkLabel(sys_box, text="介面主題:", font=self.font_main)
        lbl_theme.grid(row=0, column=0, padx=20, pady=(20, 20), sticky="w")
        
        self.theme_var = ctk.StringVar(value=self.app_settings.get("theme", "Dark"))
        theme_menu = ctk.CTkOptionMenu(sys_box, values=["Dark", "Light", "System"], variable=self.theme_var, font=self.font_main, command=self.change_theme)
        theme_menu.grid(row=0, column=1, padx=0, pady=(20, 20), sticky="w")
        
        btn_clear_cache = ctk.CTkButton(sys_box, text="🗑️ 清除處理記憶快取", font=self.font_main, fg_color="#E74C3C", hover_color="#C0392B", command=self.clear_cache)
        btn_clear_cache.grid(row=0, column=2, padx=20, pady=(20, 20), sticky="e")

    def change_theme(self, new_theme):
        ctk.set_appearance_mode(new_theme)
        self.save_current_settings()

    def clear_cache(self):
        target_dir = Path(self.target_var.get())
        hash_file = target_dir / ".hash_history.json"
        if hash_file.exists():
            try:
                hash_file.unlink()
                messagebox.showinfo("成功", "已成功清除處理記憶！下次執行將會重新辨識所有圖片。")
            except Exception as e:
                messagebox.showerror("錯誤", f"清除失敗: {e}")
        else:
            messagebox.showinfo("提示", "目前沒有任何記憶快取檔案。")

    def create_guide_frame(self):
        self.guide_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.guide_frame.grid_columnconfigure(0, weight=1)
        
        lbl_title = ctk.CTkLabel(self.guide_frame, text="📖 使用說明", font=self.font_title)
        lbl_title.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        
        guide_box = ctk.CTkFrame(self.guide_frame, corner_radius=15)
        guide_box.grid(row=1, column=0, padx=30, pady=(0, 30), sticky="ew")
        guide_box.grid_columnconfigure(0, weight=1)
        
        guide_text = """歡迎使用本工具！這是一個能幫您「全自動掃描圖片文字，並自動幫圖片改名」的超級小幫手。

🚀 步驟一：選擇來源資料夾
• 最簡單的方式：直接將您要處理的「資料夾」或是「檔案」拖曳到『🏠 控制中心』正中央的虛線大方框內。
• 您也可以前往『⚙️ 進階設定』中，手動點擊「瀏覽」來指定路徑。

🎨 步驟二：設定您的選項 (非必填)
• 在『⚙️ 進階設定』中，您可以：
  - 切換「複製（安全保留原檔）」或「移動（處理後刪除原檔）」。
  - 勾選要處理的檔案格式（支援 .jpg, .png, .pdf 等）。
  - 勾選圖片中可能出現的語言（繁體中文、日文等）。
  - 設定過濾關鍵字，避免特定的文字（如網址）成為檔名的一部分。

✨ 步驟三：一鍵開始自動改名！
• 回到『🏠 控制中心』，點擊最下方大大的「🚀 開始執行批次改名」按鈕。
• 接下來只需喝杯咖啡☕，看著上方的儀表板數字不斷增加！
• 完成後點擊「📂 開啟輸出資料夾」，即可查看所有幫您重新命名好的精美檔案！

❓ 常見問題 (Q&A)
Q: 處理到一半不小心按到停止或關閉程式怎麼辦？
A: 軟體內建「自動記憶機制」。您只要重新開啟軟體並按開始，它會自動跳過已經處理過的圖片，無縫從中斷處繼續執行！如果您想重新處理，可以到「進階設定」點擊「清除處理記憶快取」。

Q: 為什麼有些圖片被丟到「未辨識」資料夾？
A: 如果圖片沒有文字、文字太模糊，或是辨識出的文字全是您設定的「過濾關鍵字」，軟體會將它們歸類為未辨識。
"""
        
        lbl_content = ctk.CTkLabel(guide_box, text=guide_text, font=("Microsoft JhengHei UI", 15), justify="left", wraplength=600)
        lbl_content.grid(row=0, column=0, padx=30, pady=30, sticky="w")

    def select_frame_by_name(self, name):
        self.btn_nav_home.configure(fg_color=("gray75", "gray25") if name == "home" else "transparent")
        self.btn_nav_logs.configure(fg_color=("gray75", "gray25") if name == "logs" else "transparent")
        self.btn_nav_settings.configure(fg_color=("gray75", "gray25") if name == "settings" else "transparent")
        self.btn_nav_guide.configure(fg_color=("gray75", "gray25") if name == "guide" else "transparent")

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
            
        if name == "guide":
            self.guide_frame.grid(row=0, column=1, sticky="nsew")
        else:
            self.guide_frame.grid_forget()

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
            self.save_current_settings()
            self.log(f"[系統] 透過拖曳設定了來源資料夾: {path}")

    def browse_source(self):
        d = filedialog.askdirectory(initialdir=self.source_var.get())
        if d: 
            self.source_var.set(d)
            self.lbl_current_path.configure(text=f"已選取: {d}", text_color="#2ECC71")
            self.drop_zone.configure(border_color="#2ECC71")
            self.save_current_settings()

    def browse_target(self):
        d = filedialog.askdirectory(initialdir=self.target_var.get())
        if d: 
            self.target_var.set(d)
            self.save_current_settings()

    def log(self, message):
        self.log_queue.put(message)
        
    def update_stats(self, success, failed, total):
        self.progress_queue.put(("stats", success, failed, total))

    def process_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
            
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
        
        self.save_current_settings()
        
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
        
        langs = self.app_settings.get("languages", ["ch_tra", "en"])
        allowed_exts = self.app_settings.get("supported_extensions", [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".pdf"])
        
        blacklist_raw = self.app_settings.get("blacklist", "")
        blacklist = [w.strip() for w in blacklist_raw.split('\n') if w.strip()]
        
        threading.Thread(target=self.run_batch_job, args=(source_dir, target_dir, move_files, langs, allowed_exts, blacklist), daemon=True).start()

    def run_batch_job(self, source_dir, target_dir, move_files, langs, allowed_exts, blacklist):
        try:
            if not source_dir.exists():
                self.log(f"[錯誤] 來源資料夾不存在: {source_dir}")
                return
            
            image_paths = [p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed_exts]
            total_images = len(image_paths)
            
            if total_images == 0:
                self.log(f"[提示] 找不到指定的檔案格式 ({', '.join(allowed_exts)})")
                return

            self.log("正在初始化 AI OCR 引擎 (首次啟動可能需要幾秒鐘)...")
            if not self.ocr_engine or getattr(self.ocr_engine, 'current_langs', []) != langs:
                self.ocr_engine = OCREngine(languages=langs)
                self.ocr_engine.current_langs = langs
                
            self.log(f"成功載入！共找到 {total_images} 個檔案，開始處理...")
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
                        self.log(res)
                    self.update_stats(current_success, current_failed, total_images)

            with open(hash_file, "w", encoding="utf-8") as f:
                json.dump(list(processed_hashes), f)
                
            if self.is_cancelled:
                self.log("====== 🚫 處理已終止 ======")
            else:
                self.log("====== 🎉 所有檔案處理完畢！ ======")
            
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
