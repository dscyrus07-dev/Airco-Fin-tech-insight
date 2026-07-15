# Backend — Airco Insights Processing Engine

Bank-specific accuracy-first transaction categorization backend.

## 📁 Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry
│   ├── services/            # Core processing services
│   │   ├── banks/          # Bank-specific processors (V2)
│   │   │   └── hdfc/       # HDFC Bank complete processor
│   │   │       ├── processor.py          # Master orchestrator
│   │   │       ├── structure_validator.py # HDFC format validation
│   │   │       ├── parser.py             # Transaction extraction
│   │   │       ├── transaction_validator.py # Field validation
│   │   │       ├── reconciliation.py     # Balance checks
│   │   │       ├── rule_engine.py        # Classification rules
│   │   │       ├── ai_fallback.py        # Claude AI (optional)
│   │   │       ├── recurring_engine.py   # Recurring detection
│   │   │       ├── aggregation_engine.py # Analytics
│   │   │       └── excel_generator.py    # Report generation
│   │   ├── core/           # Core validators
│   │   │   ├── pdf_integrity_validator.py # PDF validation
│   │   │   └── data_integrity_guard.py    # Final validation
│   │   ├── pipeline_orchestrator_v2.py # V2 pipeline router
│   │   └── legacy_v1/      # Old architecture (archived)
│   ├── routers/            # API endpoints
│   │   ├── upload_v2.py   # V2 accuracy-first endpoint ⭐
│   │   ├── upload.py      # Legacy V1 endpoint
│   │   └── download.py    # File download endpoint
│   ├── api/
│   │   └── routes/        # Additional API routes
│   │       └── feedback.py # Feedback collection
│   ├── core/              # Core configuration
│   │   ├── config.py      # Settings & environment
│   │   └── security.py    # Upload validation
│   ├── database/          # Database layer
│   │   ├── session.py     # DB connection
│   │   └── models.py      # SQLAlchemy models
│   └── utils/             # Utilities
│       └── file_handler.py # File operations
├── scripts/               # Testing & analysis
│   ├── test_hdfc_v2.py   # HDFC V2 testing script
│   ├── analyze_all_pdfs.py # Bulk analysis
│   └── find_unclassified_patterns.py # Pattern discovery
├── tests/                 # Unit & integration tests
├── data/                  # Processing data storage
├── temp/                  # Temporary files
├── Dockerfile            # Docker container config
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## 🚀 Getting Started

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Environment Setup

Create `.env` file in root:
```env
# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# AI (optional for hybrid mode)
ANTHROPIC_API_KEY=your_claude_key

# Server
TEMP_DIR=./temp
```

### Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Test HDFC Processor

```bash
python scripts/test_hdfc_v2.py
```

## 🏗️ V2 Architecture

### Key Concepts

**Bank-Specific Processors:**
- Each bank has its own complete processing module
- No generic fallbacks or auto-detection
- User explicitly selects bank before upload

**Validation Layers:**
1. PDF Integrity → File is valid, text-based PDF
2. Structure Validation → Matches bank's statement format
3. Transaction Validation → All required fields present
4. Balance Reconciliation → Opening + Credits - Debits = Closing
5. Data Integrity → 100% checks pass before output

**Processing Pipeline:**
```
User Input (Bank Selection)
    ↓
PDF Upload → PDF Validator
    ↓
Bank-Specific Processor
    ├── Structure Validator
    ├── Parser
    ├── Transaction Validator
    ├── Reconciliation Engine
    ├── Rule Engine (Deterministic)
    ├── AI Fallback (Optional)
    ├── Recurring Detector
    ├── Aggregation Engine
    └── Excel Generator
    ↓
Integrity Guard (100% or Fail)
    ↓
Validated Output
```

## 📊 HDFC Module (Complete)

**Files:**
- `processor.py` - Orchestrates all HDFC modules
- `structure_validator.py` - Validates HDFC format, extracts metadata
- `parser.py` - Extracts transactions (table & text methods)
- `transaction_validator.py` - Validates & normalizes fields
- `reconciliation.py` - Balance verification, auto-correction
- `rule_engine.py` - 500+ deterministic rules
- `ai_fallback.py` - Claude API for unclassified (optional)
- `recurring_engine.py` - Subscription/EMI/salary detection
- `aggregation_engine.py` - Financial analytics
- `excel_generator.py` - 8-sheet Excel report

