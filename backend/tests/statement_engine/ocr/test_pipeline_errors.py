"""R10-B5: a failed step must carry its stage once, not twice."""
from app.services.pipeline_orchestrator import (
    PipelineAbortError, PipelineError, PipelineValidationError, _as_abort)


def test_an_abort_passes_through_untouched():
    e = PipelineAbortError("Scanned statement could not be read (OCR_NO_FIXTURE)", stage="ocr_reader",
                           error_code="OCR_NO_FIXTURE")
    out = _as_abort(e)
    assert out is e
    assert str(out) == "[ocr_reader] Scanned statement could not be read (OCR_NO_FIXTURE)"
    assert str(out).count("[ocr_reader]") == 1


def test_another_staged_error_keeps_one_prefix_and_its_codes():
    e = PipelineValidationError("bad input", stage="validate", error_code="BAD")
    out = _as_abort(e)
    assert isinstance(out, PipelineAbortError)
    assert str(out) == "[validate] bad input" and out.stage == "validate" and out.error_code == "BAD"


def test_an_unstaged_exception_becomes_a_processor_error():
    out = _as_abort(ValueError("boom"))
    assert out.stage == "bank_processor" and out.error_code == "PROCESSOR_ERROR"
    assert str(out) == "[bank_processor] Processing failed: boom"


def test_pipeline_error_keeps_its_unprefixed_message():
    assert PipelineError("x", stage="s").message == "x"
