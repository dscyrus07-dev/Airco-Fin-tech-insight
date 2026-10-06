"""Slice 2C service-layer tests: analyze -> confirm/override -> process, isolation, ownership, retention.
No network, no Redis, no S3: in-memory store and a fake object storage."""
import asyncio
import json
import os
import tempfile

import pikepdf

from app.services.analysis_service import (
    AnalysisError,
    AnalysisService,
    MemoryAnalysisStore,
    UploadedPdf,
)
from app.services.statement_engine import (
    Capability,
    CapabilityResult,
    Confidence,
    DetectionResult,
    DocumentAnalysis,
    DocumentState,
    Evidence,
    EvidenceKind,
)
from tests.statement_engine.test_real_pdfs import TABLE, _build_text_pdf

ALICE = {"id": "alice-1", "email": "alice@example.com", "name": "Alice"}
BOB = {"id": "bob-2", "email": "bob@example.com", "name": "Bob"}


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.fail_put = False

    def put(self, local_path, key):
        if self.fail_put:
            return False
        with open(local_path, "rb") as fh:
            self.objects[key] = fh.read()
        return True

    def get(self, key):
        if key not in self.objects:
            return None
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        f.write(self.objects[key])
        f.close()
        return f.name

    def delete(self, key):
        self.objects.pop(key, None)


def make_service():
    started = []

    async def fake_submit(rec, doc, user):
        started.append((rec["analysis_id"], doc["document_id"], doc["effective_bank"]["id"]))
        return "job-" + doc["document_id"][:6]

    svc = AnalysisService(store=MemoryAnalysisStore(), storage=FakeStorage(), submit_job=fake_submit)
    return svc, started


def pdf_bytes(text, password=None):
    pdf = _build_text_pdf(text)
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    f.close()
    if password:
        pdf.save(f.name, encryption=pikepdf.Encryption(user=password, owner=password, R=6))
    else:
        pdf.save(f.name)
    with open(f.name, "rb") as fh:
        data = fh.read()
    os.unlink(f.name)
    return data


HDFC = "HDFC BANK LIMITED\nStatement of account\nIFSC Code : HDFC0001234\nVisit www.hdfcbank.com\n" + TABLE
KOTAK = "Kotak Mahindra Bank Ltd\nIFSC Code : KKBK0000431\nVisit www.kotak.com\n" + TABLE
PAYSLIP = "Payslip for May 2024\nName: A B\nEmployee No: 3\nBank Name: HDFC Bank\n"


def run(coro):
    return asyncio.run(coro)


def doc_by_name(view, name):
    return next(d for d in view["documents"] if d["filename"] == name)


# ---------------------------------------------------------------- detection states (pure mapping)
def _analysis(state, conf, bank="hdfc", supported=True, cap=Capability.TEXT, hint_conflict=False):
    det = DetectionResult(bank_id=bank, bank_name="HDFC Bank", confidence=conf, score=50, supported=supported,
                          evidence=[Evidence(EvidenceKind.IFSC_LABELLED, bank, 40, "HDFC0001234", 1)], hint_conflict=hint_conflict)
    return DocumentAnalysis("x.pdf", state, CapabilityResult(cap, 1, 1), det, "m")


class _F:
    content = b"%PDF-1.4"


def build(analysis, layout=None):
    svc, _ = make_service()
    return svc._build_doc("d1", "x.pdf", _F, analysis, layout, "k")


def test_very_high_and_high_are_detected_without_confirmation_flag():
    for conf in (Confidence.VERY_HIGH, Confidence.HIGH):
        d = build(_analysis(DocumentState.DETECTED, conf))
        assert d["state"] == "DETECTED" and d["requires_confirmation"] is False
        assert d["bank"]["id"] == "hdfc" and d["bank"]["supported"] is True
        assert d["workflow_status"] == "AWAITING_CONFIRMATION"  # still needs the explicit confirm click


def test_medium_is_review_and_needs_confirmation():
    d = build(_analysis(DocumentState.AWAITING_CONFIRMATION, Confidence.MEDIUM))
    assert d["state"] == "REVIEW" and d["requires_confirmation"] is True and d["bank"]["confidence"] == "MEDIUM"


def test_low_is_never_a_trusted_bank():
    d = build(_analysis(DocumentState.UNKNOWN_BANK, Confidence.LOW))
    assert d["state"] == "UNKNOWN" and d["bank"] is None
    assert d["suggestion"]["id"] == "hdfc"  # kept only as a suggestion


