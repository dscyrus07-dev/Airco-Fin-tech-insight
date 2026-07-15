# Bank Integration Guide - Airco Insights

## Overview

This guide documents how to add a new bank to the Airco Insights system, using **Indian Bank** as the reference implementation. The system follows a modular architecture where each bank is a self-contained package that leverages shared components.

---

## Architecture

### Core Principle
Each bank is a self-contained package under:
```
backend/app/services/banks/<bank_name>/
```

### Shared Components (Reuse These)
The system provides shared generic implementations that all banks should use:

| Component | Location | Purpose |
|-----------|----------|---------|
| BaseBankProcessor | `_shared/base_processor.py` | 10-step processing pipeline |
| GenericClassifier | `_shared/generic_bank.py` | Rule-based classification using `words.json` |
| GenericParser | `_shared/generic_bank.py` | Text-based transaction extraction |
| GenericTransactionValidator | `_shared/generic_bank.py` | Validates transaction amounts/dates |
| GenericReconciliation | `_shared/generic_bank.py` | Balance verification |
| GenericRecurringEngine | `_shared/generic_bank.py` | Recurring transaction detection |
| GenericAggregationEngine | `_shared/generic_bank.py` | Data aggregation for reports |
| GenericExcelGenerator | `_shared/generic_bank.py` | Legacy Excel fallback |
| FormulaExcelEngineBase | `_shared/formula_excel_engine_base.py` | Primary Excel export engine |
| HygieneCheck | `_shared/hygiene_check.py` | PDF validation and bank detection |
| StatementMetadataExtractor | `_shared/` | Extracts and persists metadata to Supabase |
| AuditService | `app/services/audit_service.py` | Audit logging and metadata persistence |

### Classification Database
- **Primary**: `backend/words.json` - Shared classification rules
- All banks should load this by default
- Bank-specific tuning layered on top

---

## Step-by-Step: Adding a New Bank

### Phase 1: Create Bank Package

#### 1. Create Directory Structure
```bash
mkdir backend/app/services/banks/<bank_name>
```

#### 2. Required Files
Create these files in your new bank directory:

| File | Purpose | Recommendation |
|------|---------|----------------|
| `__init__.py` | Package exports | Copy from HDFC/Indian Bank |
| `processor.py` | Main processor | Wire shared components |
| `parser.py` | Transaction extraction | Bank-specific parsing logic |
| `structure_validator.py` | PDF validation | Bank-specific markers |
| `classifier.py` | Classification rules | Load `words.json` + bank tuning |
| `report_generator.py` | Report wrapper | Delegate to `report_generator_base` |
| `formula_excel_engine.py` | Excel export | Thin wrapper over `FormulaExcelEngineBase` |
| `transaction_validator.py` | Validation wrapper | Delegate to `GenericTransactionValidator` |
| `reconciliation.py` | Reconciliation wrapper | Delegate to `GenericReconciliation` |
| `rule_engine.py` | Rule engine wrapper | Delegate to `GenericRuleEngine` |
| `recurring_engine.py` | Recurring detection | Delegate to `GenericRecurringEngine` |
| `aggregation_engine.py` | Aggregation | Delegate to `GenericAggregationEngine` |
| `ai_fallback.py` | AI fallback | Delegate to `GenericAIFallback` |
| `excel_generator.py` | Legacy Excel | Delegate to `GenericExcelGenerator` |

#### 3. Key Configuration Constants

```python
# In your bank's config or processor
BANK_CONFIG = {
    "bank_key": "<bank_key>",           # e.g., "indian_bank"
    "bank_name": "<Bank Name>",         # e.g., "Indian Bank"
    "file_prefix": "<prefix>",          # e.g., "indian_bank"
    "markers": [
        "BANK MARKER 1",                 # Text patterns to identify bank
        "BANK MARKER 2",
        r"Regex pattern",
    ],
    "support_aliases": [
        "<alias 1>",                     # e.g., "indian bank"
        "<alias 2>",                     # e.g., "indian"
        "<alias 3>",                     # e.g., "idib"
    ],
}
```

---

### Phase 2: Implement Core Files

