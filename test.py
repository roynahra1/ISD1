# find_real_problem.py
import cv2
import numpy as np
from ultralytics import YOLO
import os
import easyocr
from pathlib import Path
import time

print("🔍 COMPREHENSIVE VALIDATION SET DIAGNOSTIC")
print("=" * 70)

# 1. Load your model
start_time = time.time()
model = YOLO("models/best.pt")
print(f"✅ Model loaded ({time.time()-start_time:.1f}s)")

# 2. Initialize EasyOCR
try:
    ocr_reader = easyocr.Reader(['en'], gpu=True)
    print("✅ EasyOCR loaded")
except Exception as e:
    ocr_reader = None
    print(f"⚠️ EasyOCR not available: {e}")

# 3. Set validation image path
val_folder = r"C:\Users\ADMIN\Downloads\Lebanese Plates Detection.v1-lb-plate.csv.yolov8\valid\images"
labels_folder = r"C:\Users\ADMIN\Downloads\Lebanese Plates Detection.v1-lb-plate.csv.yolov8\valid\labels"

# Check if path exists
if not os.path.exists(val_folder):
    print(f"❌ Validation folder not found: {val_folder}")
    # Try alternative path
    val_folder = r"C:\Users\ADMIN\Downloads\Lebanese Plates Detection.v1-lb-plate.csv.yolov8\valid\images"
    if not os.path.exists(val_folder):
        print(f"❌ Still not found. Check your path.")
        exit()