def test_unknown_stays_unknown():
    det = DetectionResult(bank_id=None, bank_name=None, confidence=Confidence.UNKNOWN)
    d = build(DocumentAnalysis("x.pdf", DocumentState.UNKNOWN_BANK, CapabilityResult(Capability.TEXT, 1, 1), det, "m"))
    assert d["state"] == "UNKNOWN" and d["bank"] is None and d["suggestion"] is None


def test_unsupported_bank_is_unsupported_but_correctable():
    d = build(_analysis(DocumentState.UNSUPPORTED_BANK, Confidence.VERY_HIGH, bank="yes", supported=False))
    assert d["state"] == "UNSUPPORTED" and d["workflow_status"] == "AWAITING_CONFIRMATION" and d["bank"]["supported"] is False


def test_scanned_and_locked_states():
    s = build(DocumentAnalysis("x.pdf", DocumentState.UNSUPPORTED_SCANNED_PDF, CapabilityResult(Capability.SCANNED, 2, 0, 2), None, "scanned"))
    assert s["state"] == "UNSUPPORTED" and s["workflow_status"] == "BLOCKED" and s["bank"] is None
    l = build(DocumentAnalysis("x.pdf", DocumentState.PASSWORD_REQUIRED, CapabilityResult(Capability.LOCKED), None, "locked"))
    assert l["state"] == "REVIEW" and l["requires_password"] is True


# ---------------------------------------------------------------- real PDFs through analyze()
def test_single_pdf_is_analyzed_with_bank_evidence_and_layout():
    svc, _ = make_service()
    view = run(svc.analyze(ALICE, [UploadedPdf("hdfc.pdf", pdf_bytes(HDFC))]))
    d = view["documents"][0]
    assert d["capability"]["capability"] == "TEXT"
    assert d["bank"]["id"] == "hdfc" and d["bank"]["confidence"] in ("VERY_HIGH", "HIGH")
    assert any(e["type"] == "IFSC" for e in d["evidence"]) and all(e["label"] for e in d["evidence"])
    assert d["layout"]["id"] == "date_narration_withdrawal_deposit_balance" and d["layout"]["parser_family"] == "legacy:hdfc"
    assert "storage_key" not in d  # internal only


def test_bank_hint_is_a_hint_not_a_decision():
    svc, _ = make_service()
    view = run(svc.analyze(ALICE, [UploadedPdf("a.pdf", pdf_bytes(HDFC))], bank_hint="SBI"))
    d = view["documents"][0]
    assert d["bank"]["id"] == "hdfc" and d["hint_conflict"] is True and d["state"] == "REVIEW"


def test_batch_isolation_mixed_files():
    svc, _ = make_service()
    scanned = _image_only_pdf()
    files = [
        UploadedPdf("a.pdf", pdf_bytes(HDFC)), UploadedPdf("b.pdf", pdf_bytes(KOTAK)), UploadedPdf("c.pdf", pdf_bytes(HDFC)),
        UploadedPdf("scan.pdf", scanned), UploadedPdf("broken.pdf", b"not a pdf"), UploadedPdf("notes.txt", b"hello"),
        UploadedPdf("payslip.pdf", pdf_bytes(PAYSLIP)),
    ]
    view = run(svc.analyze(ALICE, files))
    assert len(view["documents"]) == 7  # one bad file never fails the batch
    by = {d["filename"]: d for d in view["documents"]}
    assert by["a.pdf"]["state"] == "DETECTED" and by["b.pdf"]["bank"]["id"] == "kotak" and by["c.pdf"]["state"] == "DETECTED"
    assert by["scan.pdf"]["state"] == "UNSUPPORTED" and by["scan.pdf"]["capability"]["capability"] == "SCANNED"
    assert by["broken.pdf"]["state"] == "ERROR" and by["notes.txt"]["state"] == "ERROR"
    assert by["payslip.pdf"]["state"] in ("UNKNOWN", "UNSUPPORTED") and by["payslip.pdf"]["bank"] is None
    groups = {g["bank_id"]: g["count"] for g in view["summary"]["groups"]}
    assert groups.get("hdfc") == 2 and groups.get("kotak") == 1


