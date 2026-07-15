#!/usr/bin/env python3
"""
Standalone test for PDF hygiene checker integration
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_hygiene_checker_only():
    """Test the hygiene checker independently"""
    print("Testing PDF Hygiene Checker Standalone")
    print("=" * 50)
    
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
        print(f"  File: {result.file_name}")
        print(f"  Pages: {result.page_count}")
        print(f"  Bank: {result.bank_name}")
        print(f"  Transactions: {result.transaction_count}")
        print(f"  Format ID: {result.format_id}")
        print(f"  Date Range: {result.start_date} to {result.end_date}")
        
        if result.issues:
            print(f"  Issues: {', '.join(result.issues)}")
        
        if result.warnings:
            print(f"  Warnings: {', '.join(result.warnings)}")
        
        # Log the detailed report
        print(f"\nDetailed Report:")
        checker.log_hygiene_check_result(result)
        
        return result.is_healthy
        
    except Exception as e:
        print(f"❌ Error testing hygiene checker: {e}")
        return False

def test_unhealthy_pdf():
    """Test with an unhealthy PDF"""
    print("\nTesting with Unhealthy PDF")
    print("=" * 30)
    
    try:
        from app.services.banks._shared.hygiene_check import HygieneCheck
        
        # Create a test invalid file
        invalid_file = Path(__file__).parent / "test_invalid_hygiene.txt"
        invalid_file.write_text("This is not a PDF file")
        
        print(f"Testing with invalid file: {invalid_file.name}")
        
        # Create hygiene checker
        checker = HygieneCheck(pdf_directory=invalid_file.parent)
        
        # Validate the PDF
        result = checker.validate_single_pdf(invalid_file)
        
        print(f"\nHygiene Check Result:")
        print(f"  Healthy: {'✅' if result.is_healthy else '❌'}")
        print(f"  Issues: {', '.join(result.issues)}")
        
        # Clean up
        invalid_file.unlink()
        
        # Should be unhealthy
        return not result.is_healthy
        
    except Exception as e:
        print(f"❌ Error testing unhealthy PDF: {e}")
        return False

def test_multiple_pdfs():
    """Test hygiene check on multiple PDFs"""
    print("\nTesting Multiple PDFs")
    print("=" * 25)
    
    try:
        from app.services.banks._shared.hygiene_check import HygieneCheck
        
        # Find sample PDFs
        banks_dir = Path(__file__).parent / "banks"
        pdf_files = list(banks_dir.rglob("*.pdf"))[:5]  # Test first 5 PDFs
        
        if not pdf_files:
            print("❌ No PDF files found for testing")
            return False
        
        print(f"Testing {len(pdf_files)} PDF files...")
        
        healthy_count = 0
        for pdf_file in pdf_files:
            print(f"\nTesting: {pdf_file.name}")
            
            # Create hygiene checker for this file's directory
            checker = HygieneCheck(pdf_directory=pdf_file.parent)
            
            # Validate the PDF
            result = checker.validate_single_pdf(pdf_file)
            
            status = "✅ HEALTHY" if result.is_healthy else "❌ UNHEALTHY"
            print(f"  Status: {status}")
            print(f"  Bank: {result.bank_name}, Pages: {result.page_count}, Transactions: {result.transaction_count}")
            
            if result.issues:
                print(f"  Issues: {', '.join(result.issues)}")
            
            if result.is_healthy:
                healthy_count += 1
        
        print(f"\nSummary: {healthy_count}/{len(pdf_files)} PDFs passed hygiene check")
        return healthy_count > 0  # At least some should pass
        
    except Exception as e:
        print(f"❌ Error testing multiple PDFs: {e}")
        return False

def test_folder_batch_processing():
    """Test batch processing of a folder"""
    print("\nTesting Folder Batch Processing")
    print("=" * 35)
    
    try:
        from app.services.banks._shared.hygiene_check import HygieneCheck
        
        # Use the banks directory
        banks_dir = Path(__file__).parent / "banks"
        
        if not banks_dir.exists():
            print("❌ Banks directory not found")
            return False
        
        print(f"Processing all PDFs in: {banks_dir}")
        
        # Create hygiene checker and run batch processing
        checker = HygieneCheck(pdf_directory=banks_dir)
        
        # Run batch hygiene check (this will process all PDFs and log detailed reports)
        results = checker.run_hygiene_check()
        
        print(f"\nBatch processing completed!")
        print(f"Total files processed: {len(results)}")
        
        # Count healthy vs unhealthy
        healthy_files = sum(1 for r in results if r.get('No of Pages', 0) > 0 and r.get('No of Transactions', 0) > 0 and r.get('Bank Name') != "unknown")
        
        print(f"Healthy files: {healthy_files}")
        print(f"Unhealthy files: {len(results) - healthy_files}")
        
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ Error in batch processing: {e}")
        return False

if __name__ == "__main__":
    print("PDF Hygiene Checker Test Suite")
    print("=" * 50)
    
    # Run all tests
    test1 = test_hygiene_checker_only()
    test2 = test_unhealthy_pdf()
    test3 = test_multiple_pdfs()
    test4 = test_folder_batch_processing()
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUITE SUMMARY:")
    print(f"Individual PDF Test: {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"Unhealthy PDF Test: {'✅ PASSED' if test2 else '❌ FAILED'}")
    print(f"Multiple PDFs Test: {'✅ PASSED' if test3 else '❌ FAILED'}")
    print(f"Batch Processing Test: {'✅ PASSED' if test4 else '❌ FAILED'}")
    
    if all([test1, test2, test3, test4]):
        print("\n🎉 ALL HYGIENE CHECKER TESTS PASSED!")
        print("PDF hygiene checker is ready for integration!")
        sys.exit(0)
    else:
        print("\n❌ SOME HYGIENE CHECKER TESTS FAILED")
        sys.exit(1)
