import pytest
import sys
import os
from unittest.mock import patch, MagicMock, Mock
import logging

# Check if image processing dependencies are available
try:
    import numpy as np
    import cv2
    HAS_IMAGE_DEPS = True
except ImportError:
    HAS_IMAGE_DEPS = False

# Skip all tests if image dependencies are missing
pytestmark = pytest.mark.skipif(not HAS_IMAGE_DEPS, reason="Image processing dependencies not installed")

# Add the parent directory to Python path to import your modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plate_detector import WorkingPlateDetector, plate_detector


# ===============================
# TEST FIXTURES (Only if dependencies available)
# ===============================

@pytest.fixture
def detector():
    """Create a fresh detector instance for each test"""
    return WorkingPlateDetector()


@pytest.fixture
def sample_image():
    """Create a sample image for testing"""
    # Create a simple 400x300 black image
    return np.zeros((300, 400, 3), dtype=np.uint8)


@pytest.fixture
def sample_grayscale_image():
    """Create a sample grayscale image for testing"""
    return np.zeros((300, 400), dtype=np.uint8)


@pytest.fixture
def mock_tesseract():
    """Mock pytesseract for testing"""
    with patch('plate_detector.pytesseract') as mock_tess:
        yield mock_tess


# ===============================
# INITIALIZATION TESTS
# ===============================

def test_detector_initialization(detector):
    """Test that detector initializes properly"""
    assert detector.min_confidence == 0.5
    assert hasattr(detector, 'initialized')


@patch('plate_detector.os.name', 'nt')
@patch('plate_detector.os.path.exists')
def test_configure_tesseract_windows_success(mock_exists, detector):
    """Test tesseract configuration on Windows when found"""
    mock_exists.return_value = True
    
    detector._configure_tesseract()
    
    assert detector.initialized == True


@patch('plate_detector.os.name', 'nt')
@patch('plate_detector.os.path.exists')
def test_configure_tesseract_windows_not_found(mock_exists, detector):
    """Test tesseract configuration on Windows when not found"""
    mock_exists.return_value = False
    
    # Reset the initialized flag first
    detector.initialized = False
    detector._configure_tesseract()
    
    # Should remain False when tesseract is not found
    assert detector.initialized == False


@patch('plate_detector.os.name', 'posix')
@patch('plate_detector.shutil.which')
def test_configure_tesseract_unix_success(mock_which, detector):
    """Test tesseract configuration on Unix when found in PATH"""
    mock_which.return_value = '/usr/bin/tesseract'
    
    detector._configure_tesseract()
    
    assert detector.initialized == True


@patch('plate_detector.os.name', 'posix')
@patch('plate_detector.shutil.which')
def test_configure_tesseract_unix_not_found(mock_which, detector):
    """Test tesseract configuration on Unix when not found"""
    mock_which.return_value = None
    
    # Reset the initialized flag first
    detector.initialized = False
    detector._configure_tesseract()
    
    # Should remain False when tesseract is not found
    assert detector.initialized == False


# ===============================
# IMAGE PREPROCESSING TESTS (Only if image deps available)
# ===============================

def test_preprocess_image_color(detector, sample_image):
    """Test preprocessing of color image"""
    processed = detector.preprocess_image(sample_image)
    
    assert processed is not None
    assert len(processed.shape) == 2  # Should be grayscale
    assert processed.dtype == np.uint8


def test_preprocess_image_grayscale(detector, sample_grayscale_image):
    """Test preprocessing of grayscale image"""
    processed = detector.preprocess_image(sample_grayscale_image)
    
    assert processed is not None
    assert len(processed.shape) == 2  # Should remain grayscale
    assert processed.dtype == np.uint8


def test_preprocess_image_small(detector):
    """Test preprocessing of small image (should be upscaled)"""
    small_img = np.zeros((100, 100, 3), dtype=np.uint8)
    processed = detector.preprocess_image(small_img)
    
    assert processed is not None
    # Should be upscaled to at least 400px on the larger dimension
    assert max(processed.shape) >= 400


def test_preprocess_image_error_handling(detector):
    """Test preprocessing error handling"""
    # Pass invalid image
    result = detector.preprocess_image("invalid")
    
    # Should return the original input on error
    assert result == "invalid"


# ===============================
# CONFIDENCE HANDLING TESTS
# ===============================

def test_safe_conf_valid(detector):
    """Test safe confidence calculation with valid inputs"""
    assert detector._safe_conf("0.75") == 0.75
    assert detector._safe_conf(0.8) == 0.8
    assert detector._safe_conf("80") == 0.8  # Percentage conversion


def test_safe_conf_invalid(detector):
    """Test safe confidence calculation with invalid inputs"""
    assert detector._safe_conf(None) == 0.0
    assert detector._safe_conf("") == 0.0
    assert detector._safe_conf("-1") == 0.0
    assert detector._safe_conf("invalid") == 0.0


def test_safe_conf_various_formats(detector):
    """Test various confidence value formats"""
    # Test percentage values that need division
    assert detector._safe_conf("150") == 1.0  # 150% -> 1.0
    assert detector._safe_conf("75") == 0.75  # 75% -> 0.75
    assert detector._safe_conf("15") == 0.15  # 15% -> 0.15


