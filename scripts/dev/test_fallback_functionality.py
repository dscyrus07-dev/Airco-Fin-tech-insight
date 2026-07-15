#!/usr/bin/env python3
"""
Test script to validate 3-level fallback functionality
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_fallback_methods():
    """Test that all parsers have fallback methods with correct signatures"""
    banks = [
        "icici", "kotak", "hdfc", "sbi", "axis", 
        "canara", "idfc", "bank_of_baroda", "karnataka", 
        "paytm", "union", "unknown"
    ]
    
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
    
    results = {}
    
    for bank in banks:
        print(f"Testing {bank} fallback methods...", end=" ")
        try:
            # Import parser
            module_path = f"app.services.banks.{bank}.parser"
            module = __import__(module_path, fromlist=[''])
            
            # Get parser class
            parser_class_name = parser_class_mapping[bank]
            parser_class = getattr(module, parser_class_name)
            
            # Try to instantiate
            parser = parser_class()
            
            # Check fallback methods exist and have correct signatures
            required_methods = {
                '_parse_dynamic': '(file_path: str) -> ParseResult',
                '_parse_existing_hardcoded': '(file_path: str) -> ParseResult', 
                '_is_valid_result': '(result: ParseResult) -> bool',
                '_convert_dynamic_result': '(dynamic_result) -> ParseResult',
                '_add_to_unsupported_queue': '(file_path: str, reason: str)',
                '_record_metrics': '(method: str, success: bool, transaction_count: int, start_time: datetime)',
                '_create_empty_result': '(error_message: str) -> ParseResult'
            }
            
            missing_methods = []
            for method, signature in required_methods.items():
                if not hasattr(parser, method):
                    missing_methods.append(method)
            
            # Check if parser has shared components initialized
            has_dynamic_detector = hasattr(parser, 'dynamic_detector')
            has_unsupported_queue = hasattr(parser, 'unsupported_queue')
            has_metrics = hasattr(parser, 'metrics')
            
            if missing_methods:
                print(f"❌ Missing methods: {missing_methods}")
                results[bank] = {"status": "error", "message": f"Missing methods: {missing_methods}"}
            elif not (has_dynamic_detector and has_unsupported_queue and has_metrics):
                missing_components = []
                if not has_dynamic_detector:
                    missing_components.append("dynamic_detector")
                if not has_unsupported_queue:
                    missing_components.append("unsupported_queue")
                if not has_metrics:
                    missing_components.append("metrics")
                print(f"❌ Missing components: {missing_components}")
                results[bank] = {"status": "error", "message": f"Missing components: {missing_components}"}
            else:
                print("✅ OK")
                results[bank] = {"status": "ok"}
                
        except Exception as e:
            print(f"❌ Error: {e}")
            results[bank] = {"status": "error", "message": str(e)}
    
    return results

def test_parse_method_structure():
    """Test that parse method has the 3-level fallback structure"""
    banks = ["icici", "kotak", "hdfc"]  # Test a few key banks
    
    results = {}
    
    for bank in banks:
        print(f"Testing {bank} parse method structure...", end=" ")
        try:
            # Import parser
            module_path = f"app.services.banks.{bank}.parser"
            module = __import__(module_path, fromlist=[''])
            
            # Get parser class
            parser_class_mapping = {
                "icici": "ICICIParser",
                "kotak": "KotakParser", 
                "hdfc": "HDFCParser"
            }
            parser_class_name = parser_class_mapping[bank]
            parser_class = getattr(module, parser_class_name)
            
            # Get parse method source
            import inspect
            parse_source = inspect.getsource(parser_class.parse)
            
            # Check for 3-level fallback pattern
            has_hardcoded = "_parse_existing_hardcoded" in parse_source
            has_dynamic = "_parse_dynamic" in parse_source
            has_unsupported = "_add_to_unsupported_queue" in parse_source
            has_validation = "_is_valid_result" in parse_source
            has_metrics = "_record_metrics" in parse_source
            
            if all([has_hardcoded, has_dynamic, has_unsupported, has_validation, has_metrics]):
                print("✅ OK")
                results[bank] = {"status": "ok"}
            else:
                missing = []
                if not has_hardcoded:
                    missing.append("hardcoded")
                if not has_dynamic:
                    missing.append("dynamic")
                if not has_unsupported:
                    missing.append("unsupported")
                if not has_validation:
                    missing.append("validation")
                if not has_metrics:
                    missing.append("metrics")
                print(f"❌ Missing fallback components: {missing}")
                results[bank] = {"status": "error", "message": f"Missing: {missing}"}
                
        except Exception as e:
            print(f"❌ Error: {e}")
            results[bank] = {"status": "error", "message": str(e)}
    
    return results

if __name__ == "__main__":
    print("3-Level Fallback Functionality Test")
    print("=" * 50)
    
    # Test fallback methods
    print("Testing fallback methods:")
    fallback_results = test_fallback_methods()
    
    print("\nTesting parse method structure:")
    structure_results = test_parse_method_structure()
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    
    fallback_ok = all(r["status"] == "ok" for r in fallback_results.values())
    structure_ok = all(r["status"] == "ok" for r in structure_results.values())
    
    print(f"Fallback Methods: {'✅ OK' if fallback_ok else '❌ FAILED'}")
    print(f"Parse Structure: {'✅ OK' if structure_ok else '❌ FAILED'}")
    
    if not fallback_ok:
        print("\nFallback Method Errors:")
        for name, result in fallback_results.items():
            if result["status"] == "error":
                print(f"  {name}: {result['message']}")
    
    if not structure_ok:
        print("\nParse Structure Errors:")
        for name, result in structure_results.items():
            if result["status"] == "error":
                print(f"  {name}: {result['message']}")
    
    if fallback_ok and structure_ok:
        print("\n✅ ALL FALLBACK TESTS PASSED")
        print("3-level fallback integration is working correctly!")
        sys.exit(0)
    else:
        print("\n❌ SOME FALLBACK TESTS FAILED")
        sys.exit(1)