def _image_only_pdf():
    from pikepdf import Array, Dictionary, Name, Stream

    pdf = pikepdf.new()
    img = Stream(pdf, bytes([255]) * (50 * 50 * 3))
    img.Type, img.Subtype = Name.XObject, Name.Image
    img.Width, img.Height, img.ColorSpace, img.BitsPerComponent = 50, 50, Name.DeviceRGB, 8
    content = pdf.make_stream(b"q 400 0 0 400 50 200 cm /Im0 Do Q")
    page = pdf.make_indirect(Dictionary(Type=Name.Page, MediaBox=Array([0, 0, 595, 842]),
                                        Resources=Dictionary(XObject=Dictionary(Im0=pdf.make_indirect(img))), Contents=content))
    pdf.pages.append(pikepdf.Page(page))
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    f.close()
    pdf.save(f.name)
    data = open(f.name, "rb").read()
    os.unlink(f.name)
    return data


def test_locked_pdf_password_flow_and_password_is_never_stored():
    svc, _ = make_service()
    locked = pdf_bytes(KOTAK, password="s3cret-pw")
    view = run(svc.analyze(ALICE, [UploadedPdf("locked.pdf", locked)]))
    d = view["documents"][0]
    assert d["state"] == "REVIEW" and d["requires_password"] is True and d["bank"] is None
    aid, did = view["analysis_id"], d["document_id"]
    bad = run(svc.unlock(aid, did, ALICE, "wrong"))
    assert bad["unlocked"] is False
    assert "did not open" in bad["document"]["message"]
    ok = run(svc.unlock(aid, did, ALICE, "s3cret-pw"))
    assert ok["unlocked"] is True and ok["document"]["bank"]["id"] == "kotak" and ok["document"]["requires_password"] is False
    assert ok["document"]["document_id"] == did
    dumped = json.dumps(svc.store._data)
    assert "s3cret-pw" not in dumped and "wrong" not in dumped


def test_password_supplied_up_front_unlocks_during_analyze():
    svc, _ = make_service()
    view = run(svc.analyze(ALICE, [UploadedPdf("l.pdf", pdf_bytes(HDFC, password="pw1"))], passwords={"l.pdf": "pw1"}))
    d = view["documents"][0]
    assert d["state"] == "DETECTED" and d["bank"]["id"] == "hdfc"
    # the stored copy is the decrypted one, so processing never needs the password
    key = next(iter(svc.storage.objects))
    with pikepdf.open(__import__("io").BytesIO(svc.storage.objects[key])) as p:
        assert not p.is_encrypted


def test_storage_failure_isolated_to_one_document():
    svc, _ = make_service()
    svc.storage.fail_put = True
    view = run(svc.analyze(ALICE, [UploadedPdf("a.pdf", pdf_bytes(HDFC))]))
    assert view["documents"][0]["state"] == "ERROR"


# ---------------------------------------------------------------- confirmation, override, audit
def _analyzed(svc):
    view = run(svc.analyze(ALICE, [UploadedPdf("hdfc.pdf", pdf_bytes(HDFC)), UploadedPdf("payslip.pdf", pdf_bytes(PAYSLIP)), UploadedPdf("scan.pdf", _image_only_pdf())]))
    return view, doc_by_name(view, "hdfc.pdf"), doc_by_name(view, "payslip.pdf"), doc_by_name(view, "scan.pdf")


def test_processing_does_not_start_before_confirmation():
    svc, started = make_service()
    view, good, _, _ = _analyzed(svc)
    res = run(svc.process_confirmed(view["analysis_id"], ALICE))
    assert started == [] and res["started"] == []
    assert {s["reason"] for s in res["skipped"]} >= {"NOT_CONFIRMED", "NOT_PROCESSABLE"}


def test_confirm_then_process_uses_detected_bank():
    svc, started = make_service()
    view, good, _, _ = _analyzed(svc)
    out = run(svc.confirm(view["analysis_id"], ALICE, [{"document_id": good["document_id"], "action": "CONFIRM"}]))
    assert out["results"][0]["ok"] is True
    res = run(svc.process_confirmed(view["analysis_id"], ALICE))
    assert [s[2] for s in started] == ["hdfc"] and len(res["started"]) == 1
    again = run(svc.process_confirmed(view["analysis_id"], ALICE))  # no double start
    assert again["started"] == [] and len(started) == 1


def test_confirm_all_detected_leaves_exceptions_alone():
    svc, started = make_service()
    view, good, bad, scan = _analyzed(svc)
    out = run(svc.confirm(view["analysis_id"], ALICE, [], confirm_all_detected=True))
    status = {d["filename"]: d["workflow_status"] for d in out["documents"]}
    assert status["hdfc.pdf"] == "CONFIRMED" and status["payslip.pdf"] != "CONFIRMED" and status["scan.pdf"] == "BLOCKED"


