#!/usr/bin/env python3
"""
Test script to validate parsers locally
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_parser_imports():
    """Test importing all parsers"""
    banks = [
        "icici", "kotak", "hdfc", "sbi", "axis", 
        "canara", "idfc", "bank_of_baroda", "karnataka", 
        "paytm", "union", "unknown"
    ]
    
    results = {}
    
    for bank in banks:
        print(f"Testing {bank}...", end=" ")
        try:
            # Import parser
            module_path = f"app.services.banks.{bank}.parser"
            module = __import__(module_path, fromlist=[''])
            
            # Get parser class with correct naming
            parser_class_mapping = {
                "icici": "ICICIParser",
                "kotak": "KotakParser", 
                "hdfc": "HDFCParser",
                "sbi": "SBIParser",
                "axis": "AxisParser",
                "canara": "CanaraParser",
                "idfc": "IDFCParser",
                "bank_of_baroda": "BankOfBarodaParser",
                "karnataka": "KarnatakaParser",
                "paytm": "PaytmParser",
                "union": "UnionParser",
                "unknown": "UnknownParser"
            }
            parser_class_name = parser_class_mapping.get(bank, f"{bank.title()}Parser")
            
            parser_class = getattr(module, parser_class_name)
            
            # Try to instantiate
            parser = parser_class()
            
            # Check if fallback methods exist
            required_methods = ['parse', '_parse_existing_hardcoded', '_parse_dynamic', '_is_valid_result']
            missing_methods = []
            
            for method in required_methods:
                if not hasattr(parser, method):
                    missing_methods.append(method)
            
            if missing_methods:
                print(f"❌ Missing methods: {missing_methods}")
                results[bank] = {"status": "error", "message": f"Missing methods: {missing_methods}"}
            else:
                print("✅ OK")
                results[bank] = {"status": "ok"}
                
        except ImportError as e:
            print(f"❌ Import error: {e}")
            results[bank] = {"status": "error", "message": f"Import error: {e}"}
        except Exception as e:
            print(f"❌ Error: {e}")
            results[bank] = {"status": "error", "message": str(e)}
    
    return results

def test_shared_components():
    """Test shared components"""
    print("Testing shared components...")
    
    components = [
        ("dynamic_column_detector", "DynamicColumnDetector"),
        ("unsupported_format_queue", "UnsupportedFormatQueue"),
        ("parser_metrics", "ParserMetrics")
    ]
    
    results = {}
    
    for module_name, class_name in components:
        print(f"  Testing {module_name}...", end=" ")
        try:
            module = __import__(f"app.services.banks._shared.{module_name}", fromlist=[''])
            cls = getattr(module, class_name)
            
            # Try to instantiate
            instance = cls()
            print("✅ OK")
            results[module_name] = {"status": "ok"}
        except Exception as e:
            print(f"❌ Error: {e}")
            results[module_name] = {"status": "error", "message": str(e)}
    
    return results

if __name__ == "__main__":
    print("Parser Validation Test")
    print("=" * 50)
    
    # Test shared components first
    shared_results = test_shared_components()
    
    print("\nTesting parsers:")
    parser_results = test_parser_imports()
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    
    shared_ok = all(r["status"] == "ok" for r in shared_results.values())
    parser_ok = all(r["status"] == "ok" for r in parser_results.values())
    
    print(f"Shared Components: {'✅ OK' if shared_ok else '❌ FAILED'}")
    print(f"Parsers: {'✅ OK' if parser_ok else '❌ FAILED'}")
    
    if not shared_ok:
        print("\nShared Component Errors:")
        for name, result in shared_results.items():
            if result["status"] == "error":
                print(f"  {name}: {result['message']}")
    
    if not parser_ok:
        print("\nParser Errors:")
        for name, result in parser_results.items():
            if result["status"] == "error":
                print(f"  {name}: {result['message']}")
    
    if shared_ok and parser_ok:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