#### Processor (`processor.py`)
```python
from .._shared.base_processor import BaseBankProcessor
from .structure_validator import <Bank>StructureValidator
from .parser import <Bank>Parser
from .transaction_validator import <Bank>TransactionValidator
from .reconciliation import <Bank>Reconciliation
from .rule_engine import <Bank>RuleEngine
from .ai_fallback import <Bank>AIFallback
from .recurring_engine import <Bank>RecurringEngine
from .aggregation_engine import <Bank>AggregationEngine
from .excel_generator import <Bank>ExcelGenerator
from .formula_excel_engine import <Bank>FormulaExcelEngine
from .classifier import <Bank>Classifier

CONFIG = {
    "bank_key": "<bank_key>",
    "bank_name": "<Bank Name>",
    "file_prefix": "<prefix>",
    "markers": ["MARKER1", "MARKER2"],
    "support_aliases": ["alias1", "alias2"],
}

class <Bank>Processor(BaseBankProcessor):
    def __init__(self, **kwargs):
        super().__init__(CONFIG, **kwargs)
        self.pdf_validator = HygieneCheck()
        self.structure_validator = <Bank>StructureValidator()
        self.parser = <Bank>Parser()
        self.transaction_validator = <Bank>TransactionValidator()
        self.reconciliation = <Bank>Reconciliation()
        self.rule_engine = <Bank>RuleEngine()
        self.ai_fallback = <Bank>AIFallback()
        self.recurring_engine = <Bank>RecurringEngine()
        self.aggregation_engine = <Bank>AggregationEngine()
        self.excel_generator = <Bank>ExcelGenerator()
        self.formula_excel_engine = <Bank>FormulaExcelEngine()
        self.classifier = <Bank>Classifier()
```

#### Structure Validator (`structure_validator.py`)
```python
import re
from typing import Dict, Any, Optional
from .._shared.generic_bank import GenericStructureValidator

<BANK>_MARKERS = [
    r"BANK\s*MARKER",
    r"Account\s*Statement",
    # Add bank-specific markers
]

class <Bank>StructureValidator(GenericStructureValidator):
    def __init__(self):
        super().__init__()
        self.markers = <BANK>_MARKERS
    
    def validate(self, pdf_path: str, raw_text: str) -> Dict[str, Any]:
        # Call parent validation
        result = super().validate(pdf_path, raw_text)
        
        # Add bank-specific validation
        header = " ".join(raw_text.split()[:250]).upper()
        
        if not any(re.search(m, header) for m in self.markers):
            raise ValueError("Does not appear to be a <Bank> statement")
        
        return result
    
    def extract_metadata(self, raw_text: str) -> Dict[str, Any]:
        # Extract account number, period, balances
        metadata = {}
        # Add extraction logic
        return metadata
```

#### Parser (`parser.py`)
```python
from typing import List, Dict, Any, Optional
from .._shared.generic_bank import GenericParser

class <Bank>Parser:
    """Parse <Bank> statements."""
    
    def __init__(self):
        self.generic_parser = GenericParser()
        # Add bank-specific date/amount patterns
        
    def parse(self, pdf_path: str, **kwargs) -> Dict[str, Any]:
        # Try bank-specific parsing first
        result = self._parse_bank_specific(pdf_path)
        
        if result and result.get("transactions"):
            return result
            
        # Fall back to generic parser
        return self.generic_parser.parse(pdf_path, **kwargs)
    
    def _parse_bank_specific(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        # Implement bank-specific parsing
        pass
```

#### Classifier (`classifier.py`)
```python
from pathlib import Path
from typing import Optional
from .._shared.generic_bank import GenericClassifier

DEFAULT_KEYWORDS_FILE = str(
    Path(__file__).resolve().parents[5] / "words.json"
)

BANK_CONFIG = {
    "bank_name": "<Bank Name>",
    "narration_cleanup": {
        # Bank-specific cleanup patterns
    }
}

class <Bank>Classifier(GenericClassifier):
    """Bank classifier with shared rules + bank-specific tuning."""
    
    def __init__(self, keywords_file: Optional[str] = None):
        super().__init__(
            BANK_CONFIG,
            keywords_file=keywords_file or DEFAULT_KEYWORDS_FILE
        )
        self._apply_bank_tuning()
    
    def _apply_bank_tuning(self):
        # Add bank-specific category mappings
        # These override/extend words.json rules
        pass
```

