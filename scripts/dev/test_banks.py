#!/usr/bin/env python3
"""Test all banks systematically using direct processor calls"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.banks.hdfc.processor import HDFCProcessor
from app.services.banks.karnataka.processor import KarnatakaProcessor
from app.services.banks.sbi.processor import SBIProcessor
from app.services.banks.axis.processor import AxisProcessor
from app.services.banks.icici.processor import ICICIProcessor
from app.services.banks.canara.processor import CanaraProcessor
from app.services.banks.kotak.processor import KotakProcessor
from app.services.banks.union.processor import UnionProcessor
from app.services.banks.idfc.processor import IDFCProcessor
from app.services.banks.bob.processor import BOBProcessor
from app.services.banks.paytm.processor import PaytmProcessor

# Bank configurations
BANKS = [
    ("HDFC", HDFCProcessor, "banks/hdfc/hdfcsiva_1685441504280.pdf"),
    ("Karnataka", KarnatakaProcessor, "banks/karnataka bank/9522XXXXXXXX3801_3213191630_1690884667992.pdf"),
    ("SBI", SBIProcessor, "banks/sbi/9515_11072_1720671808775.pdf"),
    ("Axis", AxisProcessor, "banks/axis/Axis_bankstatement.pdf"),
    ("ICICI", ICICIProcessor, "banks/icici/ICICI-3M_1685081454384.pdf"),
    ("Canara", CanaraProcessor, "banks/canara/CanaraStm_1708930616809.pdf"),
    ("Kotak", KotakProcessor, "banks/kotak/61XXXXX357_1748243671168.pdf"),
    ("Union", UnionProcessor, "banks/union/Union_Bank_Statement.pdf"),
    ("IDFC", IDFCProcessor, "banks/idfc/IDFCFIRSTBankstatement_10072076528(1)_1685342952820.pdf"),
    ("BankOfBaroda", BOBProcessor, "banks/bank of baroda/Statement_1733922833120.pdf"),
    ("Paytm", PaytmProcessor, "banks/paytm/Account_Statement_010423_110723_1689140433613.pdf"),
]

def test_bank(name, processor_class, pdf_path):
    """Test a single bank"""
    print(f"\n{'='*60}")
    print(f"Testing {name}...")
    print(f"{'='*60}")
    
    # Check if file exists
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return {"bank": name, "status": "FILE_NOT_FOUND", "error": f"File not found: {pdf_path}"}
    
    try:
        # Create processor
        processor = processor_class()
        
        # Process the file
        user_info = {"user_id": "test-user", "email": "test@test.com"}
        output_dir = "/tmp"
        
        result = processor.process(pdf_path, user_info, output_dir)
        
        print(f"✅ SUCCESS!")
        print(f"   Transactions: {result.get('transaction_count', 'N/A')}")
        print(f"   Excel: {result.get('excel_path', 'N/A')}")
        
        return {
            "bank": name,
            "status": "SUCCESS",
            "transactions": result.get('transaction_count', 0),
            "excel_path": result.get('excel_path'),
        }
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"bank": name, "status": "FAILED", "error": str(e)}

def main():
    """Run all tests"""
    print("="*60)
    print("BANK TESTING - All Banks")
    print("="*60)
    
    results = []
    
    for name, processor_class, pdf_path in BANKS:
        result = test_bank(name, processor_class, pdf_path)
        results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    failed_count = len(results) - success_count
    
    print(f"Total: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    print()
    
    for r in results:
        status_emoji = "✅" if r["status"] == "SUCCESS" else "❌"
        print(f"{status_emoji} {r['bank']}: {r['status']}")
        if r["status"] != "SUCCESS":
            print(f"   Error: {r.get('error', 'Unknown')}")
    
    # Save results
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nResults saved to test_results.json")
    
    return failed_count == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
