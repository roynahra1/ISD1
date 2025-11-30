import pytest
import sys
import os
from unittest.mock import patch, MagicMock, Mock

# Check if plate_detector can be imported (it requires cv2, numpy, etc.)
try:
    from plate_detector import WorkingPlateDetector, plate_detector
    HAS_PLATE_DETECTOR_DEPS = True
except ImportError as e:
    HAS_PLATE_DETECTOR_DEPS = False
    print(f"Plate detector dependencies not available: {e}")

# Skip all tests if plate detector dependencies are missing
pytestmark = pytest.mark.skipif(not HAS_PLATE_DETECTOR_DEPS, reason="Plate detector dependencies not installed")

# Add the parent directory to Python path to import your modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import numpy separately for basic functionality tests
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


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
    if HAS_NUMPY:
        return np.zeros((300, 400, 3), dtype=np.uint8)
    return MagicMock()


@pytest.fixture
def sample_grayscale_image():
    """Create a sample grayscale image for testing"""
    if HAS_NUMPY:
        return np.zeros((300, 400), dtype=np.uint8)
    return MagicMock()


@pytest.fixture
def mock_tesseract():
    """Mock pytesseract for testing"""
    with patch('plate_detector.pytesseract') as mock_tess:
        yield mock_tess


# ===============================
# BASIC FUNCTIONALITY TESTS (Will run if dependencies available)
# ===============================

def test_detector_initialization(detector):
    """Test that detector initializes properly"""
    assert detector.min_confidence == 0.5
    assert hasattr(detector, 'initialized')


def test_clean_text_normal(detector):
    """Test normal text cleaning"""
    assert detector.clean_text("abc123") == "ABC123"
    assert detector.clean_text("ABC 123") == "ABC123"


def test_is_valid_plate_valid_patterns(detector):
    """Test valid license plate patterns"""
    valid_plates = ["A123", "AB123", "ABC1234"]
    for plate in valid_plates:
        assert detector.is_valid_plate(plate) == True


def test_is_valid_plate_invalid_patterns(detector):
    """Test invalid license plate patterns"""
    invalid_plates = ["", "ABC", "ABCDEFGHI", "123456"]
    for plate in invalid_plates:
        assert detector.is_valid_plate(plate) == False


def test_safe_conf_valid(detector):
    """Test safe confidence calculation with valid inputs"""
    assert detector._safe_conf("0.75") == 0.75
    assert detector._safe_conf(0.8) == 0.8
    assert detector._safe_conf("80") == 0.8


def test_safe_conf_invalid(detector):
    """Test safe confidence calculation with invalid inputs"""
    assert detector._safe_conf(None) == 0.0
    assert detector._safe_conf("") == 0.0
    assert detector._safe_conf("-1") == 0.0


# ===============================
# MOCKED IMAGE PROCESSING TESTS
# ===============================

@patch('plate_detector.pytesseract.image_to_data')
def test_ocr_region_success(mock_tesseract, detector):
    """Test successful OCR region processing with mock"""
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


def test_ocr_region_not_initialized(detector):
    """Test OCR when detector is not initialized"""
    detector.initialized = False
    
    mock_image = MagicMock()
    text, confidence = detector.ocr_region(mock_image)
    
    assert text is None
    assert confidence == 0.0


# ===============================
# PLATE DETECTION TESTS (Mocked)
# ===============================

@patch('plate_detector.pytesseract.image_to_data')
def test_detect_plate_success(mock_tesseract, detector):
    """Test successful plate detection with mock"""
    mock_tesseract.return_value = {
        'text': ['ABC123'],
        'conf': ['90']
    }
    
    detector.initialized = True
    
    # Create a mock image
    mock_image = MagicMock()
    mock_image.shape = (300, 400, 3)
    
    text, confidence = detector.detect_plate(mock_image)
    
    assert text == "ABC123"
    assert confidence > 0


def test_detect_plate_not_initialized(detector):
    """Test plate detection when not initialized"""
    detector.initialized = False
    
    mock_image = MagicMock()
    mock_image.shape = (300, 400, 3)
    
    text, confidence = detector.detect_plate(mock_image)
    
    assert text is None
    assert confidence == 0.0


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
    dirty_text = " AB123 "
    cleaned = detector.clean_text(dirty_text)
    assert cleaned == "AB123"
    
    is_valid = detector.is_valid_plate(cleaned)
    assert is_valid == True


# ===============================
# CONFIGURATION TESTS
# ===============================

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
    
    detector.initialized = False
    detector._configure_tesseract()
    
    assert detector.initialized == False


# ===============================
# FALLBACK TESTS (Run even without full dependencies)
# ===============================

class TestPlateDetectorBasic:
    """Basic tests that work even without full dependencies"""
    
    def test_import_plate_detector(self):
        """Test that plate_detector module can be imported"""
        # This will be skipped if dependencies are missing due to the pytestmark
        assert HAS_PLATE_DETECTOR_DEPS == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])