# ===============================
# TEXT CLEANING TESTS
# ===============================

def test_clean_text_normal(detector):
    """Test normal text cleaning"""
    assert detector.clean_text("abc123") == "ABC123"
    assert detector.clean_text("ABC 123") == "ABC123"
    assert detector.clean_text("A-B_C.1,2@3") == "ABC123"


def test_clean_text_edge_cases(detector):
    """Test edge cases in text cleaning"""
    assert detector.clean_text("") == ""
    assert detector.clean_text(None) == ""
    assert detector.clean_text("!@#$%") == ""


def test_clean_text_preserve_valid_chars(detector):
    """Test that valid characters are preserved"""
    input_text = "AB12CD34"
    result = detector.clean_text(input_text)
    assert result == "AB12CD34"


# ===============================
# PLATE VALIDATION TESTS
# ===============================

def test_is_valid_plate_valid_patterns(detector):
    """Test valid license plate patterns"""
    valid_plates = [
        "A123",      # 1 letter + 3 digits
        "AB123",     # 2 letters + 3 digits  
        "ABC1234",   # 3 letters + 4 digits
        "123A",      # 3 digits + 1 letter
        "1234AB",    # 4 digits + 2 letters
        "AB12CD",    # 2 letters + 2 digits + 2 letters
    ]
    
    for plate in valid_plates:
        assert detector.is_valid_plate(plate) == True, f"Should be valid: {plate}"


def test_is_valid_plate_invalid_patterns(detector):
    """Test invalid license plate patterns"""
    invalid_plates = [
        "",           # Empty
        "ABC",        # Too short
        "ABCDEFGHI",  # Too long
        "123456",     # No letters
        "ABCDEF",     # No digits
        "A1B2C3D4",   # Mixed but too long
        "!@#$%",      # Special characters
        "AB CD",      # Contains space
    ]
    
    for plate in invalid_plates:
        assert detector.is_valid_plate(plate) == False, f"Should be invalid: {plate}"


def test_is_valid_plate_boundary_lengths(detector):
    """Test plate validation with boundary lengths"""
    assert detector.is_valid_plate("A123") == True    # Minimum valid length
    assert detector.is_valid_plate("ABC1234") == True # Maximum valid length
    assert detector.is_valid_plate("ABC") == False    # Below minimum
    assert detector.is_valid_plate("ABCD12345") == False # Above maximum


# ===============================
# OCR REGION TESTS (Mocked - always work)
# ===============================

@patch('plate_detector.pytesseract.image_to_data')
def test_ocr_region_success(mock_tesseract, detector):
    """Test successful OCR region processing"""
    # Mock tesseract response
    mock_tesseract.return_value = {
        'text': ['ABC123', 'invalid'],
        'conf': ['85', '30']
    }
    
    detector.initialized = True
    
    # Create a simple mock image
    mock_image = MagicMock()
    text, confidence = detector.ocr_region(mock_image)
    
    assert text == "ABC123"
    assert confidence > 0


@patch('plate_detector.pytesseract.image_to_data')
def test_ocr_region_no_valid_text(mock_tesseract, detector):
    """Test OCR when no valid text is found"""
    mock_tesseract.return_value = {
        'text': ['', '!@#$'],
        'conf': ['10', '20']
    }
    
    detector.initialized = True
    
    mock_image = MagicMock()
    text, confidence = detector.ocr_region(mock_image)
    
    assert text is None
    assert confidence == 0.0


@patch('plate_detector.pytesseract.image_to_data')
def test_ocr_region_low_confidence(mock_tesseract, detector):
    """Test OCR with low confidence results"""
    mock_tesseract.return_value = {
        'text': ['ABC123'],
        'conf': ['40']  # Below min_confidence of 50
    }
    
    detector.initialized = True
    
    mock_image = MagicMock()
    text, confidence = detector.ocr_region(mock_image)
    
    assert text is None
    assert confidence == 0.0


def test_ocr_region_not_initialized(detector):
    """Test OCR when detector is not initialized"""
    detector.initialized = False
    
    mock_image = MagicMock()
    text, confidence = detector.ocr_region(mock_image)
    
    assert text is None
    assert confidence == 0.0


@patch('plate_detector.pytesseract.image_to_data')
def test_ocr_region_exception_handling(mock_tesseract, detector):
    """Test OCR exception handling"""
    mock_tesseract.side_effect = Exception("Tesseract error")
    
    detector.initialized = True
    
    mock_image = MagicMock()
    text, confidence = detector.ocr_region(mock_image)
    
    assert text is None
    assert confidence == 0.0


# ===============================
# PLATE DETECTION TESTS (Mixed real/mocked)
# ===============================

@patch('plate_detector.pytesseract.image_to_data')
def test_detect_plate_success(mock_tesseract, detector, sample_image):
    """Test successful plate detection"""
    mock_tesseract.return_value = {
        'text': ['ABC123'],
        'conf': ['90']
    }
    
    detector.initialized = True
    text, confidence = detector.detect_plate(sample_image)
    
    assert text == "ABC123"
    assert confidence > 0


