import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import queue
import os
import windnd
import time
from pathlib import Path

from src.config import load_settings, save_settings
from src.processor import BatchProcessor

APP_VERSION = "v1.8.6"

class OCRDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("圖片文字辨識與自動改名工具")
        
        # 取得螢幕解析度並將視窗置中，適應筆電小螢幕
        window_width = 900
        window_height = 650
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        center_x = int(screen_width / 2 - window_width / 2)
        center_y = int(screen_height / 2 - window_height / 2)
        
        self.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        self.minsize(800, 600)
        
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
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(1, weight=1)
        
        self.create_sidebar()
        self.create_home_frame()
        self.create_settings_frame()
        self.create_logs_frame()
        self.create_guide_frame()
        self.create_global_footer()
        
        # 預設顯示首頁
        self.select_frame_by_name("home")
        
        # 啟動時預先讀取資料夾內檔案數
        self.update_preview_stats()
        
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
        if hasattr(self, 'auto_open_var'):
            self.app_settings["auto_open_folder"] = self.auto_open_var.get()
        
        selected_langs = [k for k, v in self.lang_vars.items() if v.get()]
        self.app_settings["languages"] = selected_langs if selected_langs else ["en"]
        
        selected_exts = [k for k, v in self.ext_vars.items() if v.get()]
        self.app_settings["supported_extensions"] = selected_exts if selected_exts else [".jpg"]
        
        save_settings(self.app_settings)

    def create_sidebar(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
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
        
        self.copyright_label = ctk.CTkLabel(self.sidebar_frame, text="© 2026 @youzih\nAll Rights Reserved", font=("Microsoft JhengHei UI", 12), text_color="gray")
        self.copyright_label.grid(row=5, column=0, padx=20, pady=(20, 0), sticky="s")
        
        self.version_label = ctk.CTkLabel(self.sidebar_frame, text=f"版本 {APP_VERSION}", font=("Microsoft JhengHei UI", 12), text_color="gray")
        self.version_label.grid(row=6, column=0, padx=20, pady=(5, 20))

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

    def create_global_footer(self):
        self.control_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.control_frame.grid(row=1, column=1, padx=30, pady=(0, 20), sticky="ew")
        self.control_frame.grid_columnconfigure(0, weight=1)
        
        self.lbl_status = ctk.CTkLabel(self.control_frame, text="準備就緒，等待開始...", font=("Microsoft JhengHei UI", 14), text_color="gray")
        self.lbl_status.grid(row=0, column=0, columnspan=3, pady=(0, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self.control_frame, height=12, corner_radius=6)
        self.progress_bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        self.progress_bar.set(0)
        
        self.btn_start = ctk.CTkButton(self.control_frame, text="🚀 開始執行批次改名", font=("Microsoft JhengHei UI", 16, "bold"), height=50, corner_radius=10, command=self.start_processing)
        self.btn_start.grid(row=2, column=0, sticky="ew", padx=(0, 10))
        
        self.btn_cancel = ctk.CTkButton(self.control_frame, text="⛔ 停止", font=("Microsoft JhengHei UI", 16, "bold"), fg_color="#D9534F", hover_color="#C9302C", height=50, width=120, corner_radius=10, command=self.cancel_processing, state="disabled")
        self.btn_cancel.grid(row=2, column=1, padx=(0, 10))
        
        self.btn_open_folder = ctk.CTkButton(self.control_frame, text="📂 開啟輸出資料夾", font=("Microsoft JhengHei UI", 16, "bold"), fg_color="#5CB85C", hover_color="#4CAE4C", height=50, width=180, corner_radius=10, command=self.open_output_folder)
        self.btn_open_folder.grid(row=2, column=2)

    def create_logs_frame(self):
        self.logs_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.logs_frame.grid_rowconfigure(1, weight=1)
        self.logs_frame.grid_columnconfigure(0, weight=1)
        
        header_frame = ctk.CTkFrame(self.logs_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=30, pady=(30, 10), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        
        lbl_title = ctk.CTkLabel(header_frame, text="📜 處理日誌", font=self.font_title)
        lbl_title.grid(row=0, column=0, sticky="w")
        
        btn_clear_log = ctk.CTkButton(header_frame, text="🗑️ 清除畫面", font=self.font_main, width=100, command=self.clear_log_screen)
        btn_clear_log.grid(row=0, column=1, padx=(0, 10))
        
        btn_open_log = ctk.CTkButton(header_frame, text="📂 開啟日誌資料夾", font=self.font_main, width=150, fg_color="#5CB85C", hover_color="#4CAE4C", command=self.open_output_folder)
        btn_open_log.grid(row=0, column=2)
        
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
        lbl_theme.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.theme_var = ctk.StringVar(value=self.app_settings.get("theme", "Dark"))
        theme_menu = ctk.CTkOptionMenu(sys_box, values=["Dark", "Light", "System"], variable=self.theme_var, font=self.font_main, command=self.change_theme)
        theme_menu.grid(row=0, column=1, padx=0, pady=(20, 10), sticky="w")
        btn_clear_cache = ctk.CTkButton(sys_box, text="🗑️ 清除快取", font=self.font_main, fg_color="#E74C3C", hover_color="#C0392B", command=self.clear_cache)
        btn_clear_cache.grid(row=0, column=2, padx=20, pady=(20, 10), sticky="e")
        
        self.auto_open_var = ctk.BooleanVar(value=self.app_settings.get("auto_open_folder", True))
        chk_auto_open = ctk.CTkCheckBox(sys_box, text="處理完成後自動開啟輸出資料夾", variable=self.auto_open_var, font=self.font_main, command=self.save_current_settings)
        chk_auto_open.grid(row=1, column=0, columnspan=3, padx=20, pady=(10, 20), sticky="w")

    def create_guide_frame(self):
        self.guide_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.guide_frame.grid_columnconfigure(0, weight=1)
        
        lbl_title = ctk.CTkLabel(self.guide_frame, text="📖 使用說明", font=self.font_title)
        lbl_title.grid(row=0, column=0, padx=30, pady=(30, 20), sticky="w")
        
        # 歡迎區塊 (亮色吸睛)
        welcome_box = ctk.CTkFrame(self.guide_frame, corner_radius=15, fg_color="#2980B9")
        welcome_box.grid(row=1, column=0, padx=30, pady=(0, 20), sticky="ew")
        welcome_lbl = ctk.CTkLabel(welcome_box, text="✨ 歡迎使用！這是一個能幫您「全自動掃描圖片文字，並幫圖片改名」的小幫手。\n只要跟著以下三個簡單的步驟，就能輕鬆完成！", font=("Microsoft JhengHei UI", 16, "bold"), text_color="white", justify="left")
        welcome_lbl.pack(padx=20, pady=20, anchor="w")
        
        # 建立步驟卡片的輔助函式
        def create_step_card(parent, icon, title, content):
            card = ctk.CTkFrame(parent, corner_radius=15, fg_color="#2B2B2B")
            card.grid_columnconfigure(1, weight=1)
            
            lbl_icon = ctk.CTkLabel(card, text=icon, font=("Segoe UI Emoji", 40))
            lbl_icon.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="n")
            
            text_frame = ctk.CTkFrame(card, fg_color="transparent")
            text_frame.grid(row=0, column=1, padx=(0, 20), pady=20, sticky="ew")
            
            lbl_title = ctk.CTkLabel(text_frame, text=title, font=("Microsoft JhengHei UI", 18, "bold"), text_color="#3498DB")
            lbl_title.pack(anchor="w", pady=(0, 10))
            
            lbl_content = ctk.CTkLabel(text_frame, text=content, font=("Microsoft JhengHei UI", 15), text_color="#E0E0E0", justify="left")
            lbl_content.pack(anchor="w")
            
            return card

        # 步驟一
        step1_text = "• 來源資料夾：您可以點擊「瀏覽」按鈕，或直接將資料夾「拖曳」到首頁的輸入框內！\n• 輸出資料夾：拖曳資料夾後，系統會自動設定好輸出路徑，您也可以自行修改。\n• 處理模式：建議選擇「複製 (安全)」，系統只會把改名後的圖片複製過去，保留原檔。"
        card1 = create_step_card(self.guide_frame, "📁", "步驟一：設定您的資料夾", step1_text)
        card1.grid(row=2, column=0, padx=30, pady=(0, 15), sticky="ew")

        # 步驟二
        step2_text = "如果您想自訂辨識的語言 (中/英/日/韓)、支援的檔案格式 (例如 PDF)，\n或是想過濾掉特定的檔名文字，都可以前往左側的「⚙️ 進階設定」進行勾選與調整。"
        card2 = create_step_card(self.guide_frame, "⚙️", "步驟二：進階設定 (可選)", step2_text)
        card2.grid(row=3, column=0, padx=30, pady=(0, 15), sticky="ew")
        
        # 步驟三
        step3_text = "回到「🏠 控制中心」，點擊最下方大大的「🚀 開始執行批次改名」按鈕。\n處理完畢後點擊「📂 開啟輸出資料夾」，裡面會自動分類好：\n  - 📁 已辨識：成功改名的圖片\n  - 📁 未辨識：模糊或無文字的圖片\n  - 📄 辨識紀錄.txt：詳細的文字紀錄"
        card3 = create_step_card(self.guide_frame, "🚀", "步驟三：一鍵開始自動改名！", step3_text)
        card3.grid(row=4, column=0, padx=30, pady=(0, 30), sticky="ew")
        
        # Q&A 區塊
        qa_lbl = ctk.CTkLabel(self.guide_frame, text="❓ 常見問題 (Q&A)", font=("Microsoft JhengHei UI", 18, "bold"))
        qa_lbl.grid(row=5, column=0, padx=30, pady=(0, 10), sticky="w")
        
        qa_box = ctk.CTkFrame(self.guide_frame, corner_radius=15, fg_color="#1E1E1E")
        qa_box.grid(row=6, column=0, padx=30, pady=(0, 30), sticky="ew")
        qa_box.grid_columnconfigure(0, weight=1)
        
        q1 = ctk.CTkLabel(qa_box, text="Q: 處理到一半我不小心關掉視窗了怎麼辦？", font=("Microsoft JhengHei UI", 15, "bold"), text_color="#F1C40F")
        q1.pack(anchor="w", padx=20, pady=(20, 5))
        a1 = ctk.CTkLabel(qa_box, text="A: 別擔心！程式有「記憶快取功能」。重新開啟按下開始，會自動跳過已處理過的圖片。\n   若想重新處理，請至進階設定點擊「🗑️ 清除快取」。", font=("Microsoft JhengHei UI", 14), text_color="#CCCCCC", justify="left")
        a1.pack(anchor="w", padx=20, pady=(0, 15))

        q2 = ctk.CTkLabel(qa_box, text="Q: 為什麼有些圖片辨識出來的檔名怪怪的？", font=("Microsoft JhengHei UI", 15, "bold"), text_color="#F1C40F")
        q2.pack(anchor="w", padx=20, pady=(5, 5))
        a2 = ctk.CTkLabel(qa_box, text="A: 如果文字太小、有陰影或太模糊，AI 有時會辨識出亂碼。建議盡量使用清晰的圖片！", font=("Microsoft JhengHei UI", 14), text_color="#CCCCCC", justify="left")
        a2.pack(anchor="w", padx=20, pady=(0, 20))

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
            self.update_preview_stats()
            self.save_current_settings()

    def browse_source(self):
        d = filedialog.askdirectory(initialdir=self.source_var.get())
        if d: 
            self.source_var.set(d)
            self.lbl_current_path.configure(text=f"當前來源: {d}", text_color="#3498DB")
            self.update_preview_stats()
            self.save_current_settings()

    def browse_target(self):
        d = filedialog.askdirectory(initialdir=self.target_var.get())
        if d: 
            self.target_var.set(d)
            self.save_current_settings()

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

    def update_preview_stats(self):
        try:
            source_dir = Path(self.source_var.get())
            if not source_dir.exists() or not source_dir.is_dir():
                self.val_total.configure(text="0")
                self.lbl_status.configure(text="尚未選擇有效的來源資料夾", text_color="gray")
                return

            exts = [k for k, v in self.ext_vars.items() if v.get()] if hasattr(self, 'ext_vars') else self.app_settings.get("supported_extensions", [".jpg"])
            if not exts: exts = [".jpg"]
            
            image_paths = [p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
            total_images = len(image_paths)
            
            self.val_total.configure(text=str(total_images))
            self.val_success.configure(text="0")
            self.val_failed.configure(text="0")
            
            if total_images > 0:
                self.lbl_status.configure(text=f"✅ 準備就緒！共掃描到 {total_images} 個檔案，等待開始", text_color="#2ECC71")
            else:
                self.lbl_status.configure(text="⚠️ 警告：此資料夾內沒有找到支援的圖片格式！", text_color="#E74C3C")
        except Exception as e:
            pass

    def clear_log_screen(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def process_queue(self):
        try:
            while True:
                msg, stats = self.update_queue.get_nowait()
                if msg == "PROCESS_DONE":
                    self.is_processing = False
                    self.btn_start.configure(state="normal", text="🚀 開始執行批次改名")
                    self.btn_cancel.configure(state="disabled", text="⛔ 停止")
                    self.lbl_status.configure(text="✅ 所有任務已處理完畢！", text_color="#2ECC71")
                    self.progress_bar.configure(progress_color="#2ECC71")
                    self.progress_bar.set(1.0)
                    
                    if hasattr(self, 'auto_open_var') and self.auto_open_var.get():
                        self.open_output_folder()
                    messagebox.showinfo("完成通知", "🎉 所有圖片已批次改名完畢！", parent=self)
                    
                elif msg:
                    self.update_log(msg)
                    if "初始化" in msg or "成功載入" in msg:
                        self.lbl_status.configure(text="⏳ " + msg, text_color="#F1C40F")
                        self.progress_bar.configure(progress_color="#F1C40F")
                    elif "處理已終止" in msg:
                        self.lbl_status.configure(text="⛔ 處理已強制終止", text_color="#E74C3C")
                        self.progress_bar.configure(progress_color="#E74C3C")
                
                if stats:
                    success, failed, total = stats
                    processed = success + failed
                    if total > 0: 
                        progress_val = processed / total
                        self.progress_bar.set(progress_val)
                        if progress_val < 1.0 and processed > 0:
                            elapsed = time.time() - self.start_time
                            speed = processed / elapsed if elapsed > 0 else 0
                            remain = total - processed
                            eta = remain / speed if speed > 0 else 0
                            eta_str = f"{int(eta)} 秒" if eta < 60 else f"{int(eta//60)} 分 {int(eta%60)} 秒"
                            self.lbl_status.configure(text=f"🔄 處理中... ({processed}/{total}) | ⚡ {speed:.1f} 張/秒 | ⏳ 剩餘約 {eta_str}", text_color="#3498DB")
                            self.progress_bar.configure(progress_color="#3498DB")
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
            self.lbl_status.configure(text="⚠️ 正在強制中斷，請稍候...", text_color="#E74C3C")
            self.progress_bar.configure(progress_color="#E74C3C")
            self.update_log("⚠️ 觸發停止，等待當前任務結束...")

    def start_processing(self):
        if self.is_processing: return
        self.is_processing = True
        
        self.start_time = time.time()
        self.save_current_settings()
        self.btn_start.configure(state="disabled", text="處理中，請稍候...")
        self.btn_cancel.configure(state="normal", text="⛔ 停止")
        self.lbl_status.configure(text="⏳ 準備啟動 AI 引擎...", text_color="#F1C40F")
        self.progress_bar.configure(progress_color="#3498DB")
        self.progress_bar.set(0)
        self.update_log("--------------------------------")
        
        # 自動跳轉到處理日誌頁面，讓使用者可以即時預覽進度
        self.select_frame_by_name("logs")
        
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
