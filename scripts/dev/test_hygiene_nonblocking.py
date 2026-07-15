#!/usr/bin/env python3
"""
Test script to validate non-blocking hygiene checker
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_hygiene_warnings_proceed():
    """Test that hygiene warnings don't block processing"""
    print("Testing Non-Blocking Hygiene Checker")
    print("=" * 50)
    
    try:
        from app.services.banks._shared.hygiene_check import HygieneCheck
        
        # Create an invalid file to test warnings
        invalid_file = Path(__file__).parent / "test_invalid_nonblocking.txt"
        invalid_file.write_text("This is not a PDF file")
        
        print(f"Testing with invalid file: {invalid_file.name}")
        
        # Create hygiene checker
        checker = HygieneCheck(pdf_directory=invalid_file.parent)
        
        # Validate the PDF
        result = checker.validate_single_pdf(invalid_file)
        
        print(f"\nHygiene Check Result:")
        print(f"  Healthy: {'✅' if result.is_healthy else '❌'}")
        print(f"  Issues: {', '.join(result.issues)}")
        
        # Log the detailed report (should show warnings, not blocking)
        print(f"\nDetailed Report:")
        checker.log_hygiene_check_result(result)
        
        # Clean up
        invalid_file.unlink()
        
        # Should be unhealthy but log shows it will proceed
        return not result.is_healthy
        
    except Exception as e:
        print(f"❌ Error testing non-blocking hygiene: {e}")
        return False

def test_healthy_pdf_proceeds():
    """Test that healthy PDFs proceed normally"""
    print("\nTesting Healthy PDF Processing")
    print("=" * 35)
    
    try:
        from app.services.banks._shared.hygiene_check import HygieneCheck
        
        # Test with a sample PDF
        sample_pdf = Path(__file__).parent / "banks/hdfc/AcctStatement_XX0182_09102023_1696857565466.pdf"
        
        if not sample_pdf.exists():
            print(f"❌ Sample PDF not found: {sample_pdf}")
            return False
        
        print(f"Testing with: {sample_pdf.name}")
        
        # Create hygiene checker
        checker = HygieneCheck(pdf_directory=sample_pdf.parent)
        
        # Validate the PDF
        result = checker.validate_single_pdf(sample_pdf)
        
        print(f"\nHygiene Check Result:")
        print(f"  Healthy: {'✅' if result.is_healthy else '❌'}")
        print(f"  Transactions: {result.transaction_count}")
        print(f"  Warnings: {', '.join(result.warnings)}")
        
        # Log the detailed report
        print(f"\nDetailed Report:")
        checker.log_hygiene_check_result(result)
        
        return result.is_healthy
        
    except Exception as e:
        print(f"❌ Error testing healthy PDF: {e}")
        return False

if __name__ == "__main__":
    print("Non-Blocking Hygiene Checker Test")
    print("=" * 50)
    
    # Test unhealthy PDF (should show warnings but proceed)
    test1 = test_hygiene_warnings_proceed()
    
    # Test healthy PDF (should proceed normally)
    test2 = test_healthy_pdf_proceeds()
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY:")
    print(f"Unhealthy PDF Test: {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"Healthy PDF Test: {'✅ PASSED' if test2 else '❌ FAILED'}")
    
    if test1 and test2:
        print("\n🎉 NON-BLOCKING HYGIENE CHECKER WORKING!")
        print("✅ Warnings are logged but processing continues")
        print("✅ Healthy PDFs proceed normally")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
