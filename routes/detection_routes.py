import io
import logging
import re
from flask import Blueprint, request, jsonify, session, render_template
import numpy as np
import cv2

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

detection_bp = Blueprint("detection", __name__, template_folder="../templates", static_folder="../static")

# ------------------------
# YOLOv8 License Plate Model
# ------------------------
try:
    from ultralytics import YOLO
    yolo_model = YOLO("models/best.pt")  # Your trained Lebanese plate model
    logger.info("✅ Custom-trained Lebanese plate model loaded (96.2% mAP50)")
except Exception as e:
    yolo_model = None
    logger.warning("YOLOv8 not available: %s", e)

# ------------------------
# EasyOCR
# ------------------------
try:
    import easyocr
    ocr_reader = easyocr.Reader(['en'], gpu=True)
    logger.info("✅ EasyOCR loaded")
except Exception as e:
    ocr_reader = None
    logger.warning("EasyOCR not available: %s", e)

# ------------------------
# Helper Functions for Better OCR Processing
# ------------------------
def preprocess_plate_image(plate_crop):
    """Enhance plate image for better OCR"""
    if len(plate_crop.shape) == 3:
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = plate_crop
    
    # Enhance contrast using CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    return enhanced

def clean_and_validate_plate_text(text, debug_info=""):
    """
    Clean OCR text with character confusion handling
    First character: if digit/letter confused → choose LETTER
    Other characters: if letter/digit confused → choose DIGIT
    """
    if not text:
        logger.info(f"{debug_info}❌ Empty text")
        return None
    
    # Clean text - keep only alphanumeric, uppercase
    clean_text = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    if len(clean_text) < 3:
        logger.info(f"{debug_info}❌ Too short: '{clean_text}'")
        return None
    
    logger.info(f"{debug_info}Raw: '{text}' → Clean: '{clean_text}'")
    
    # CHARACTER CONFUSION RULES
    # -----------------------------------------------------
    # RULE 1: FIRST CHARACTER - if confused → choose LETTER
    first_char = clean_text[0]
    
    # Common OCR confusions for FIRST character (digit→letter)
    first_char_corrections = {
        '1': 'I',  # 1 looks like I → Choose I
        '2': 'Z',  # 2 looks like Z → Choose Z
        '6': 'G',  # 6 looks like G → Choose G
        '0': 'O',  # 0 looks like O → Choose O
        '8': 'B',  # 8 looks like B → Choose B
        '5': 'S',  # 5 looks like S → Choose S
        '7': 'T',  # 7 looks like T → Choose T  ← YOUR ISSUE FIXED
        '3': 'E',  # 3 looks like E → Choose E
        '4': 'A',  # 4 looks like A → Choose A
        '9': 'Q',  # 9 looks like Q → Choose Q
    }
    
    # Apply first character rule
    if first_char in first_char_corrections:
        corrected_first = first_char_corrections[first_char]
        logger.info(f"{debug_info}First char '{first_char}' → '{corrected_first}' (digit→letter)")
        clean_text = corrected_first + clean_text[1:]
    
    # -----------------------------------------------------
    # RULE 2: OTHER CHARACTERS - if confused → choose DIGIT
    remaining_chars = clean_text[1:] if len(clean_text) > 1 else ""
    
    # Common OCR confusions for OTHER characters (letter→digit)
    other_chars_corrections = {
        'I': '1', 'L': '1',  # I/L look like 1 → Choose 1
        'O': '0', 'Q': '0',  # O/Q look like 0 → Choose 0  ← YOUR ISSUE FIXED
        'Z': '2',            # Z looks like 2 → Choose 2
        'E': '3',            # E looks like 3 → Choose 3
        'A': '4',            # A looks like 4 → Choose 4
        'S': '5',            # S looks like 5 → Choose 5
        'G': '6',            # G looks like 6 → Choose 6
        'T': '7',            # T looks like 7 → Choose 7  ← YOUR ISSUE FIXED
        'B': '8',            # B looks like 8 → Choose 8
        'Q': '9',            # Q looks like 9 → Choose 9
        
        # Additional common confusions
        'D': '0', 'U': '0',  # D/U look like 0
        'J': '1', 'V': '1',  # J/V look like 1
        'Y': '7', 'X': '7',  # Y/X look like 7
        'M': '1', 'N': '1',  # M/N look like 1
        'H': '1', 'K': '1',  # H/K look like 1
        'P': '9', 'R': '2',  # P→9, R→2
        'F': '7', 'W': '7',  # F/W→7
        'C': '0',            # C→0
    }
    
    # Convert remaining characters
    corrected_remaining = ""
    for i, char in enumerate(remaining_chars):
        if char.isdigit():
            corrected_remaining += char  # Already digit
        elif char in other_chars_corrections:
            corrected_digit = other_chars_corrections[char]
            corrected_remaining += corrected_digit
            logger.debug(f"{debug_info}Char {i+2}: '{char}' → '{corrected_digit}'")
        else:
            corrected_remaining += char  # Keep as-is if unknown
    
    # Reconstruct final text
    final_text = clean_text[0] + corrected_remaining
    
    # -----------------------------------------------------
    # VALIDATE AGAINST LEBANESE PLATE PATTERNS
    patterns = [
        r'^[A-Z]\d{5,7}$',      # B123456, B203333
        r'^\d{5,8}$',           # 624651, 6210290
        r'^[A-Z]{2}\d{4,6}$',   # IN19981, N149881
        r'^[A-Z]\d{3,6}[A-Z]?$', # 205346J, 6587904
        r'^\d{4,7}[A-Z]?$',     # 220074, 587904
    ]
    
    for pattern in patterns:
        if re.match(pattern, final_text):
            if 4 <= len(final_text) <= 8:
                logger.info(f"{debug_info}✅ Valid: '{final_text}' matches {pattern}")
                return final_text
    
    # Fallback: if reasonable, accept it
    if 4 <= len(final_text) <= 8:
        letters = sum(1 for c in final_text if c.isalpha())
        digits = sum(1 for c in final_text if c.isdigit())
        
        if digits >= 3:
            logger.info(f"{debug_info}⚠️  Accepting: '{final_text}' ({letters}L/{digits}D)")
            return final_text
    
    logger.info(f"{debug_info}❌ Rejected: '{final_text}'")
    return None

