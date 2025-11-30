import cv2
import pytesseract
import numpy as np
import re
import logging

# Configure Tesseract path for Windows (adjust if needed)
try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except:
    pass  # Use system PATH

logger = logging.getLogger(__name__)

class SimplePlateDetector:
    def __init__(self):
        self.initialized = True
        logger.info("✅ Simple Plate Detector Ready (Tesseract only)")
    
    def preprocess_image(self, image):
        """Basic image preprocessing"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Apply threshold
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def clean_text(self, text):
        """Clean detected text"""
        if not text:
            return ""
        # Keep only alphanumeric characters
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        return cleaned
    
    def is_valid_plate(self, text):
        """Validate license plate format"""
        if not text or len(text) < 4 or len(text) > 8:
            return False
        
        # Must have both letters and numbers
        has_letters = any(c.isalpha() for c in text)
        has_numbers = any(c.isdigit() for c in text)
        
        if not (has_letters and has_numbers):
            return False
        
        # Common plate patterns
        patterns = [
            r'^[A-Z]{2,3}\d{1,4}$',    # ABC123
            r'^[A-Z]{1,2}\d{3,4}$',    # A1234
            r'^\d{3,4}[A-Z]{1,2}$',    # 123AB
        ]
        
        return any(re.match(pattern, text) for pattern in patterns)
    
    def detect_plate(self, image):
        """Simple plate detection using Tesseract"""
        try:
            # Preprocess image
            processed = self.preprocess_image(image)
            
            # Try multiple Tesseract configurations
            configs = [
                '--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
            ]
            
            best_plate = None
            best_confidence = 0
            
            for config in configs:
                try:
                    # Get text with confidence
                    data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT, config=config)
                    
                    for i, text in enumerate(data['text']):
                        text = text.strip()
                        if not text:
                            continue
                        
                        confidence = float(data['conf'][i]) / 100.0
                        cleaned = self.clean_text(text)
                        
                        if self.is_valid_plate(cleaned) and confidence > best_confidence:
                            best_plate = cleaned
                            best_confidence = confidence
                            logger.info(f"✅ Found plate: {cleaned} (conf: {confidence:.2f})")
                            
                except Exception as e:
                    logger.warning(f"Tesseract config failed: {e}")
                    continue
            
            if best_plate and best_confidence > 0.3:
                return best_plate, best_confidence
            else:
                return None, 0.0
                
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return None, 0.0

# Create detector instance
plate_detector = SimplePlateDetector()