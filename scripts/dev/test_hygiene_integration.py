#!/usr/bin/env python3
"""
Test script to validate hygiene checker integration with parsers
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_hygiene_integration():
    """Test hygiene checker integration with a parser"""
    print("Testing Hygiene Checker Integration")
    print("=" * 50)
    
    try:
        # Import HDFC parser (as an example)
        from app.services.banks.hdfc.parser import HDFCParser
        
        # Create parser instance
        parser = HDFCParser()
        
        # Test with a sample PDF
        sample_pdf = Path(__file__).parent / "banks/hdfc/AcctStatement_XX0182_09102023_1696857565466.pdf"
        
        if not sample_pdf.exists():
            print(f"❌ Sample PDF not found: {sample_pdf}")
            return False
        
        print(f"Testing with: {sample_pdf.name}")
        
        # Test the hygiene validation method directly
        hygiene_result = parser._validate_pdf_hygiene(str(sample_pdf))
        
        print(f"\nHygiene Check Result:")
        print(f"  Healthy: {'✅' if hygiene_result.is_healthy else '❌'}")
        print(f"  File: {hygiene_result.file_name}")
        print(f"  Pages: {hygiene_result.page_count}")
        print(f"  Bank: {hygiene_result.bank_name}")
        print(f"  Transactions: {hygiene_result.transaction_count}")
        print(f"  Format ID: {hygiene_result.format_id}")
        print(f"  Date Range: {hygiene_result.start_date} to {hygiene_result.end_date}")
        
        if hygiene_result.issues:
            print(f"  Issues: {', '.join(hygiene_result.issues)}")
        
        if hygiene_result.warnings:
            print(f"  Warnings: {', '.join(hygiene_result.warnings)}")
        
        # Now test the full parse method (includes hygiene check)
        print(f"\nTesting full parse with hygiene check...")
        parse_result = parser.parse(str(sample_pdf))
        
        if parse_result.final_method == "hygiene_failed":
            print("❌ Parse failed due to hygiene check")
            return False
        else:
            print(f"✅ Parse succeeded with method: {parse_result.final_method}")
            print(f"  Transactions extracted: {len(parse_result.transactions)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing hygiene integration: {e}")
        return False

def test_unhealthy_pdf():
    """Test with an unhealthy PDF (invalid file)"""
    print("\nTesting with Unhealthy PDF")
    print("=" * 30)
    
    try:
        # Import Unknown parser
        from app.services.banks.unknown.parser import UnknownParser
        
        # Create parser instance
        parser = UnknownParser()
        
        # Create a test invalid file
        invalid_file = Path(__file__).parent / "test_invalid_hygiene.txt"
        invalid_file.write_text("This is not a PDF file")
        
        print(f"Testing with invalid file: {invalid_file.name}")
        
        # Test the hygiene validation method
        hygiene_result = parser._validate_pdf_hygiene(str(invalid_file))
        
        print(f"\nHygiene Check Result:")
        print(f"  Healthy: {'✅' if hygiene_result.is_healthy else '❌'}")
        print(f"  Issues: {', '.join(hygiene_result.issues)}")
        
        # Clean up
        invalid_file.unlink()
        
        # Test full parse method
        parse_result = parser.parse(str(invalid_file))
        
        if parse_result.final_method == "hygiene_failed":
            print("✅ Correctly rejected unhealthy PDF")
            return True
        else:
            print("❌ Should have rejected unhealthy PDF")
            return False
        
    except Exception as e:
        print(f"❌ Error testing unhealthy PDF: {e}")
        return False

if __name__ == "__main__":
    print("Hygiene Checker Integration Test")
    print("=" * 50)
    
    # Test healthy PDF
    healthy_test = test_hygiene_integration()
    
    # Test unhealthy PDF
    unhealthy_test = test_unhealthy_pdf()
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"Healthy PDF Test: {'✅ PASSED' if healthy_test else '❌ FAILED'}")
    print(f"Unhealthy PDF Test: {'✅ PASSED' if unhealthy_test else '❌ FAILED'}")
    
    if healthy_test and unhealthy_test:
        print("\n✅ ALL HYGIENE INTEGRATION TESTS PASSED")
        print("Hygiene checker is working correctly with 3-level fallback!")
        sys.exit(0)
    else:
        print("\n❌ SOME HYGIENE INTEGRATION TESTS FAILED")
        sys.exit(1)