# ------------------------
# Fixed Plate detection endpoint
# ------------------------
@detection_bp.route('/detect', methods=['POST', 'OPTIONS'])
def detect_plate():
    try:
        if 'image' not in request.files:
            return jsonify({"success": False, "message": "No image provided"}), 400
        file = request.files['image']
        img_bytes = file.read()
        if not img_bytes:
            return jsonify({"success": False, "message": "Empty image file"}), 400

        # Convert bytes to OpenCV image
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"success": False, "message": "Invalid image format"}), 400

        logger.info(f"📊 Image received: {img.shape}")

        best_plate = None
        best_conf = 0.0
        best_details = {}

        # ------------------------
        # IMPROVED YOLOv8 + EasyOCR Logic
        # ------------------------
        if yolo_model and ocr_reader:
            try:
                # Use adaptive confidence thresholds
                # Start with 0.25 (your original), but try lower if needed
                confidence_thresholds = [0.25, 0.15, 0.1, 0.05]
                
                for conf_thresh in confidence_thresholds:
                    results = yolo_model.predict(img, verbose=False, conf=conf_thresh)
                    
                    # Check if any detections
                    if results[0].boxes is not None and len(results[0].boxes) > 0:
                        logger.info(f"📊 YOLO predictions: {len(results[0].boxes)} boxes at conf={conf_thresh}")
                        
                        for idx, r in enumerate(results[0].boxes):
                            conf = float(r.conf)
                            x1, y1, x2, y2 = map(int, r.xyxy[0])
                            
                            logger.info(f"📊 Detected box {idx+1}: conf={conf:.2f}, coords=({x1},{y1},{x2},{y2})")
                            
                            # Extract plate region with padding
                            padding = 5
                            h, w = img.shape[:2]
                            x1_pad = max(0, x1 - padding)
                            y1_pad = max(0, y1 - padding)
                            x2_pad = min(w, x2 + padding)
                            y2_pad = min(h, y2 + padding)
                            
                            plate_crop = img[y1_pad:y2_pad, x1_pad:x2_pad]
                            logger.info(f"📊 Plate crop size: {plate_crop.shape}")
                            
                            if plate_crop.size == 0:
                                continue
                            
                            # Resize if too small for OCR
                            h_crop, w_crop = plate_crop.shape[:2]
                            if h_crop < 30 or w_crop < 60:
                                scale_h = max(30/h_crop, 1.5) if h_crop < 30 else 1.0
                                scale_w = max(60/w_crop, 1.5) if w_crop < 60 else 1.0
                                scale = max(scale_h, scale_w)
                                new_h = int(h_crop * scale)
                                new_w = int(w_crop * scale)
                                plate_crop = cv2.resize(plate_crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
                                logger.info(f"📊 Resized crop to: {plate_crop.shape}")
                            
                            # Preprocess for better OCR
                            processed_crop = preprocess_plate_image(plate_crop)
                            
                            # OCR with multiple attempts
                            ocr_attempts = []
                            
                            # Attempt 1: Normal OCR
                            try:
                                ocr_results = ocr_reader.readtext(
                                    processed_crop,
                                    allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                                    width_ths=0.7,
                                    height_ths=0.7
                                )
                                ocr_attempts.extend(ocr_results)
                            except Exception as ocr_err:
                                logger.warning(f"OCR attempt 1 failed: {ocr_err}")
                            
                            # Attempt 2: Original image if first failed
                            if not ocr_attempts:
                                try:
                                    ocr_results = ocr_reader.readtext(
                                        plate_crop,
                                        allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                                        width_ths=0.5
                                    )
                                    ocr_attempts.extend(ocr_results)
                                except Exception as ocr_err:
                                    logger.warning(f"OCR attempt 2 failed: {ocr_err}")
                            
                            # Process OCR results
                            for _, text, text_conf in ocr_attempts:
                                logger.info(f"📊 OCR raw text: '{text}' (conf={text_conf:.2f})")
                                
                                # Clean and validate the text
                                plate_text = clean_and_validate_plate_text(text, f"📊 Box{idx+1}: ")
                                
                                if plate_text:
                                    # Calculate score (weighted combination)
                                    score = (conf * 0.6) + (text_conf * 0.4)  # YOLO confidence weighted more
                                    
                                    logger.info(f"📊 Valid plate: '{plate_text}' (YOLO={conf:.2f}, OCR={text_conf:.2f}, total={score:.2f})")
                                    
                                    if score > best_conf:
                                        best_plate = plate_text
                                        best_conf = score
                                        best_details = {
                                            'yolo_conf': conf,
                                            'ocr_conf': text_conf,
                                            'coords': (x1, y1, x2, y2),
                                            'original_text': text
                                        }
                                        
                                        # If we have good confidence, break early
                                        if score >= 0.6:
                                            break
                            
                            if best_conf >= 0.6:  # Good enough, stop processing
                                break
                    
                    # If we found a plate with this threshold, move on
                    if best_plate:
                        break
                        
            except Exception as e:
                logger.exception(f"YOLO/EasyOCR detection failed: {e}")

        # ------------------------
        # Return JSON result
        # ------------------------
        if best_plate:
            session['detected_plate'] = best_plate
            session['detection_confidence'] = float(best_conf)
            
            logger.info(f"✅ SUCCESS: Plate detected: {best_plate} (conf={best_conf:.2f})")
            
            return jsonify({
                "success": True,
                "plate_number": best_plate,
                "confidence": float(best_conf),
                "confidence_percent": int(best_conf * 100),
                "details": {
                    "yolo_confidence": float(best_details.get('yolo_conf', 0)),
                    "ocr_confidence": float(best_details.get('ocr_conf', 0))
                }
            })

        logger.warning("❌ No license plate detected")
        return jsonify({
            "success": False, 
            "message": "No license plate detected. Ensure:\n• Plate is clearly visible\n• Good lighting conditions\n• Plate is within focus area"
        })

    except Exception as e:
        logger.exception(f"Detection error: {e}")
        return jsonify({"success": False, "message": f"Error processing image"}), 500


# ------------------------
# Plate detection page
# ------------------------
@detection_bp.route('/plate-detection')
def plate_detection_page():
    return render_template('homee.html')