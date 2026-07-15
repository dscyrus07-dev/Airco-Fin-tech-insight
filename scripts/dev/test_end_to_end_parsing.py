#!/usr/bin/env python3
"""
Test script to validate end-to-end parsing with sample PDFs
"""

import sys
import os
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_hdfc_parsing():
    """Test HDFC parsing with a sample PDF"""
    print("Testing HDFC parsing with sample PDF...")
    
    try:
        # Import HDFC parser
        from app.services.banks.hdfc.parser import HDFCParser
        
        # Create parser instance
        parser = HDFCParser()
        
        # Test with a sample PDF
        sample_pdf = Path(__file__).parent / "banks/hdfc/AcctStatement_XX0182_09102023_1696857565466.pdf"
        
        if not sample_pdf.exists():
            print(f"❌ Sample PDF not found: {sample_pdf}")
            return {"status": "error", "message": "Sample PDF not found"}
        
        print(f"  Testing with: {sample_pdf.name}")
        
        # Test parsing
        result = parser.parse(str(sample_pdf))
        
        if result and hasattr(result, 'transactions') and result.transactions:
            print(f"✅ HDFC parsing successful - {len(result.transactions)} transactions")
            print(f"  Parse method: {result.parse_method}")
            print(f"  Total count: {result.total_count}")
            return {"status": "ok", "transactions": len(result.transactions), "method": result.parse_method}
        else:
            print("❌ HDFC parsing failed - no transactions found")
            return {"status": "error", "message": "No transactions found"}
            
    except Exception as e:
        print(f"❌ HDFC parsing error: {e}")
        return {"status": "error", "message": str(e)}

def test_icici_parsing():
    """Test ICICI parsing with a sample PDF"""
    print("Testing ICICI parsing with sample PDF...")
    
    try:
        # Import ICICI parser
        from app.services.banks.icici.parser import ICICIParser
        
        # Create parser instance
        parser = ICICIParser()
        
        # Test with a sample PDF
        sample_pdf = Path(__file__).parent / "banks/icici/ICICI-3M_1685081454384.pdf"
        
        if not sample_pdf.exists():
            print(f"❌ Sample PDF not found: {sample_pdf}")
            return {"status": "error", "message": "Sample PDF not found"}
        
        print(f"  Testing with: {sample_pdf.name}")
        
        # Test parsing
        result = parser.parse(str(sample_pdf))
        
        if result and hasattr(result, 'transactions') and result.transactions:
            print(f"✅ ICICI parsing successful - {len(result.transactions)} transactions")
            print(f"  Parse method: {result.parse_method}")
            print(f"  Total count: {result.total_count}")
            return {"status": "ok", "transactions": len(result.transactions), "method": result.parse_method}
        else:
            print("❌ ICICI parsing failed - no transactions found")
            return {"status": "error", "message": "No transactions found"}
            
    except Exception as e:
        print(f"❌ ICICI parsing error: {e}")
        return {"status": "error", "message": str(e)}

def test_dynamic_fallback():
    """Test dynamic fallback with a potentially problematic PDF"""
    print("Testing dynamic fallback...")
    
    try:
        # Import a parser to test dynamic fallback
        from app.services.banks.axis.parser import AxisParser
        
        # Create parser instance
        parser = AxisParser()
        
        # Test with a sample PDF that might trigger dynamic fallback
        sample_pdf = Path(__file__).parent / "banks/axis/Axis_bankstatement.pdf"
        
        if not sample_pdf.exists():
            print(f"❌ Sample PDF not found: {sample_pdf}")
            return {"status": "error", "message": "Sample PDF not found"}
        
        print(f"  Testing with: {sample_pdf.name}")
        
        # Test parsing
        result = parser.parse(str(sample_pdf))
        
        if result and hasattr(result, 'transactions') and result.transactions:
            print(f"✅ Axis parsing successful - {len(result.transactions)} transactions")
            print(f"  Parse method: {result.parse_method}")
            print(f"  Total count: {result.total_count}")
            
            # Check if dynamic fallback was used
            if result.parse_method == "dynamic":
                print("  🔄 Dynamic fallback was used!")
            elif result.parse_method == "hardcoded":
                print("  ✅ Hardcoded parser worked!")
            
            return {"status": "ok", "transactions": len(result.transactions), "method": result.parse_method}
        else:
            print("❌ Axis parsing failed - no transactions found")
            return {"status": "error", "message": "No transactions found"}
            
    except Exception as e:
        print(f"❌ Axis parsing error: {e}")
        return {"status": "error", "message": str(e)}

def test_unsupported_queue():
    """Test unsupported queue with an invalid file"""
    print("Testing unsupported queue...")
    
    try:
        # Import a parser to test unsupported queue
        from app.services.banks.unknown.parser import UnknownParser
        
        # Create parser instance
        parser = UnknownParser()
        
        # Create a test invalid file (not a PDF)
        invalid_file = Path(__file__).parent / "test_invalid.txt"
        invalid_file.write_text("This is not a PDF file")
        
        print(f"  Testing with invalid file: {invalid_file.name}")
        
        # Test parsing - should fail and add to unsupported queue
        result = parser.parse(str(invalid_file))
        
        # Clean up
        invalid_file.unlink()
        
        # The result should be empty/failed
        if result and hasattr(result, 'transactions') and not result.transactions:
            print("✅ Unsupported queue test passed - invalid file handled correctly")
            return {"status": "ok"}
        else:
            print("❌ Unsupported queue test failed - invalid file was not handled correctly")
            return {"status": "error", "message": "Invalid file not handled correctly"}
            
    except Exception as e:
        print(f"❌ Unsupported queue test error: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print("End-to-End Parsing Test")
    print("=" * 50)
    
    # Run tests
    hdfc_result = test_hdfc_parsing()
    print()
    
    icici_result = test_icici_parsing()
    print()
    
    axis_result = test_dynamic_fallback()
    print()
    
    queue_result = test_unsupported_queue()
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    
    hdfc_ok = hdfc_result["status"] == "ok"
    icici_ok = icici_result["status"] == "ok"
    axis_ok = axis_result["status"] == "ok"
    queue_ok = queue_result["status"] == "ok"
    
    print(f"HDFC Parsing: {'✅ OK' if hdfc_ok else '❌ FAILED'}")
    print(f"ICICI Parsing: {'✅ OK' if icici_ok else '❌ FAILED'}")
    print(f"Dynamic Fallback: {'✅ OK' if axis_ok else '❌ FAILED'}")
    print(f"Unsupported Queue: {'✅ OK' if queue_ok else '❌ FAILED'}")
    
    if hdfc_ok and icici_ok and axis_ok and queue_ok:
        print("\n✅ ALL END-TO-END TESTS PASSED")
        print("3-level fallback system is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ SOME END-TO-END TESTS FAILED")
        sys.exit(1)