**Test Results:**
- 12/12 PDFs processed successfully
- 7,129 total transactions
- 64.2% rule engine coverage
- 100% balance reconciliation
- ~7 seconds average processing time

## 🔧 API Endpoints

### V2 Endpoints (Primary)

**POST /process/v2**
```python
# Request
{
    "full_name": str,
    "account_type": "Salaried" | "Business",
    "bank_name": "HDFC Bank",  # Required
    "mode": "free" | "hybrid",
    "file": UploadFile
}

# Response
{
    "status": "success",
    "excel_url": str,
    "stats": {
        "total_transactions": int,
        "rule_engine_classified": int,
        "others": int,
        "coverage_percent": float
    },
    "validation": {
        "reconciliation_passed": bool,
        "integrity_passed": bool
    },
    "performance": {...}
}
```

**GET /supported-banks**
```python
# Response
{
    "banks": [
        {
            "key": "hdfc",
            "name": "HDFC Bank",
            "status": "available",
            "accuracy": "99%+"
        }
    ],
    "modes": [...]
}
```

### Legacy Endpoints (V1)

**POST /process**  
Generic processing with auto-detection (deprecated but functional)

## 🧪 Testing

### Unit Tests
```bash
pytest tests/
```

### HDFC Integration Test
```bash
# Single PDF
python scripts/test_hdfc_v2.py

# All PDFs
python scripts/test_hdfc_v2.py --all
```

## 📝 Adding New Banks

### Step 1: Create Bank Module
```bash
mkdir -p app/services/banks/icici
```

### Step 2: Implement Required Files
Copy HDFC module structure and adapt:
- `processor.py` - Main orchestrator
- `structure_validator.py` - Bank-specific format validation
- `parser.py` - Transaction extraction logic
- `transaction_validator.py` - Field validation
- `reconciliation.py` - Balance verification
- `rule_engine.py` - Classification rules
- `ai_fallback.py` - AI integration
- `recurring_engine.py` - Pattern detection
- `aggregation_engine.py` - Analytics
- `excel_generator.py` - Report generation

### Step 3: Register in Pipeline
Edit `app/services/pipeline_orchestrator_v2.py`:
```python
def _get_bank_processor(bank_key: str):
    if bank_key == "hdfc":
        from app.services.banks.hdfc import HDFCProcessor
        return HDFCProcessor
    elif bank_key == "icici":
        from app.services.banks.icici import ICICIProcessor
        return ICICIProcessor
    # ...
```

### Step 4: Test Thoroughly
- Create test script: `scripts/test_icici_v2.py`
- Test with 10+ sample PDFs
- Verify 100% balance reconciliation
- Check classification coverage

## 🐛 Debugging

### Enable Detailed Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Issues

**Parsing Failure:**
- Check PDF format (text vs scanned)
- Verify statement structure matches parser expectations
- Review table extraction vs text extraction logic

**Balance Mismatch:**
- Enable auto-correction in reconciliation
- Check for multi-line transactions
- Verify debit/credit detection logic

**Low Classification:**
- Add more keywords to rule_engine.py
- Use hybrid mode for AI assistance
- Analyze unclassified patterns with scripts

## 📈 Performance

Current benchmarks (HDFC):
- PDF parsing: ~1.5s
- Transaction validation: ~10ms
- Rule engine: ~5ms
- Excel generation: ~600ms
- **Total: ~2-3s** (without AI)

Optimization targets:
- Parallel PDF processing
- Rule engine caching
- Batch AI classification

## 🔒 Security

- File size limit: 20MB
- Allowed formats: PDF only
- API key validation (hybrid mode)
- Temporary file cleanup
- No sensitive data logging

## 📄 Code Style

- Type hints everywhere
- Docstrings for all public functions
- Error handling with custom exceptions
- Logging at key checkpoints
- Clean separation of concerns

## 🚧 Future Enhancements

- [ ] ICICI Bank processor
- [ ] Axis Bank processor
- [ ] Kotak Bank processor
- [ ] Async processing with Celery
- [ ] WebSocket progress updates
- [ ] Multi-page batch upload
- [ ] Export to other formats (CSV, JSON)
- [ ] Machine learning model training
- [ ] Auto-rule generation from corrections

---

**Version:** 2.0.0  
**Python:** 3.11+  
**Framework:** FastAPI  
**Last Updated:** February 2026