def test_detect_plate_not_initialized(detector, sample_image):
    """Test plate detection when not initialized"""
    detector.initialized = False
    text, confidence = detector.detect_plate(sample_image)
    
    assert text is None
    assert confidence == 0.0


@patch('plate_detector.pytesseract.image_to_data')
def test_detect_plate_large_image_resize(mock_tesseract, detector):
    """Test that large images are properly resized"""
    # Create a large image
    large_image = np.zeros((1000, 2000, 3), dtype=np.uint8)
    mock_tesseract.return_value = {
        'text': ['ABC123'],
        'conf': ['90']
    }
    
    detector.initialized = True
    text, confidence = detector.detect_plate(large_image)
    
    # Should still work despite large input
    assert text == "ABC123"
    assert confidence > 0


@patch('plate_detector.pytesseract.image_to_data')
def test_detect_plate_no_contours(mock_tesseract, detector, sample_image):
    """Test plate detection when no contours are found"""
    # Mock empty contours
    with patch('cv2.findContours') as mock_contours:
        mock_contours.return_value = ([], None)
        
        # Mock full image OCR
        mock_tesseract.return_value = {
            'text': ['ABC123'],
            'conf': ['90']
        }
        
        detector.initialized = True
        text, confidence = detector.detect_plate(sample_image)
        
        assert text == "ABC123"
        assert confidence > 0


@patch('plate_detector.pytesseract.image_to_data')
def test_detect_plate_contour_processing(mock_tesseract, detector, sample_image):
    """Test plate detection with contour processing"""
    # Mock contours that match plate criteria
    mock_contour = np.array([[[10, 10]], [[100, 10]], [[100, 50]], [[10, 50]]])
    
    with patch('cv2.findContours') as mock_find_contours:
        mock_find_contours.return_value = ([mock_contour], None)
        
        mock_tesseract.return_value = {
            'text': ['ABC123'],
            'conf': ['90']
        }
        
        detector.initialized = True
        text, confidence = detector.detect_plate(sample_image)
        
        assert text == "ABC123"
        assert confidence > 0


# ===============================
# INTEGRATION TESTS
# ===============================

def test_plate_detector_singleton():
    """Test that plate_detector is a singleton instance"""
    assert isinstance(plate_detector, WorkingPlateDetector)
    assert hasattr(plate_detector, 'initialized')


def test_end_to_end_validation_flow(detector):
    """Test the complete validation flow"""
    # Test text that goes through cleaning and validation
    # Use a pattern that matches one of the valid regex patterns
    dirty_text = " AB123 "  # This matches pattern: 1-3 letters + 1-4 digits
    cleaned = detector.clean_text(dirty_text)
    assert cleaned == "AB123"
    
    is_valid = detector.is_valid_plate(cleaned)
    assert is_valid == True


# ===============================
# ERROR HANDLING TESTS
# ===============================

def test_detect_plate_invalid_input(detector):
    """Test plate detection with invalid input"""
    # Mock the shape access to avoid AttributeError
    with patch.object(detector, 'initialized', False):
        text, confidence = detector.detect_plate(None)
    
    assert text is None
    assert confidence == 0.0


@patch('plate_detector.pytesseract.image_to_data')
def test_detect_plate_ocr_failure(mock_tesseract, detector, sample_image):
    """Test plate detection when OCR fails"""
    mock_tesseract.side_effect = Exception("OCR failed")
    
    detector.initialized = True
    text, confidence = detector.detect_plate(sample_image)
    
    assert text is None
    assert confidence == 0.0


# ===============================
# PERFORMANCE TESTS
# ===============================

def test_preprocess_performance(detector):
    """Test that preprocessing doesn't take too long"""
    import time
    
    image = np.random.randint(0, 255, (500, 500, 3), dtype=np.uint8)
    
    start_time = time.time()
    processed = detector.preprocess_image(image)
    end_time = time.time()
    
    assert processed is not None
    # Should complete in reasonable time (less than 1 second)
    assert end_time - start_time < 1.0


# ===============================
# ADDITIONAL TESTS FOR COVERAGE
# ===============================

def test_configure_tesseract_exception_handling(detector):
    """Test tesseract configuration exception handling"""
    with patch('plate_detector.os.name', 'nt'):
        with patch('plate_detector.os.path.exists', side_effect=Exception("OS error")):
            # Reset initialized flag
            detector.initialized = False
            detector._configure_tesseract()
            
            # Should handle exception gracefully
            assert detector.initialized == False


# ===============================
# MOCK-ONLY TESTS (For when image deps are missing)
# ===============================

class TestPlateDetectorWithoutImageDeps:
    """Tests that work even without image dependencies"""
    
    @pytest.fixture
    def detector(self):
        return WorkingPlateDetector()
    
    def test_basic_functionality_without_image_deps(self, detector):
        """Test basic functionality without image processing"""
        # These should work even without numpy/cv2
        assert detector.clean_text("abc123") == "ABC123"
        assert detector.is_valid_plate("ABC123") == True
        assert detector._safe_conf("0.8") == 0.8


if __name__ == '__main__':
    pytest.main([__file__, '-v'])