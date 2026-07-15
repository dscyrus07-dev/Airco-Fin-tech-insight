# Bank-Specific Processors

This directory contains bank-specific processing modules for the V2 accuracy-first architecture.

## Philosophy

**One Bank = One Complete Processor**

Each bank has its own dedicated module with:
- Structure validation (format detection)
- Transaction parsing (extraction logic)
- Field validation (data quality)
- Balance reconciliation (verification)
- Classification rules (deterministic)
- AI fallback (optional enhancement)
- Analytics & reporting

**No Generic Fallbacks**

The system does NOT:
- Auto-detect banks
- Use generic parsers
- Apply universal rules
- Mix bank logic

## Directory Structure

```
banks/
├── __init__.py
├── README.md (this file)
├── hdfc/                    # HDFC Bank (Complete ✅)
│   ├── __init__.py
│   ├── processor.py        # Master orchestrator
│   ├── structure_validator.py
│   ├── parser.py
│   ├── transaction_validator.py
│   ├── reconciliation.py
│   ├── rule_engine.py
│   ├── ai_fallback.py
│   ├── recurring_engine.py
│   ├── aggregation_engine.py
│   └── excel_generator.py
├── icici/                   # ICICI Bank (Planned)
├── axis/                    # Axis Bank (Planned)
└── kotak/                   # Kotak Bank (Planned)
```

## Module Template

Every bank module must implement these files:

### 1. `processor.py` (Required)
Master controller that orchestrates all other modules.

**Class:** `{Bank}Processor`

**Methods:**
- `__init__(strict_mode, enable_ai, api_key)`
- `process(file_path, user_info, output_dir) -> Result`

**Responsibilities:**
- Initialize all sub-modules
- Execute pipeline in strict order
- Handle errors at each stage
- Return structured result

### 2. `structure_validator.py` (Required)
Validates PDF matches bank's statement format.

**Class:** `{Bank}StructureValidator`

**Methods:**
- `validate(text_content, first_page_text) -> Result`

**Responsibilities:**
- Check for bank markers (logo, IFSC, etc.)
- Extract statement metadata
- Verify transaction table structure
- Return confidence score

### 3. `parser.py` (Required)
Extracts transactions from PDF.

**Class:** `{Bank}Parser`

**Methods:**
- `parse(file_path, text_content) -> Result`

**Responsibilities:**
- Try table extraction first
- Fallback to text parsing
- Handle multi-line transactions
- Extract all fields (date, desc, debit, credit, balance)
- Return 100% of transactions or fail

### 4. `transaction_validator.py` (Required)
Validates extracted transaction fields.

**Class:** `{Bank}TransactionValidator`

**Methods:**
- `validate(transactions) -> Result`

**Responsibilities:**
- Check required fields present
- Normalize date formats
- Validate amounts
- Clean descriptions
- Generate transaction IDs

### 5. `reconciliation.py` (Required)
Verifies balance integrity.

**Class:** `{Bank}Reconciliation`

**Methods:**
- `reconcile(transactions, expected_opening, expected_closing) -> Result`
- `auto_correct_debit_credit(transactions) -> (corrected, count)`

**Responsibilities:**
- Check opening + credits - debits = closing
- Verify sequential balance progression
- Auto-correct debit/credit if needed
- Return pass/fail with details

### 6. `rule_engine.py` (Required)
Deterministic classification rules.

**Class:** `{Bank}RuleEngine`

**Methods:**
- `classify(transactions) -> (classified, unclassified)`

**Responsibilities:**
- Apply bank-specific keyword rules
- Category hierarchy (exact > pattern > merchant)
- High confidence assignments (0.9+)
- Return classified + unclassified lists

### 7. `ai_fallback.py` (Required)
AI classification for unresolved transactions.

**Class:** `{Bank}AIFallback`

**Methods:**
- `classify(transactions, bank_name, account_type) -> (results, stats)`
- `estimate_cost(count) -> dict`

**Responsibilities:**
- Claude API integration
- Batch processing
- Cost estimation
- Validate AI responses
- Fallback to "Others" on error

