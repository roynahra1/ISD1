#!/usr/bin/env python3
"""Test runner for the appointment system."""

import pytest
import sys

def main():
    """Run all tests with pytest."""
    print("🚀 Running Appointment System Tests...")
    print("=" * 50)
    
    result = pytest.main([
        "-v",
        "--tb=short",
        "tests/",
        "--cov=.",
        "--cov-report=term",
        "--cov-report=html",
        "--durations=10"
    ])
    
    print("=" * 50)
    
    if result == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    sys.exit(result)

if __name__ == "__main__":
    main()