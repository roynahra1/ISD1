import sys
import os

print("=== Python Environment Debug ===")
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Python path: {sys.path}")

print("\n=== Checking Imports ===")
try:
    import easyocr
    print("✅ easyocr - SUCCESS")
except ImportError as e:
    print(f"❌ easyocr - FAILED: {e}")

try:
    import flask
    print("✅ flask - SUCCESS")
except ImportError as e:
    print(f"❌ flask - FAILED: {e}")

try:
    import cv2
    print("✅ opencv - SUCCESS")
except ImportError as e:
    print(f"❌ opencv - FAILED: {e}")

try:
    import pytesseract
    print("✅ pytesseract - SUCCESS")
except ImportError as e:
    print(f"❌ pytesseract - FAILED: {e}")

print("\n=== EasyOCR Info ===")
try:
    import easyocr
    print(f"EasyOCR version: {easyocr.__version__}")
except:
    print("EasyOCR not available")