### 8. `recurring_engine.py` (Required)
Detects recurring patterns.

**Class:** `{Bank}RecurringEngine`

**Methods:**
- `detect(transactions) -> transactions_with_flags`

**Responsibilities:**
- Detect subscriptions, EMIs, salaries
- Identify frequency (weekly, monthly, quarterly)
- Mark recurring vs one-time
- Add metadata fields

### 9. `aggregation_engine.py` (Required)
Computes financial analytics.

**Class:** `{Bank}AggregationEngine`

**Methods:**
- `aggregate(transactions, opening, closing) -> Result`

**Responsibilities:**
- Category-wise totals
- Monthly/weekly summaries
- Recurring split
- Top merchants
- Spending trends

### 10. `excel_generator.py` (Required)
Generates formatted Excel report.

**Class:** `{Bank}ExcelGenerator`

**Methods:**
- `generate(transactions, aggregation, user_info, output_path) -> path`

**Responsibilities:**
- Create 8+ sheet workbook
- Professional formatting
- Charts (optional)
- Summary page
- All transactions page

## Implementation Checklist

When creating a new bank module:

### Phase 1: Research & Analysis
- [ ] Collect 10+ sample PDFs
- [ ] Document statement format
- [ ] Identify column structure
- [ ] Note date/amount formats
- [ ] List bank-specific patterns

### Phase 2: Core Implementation
- [ ] Implement structure_validator
- [ ] Implement parser (table + text)
- [ ] Implement transaction_validator
- [ ] Implement reconciliation
- [ ] Test with all sample PDFs

### Phase 3: Intelligence
- [ ] Build bank-specific rule engine
- [ ] Add 200+ classification keywords
- [ ] Test classification coverage
- [ ] Implement AI fallback
- [ ] Implement recurring detection

### Phase 4: Output & Polish
- [ ] Implement aggregation engine
- [ ] Implement excel generator
- [ ] Create processor orchestrator
- [ ] Add comprehensive error handling
- [ ] Write unit tests

### Phase 5: Integration
- [ ] Register in pipeline_orchestrator_v2.py
- [ ] Add to supported banks list
- [ ] Update API documentation
- [ ] Create test script
- [ ] Deploy to production

## Testing Standards

Every bank module must pass:

1. **Parsing Accuracy:** 100% transaction capture
2. **Balance Reconciliation:** 100% pass rate
3. **Classification Coverage:** 60%+ (rule engine only)
4. **Processing Speed:** <10 seconds per statement
5. **Error Handling:** Graceful failures with clear messages

## Quality Metrics

Target benchmarks per bank:

| Metric | Target | Excellent |
|--------|--------|-----------|
| Parsing Success | 95%+ | 99%+ |
| Balance Reconciliation | 95%+ | 99%+ |
| Classification (Rules) | 50%+ | 70%+ |
| Classification (AI) | 85%+ | 95%+ |
| Processing Time | <15s | <5s |

## Code Standards

- **Type Hints:** All functions must have type hints
- **Docstrings:** All classes and public methods
- **Error Handling:** Custom exceptions with error codes
- **Logging:** Info at checkpoints, debug for details
- **No Side Effects:** Pure functions where possible
- **Testability:** Easy to unit test each component

## Common Patterns

### Error Handling
```python
class BankSpecificError(Exception):
    def __init__(self, message, error_code, details=None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)
```

### Result Objects
```python
from dataclasses import dataclass

@dataclass
class ProcessingResult:
    is_valid: bool
    data: Any
    error_code: Optional[str] = None
    error_message: Optional[str] = None
```

### Logging
```python
logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
logger.info("Processing started: %d transactions", count)
logger.debug("Detailed info: %s", data)
```

## Resources

- **HDFC Reference:** Complete implementation in `hdfc/`
- **Core Validators:** `../core/` for reusable validation logic
- **Legacy V1:** `../legacy_v1/` for historical reference (don't copy this!)

---

**Maintainer:** Airco Insights Team  
**Last Updated:** February 2026