#### Formula Excel Engine (`formula_excel_engine.py`)
```python
from .._shared.formula_excel_engine_base import FormulaExcelEngineBase

class <Bank>FormulaExcelEngine(FormulaExcelEngineBase):
    def __init__(self):
        super().__init__(
            bank_name="<Bank Name>",
            report_generator_module="app.services.banks.<bank_name>.report_generator",
        )

# Backward compatibility alias
FormulaExcelEngine = <Bank>FormulaExcelEngine
```

#### Report Generator (`report_generator.py`)
```python
from .._shared import report_generator_base
from .classifier import <Bank>Classifier, get_classifier as _get_bank_classifier

def classify(description: str, debit: float = 0, credit: float = 0, **kwargs):
    return report_generator_base.classify(
        description, debit, credit,
        classifier_factory=_get_bank_classifier,
        **kwargs
    )

def generate_report(transactions: list, output_path: str, user_info: dict, **kwargs):
    return report_generator_base.generate_report(
        transactions, output_path, user_info,
        classifier_factory=_get_bank_classifier,
        bank_name="<Bank Name>"
    )

def get_classifier():
    return _get_bank_classifier()
```

#### Wrapper Files (Thin Delegation Pattern)

All wrapper files follow the same pattern:

```python
# transaction_validator.py
from .._shared.generic_bank import GenericTransactionValidator

class <Bank>TransactionValidator(GenericTransactionValidator):
    """Bank transaction validator."""
    pass

# reconciliation.py
from typing import List, Dict, Any, Optional
from .._shared.generic_bank import GenericReconciliation

class <Bank>Reconciliation:
    """Bank reconciliation wrapper."""
    
    def __init__(self):
        self._delegate = GenericReconciliation()
    
    def reconcile(
        self,
        transactions: List[Dict[str, Any]],
        opening: Optional[float] = None,
        closing: Optional[float] = None,
        expected_opening: Optional[float] = None,
        expected_closing: Optional[float] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        resolved_opening = expected_opening if expected_opening is not None else opening
        resolved_closing = expected_closing if expected_closing is not None else closing
        return self._delegate.reconcile(transactions, resolved_opening, resolved_closing)

# rule_engine.py
from .._shared.generic_bank import GenericRuleEngine

class <Bank>RuleEngine(GenericRuleEngine):
    pass

# recurring_engine.py
from .._shared.generic_bank import GenericRecurringEngine

class <Bank>RecurringEngine(GenericRecurringEngine):
    pass

# aggregation_engine.py
from .._shared.generic_bank import GenericAggregationEngine

class <Bank>AggregationEngine(GenericAggregationEngine):
    pass

# ai_fallback.py
from .._shared.generic_bank import GenericAIFallback

class <Bank>AIFallback(GenericAIFallback):
    pass

# excel_generator.py
from .._shared.generic_bank import GenericExcelGenerator

class <Bank>ExcelGenerator(GenericExcelGenerator):
    """Bank Excel generator."""
    pass
```

#### Package Init (`__init__.py`)
```python
from .processor import <Bank>Processor, CONFIG as BANK_CONFIG
from .structure_validator import <Bank>StructureValidator
from .parser import <Bank>Parser
from .transaction_validator import <Bank>TransactionValidator
from .reconciliation import <Bank>Reconciliation
from .rule_engine import <Bank>RuleEngine
from .ai_fallback import <Bank>AIFallback
from .recurring_engine import <Bank>RecurringEngine
from .aggregation_engine import <Bank>AggregationEngine
from .excel_generator import <Bank>ExcelGenerator
from .formula_excel_engine import <Bank>FormulaExcelEngine, FormulaExcelEngine
from .classifier import <Bank>Classifier, get_classifier
from .report_generator import classify, generate_report

__all__ = [
    "<Bank>Processor",
    "<Bank>StructureValidator",
    "<Bank>Parser",
    "<Bank>TransactionValidator",
    "<Bank>Reconciliation",
    "<Bank>RuleEngine",
    "<Bank>AIFallback",
    "<Bank>RecurringEngine",
    "<Bank>AggregationEngine",
    "<Bank>ExcelGenerator",
    "<Bank>FormulaExcelEngine",
    "<Bank>Classifier",
    "classify",
    "generate_report",
    "get_classifier",
    "FormulaExcelEngine",
    "BANK_CONFIG",
]
```

