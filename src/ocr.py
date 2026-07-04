import easyocr

class OCREngine:
    def __init__(self, languages: list[str] = None):
        """初始化 OCR 引擎。預設使用繁體中文與英文。"""
        import torch
        if languages is None:
            languages = ["ch_tra", "en"]
        print("正在載入 OCR 辨識引擎（首次執行會下載模型，請稍候）...")
        self.use_gpu = torch.cuda.is_available()
        self.reader = easyocr.Reader(languages, gpu=self.use_gpu)
        print(f"OCR 辨識引擎載入成功！(使用 {'GPU' if self.use_gpu else 'CPU'})")

    def extract_text(self, image_path: str) -> str:
        """從圖片中提取文字，並以空白組合所有辨識到的片段。"""
        import cv2
        import numpy as np
        
        if image_path.lower().endswith('.pdf'):
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(image_path)
            if len(pdf) > 0:
                page = pdf[0]
                pil_img = page.render(scale=2).to_pil()
                img = np.array(pil_img)
            else:
                raise ValueError("PDF 檔案沒有頁面")
        else:
            # 嘗試使用 OpenCV 讀取 (處理中文路徑)
            img_array = np.fromfile(image_path, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if img is None:
                # 啟用自動轉檔機制
                try:
                    from PIL import Image
                    pil_img = Image.open(image_path).convert("RGB")
                    img = np.array(pil_img)
                except Exception as e:
                    raise ValueError(f"無法讀取該圖片，檔案可能已損壞或不支援: {e}")
            
        results = self.reader.readtext(img)
        recognized_text = " ".join([res[1] for res in results])
        return recognized_text