def test_unknown_must_be_overridden_not_confirmed():
    svc, started = make_service()
    view, _, bad, _ = _analyzed(svc)
    r = run(svc.confirm(view["analysis_id"], ALICE, [{"document_id": bad["document_id"], "action": "CONFIRM"}]))["results"][0]
    assert r["ok"] is False and r["code"] == "BANK_REQUIRED"


def test_override_is_audited_and_keeps_original_detection():
    svc, started = make_service()
    view, good, _, _ = _analyzed(svc)
    out = run(svc.confirm(view["analysis_id"], ALICE, [{"document_id": good["document_id"], "action": "OVERRIDE", "bank_id": "sbi"}]))
    d = doc_by_name(out, "hdfc.pdf")
    assert d["bank"]["id"] == "hdfc" and d["bank"]["confidence"] in ("VERY_HIGH", "HIGH")  # detection untouched
    assert d["effective_bank"]["id"] == "sbi" and d["selection"]["action"] == "OVERRIDE"
    ev = next(e for e in d["events"] if e["event"] == "USER_OVERRIDE")
    assert ev["detected_bank"] == "hdfc" and ev["user_selected_bank"] == "sbi" and ev["by"] == ALICE["id"]
    run(svc.process_confirmed(view["analysis_id"], ALICE))
    assert started[0][2] == "sbi"


def test_override_unknown_document_and_reject_bad_banks():
    svc, started = make_service()
    view, _, bad, scan = _analyzed(svc)
    ok = run(svc.confirm(view["analysis_id"], ALICE, [{"document_id": bad["document_id"], "action": "OVERRIDE", "bank_id": "kotak"}]))["results"][0]
    assert ok["ok"] is True
    for bank in ("yes", "unknown", "", None, "../etc"):
        r = run(svc.confirm(view["analysis_id"], ALICE, [{"document_id": bad["document_id"], "action": "OVERRIDE", "bank_id": bank}]))["results"][0]
        assert r["ok"] is False and r["code"] == "BANK_NOT_SUPPORTED"
    r = run(svc.confirm(view["analysis_id"], ALICE, [{"document_id": scan["document_id"], "action": "OVERRIDE", "bank_id": "hdfc"}]))["results"][0]
    assert r["ok"] is False and r["code"] == "NOT_CONFIRMABLE"  # a scanned PDF can never be forced through


def test_locked_document_cannot_be_confirmed_before_unlock():
    svc, _ = make_service()
    view = run(svc.analyze(ALICE, [UploadedPdf("l.pdf", pdf_bytes(HDFC, password="pw"))]))
    d = view["documents"][0]
    r = run(svc.confirm(view["analysis_id"], ALICE, [{"document_id": d["document_id"], "action": "OVERRIDE", "bank_id": "hdfc"}]))["results"][0]
    assert r["ok"] is False and r["code"] == "PASSWORD_REQUIRED"


# ---------------------------------------------------------------- ownership
def test_other_users_cannot_read_confirm_or_process():
    svc, started = make_service()
    view, good, _, _ = _analyzed(svc)
    aid = view["analysis_id"]
    for call in (
        lambda: svc.get(aid, BOB),
        lambda: svc.confirm(aid, BOB, [{"document_id": good["document_id"], "action": "CONFIRM"}]),
        lambda: svc.process_confirmed(aid, BOB),
        lambda: svc.unlock(aid, good["document_id"], BOB, "x"),
    ):
        try:
            run(call())
            assert False, "foreign access must fail"
        except AnalysisError as exc:
            assert exc.status_code == 404  # indistinguishable from a missing analysis
    assert started == []


def test_unauthenticated_user_dict_is_rejected():
    svc, _ = make_service()
    try:
        run(svc.analyze({}, [UploadedPdf("a.pdf", pdf_bytes(HDFC))]))
        assert False
    except AnalysisError as exc:
        assert exc.status_code == 401


def test_limits():
    svc, _ = make_service()
    try:
        run(svc.analyze(ALICE, []))
        assert False
    except AnalysisError as exc:
        assert exc.code == "NO_FILES"


# ---------------------------------------------------------------- retention
def test_expired_unconfirmed_analyses_are_purged_with_their_files():
    svc, _ = make_service()
    view = run(svc.analyze(ALICE, [UploadedPdf("a.pdf", pdf_bytes(HDFC))]))
    assert len(svc.storage.objects) == 1
    assert run(svc.purge_expired(now_ts=0)) == 0  # not yet expired
    import time

    assert run(svc.purge_expired(now_ts=time.time() + 10 * 24 * 3600)) == 1
    assert svc.storage.objects == {} and run(svc.store.get(view["analysis_id"])) is None