---

### Phase 3: Register in Routing

#### 1. Bank Package Exports (`backend/app/services/banks/__init__.py`)

Add to the imports:

```python
# Add <Bank> support
from app.services.banks.<bank_name> import (
    <Bank>Processor,
    <Bank>StructureValidator,
    <Bank>Parser,
    <Bank>TransactionValidator,
    <Bank>Reconciliation,
    <Bank>RuleEngine,
    <Bank>AIFallback,
    <Bank>RecurringEngine,
    <Bank>AggregationEngine,
    <Bank>ExcelGenerator,
    <Bank>FormulaExcelEngine,
    <Bank>Classifier,
    BANK_CONFIG as <BANK>_CONFIG,
)
```

Add to the bank registry:

```python
BANK_REGISTRY = {
    # ... existing banks ...
    "<bank_key>": {
        "processor": <Bank>Processor,
        "config": <BANK>_CONFIG,
        "structure_validator": <Bank>StructureValidator,
        "parser": <Bank>Parser,
        "transaction_validator": <Bank>TransactionValidator,
        "reconciliation": <Bank>Reconciliation,
        "rule_engine": <Bank>RuleEngine,
        "ai_fallback": <Bank>AIFallback,
        "recurring_engine": <Bank>RecurringEngine,
        "aggregation_engine": <Bank>AggregationEngine,
        "excel_generator": <Bank>ExcelGenerator,
        "formula_excel_engine": <Bank>FormulaExcelEngine,
        "classifier": <Bank>Classifier,
    },
}
```

#### 2. Pipeline Orchestrator (`backend/app/services/pipeline_orchestrator.py`)

Add to `SUPPORTED_BANKS`:

```python
SUPPORTED_BANKS = {
    # ... existing banks ...
    "<bank_key>": {
        "name": "<Bank Name>",
        "aliases": ["alias1", "alias2", "alias3"],
    },
}
```

Add to `SUPPORTED_BANK_PROCESSORS`:

```python
SUPPORTED_BANK_PROCESSORS = {
    # ... existing banks ...
    "<bank_key>": "app.services.banks.<bank_name>.processor",
}
```

Add to `_get_bank_processor`:

```python
def _get_bank_processor(bank_key: str) -> Any:
    # ... existing mappings ...
    mapping = {
        # ... existing entries ...
        "<bank_key>": "app.services.banks.<bank_name>.processor",
    }
    # ... rest of function
```

#### 3. Hygiene Check (`backend/app/services/banks/_shared/hygiene_check.py`)

Add to `BANK_CODE_MAP`:

```python
BANK_CODE_MAP = {
    # ... existing banks ...
    "<bank name>": "<bank_code>",
    "<alias>": "<bank_code>",
}
```

Add to `bank_keywords`:

```python
bank_keywords = {
    # ... existing banks ...
    "<bank_key>": ["marker1", "marker2", "regex_pattern"],
}
```

Add detection patterns to `BANK_TEXT_PATTERNS` if needed:

```python
BANK_TEXT_PATTERNS = [
    # ... existing patterns ...
    ("<bank_key>", re.compile(r"pattern", re.IGNORECASE)),
]
```

---

### Phase 4: Frontend Integration

#### 1. Type Definitions (`frontend/types/index.ts`)

Add to `BankName` union type:

```typescript
export type BankName =
  | 'HDFC Bank'
  | 'ICICI Bank'
  | 'Axis Bank'
  // ... existing banks ...
  | '<Bank Name>';  // Add this
```

#### 2. Bank Options (`frontend/lib/banks.ts`)

Add to `SUPPORTED_BANK_OPTIONS`:

```typescript
export const SUPPORTED_BANK_OPTIONS: SupportedBankOption[] = [
  // ... existing banks ...
  { name: '<Bank Name>', available: true },
];
```

