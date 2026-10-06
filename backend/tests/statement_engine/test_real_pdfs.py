"""Real PDF files built with pikepdf (a runtime dependency of the app, so these always run: no importorskip)."""
import pikepdf
from pikepdf import Name, Dictionary, Array, Stream

from app.services.statement_engine import Capability, DocumentState, analyze_pdf

TABLE = "Date Narration Withdrawal Deposit Balance\n" + "01/04/2021 UPI/1/SHOP 100.00 5000.00\n" * 6


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_text_pdf(text: str) -> pikepdf.Pdf:
    pdf = pikepdf.new()
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    ops = ["BT", "/F1 11 Tf", "13 TL", "50 780 Td"]
    for line in text.splitlines():
        ops.append(f"({_escape(line)}) Tj T*")
    ops.append("ET")
    content = pdf.make_stream("\n".join(ops).encode("latin-1"))
    page = pdf.make_indirect(Dictionary(
        Type=Name.Page, MediaBox=Array([0, 0, 595, 842]),
        Resources=Dictionary(Font=Dictionary(F1=font)), Contents=content))
    pdf.pages.append(pikepdf.Page(page))
    return pdf


def test_real_text_pdf_is_detected(tmp_path):
    p = tmp_path / "statement.pdf"
    _build_text_pdf("HDFC BANK LIMITED\nStatement of account for the period\nIFSC Code : HDFC0001234\n" + TABLE).save(str(p))
    a = analyze_pdf(str(p))
    assert a.capability.capability == Capability.TEXT
    assert a.detection and a.detection.bank_id == "hdfc"
    assert a.state == DocumentState.DETECTED


def test_real_image_only_pdf_is_scanned(tmp_path):
    pdf = pikepdf.new()
    img = Stream(pdf, bytes([255]) * (50 * 50 * 3))
    img.Type, img.Subtype = Name.XObject, Name.Image
    img.Width, img.Height, img.ColorSpace, img.BitsPerComponent = 50, 50, Name.DeviceRGB, 8
    content = pdf.make_stream(b"q 400 0 0 400 50 200 cm /Im0 Do Q")
    page = pdf.make_indirect(Dictionary(
        Type=Name.Page, MediaBox=Array([0, 0, 595, 842]),
        Resources=Dictionary(XObject=Dictionary(Im0=pdf.make_indirect(img))), Contents=content))
    pdf.pages.append(pikepdf.Page(page))
    p = tmp_path / "scan.pdf"
    pdf.save(str(p))
    a = analyze_pdf(str(p))
    assert a.capability.capability == Capability.SCANNED
    assert a.state == DocumentState.UNSUPPORTED_SCANNED_PDF


def test_real_encrypted_pdf_is_locked_then_opens_with_password(tmp_path):
    p = tmp_path / "locked.pdf"
    _build_text_pdf("Axis Bank Limited\nIFSC: UTIB0000123\n" + TABLE).save(
        str(p), encryption=pikepdf.Encryption(user="secret", owner="owner", R=6))
    assert analyze_pdf(str(p)).state == DocumentState.PASSWORD_REQUIRED
    assert analyze_pdf(str(p), password="wrong").state == DocumentState.PASSWORD_REQUIRED
    ok = analyze_pdf(str(p), password="secret")
    assert ok.state == DocumentState.DETECTED and ok.detection.bank_id == "axis"


def test_garbage_file_is_failed_not_a_crash(tmp_path):
    p = tmp_path / "broken.pdf"
    p.write_bytes(b"not a pdf at all")
    assert analyze_pdf(str(p)).state == DocumentState.FAILED
