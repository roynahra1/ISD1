import cv2
import pytesseract
import numpy as np
import re
import logging
import os
import shutil

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class WorkingPlateDetector:
    def __init__(self):
        self.initialized = False
        self.min_confidence = 0.5
        self._configure_tesseract()

    def _configure_tesseract(self):
        try:
            if os.name == 'nt':
                possible_paths = [
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
                ]
                for p in possible_paths:
                    if os.path.exists(p):
                        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                        self.initialized = True
                        logger.info("Configured tesseract at %s", p)
                        return
            if shutil.which("tesseract"):
                self.initialized = True
                logger.info("Found tesseract in PATH")
                return
            logger.warning("Tesseract not found; plate_detector will be disabled until installed.")
        except Exception as e:
            logger.error("Tesseract configure error: %s", e)

    def preprocess_image(self, image):
        try:
            img = image.copy()
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            h, w = gray.shape
            if max(h, w) < 400:
                scale = 400.0 / max(h, w)
                gray = cv2.resize(gray, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
            blurred = cv2.GaussianBlur(gray, (3,3), 0)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(blurred)
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            kernel = np.ones((2,2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            return cleaned
        except Exception as e:
            logger.error("Preprocess error: %s", e)
            return image

    def _safe_conf(self, val):
        try:
            if val is None:
                return 0.0
            s = str(val).strip()
            if s == "" or s == "-1":
                return 0.0
            v = float(s)
            if v > 1.0:
                v = v / 100.0
            return max(0.0, min(1.0, v))
        except Exception:
            return 0.0

    def clean_text(self, text):
        if not text:
            return ""
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        return cleaned

    def is_valid_plate(self, text):
        if not text or len(text) < 4 or len(text) > 8:
            return False
        has_letters = any(c.isalpha() for c in text)
        has_digits = any(c.isdigit() for c in text)
        if not (has_letters and has_digits):
            return False
        patterns = [
            r'^[A-Z]{1,3}\d{1,4}$',
            r'^\d{3,4}[A-Z]{1,2}$',
            r'^[A-Z]{1,2}\d{2}[A-Z]{1,2}$'
        ]
        return any(re.match(p, text) for p in patterns)

    def ocr_region(self, region):
        try:
            proc = self.preprocess_image(region)
            configs = [
                '--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            ]
            best_text = None
            best_conf = 0.0
            for cfg in configs:
                data = pytesseract.image_to_data(proc, config=cfg, output_type=pytesseract.Output.DICT)
                texts = data.get('text', [])
                confs = data.get('conf', [])
                for i, t in enumerate(texts):
                    if not t or str(t).strip() == "":
                        continue
                    conf = self._safe_conf(confs[i] if i < len(confs) else None)
                    if conf < self.min_confidence:
                        continue
                    cleaned = self.clean_text(t)
                    if self.is_valid_plate(cleaned) and conf > best_conf:
                        best_text = cleaned
                        best_conf = conf
            return best_text, best_conf
        except Exception as e:
            logger.error("OCR region error: %s", e)
            return None, 0.0

    def detect_plate(self, image):
        if not self.initialized:
            logger.error("Tesseract not initialized")
            return None, 0.0
        h, w = image.shape[:2]
        if w > 1200:
            scale = 1200 / w
            image = cv2.resize(image, (1200, int(h*scale)))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        v = np.median(gray)
        lower = int(max(0, 0.66*v))
        upper = int(min(255, 1.33*v))
        edges = cv2.Canny(gray, lower, upper)
        kernel = np.ones((3,3), np.uint8)
        dil = cv2.dilate(edges, kernel, iterations=2)
        cnts, _ = cv2.findContours(dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for c in cnts:
            x,y,wc,hc = cv2.boundingRect(c)
            if hc == 0: continue
            ar = float(wc)/float(hc)
            area = wc*hc
            img_area = image.shape[0]*image.shape[1]
            if 2.0 <= ar <= 6.0 and 0.001 < (area/img_area) < 0.5 and wc>=60 and hc>=20:
                candidates.append((x,y,wc,hc))
        candidates = sorted(candidates, key=lambda r: r[2]*r[3], reverse=True)
        best_text = None
        best_conf = 0.0
        for (x,y,wc,hc) in candidates:
            ex = 8
            x1 = max(0, x-ex); y1 = max(0, y-ex)
            x2 = min(image.shape[1], x+wc+ex); y2 = min(image.shape[0], y+hc+ex)
            region = image[y1:y2, x1:x2]
            txt, conf = self.ocr_region(region)
            if txt and conf > best_conf:
                best_text = txt; best_conf = conf
        if not best_text:
            txt, conf = self.ocr_region(image)
            if txt and conf > best_conf:
                best_text = txt; best_conf = conf
        return best_text, best_conf

plate_detector = WorkingPlateDetector()