---

### Phase 5: Test & Verify

#### Smoke Test Commands

```bash
# 1. Compile check
cd backend
python -m py_compile app/services/banks/<bank_name>/*.py

# 2. Processor test
python -c "
from app.services.banks.<bank_name> import <Bank>Processor
p = <Bank>Processor(strict_mode=False, enable_ai=False)
print('Processor loaded successfully')
"

# 3. End-to-end test
python -c "
from pathlib import Path
from app.services.banks.<bank_name> import <Bank>Processor

sample = r'path/to/sample.pdf'
outdir = Path(r'path/to/output')
outdir.mkdir(parents=True, exist_ok=True)

p = <Bank>Processor(strict_mode=False, enable_ai=False)
result = p.process(
    sample,
    {'full_name': 'Test User', 'bank_name': '<Bank Name>', 'account_no': '1234567890'},
    output_dir=str(outdir)
)

print(f'Status: {result.status}')
print(f'Transactions: {len(result.transactions)}')
print(f'Excel: {result.excel_path}')
"

# 4. Verify Excel output
python -c "
from openpyxl import load_workbook
wb = load_workbook(r'path/to/output.xlsx')
print('Sheets:', wb.sheetnames)
"
```

#### Expected Excel Sheet Names
When using `FormulaExcelEngineBase`, the output should include:
- `Summary`
- `Monthly Analysis`
- `Weekly Analysis`
- `Category Analysis`
- `Bounces & Penal`
- `Funds Received`
- `Funds Remittance`
- `Raw Transaction`
- `Source Analysis`
- `Category Outcome`
- `Finbit`
- `Salary Credits Transactions`
- `Loan Transactions`
- `Bounce Transactions`

---

## Indian Bank Reference Implementation

### Files Created for Indian Bank

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 40 | Package exports |
| `processor.py` | 77 | Main processor wiring |
| `parser.py` | 99 | Transaction extraction |
| `structure_validator.py` | 108 | PDF validation |
| `indian_bank_classifier.py` | 85 | Classification rules |
| `report_generator.py` | 64 | Report wrapper |
| `formula_excel_engine.py` | 20 | Excel export (thin wrapper) |
| `transaction_validator.py` | 19 | Validation wrapper |
| `reconciliation.py` | 25 | Reconciliation wrapper |
| `rule_engine.py` | 19 | Rule engine wrapper |
| `recurring_engine.py` | 16 | Recurring detection wrapper |
| `aggregation_engine.py` | 16 | Aggregation wrapper |
| `excel_generator.py` | 17 | Legacy Excel wrapper |
| `ai_fallback.py` | 17 | AI fallback wrapper |

### Indian Bank Markers
```python
INDIAN_BANK_MARKERS = [
    r"INDIAN\s*BANK",
    r"idib\.in",
    r"IDIB\d{7}",
    r"ACCOUNT\s*STATEMENT",
    r"ACCOUNT\s*ACTIVITY",
    r"Account\s*Type",
    r"SAVINGS",
    r"Opening\s*Balance",
    r"Closing\s*Balance",
]
```

### Indian Bank Aliases
```python
support_aliases = [
    "indian bank",
    "indian",
    "idib",
]
```

### Key Design Decisions for Indian Bank

1. **Uses Shared Components**: All wrapper files delegate to shared generic implementations
2. **Loads words.json**: Classifier explicitly loads the shared classification database
3. **Thin Excel Engine**: `FormulaExcelEngine` is a thin wrapper over `FormulaExcelEngineBase`
4. **Supabase Integration**: Uses shared `StatementMetadataExtractor` and `AuditService` for metadata persistence
5. **Frontend Support**: Added to bank types and options for UI selection

---

## Bank of India Reference Implementation

Bank of India now follows the same first-class integration pattern as Indian Bank and HDFC, with a dedicated package and shared backend routing.