# 4. Get all validation images
val_images = [f for f in os.listdir(val_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
print(f"\n📊 Found {len(val_images)} validation images")
print("-" * 70)

# 5. Statistics tracking
stats = {
    'total': 0,
    'detected': 0,
    'detected_with_high_conf': 0,
    'ocr_success': 0,
    'conf_sum': 0,
    'detection_times': []
}

# 6. Process each image
for img_idx, img_name in enumerate(val_images[:20]):  # Limit to first 20 for testing
    img_path = os.path.join(val_folder, img_name)
    print(f"\n{'='*70}")
    print(f"IMAGE {img_idx+1}/{min(20, len(val_images))}: {img_name}")
    print(f"{'='*70}")
    
    # Load image
    img = cv2.imread(img_path)
    if img is None:
        print(f"❌ Failed to load: {img_name}")
        continue
    
    stats['total'] += 1
    print(f"Size: {img.shape}")
    
    # Check corresponding label file for ground truth
    label_path = os.path.join(labels_folder, img_name.replace('.jpg', '.txt').replace('.png', '.txt'))
    ground_truth = []
    if os.path.exists(label_path):
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    # YOLO format: class x_center y_center width height (normalized)
                    class_id = int(parts[0])
                    x_center = float(parts[1])
                    y_center = float(parts[2])
                    width = float(parts[3])
                    height = float(parts[4])
                    
                    # Convert to pixel coordinates
                    img_h, img_w = img.shape[:2]
                    x1 = int((x_center - width/2) * img_w)
                    y1 = int((y_center - height/2) * img_h)
                    x2 = int((x_center + width/2) * img_w)
                    y2 = int((y_center + height/2) * img_h)
                    
                    ground_truth.append({
                        'class': class_id,
                        'coords': (x1, y1, x2, y2),
                        'size': f"{x2-x1}x{y2-y1}"
                    })
        if ground_truth:
            print(f"📝 Ground truth: {len(ground_truth)} plate(s) marked in labels")
    
    # 7. Test with ADAPTIVE confidence thresholds (like your Flask app should)
    print("\n🔍 YOLO DETECTION TEST:")
    print("-" * 40)
    
    detection_start = time.time()
    best_detection = None
    best_conf = 0
    best_coords = None
    
    # Try multiple confidence thresholds (adaptive approach)
    confidence_levels = [0.5, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05]
    
    for conf_threshold in confidence_levels:
        results = model.predict(img, conf=conf_threshold, verbose=False)
        
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            # Get the highest confidence detection
            max_idx = np.argmax([float(box.conf) for box in results[0].boxes])
            current_conf = float(results[0].boxes[max_idx].conf)
            
            if current_conf > best_conf:
                best_conf = current_conf
                best_detection = results[0].boxes[max_idx]
                best_coords = list(map(int, best_detection.xyxy[0]))
                used_threshold = conf_threshold
                
            if current_conf >= 0.5:  # Good enough confidence, stop
                break
    
    detection_time = time.time() - detection_start
    stats['detection_times'].append(detection_time)
    
    # 8. Process results
    if best_detection:
        stats['detected'] += 1
        stats['conf_sum'] += best_conf
        if best_conf >= 0.5:
            stats['detected_with_high_conf'] += 1
        
        x1, y1, x2, y2 = best_coords
        print(f"✅ DETECTED with conf={used_threshold}")
        print(f"   Confidence: {best_conf:.3f}")
        print(f"   Detection time: {detection_time:.3f}s")
        print(f"   Coordinates: ({x1}, {y1}) to ({x2}, {y2})")
        print(f"   Plate size: {x2-x1}x{y2-y1} pixels")
        
        # Extract plate region
        plate_crop = img[y1:y2, x1:x2]
        
        # Save visualization
        result_img = img.copy()
        cv2.rectangle(result_img, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(result_img, f"Conf: {best_conf:.2f}", (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Draw ground truth if available
        for gt in ground_truth:
            gt_x1, gt_y1, gt_x2, gt_y2 = gt['coords']
            cv2.rectangle(result_img, (gt_x1, gt_y1), (gt_x2, gt_y2), (255, 0, 0), 2)
            cv2.putText(result_img, "GT", (gt_x1, gt_y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        # Create output directory
        output_dir = "validation_results"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save results
        base_name = os.path.splitext(img_name)[0]
        cv2.imwrite(f"{output_dir}/{base_name}_detected.jpg", result_img)
        cv2.imwrite(f"{output_dir}/{base_name}_plate.jpg", plate_crop)
        
        # 9. Perform OCR if available
        if ocr_reader and plate_crop.shape[0] > 10 and plate_crop.shape[1] > 10:
            print("\n   🔤 OCR PROCESSING:")
            
            # Preprocess for OCR
            if len(plate_crop.shape) == 3:
                gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
            else:
                gray = plate_crop
            
            # Multiple preprocessing attempts
            ocr_texts = []
            
            # Try 1: Original grayscale
            try:
                results1 = ocr_reader.readtext(
                    gray, 
                    allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                    width_ths=0.7
                )
                ocr_texts.extend([(text, conf, 'gray') for _, text, conf in results1])
            except:
                pass
            
            # Try 2: Enhanced contrast
            try:
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
                enhanced = clahe.apply(gray)
                results2 = ocr_reader.readtext(
                    enhanced, 
                    allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                    width_ths=0.7
                )
                ocr_texts.extend([(text, conf, 'enhanced') for _, text, conf in results2])
            except:
                pass
            
            # Try 3: Thresholded
            try:
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                results3 = ocr_reader.readtext(
                    binary, 
                    allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                    width_ths=0.7
                )
                ocr_texts.extend([(text, conf, 'binary') for _, text, conf in results3])
            except:
                pass
            
            # Process OCR results
            if ocr_texts:
                # Sort by confidence
                ocr_texts.sort(key=lambda x: x[1], reverse=True)
                
                print(f"   Found {len(ocr_texts)} OCR segments:")
                for i, (text, conf, method) in enumerate(ocr_texts[:3]):  # Top 3
                    print(f"   {i+1}. '{text}' (conf: {conf:.2f}, method: {method})")
                
                # Take the best OCR result
                best_text, best_ocr_conf, best_method = ocr_texts[0]
                clean_text = ''.join([c for c in best_text.upper() if c.isalnum()])
                
                if len(clean_text) >= 3:  # Reasonable plate length
                    stats['ocr_success'] += 1
                    print(f"\n   🎯 BEST OCR RESULT: '{clean_text}'")
                    print(f"   Method: {best_method}, Confidence: {best_ocr_conf:.2f}")
                    
                    # Add OCR text to image
                    cv2.putText(result_img, f"OCR: {clean_text}", (x1, y2+30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
                    cv2.imwrite(f"{output_dir}/{base_name}_with_ocr.jpg", result_img)
                else:
                    print("   ⚠️  OCR text too short")
            else:
                print("   ❌ No OCR text found")
        else:
            print("   ⚠️  OCR skipped")
            
    else:
        print("❌ NO PLATE DETECTED")
        print(f"   Tried thresholds: {confidence_levels}")
        
        # Save failed detection for analysis
        output_dir = "validation_results"
        os.makedirs(output_dir, exist_ok=True)
        cv2.imwrite(f"{output_dir}/{os.path.splitext(img_name)[0]}_failed.jpg", img)
    
    print(f"\n⏱️  Total processing time: {time.time()-start_time:.2f}s")

# 10. Final Statistics
print("\n" + "=" * 70)
print("📈 FINAL STATISTICS")
print("=" * 70)

if stats['total'] > 0:
    detection_rate = (stats['detected'] / stats['total']) * 100
    high_conf_rate = (stats['detected_with_high_conf'] / stats['total']) * 100
    avg_confidence = stats['conf_sum'] / stats['detected'] if stats['detected'] > 0 else 0
    avg_detection_time = np.mean(stats['detection_times']) if stats['detection_times'] else 0
    ocr_success_rate = (stats['ocr_success'] / stats['detected']) * 100 if stats['detected'] > 0 else 0
    
    print(f"Images processed: {stats['total']}")
    print(f"Plates detected: {stats['detected']}/{stats['total']} ({detection_rate:.1f}%)")
    print(f"High confidence (≥0.5): {stats['detected_with_high_conf']} ({high_conf_rate:.1f}%)")
    print(f"Average confidence: {avg_confidence:.3f}")
    print(f"Average detection time: {avg_detection_time:.3f}s")
    print(f"OCR successful: {stats['ocr_success']}/{stats['detected']} ({ocr_success_rate:.1f}%)")
    
    print(f"\n📁 Results saved in: validation_results/")
    print(f"   • [image_name]_detected.jpg - Detection visualization")
    print(f"   • [image_name]_plate.jpg - Cropped plate")
    print(f"   • [image_name]_with_ocr.jpg - Image with OCR result")
    print(f"   • [image_name]_failed.jpg - Images where detection failed")

print("\n" + "=" * 70)
print("🔧 RECOMMENDATIONS BASED ON RESULTS:")
print("-" * 70)

if detection_rate < 90:
    print("1. ⚠️ Detection rate is low - Consider:")
    print("   • Lowering confidence threshold in Flask app")
    print("   • Adding image preprocessing in detection_routes.py")
    print("   • Training model with more varied data")
    
if avg_confidence < 0.5:
    print("2. ⚠️ Average confidence is low - Your model is uncertain")
    print("   • Use adaptive thresholds (as shown in this script)")
    print("   • Implement confidence-weighted results in Flask")
    
if ocr_success_rate < 70:
    print("3. ⚠️ OCR success rate is low - Improve OCR pipeline:")
    print("   • Add better preprocessing in detection_routes.py")
    print("   • Try multiple OCR methods and pick best")
    print("   • Post-process OCR results (remove noise, validate format)")

print("\n4. ✅ For your Flask app, implement:")
print("   • Adaptive confidence thresholds (not fixed 0.25)")
print("   • Multiple OCR attempts with different preprocessing")
print("   • Better logging of confidence scores")