import io
import logging
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
    yolo_model = YOLO("models/yolov8_lp.pt")  # <-- your downloaded YOLOv8 model
    logger.info("✅ YOLOv8 license plate model loaded from models/yolov8_lp.pt")
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
# Fallback Tesseract-based detector
# ------------------------
from plate_detector import plate_detector

# ------------------------
# Plate detection endpoint
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

        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"success": False, "message": "Invalid image format"}), 400

        best_plate = None
        best_conf = 0.0

        # ------------------------
        # 1️⃣ YOLOv8 + EasyOCR
        # ------------------------
        if yolo_model and ocr_reader:
            try:
                results = yolo_model.predict(img, verbose=False)
                for r in results[0].boxes:
                    conf = float(r.conf)
                    x1, y1, x2, y2 = map(int, r.xyxy[0])
                    plate_crop = img[y1:y2, x1:x2]

                    # Resize crop for better OCR
                    h, w = plate_crop.shape[:2]
                    if h < 50:
                        scale = 50 / h
                        plate_crop = cv2.resize(plate_crop, (int(w*scale), 50))

                    ocr_results = ocr_reader.readtext(plate_crop, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                    for _, text, text_conf in ocr_results:
                        plate_text = ''.join([c for c in text.upper() if c.isalnum()])
                        if len(plate_text) >= 4 and text_conf*conf > best_conf:
                            best_plate = plate_text
                            best_conf = text_conf*conf
            except Exception as e:
                logger.warning("YOLO/EasyOCR detection failed: %s", e)

        # ------------------------
        # 2️⃣ Fallback Tesseract detector
        # ------------------------
        if not best_plate and plate_detector and plate_detector.initialized:
            plate_text, conf = plate_detector.detect_plate(img)
            if plate_text:
                best_plate = plate_text
                best_conf = conf

        # ------------------------
        # 3️⃣ Return JSON Result
        # ------------------------
        if best_plate:
            session['detected_plate'] = best_plate
            session['detection_confidence'] = float(best_conf)
            return jsonify({
                "success": True,
                "plate_number": best_plate,
                "confidence": float(best_conf),
                "confidence_percent": int(best_conf*100)
            })

        return jsonify({"success": False, "message": "No license plate detected. Ensure the plate is clear and retry."})

    except Exception as e:
        logger.exception("Detection error: %s", e)
        return jsonify({"success": False, "message": f"Error processing image: {e}"}), 500

# ------------------------
# Plate detection page
# ------------------------
@detection_bp.route('/plate-detection')
def plate_detection_page():
    return render_template('homee.html')