### Files Created for Bank of India

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `processor.py` | Main processor wiring shared components |
| `parser.py` | Bank of India-specific transaction parsing |
| `structure_validator.py` | PDF validation with Bank of India markers |
| `bank_of_india_classifier.py` | Classification with `words.json` + Bank of India tuning |
| `report_generator.py` | Report wrapper for shared report generator |
| `formula_excel_engine.py` | Excel export (thin wrapper over shared base) |
| `transaction_validator.py` | Validation wrapper |
| `reconciliation.py` | Reconciliation wrapper |
| `rule_engine.py` | Rule engine wrapper |
| `recurring_engine.py` | Recurring detection wrapper |
| `aggregation_engine.py` | Aggregation wrapper |
| `excel_generator.py` | Legacy Excel wrapper |
| `ai_fallback.py` | AI fallback wrapper |

### Bank of India Markers
```python
BANK_OF_INDIA_MARKERS = [
    r"DETAILED STATEMENT",
    r"CUSTOMER ID",
    r"ACCOUNT HOLDER NAME",
    r"ACCOUNT NUMBER",
    r"SR NO",
    r"DEBIT CREDIT BALANCE",
    r"BKID",
]
```

### Bank of India Aliases
```python
support_aliases = [
    "bank of india",
    "bankofindia",
    "boi",
    "bkid",
]
```

### Key Design Decisions for Bank of India

1. **Uses Shared Components**: All wrapper files delegate to shared generic implementations.
2. **Loads words.json**: Classifier explicitly loads the shared classification database.
3. **FormulaExcelEngineBase**: Excel export uses the same shared engine and workbook structure as other banks.
4. **Supabase Integration**: Uses the shared metadata persistence path in the base processor pipeline.
5. **Frontend Support**: Added to the frontend bank types and options for UI selection.

---

## Troubleshooting

### Common Issues

#### Issue: `TypeError: reconcile() got unexpected keyword argument 'expected_opening'`
**Fix**: Update reconciliation wrapper to accept and pass through all keyword arguments:
```python
def reconcile(self, ..., expected_opening=None, expected_closing=None, **kwargs):
    resolved_opening = expected_opening if expected_opening is not None else opening
    resolved_closing = expected_closing if expected_closing is not None else closing
    return self._delegate.reconcile(...)
```

#### Issue: `OSError: Cannot save file into non-existent directory`
**Fix**: Ensure `FormulaExcelEngineBase.generate()` creates the output directory:
```python
parent_dir = os.path.dirname(output_path)
if parent_dir:
    os.makedirs(parent_dir, exist_ok=True)
```

#### Issue: Excel export doesn't match other banks
**Fix**: Ensure you're using `FormulaExcelEngineBase` (shared) instead of a custom writer.

#### Issue: Category classification inaccurate
**Fix**: 
1. Ensure classifier loads `words.json`: `keywords_file or DEFAULT_KEYWORDS_FILE`
2. Add bank-specific aliases to `words.json` under `entity_interpretation`
3. Add bank-specific tuning in classifier's `_apply_bank_tuning()`

---

## Checklist for New Bank

- [ ] Create bank package directory
- [ ] Create all required Python files
- [ ] Define bank markers and aliases
- [ ] Implement parser with bank-specific patterns
- [ ] Implement structure validator
- [ ] Create classifier loading `words.json`
- [ ] Create thin wrapper files for all shared components
- [ ] Register in `banks/__init__.py`
- [ ] Register in `pipeline_orchestrator.py`
- [ ] Add hygiene detection in `hygiene_check.py`
- [ ] Add frontend types in `frontend/types/index.ts`
- [ ] Add frontend options in `frontend/lib/banks.ts`
- [ ] Compile test all Python files
- [ ] Smoke test with sample PDF
- [ ] Verify Excel output matches shared format
- [ ] Verify metadata persists to Supabase
- [ ] Confirm no regressions in other banks

---

## Summary

The Indian Bank integration demonstrates the **thin wrapper pattern**: bank-specific logic is limited to parsing and validation, while all other functionality delegates to shared components. This ensures:

1. **Consistency**: All banks export the same Excel format
2. **Maintainability**: Changes to shared logic apply to all banks
3. **Accuracy**: All banks use the same classification database (`words.json`)
4. **Reliability**: Shared components are tested across all banks

For adding a new bank, use **HDFC or Indian Bank** as your reference template, and follow the checklist above.
