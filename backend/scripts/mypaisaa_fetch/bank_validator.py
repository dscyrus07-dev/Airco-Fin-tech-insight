"""Second-pass bank statement validator.

Independently re-classifies every PDF under "Ready to Use PDF" using
multi-signal evidence (labeled IFSC, header bank name, bank domain, OCR
fallback for scanned pages, manifest metadata) and compares the detected
bank against the folder the file currently sits in.

IMPORTANT: requires the OCR-capable interpreter (easyocr + PyMuPDF):
    C:\\Users\\admin\\AppData\\Local\\Microsoft\\WindowsApps\\python.exe

Usage (from backend/):
    python -m scripts.mypaisaa_fetch.bank_validator --dry-run
    python -m scripts.mypaisaa_fetch.bank_validator --apply
    python -m scripts.mypaisaa_fetch.bank_validator --validate
    python -m scripts.mypaisaa_fetch.bank_validator --dry-run --sample 100
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import sqlite3
import sys
import time
import unicodedata
import zlib
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

BASE = Path(r"X:\Airco Projects\Airco Insights fintech\New Dataset\Ready to Use PDF")
MANIFEST = Path(r"X:\Airco Projects\Airco Insights fintech\New Dataset\bank_statements\manifest.db")
RULE_VERSION = 5   # bump when detection rules change -> re-detect from cached text

CACHE_FILE = BASE / "_bank_validation_cache.jsonl"
REPORT_CSV = BASE / "bank_validation_report.csv"
SUMMARY_CSV = BASE / "bank_validation_summary.csv"
MISCSV = BASE / "misclassified_statements.csv"
REVIEWCSV = BASE / "review_required.csv"

# ---------------------------------------------------------------- banks -----

# canonical bank key -> (display folder, domains, header-name regex)
BANKS: dict[str, dict] = {}


def _bank(key, folder, ifsc_prefixes, domains, name_patterns):
    BANKS[key] = {
        "folder": folder,
        "ifsc": set(ifsc_prefixes),
        "domains": [re.compile(r"(?<![a-z0-9@])" + re.escape(d), re.I)
                    for d in domains],
        "names": [re.compile(p, re.I) for p in name_patterns],
    }


_bank("hdfc", "HDFC Bank", ["HDFC"], ["hdfcbank.com", "hdfcbank.co.in"],
      [r"hdfc\s*bank"])
_bank("icici", "ICICI Bank", ["ICIC"], ["icicibank.com", "icicibank.co.in"],
      [r"icici\s*bank"])
_bank("sbi", "SBI", ["SBIN", "SBBJ", "SBHY", "SBMY", "SBTR", "SBPA", "SBRT"],
      ["sbi.co.in", "onlinesbi.sbi", "onlinesbi.com", "sbibank.com"],
      [r"state\s*bank\s*of\s*india", r"\bsbi\b(?!\s*card)"])
_bank("axis", "Axis Bank", ["UTIB"], ["axisbank.com", "axisbank.co.in"],
      [r"axis\s*bank"])
_bank("kotak", "Kotak Mahindra Bank", ["KKBK"], ["kotak.com"],
      [r"kotak\s*mahindra", r"kotak\s*bank"])
_bank("bank_of_baroda", "Bank of Baroda", ["BARB", "VIJB", "DENN"],
      ["bankofbaroda.com", "bankofbaroda.co.in", "bankofbaroda.in"],
      [r"bank\s*of\s*baroda", r"baroda\s*bank"])
_bank("canara", "Canara Bank", ["CNRB", "SYNB"],
      ["canarabank.com", "canarabank.in"],
      [r"canara\s*bank"])
_bank("idfc", "IDFC First Bank", ["IDFB"], ["idfcfirstbank.com"],
      [r"idfc\s*first", r"idfc\s*bank"])
_bank("union", "Union Bank of India", ["UBIN", "ANDB", "CORP"],
      ["unionbankofindia.co", "unionbankofindia.co.in", "unionbank.online"],
      [r"union\s*bank\s*of\s*india"])
_bank("karnataka", "Karnataka Bank", ["KARB"],
      ["karnatakabank.com", "karnatakabank.co.in", "ktkbank.com"],
      [r"karnataka\s*bank"])
_bank("paytm", "Paytm Payments Bank", ["PYTM"], ["paytmbank.com", "paytm.com"],
      [r"paytm\s*payments\s*bank"])
_bank("bank_of_india", "Bank of India", ["BKID"],
      ["bankofindia.co.in", "bankofindia.com"],
      [r"(?<!state\s)(?<!state of )bank\s*of\s*india"])
_bank("indian_bank", "Indian Bank", ["IDIB", "ALLA"],
      ["indianbank.in", "indianbank.net.in"],
      [r"indian\s*bank(?!\s*overseas)"])
_bank("indusind", "IndusInd Bank", ["INDB"], ["indusind.com"],
      [r"indusind"])
_bank("yes", "Yes Bank", ["YESB"], ["yesbank.in"],
      [r"yes\s*bank"])
_bank("federal", "Federal Bank", ["FDRL"], ["federalbank.co.in", "federalbank.com"],
      [r"federal\s*bank"])
_bank("pnb", "Punjab National Bank", ["PUNB", "UTBI", "OBC"],
      ["pnbindia.in", "pnb.co.in"],
      [r"punjab\s*national\s*bank", r"united\s*bank\s*of\s*india",
       r"oriental\s*bank\s*of\s*commerce"])
_bank("idbi", "IDBI Bank", ["IBKL"], ["idbibank.in", "idbibank.com"],
      [r"idbi\s*bank"])
_bank("dbs", "DBS Bank", ["DBSS"], ["dbs.com", "dbsbank.com"],
      [r"dbs\s*bank"])
_bank("citi", "Citibank", ["CITI"], ["citibank.com", "citibank.co.in", "citi.com"],
      [r"citibank", r"citi\s*bank"])
_bank("hsbc", "HSBC", ["HSBC"], ["hsbc.co.in", "hsbc.com"],
      [r"\bhsbc\b"])
_bank("bandhan", "Bandhan Bank", ["BDBL"], ["bandhanbank.com"],
      [r"bandhan\s*bank"])
_bank("karur_vysya", "Karur Vysya Bank", ["KVBL"], ["kvb.co.in", "kvbonline.com"],
      [r"karur\s*vysya"])
_bank("iob", "Indian Overseas Bank", ["IOBA"], ["iob.in", "iobnet.co.in"],
      [r"indian\s*overseas\s*bank"])
_bank("equitas", "Equitas Small Finance Bank", ["ESFB"], ["equitasbank.com"],
      [r"equitas"])
_bank("rbl", "RBL Bank", ["RATN"], ["rblbank.com"],
      [r"rbl\s*bank"])
_bank("tmb", "Tamilnad Mercantile Bank", ["TMBL"], ["tmbank.in", "tmb.in"],
      [r"tamilnad\s*mercantile"])
_bank("south_indian", "South Indian Bank", ["SIBL", "PSIB"], ["southindianbank.com"],
      [r"south\s*indian\s*bank"])
_bank("dcb", "DCB Bank", ["DCBL"], ["dcbbank.com"],
      [r"dcb\s*bank"])
_bank("central_bank", "Central Bank of India", ["CBIN"],
      ["centralbankofindia.co.in", "centralbankofindia.com"],
      [r"central\s*bank\s*of\s*india"])
_bank("uco", "UCO Bank", ["UCBA"], ["ucobank.com"],
      [r"uco\s*bank"])
_bank("au", "AU Small Finance Bank", ["AUBL"], ["aubank.in"],
      [r"au\s*small\s*finance"])
_bank("jana", "Jana Small Finance Bank", ["JSFB"], ["janabank.com"],
      [r"jana\s*(small\s*finance|bank)"])
_bank("ujjivan", "Ujjivan Small Finance Bank", ["UJVN", "UJVA"], ["ujjivansfb.in"],
      [r"ujjivan"])
_bank("saraswat", "Saraswat Bank", ["SRCB"], ["saraswatbank.com"],
      [r"saraswat\s*(co-?op|bank)"])
_bank("bom", "Bank of Maharashtra", ["MAHB"],
      ["bankofmaharashtra.in", "bankofmaharashtra.co.in"],
      [r"bank\s*of\s*maharashtra"])
_bank("sbm", "SBM Bank", ["STCB"], ["sbmbank.co.in"],
      [r"sbm\s*bank"])
_bank("fino", "Fino Payments Bank", ["FINO"], ["finopaymentsbank.in"],
      [r"fino\s*payments"])
_bank("airtel", "Airtel Payments Bank", ["AIRP"], [],
      [r"airtel\s*payments"])
_bank("ippb", "India Post Payments Bank", ["IPOS"], ["ippbonline.com"],
      [r"india\s*post\s*payments"])
_bank("deutsche", "Deutsche Bank", ["DEUT"], ["db.com", "deutsche-bank.com"],
      [r"deutsche\s*bank"])
_bank("sc", "Standard Chartered Bank", ["SCBL"], ["sc.com/in"],
      [r"standard\s*chartered"])
_bank("esaf", "ESAF Small Finance Bank", ["ESMF"], ["esafbank.com"],
      [r"esaf"])
_bank("csb", "CSB Bank", ["CSBK"], ["csb.co.in"],
      [r"csb\s*bank"])
_bank("kerala_gramin", "Kerala Gramin Bank", ["KLGB"], ["keralagbank.com"],
      [r"kerala\s*gramin"])
_bank("tjsb", "TJSB Sahakari Bank", ["TJSB"], ["tjsbbank.com"],
      [r"tjsb"])
_bank("nsdl", "NSDL Payments Bank", ["NSPB"], ["nsdlbank.com"],
      [r"nsdl\s*payments"])
_bank("nkgsb", "NKGSB Co-operative Bank", ["NKGS"], ["nkgsb-bank.com"],
      [r"nkgsb"])

IFSC_TO_KEY = {p: k for k, v in BANKS.items() for p in v["ifsc"]}
FOLDER_TO_KEY = {v["folder"]: k for k, v in BANKS.items()}
SPECIAL_FOLDERS = {"Other_Unknown", "Non_Bank_Documents", "Password_Protected"}

# ------------------------------------------------------------------ regex ---

IFSC_RE = re.compile(r"\b([A-Za-z]{4}0[A-Za-z0-9]{6})\b")
IFSC_LABEL_RE = re.compile(r"ifsc[^\n]{0,40}", re.I)

# transaction-table markers — bank statement evidence
STMT_MARKERS = [
    r"statement\s+of\s+(account|transactions)", r"account\s+statement",
    r"transaction\s+(history|details|summary)", r"opening\s+balance",
    r"closing\s+balance", r"withdrawal", r"\bdeposit\b", r"\bbalance\b",
    r"\bdebit\b", r"\bcredit\b", r"ifsc\s*code", r"branch\s*code",
    r"account\s*(number|no)\b", r"a/?c\s*no",
]
# non-bank-document markers — payslip / tax / HR docs
NONBANK_MARKERS = [
    r"\bpay\s*slip\b", r"\bpayslip\b", r"wage\s*slip", r"salary\s*slip",
    r"income\s*tax\s*computation", r"\bform\s*16\b", r"it\s*declaration",
    r"investment\s*declaration", r"declaration\s*of\s*income",
    r"earning\s*statement", r"gross\s*pay", r"net\s*pay.*deductions",
    r"loan\s*(agreement|sanction|schedule)", r"sanction\s*letter",
    r"provident\s*fund", r"epf\s*statement", r"passbook\s+copy",
]
STMT_RE = re.compile("|".join(STMT_MARKERS), re.I)
NONBANK_RE = re.compile("|".join(NONBANK_MARKERS), re.I)

# transaction rows almost always open with a date at line start
_TXN_LINE = re.compile(r"(?m)^\s*\d{1,2}[-/ .]\d{1,2}[-/ .]\d{2,4}\b")
_TXN_LINE_MON = re.compile(
    r"(?m)^\s*\d{1,2}[-/ ](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-/ ]\d{2,4}\b",
    re.I)


def _header_region(text: str, max_chars: int = 1500) -> str:
    """Top of page-1: up to the first transaction-table row."""
    stops = [m.start() for m in _TXN_LINE.finditer(text)]
    stops += [m.start() for m in _TXN_LINE_MON.finditer(text)]
    cut = min(stops) if stops else len(text)
    return text[: min(cut, max_chars)]


def _name_hit(pat, region: str):
    """First name match not inside a narration line (UPI/IMPS/... slashes)."""
    best = None
    for m in pat.finditer(region):
        line_start = region.rfind("\n", 0, m.start()) + 1
        seg = region[line_start:m.start()]
        if "/" in seg or "|" in seg:
            continue                      # narration-style token
        if best is None or m.start() < best.start():
            best = m
    return best


# --------------------------------------------------------------- workers ----

_EASYOCR = None


def _ocr_init():
    global _EASYOCR
    import torch
    torch.set_num_threads(3)
    import easyocr
    _EASYOCR = easyocr.Reader(["en"], gpu=False, verbose=False)


def _ocr_page(doc, page_no: int, dpi: int = 150) -> str:
    """Render page and OCR via the process-global reader."""
    global _EASYOCR
    if _EASYOCR is None:
        _ocr_init()
    pix = doc[page_no].get_pixmap(dpi=dpi)
    import numpy as np
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n)
    return "\n".join(t for _, t, _ in _EASYOCR.readtext(img, detail=0))


def _open_text(path: str, password: str | None) -> tuple[str, str]:
    """Returns (text, open_status). open_status: open|password_protected|corrupt."""
    try:
        import fitz
        doc = fitz.open(path)
    except Exception:
        return "", "corrupt"
    try:
        if doc.needs_pass:
            ok = doc.authenticate("")
            if not ok and password:
                ok = doc.authenticate(password)
            if not ok:
                return "", "password_protected"
        parts = [doc[i].get_text() for i in range(min(3, len(doc)))]
        return "\n".join(parts), "open"
    except Exception:
        return "", "corrupt"
    finally:
        doc.close()


def analyze_file(arg: tuple) -> dict:
    """Extract text evidence from one PDF. arg=(path, manifest_password)."""
    path_str, password = arg
    p = Path(path_str)
    res = {
        "path": str(p), "filename": p.name, "folder": p.parent.name,
        "pages": 0, "open": "open", "text": "", "ocr_used": False,
    }
    text, status = _open_text(str(p), password)
    res["open"] = status
    if status == "open":
        try:
            import fitz
            with fitz.open(str(p)) as d:
                if d.needs_pass:
                    d.authenticate("") or (password and d.authenticate(password))
                res["pages"] = len(d)
        except Exception:
            pass
    res["text"] = text[:100_000]
    return res


def detect_bank(ev: dict, manifest_key: str | None) -> dict:
    """Score evidence -> detected bank + confidence + reason strings."""
    text = ev["text"]
    lower = unicodedata.normalize("NFKD", text).lower()
    header = _header_region(text)

    ifsc_labeled, ifsc_header, ifsc_body = [], [], []
    ifsc_token = ""
    for m in IFSC_RE.finditer(text):
        token = m.group(1).upper()
        pref = token[:4]
        if pref not in IFSC_TO_KEY:
            continue
        start = m.start()
        # NPCI UPI handles like "10411140006209@HDFC0001041.ifsc.npci" are
        # counterparty references, never the account's own IFSC
        if text[start - 1:start] == "@" or \
           text[m.end():m.end() + 5].lower() == ".ifsc":
            continue
        near_label = bool(
            # "IFSC Code : XXXX" / "IFS Code: XXXX" — label directly precedes
            re.search(r"(?:ifsc|ifs)(?:\s*code|\s*cd)?\s*[:\-–.]?\s*$",
                      text[max(0, start - 40):start], re.I)
            # "(IFSC)" style suffix directly after
            or re.match(r"[\s:.\-–]*\(?\s*(?:ifsc|ifs)\b",
                        text[m.end():], re.I))
        if near_label:
            ifsc_labeled.append(pref)
        elif start < 2000:
            ifsc_header.append(pref)
        else:
            ifsc_body.append(pref)
    ifsc_bank = None
    ifsc_strong = False
    ifsc_count = 0
    # strict tier priority: a labeled "IFSC: XXXX0..." beats position-based
    # hits, which beat bare narration tokens (NEFT*UTIB0001920* refs etc.)
    for tier, strong in ((ifsc_labeled, True), (ifsc_header, True),
                         (ifsc_body, False)):
        if tier:
            top_pref, ifsc_count = Counter(tier).most_common(1)[0]
            ifsc_bank = IFSC_TO_KEY[top_pref]
            ifsc_token = top_pref + "0xxxxx" + ("" if strong else "(body)")
            ifsc_strong = strong
            break

    # header name: earliest narration-free occurrence wins
    best_pos, name_bank = None, None
    for k, v in BANKS.items():
        for pat in v["names"]:
            m = _name_hit(pat, header)
            if m and (best_pos is None or m.start() < best_pos):
                best_pos, name_bank = m.start(), k

    domain_bank, dom_str = None, ""
    for k, v in BANKS.items():
        for pat in v["domains"]:
            m = pat.search(lower)
            if m:
                domain_bank, dom_str = k, m.group(0)
                break
        if domain_bank:
            break

    has_stmt = bool(STMT_RE.search(lower))
    has_nonbank = bool(NONBANK_RE.search(lower[:3000]))

    # ---- non-bank document gate ----
    if has_nonbank and not ifsc_bank and not has_stmt:
        conf = "MEDIUM" if name_bank else "HIGH"
        return _dec(ev, "NON_BANK", None, conf,
                    "non_bank_markers", "", None, ifsc_token)

    # ---- combine signals ----------------------------------------------------
    # IFSC is near-authoritative (issued by the bank itself). A header-name
    # hit alone cannot outvote it: customer addresses/narrations routinely
    # contain other banks' names. Only name+domain agreeing AGAINST the IFSC
    # is treated as a real conflict.
    votes = Counter()
    if ifsc_bank:
        votes[ifsc_bank] += 60 + 5 * min(ifsc_count, 4)
    if name_bank:
        votes[name_bank] += 50
    if domain_bank:
        votes[domain_bank] += 30
    if manifest_key:
        votes[manifest_key] += 10
    detected = votes.most_common(1)[0][0] if votes else None

    sig = [n for n, b in (("ifsc", ifsc_bank), ("name", name_bank),
                          ("domain", domain_bank)) if b]
    if manifest_key:
        sig.append("manifest")
    method = "+".join(sig)

    name_domain_oppose = (name_bank and domain_bank and
                          name_bank == domain_bank and
                          ifsc_bank and name_bank != ifsc_bank)
    conflict_key = None
    if ifsc_bank and ifsc_strong:
        detected = ifsc_bank                     # IFSC always wins
        if name_domain_oppose:
            conf = "MEDIUM"; conflict_key = name_bank
        elif domain_bank and domain_bank != ifsc_bank:
            conf = "MEDIUM"; conflict_key = domain_bank   # domain contradicts IFSC
        elif name_bank == ifsc_bank:
            conf = "VERY_HIGH"
        else:
            conf = "HIGH"   # IFSC + agreeing/absent domain; stray name = noise
    elif ifsc_bank:                              # body-tier IFSC only
        detected = ifsc_bank
        if name_bank == ifsc_bank or domain_bank == ifsc_bank:
            conf = "HIGH"
        elif name_domain_oppose:
            conf = "MEDIUM"; conflict_key = name_bank
        else:
            conf = "MEDIUM"
    elif name_bank and domain_bank == name_bank:
        detected = name_bank
        conf = "VERY_HIGH"
    elif name_bank:
        detected = name_bank
        conf = "MEDIUM" if domain_bank else "HIGH"
    elif domain_bank:
        detected = domain_bank
        conf = "MEDIUM"
    elif manifest_key:
        detected = manifest_key
        conf = "LOW"
    else:
        detected = None
        conf = "UNKNOWN"
        method = "no_evidence"

    return _dec(ev, detected, conflict_key, conf, method, dom_str,
                name_bank, ifsc_token)


def _dec(ev, detected, conflict_key, conf, method, dom, name_bank, ifsc_token):
    evidence = []
    if ifsc_token:
        evidence.append(f"IFSC:{ifsc_token}")
    if name_bank:
        evidence.append(f"NAME:{BANKS[name_bank]['folder']}")
    if dom:
        evidence.append(f"DOM:{dom}")
    if conflict_key:
        evidence.append(f"CONFLICT:{BANKS[conflict_key]['folder']}")
    if detected == "NON_BANK":
        folder = "Non_Bank_Documents"
    elif detected:
        folder = BANKS[detected]["folder"]
    else:
        folder = ""
    return {
        **{k: v for k, v in ev.items() if k != "text"},
        "detected": detected,
        "detected_folder": folder,
        "confidence": conf,
        "method": method,
        "evidence": "; ".join(evidence),
        "ifsc": ifsc_token or "",
        "domain": dom,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--sample", type=int, default=0,
                    help="limit to N files per folder (testing)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--ocr-workers", type=int, default=3)
    args = ap.parse_args()

    if not (args.apply or args.validate):
        args.dry_run = True

    t0 = time.time()

    # ---------- manifest maps: exported filename -> (bank_key, password) -----
    manifest_by_file: dict[str, tuple[str, str | None]] = {}
    if MANIFEST.exists():
        conn = sqlite3.connect(str(MANIFEST))
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            "SELECT user_id, bank_name, password, original_filename, filename, local_path"
            " FROM statements WHERE local_path IS NOT NULL"
        ):
            stem = row["original_filename"] or row["filename"] or Path(row["local_path"]).stem
            stem = re.sub(r'[\\/:*?"<>|]+', "_", Path(stem).stem).strip(" ._") or "statement"
            export_name = f"{row['user_id']}_{stem}.pdf"
            bname = re.sub(r"[^A-Z0-9]", "", str(row["bank_name"] or "").upper())
            manifest_by_file[export_name] = (ALIAS.get(bname), row["password"])
        conn.close()

    def _mani_lookup(name: str):
        m = manifest_by_file.get(name)
        if m is None:  # collision-suffixed exports: strip trailing _N
            base = re.sub(r"_\d+\.pdf$", ".pdf", name, flags=re.I)
            m = manifest_by_file.get(base, (None, None))
        return m

    # ---------- collect files ------------------------------------------------
    files = []
    for folder in sorted(BASE.iterdir()):
        if not folder.is_dir():
            continue
        pdfs = [f for f in folder.iterdir() if f.suffix.lower() == ".pdf"]
        if args.sample:
            pdfs = pdfs[: args.sample]
        files.extend(pdfs)
    # loose PDFs at root (from previous exports)
    loose = [f for f in BASE.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]
    files.extend(loose[: args.sample] if args.sample else loose)
    print(f"files to validate: {len(files)}", flush=True)

    # ---------- cache --------------------------------------------------------
    cache: dict[str, dict] = {}
    if CACHE_FILE.exists():
        for line in CACHE_FILE.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                cache[d["sha256"]] = d
            except Exception:
                pass
    print(f"cached detections: {len(cache)}", flush=True)

    # ---------- phase 1: hash -> cache hits ----------------------------------
    work = [(str(p), *_mani_lookup(p.name)) for p in files]  # (path, bkey, pw)
    with Pool(args.workers) as pool:
        shas = pool.map(_sha_for, [str(p) for p in files], chunksize=50)

    cached_rows, redetect, todo = [], [], []
    for (path, mkey, pw), sha in zip(work, shas):
        c = cache.get(sha)
        if c is not None and (c.get("v") == RULE_VERSION
                              or c.get("open") != "open"
                              or not c.get("text_z")):
            d = dict(c)
            d.update(path=path, folder=Path(path).parent.name,
                     filename=Path(path).name, manifest_key=mkey,
                     _cached=True)
            cached_rows.append(d)
        elif c is not None and c.get("text_z"):  # stale rules: re-detect on cached text
            d = {k: c.get(k) for k in ("open", "pages", "ocr_used")}
            d.update(path=path, folder=Path(path).parent.name,
                     filename=Path(path).name, manifest_key=mkey, sha256=sha,
                     text=zlib.decompress(base64.b64decode(c["text_z"])).decode(
                         "utf-8", "replace"))
            redetect.append(d)
        else:
            todo.append((path, mkey, pw, sha))
    print(f"cache hits: {len(cached_rows)} | re-detect: {len(redetect)}"
          f" | need analysis: {len(todo)}", flush=True)

    # ---------- phase 2: text extraction of uncached -------------------------
    fresh: dict[str, dict] = {}
    if todo:
        with Pool(args.workers) as pool:
            for d in pool.imap_unordered(_analyze_pool,
                                         [(p, pw) for p, _, pw, _ in todo],
                                         chunksize=10):
                fresh[d["path"]] = d
        for p, mkey, pw, sha in todo:
            fresh[p]["sha256"] = sha
            fresh[p]["manifest_key"] = mkey

    # ---------- detection helper ----------------------------------------------
    cache_fh = CACHE_FILE.open("a", encoding="utf-8")

    def _detect_row(d: dict) -> dict:
        mkey = d.get("manifest_key")
        if d.get("_cached"):
            r = dict(d)
        elif d["open"] != "open":
            r = {k: v for k, v in d.items() if k != "text"}
            r.update(detected=None, detected_folder="", confidence="UNKNOWN",
                     method=d["open"], evidence="", ifsc="", domain="")
        else:
            r = detect_bank(d, mkey)
        if d["open"] == "password_protected":
            r["status"] = "PASSWORD_PROTECTED"
        elif d["open"] == "corrupt":
            r["status"] = "REVIEW_REQUIRED"
        else:
            r["status"] = _status(r)
        r["original_folder"] = r["folder"]
        r["original_path"] = r["path"]
        return r

    def _persist(r: dict, src: dict | None = None):
        text = (src or {}).get("text", "") or ""
        tz = (base64.b64encode(zlib.compress(text.encode("utf-8", "replace"), 6))
              .decode() if text else "")
        cache_fh.write(json.dumps({
            "v": RULE_VERSION,
            **{k: r.get(k) for k in (
                "sha256", "detected", "detected_folder", "confidence",
                "method", "evidence", "ifsc", "domain", "open", "pages",
                "ocr_used", "filename")},
            "text_z": tz}) + "\n")
        cache_fh.flush()

    # ---------- phase 3: OCR for no-text files -------------------------------
    need_ocr = {d["path"] for d in fresh.values()
                if d["open"] == "open" and len(d["text"].strip()) < 120}
    print(f"files needing OCR: {len(need_ocr)}", flush=True)

    results = []

    # stale-rule cache hits: re-detect from cached text, persist updated verdict
    for d in redetect:
        r = _detect_row(d)
        _persist(r, d)
        results.append(r)

    # non-OCR fresh rows: detect + persist immediately
    for path, d in fresh.items():
        if path in need_ocr:
            continue
        r = _detect_row(d)
        _persist(r, d)
        results.append(r)

    # OCR rows: as each result arrives -> attach, detect, persist
    if need_ocr:
        pw_of = {p: pw for p, _, pw, _ in todo}
        done = 0
        with Pool(args.ocr_workers, initializer=_ocr_init) as pool:
            for res in pool.imap_unordered(
                    _ocr_file,
                    [(p, pw_of.get(p)) for p in need_ocr], chunksize=1):
                d = fresh[res["path"]]
                d["text"] = res["text"][:100_000]
                d["ocr_used"] = True
                r = _detect_row(d)
                _persist(r, d)
                results.append(r)
                done += 1
                if done % 25 == 0:
                    print(f"  ocr {done}/{len(need_ocr)}", flush=True)

    for d in cached_rows:
        results.append(_detect_row(d))
    cache_fh.close()

    _write_reports(results)

    # ---------- apply moves ----------------------------------------------------
    if args.apply:
        _apply_moves(results)
    elif args.dry_run or args.validate:
        print("\n(dry-run: no files moved)")

    print(f"\nelapsed {time.time() - t0:.0f}s")
    return 0


def _sha_for(path_str: str) -> str:
    h = hashlib.sha256()
    with open(path_str, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _analyze_pool(arg):
    return analyze_file(arg)  # (path, manifest_password)


def _ocr_file(arg):
    path, pw = arg
    text, status = _open_text(path, pw)
    if status != "open":
        return {"path": path, "text": ""}
    try:
        import fitz
        with fitz.open(path) as d:
            if d.needs_pass:
                d.authenticate("") or (pw and d.authenticate(pw))
            parts = []
            for pg in range(min(2, len(d))):
                try:
                    parts.append(_ocr_page(d, pg))
                except Exception:
                    pass
                if len("".join(parts).strip()) > 300:
                    break          # page 1 evidence sufficient — skip page 2
            text = "\n".join(parts)
    except Exception:
        text = ""
    return {"path": path, "text": text}


def _status(r: dict) -> str:
    if r.get("method") == "non_bank_markers":
        return "NON_BANK_DOCUMENT"
    conf = r["confidence"]
    detected = r["detected"]
    claimed = FOLDER_TO_KEY.get(r["folder"], r["folder"])
    if detected is None:
        return "UNKNOWN"
    if conf in ("VERY_HIGH", "HIGH"):
        return "VERIFIED" if detected == claimed else "MISCLASSIFIED"
    return "REVIEW_REQUIRED"


def _write_reports(results):
    # main report
    with REPORT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["filename", "current_folder", "detected_bank", "confidence",
                    "status", "detection_method", "evidence", "ifsc",
                    "bank_domain", "page_count", "password_status", "sha256",
                    "recommended_action"])
        for r in sorted(results,
                        key=lambda r: (r["original_folder"], r["filename"])):
            w.writerow([
                r["filename"], r["original_folder"], r["detected_folder"] or "-",
                r["confidence"], r["status"], r["method"], r["evidence"],
                r["ifsc"], r["domain"], r.get("pages", 0), r["open"],
                r["sha256"], _action(r)])

    # summary per current folder
    per = {}
    for r in results:
        s = per.setdefault(r["original_folder"], Counter())
        s[r["status"]] += 1
        s["total"] += 1
    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["folder", "total", "verified", "misclassified", "corrected",
                    "review_required", "password_protected",
                    "non_bank", "unknown"])
        for f, s in sorted(per.items()):
            w.writerow([f, s["total"], s["VERIFIED"], s["MISCLASSIFIED"],
                        s["CORRECTED"], s["REVIEW_REQUIRED"],
                        s["PASSWORD_PROTECTED"], s["NON_BANK_DOCUMENT"],
                        s["UNKNOWN"]])

    # misclassified detail (incl. files already corrected by --apply)
    with MISCSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["filename", "current_bank", "correct_bank", "confidence",
                    "reason", "evidence", "source_path", "destination_path",
                    "moved"])
        for r in results:
            if r["status"] == "MISCLASSIFIED" or r["status"].startswith("MOVE_FAILED") or \
               (r.get("moved") and r["status"] in
                ("NON_BANK_DOCUMENT", "PASSWORD_PROTECTED")):
                w.writerow([r["filename"], r["original_folder"], r["detected_folder"],
                            r["confidence"], r["method"], r["evidence"],
                            r.get("original_path", r["path"]),
                            str(BASE / r["detected_folder"] / r["filename"]),
                            r.get("moved", "no")])

    # review queue
    with REVIEWCSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["filename", "current_folder", "detected_bank", "confidence",
                    "evidence", "reason"])
        for r in results:
            if r["status"] == "REVIEW_REQUIRED":
                w.writerow([r["filename"], r["folder"],
                            r["detected_folder"] or "-", r["confidence"],
                            r["evidence"], r["method"]])

    counts = Counter(r["status"] for r in results)
    print("\n================ VALIDATION SUMMARY ================")
    print(f"TOTAL PDFs scanned : {len(results)}")
    for s in ("VERIFIED", "MISCLASSIFIED", "REVIEW_REQUIRED",
              "PASSWORD_PROTECTED", "NON_BANK_DOCUMENT", "UNKNOWN"):
        print(f"{s:20s}: {counts.get(s, 0)}")
    print("====================================================")
    print(f"report: {REPORT_CSV}")
    print(f"summary: {SUMMARY_CSV}")
    print(f"misclassified: {MISCSV}")
    print(f"review: {REVIEWCSV}")


def _action(r: dict) -> str:
    st = r["status"]
    if st == "MISCLASSIFIED" and r["confidence"] in ("VERY_HIGH", "HIGH"):
        return f"MOVE_TO:{r['detected_folder']}"
    if st == "NON_BANK_DOCUMENT":
        return "MOVE_TO:Non_Bank_Documents"
    if st == "PASSWORD_PROTECTED":
        return "MOVE_TO:Password_Protected"
    if st == "REVIEW_REQUIRED":
        return "MANUAL_REVIEW"
    return "KEEP"


def _apply_moves(results):
    moved = dup = kept = 0
    for r in results:
        act = _action(r)
        if not act.startswith("MOVE_TO:"):
            kept += 1
            continue
        dest_dir = BASE / act.split(":", 1)[1]
        dest_dir.mkdir(exist_ok=True)
        src = Path(r["path"])
        if not src.exists():
            kept += 1
            continue
        dest = dest_dir / r["filename"]
        if dest.exists():
            existing_sha = _sha_for(str(dest))
            if existing_sha == r["sha256"]:
                dup += 1
                r["status"] = "DUPLICATE_ALREADY_EXISTS"
                continue
            stem, suf = dest.stem, dest.suffix
            i = 2
            while (dest_dir / f"{stem}_{i}{suf}").exists():
                i += 1
            dest = dest_dir / f"{stem}_{i}{suf}"
        try:
            src.rename(dest)
            moved += 1
            r["moved"] = dest_dir.name
            r["path"] = str(dest)
            r["folder"] = dest_dir.name
        except OSError as e:
            r["status"] = f"MOVE_FAILED:{e}"
            kept += 1
    print(f"\nmoved={moved} duplicates_skipped={dup} kept={kept}")
    _write_reports(results)


# manifest bank_name normalisation (alias -> canonical key)
ALIAS = {}
for _k, _v in BANKS.items():
    for _tok in _v["names"]:
        pass
    ALIAS[re.sub(r"[^A-Z0-9]", "", _v["folder"].upper())] = _k
# extra aliases
ALIAS.update({
    "STATEBANKOFINDIA": "sbi", "STATEBANK": "sbi", "SBIBANK": "sbi",
    "HDFCBANK": "hdfc", "ICICIBANK": "icici", "AXISBANK": "axis",
    "KOTAKBANK": "kotak", "KOTAKMAHINDRABANK": "kotak", "KOTAKMAHINDRA": "kotak",
    "BOB": "bank_of_baroda", "BARODA": "bank_of_baroda",
    "CANARABANK": "canara", "SYNDICATE": "canara", "SYNDICATEBANK": "canara",
    "IDFCBANK": "idfc", "IDFCFIRST": "idfc", "IDFCFIRSTBANK": "idfc",
    "UNIONBANK": "union", "UNIONBANKOFINDIA": "union", "UBI": "union",
    "ANDHRA": "union", "ANDHRABANK": "union", "CORPORATION": "union",
    "CORPORATIONBANK": "union",
    "KARNATAKABANK": "karnataka",
    "PAYTMBANK": "paytm", "PAYTMPAYMENTSBANK": "paytm",
    "BOI": "bank_of_india",
    "INDIANBANK": "indian_bank", "ALLAHABAD": "indian_bank", "ALLAHABADBANK": "indian_bank",
    "INDUSINDBANK": "indusind",
    "YESBANK": "yes",
    "FEDERALBANK": "federal",
    "PUNJABNATIONALBANK": "pnb", "UNITEDBANK": "pnb", "UNITEDBANKOFINDIA": "pnb",
    "OBC": "pnb", "ORIENTALBANK": "pnb", "ORIENTALBANKOFCOMMERCE": "pnb",
    "IDBIBANK": "idbi",
    "DBSBANK": "dbs",
    "CITIBANK": "citi", "CITIBANKNA": "citi",
    "HSBCBANK": "hsbc",
    "BANDHANBANK": "bandhan",
    "KARURVYSYABANK": "karur_vysya", "KARURVYASA": "karur_vysya",
    "KARURVYSYA": "karur_vysya", "KVB": "karur_vysya",
    "INDIANOVERSEAS": "iob", "INDIANOVERSEASBANK": "iob",
    "EQUITASSMALLFINANCEBANK": "equitas", "EQUITAS": "equitas",
    "RBLBANK": "rbl", "RATNAKARBANK": "rbl",
    "TAMILNADMERCANTILE": "tmb", "TAMILNADMERCANTILEBANK": "tmb",
    "SOUTHINDIANBANK": "south_indian", "SIB": "south_indian",
    "DCBBANK": "dcb",
    "CENTRALBANK": "central_bank", "CENTRALBANKOFINDIA": "central_bank",
    "UCOBANK": "uco",
    "AUSMALLFINANCEBANK": "au", "AUBANK": "au",
    "JANASMALLFINANCEBANK": "jana", "JANABANK": "jana",
    "UJJIVANSMALLFINANCEBANK": "ujjivan",
    "SARASWATBANK": "saraswat", "SARASWATCOOPBANK": "saraswat",
    "BANKOFMAHARASHTRA": "bom", "MAHB": "bom",
    "SBMBANK": "sbm", "SBMBANKINDIA": "sbm", "SBM": "sbm",
    "FINOPAYMENTSBANK": "fino", "FINO": "fino",
    "AIRTELPAYMENTSBANK": "airtel", "AIRTEL": "airtel",
    "INDIAPOSTPAYMENTSBANK": "ippb", "IPPB": "ippb",
    "DEUTSCHEBANK": "deutsche",
    "STANDARDCHARTERED": "sc", "STANDARDCHARTEREDBANK": "sc",
    "ESAFSMALLFINANCEBANK": "esaf",
    "CSBBANK": "csb",
    "KERALAGRAMINBANK": "kerala_gramin",
    "TJSBBANK": "tjsb",
    "NSDLPAYMENTSBANK": "nsdl",
    "NKGSB": "nkgsb", "NKGSBCOOPBANK": "nkgsb",
})


if __name__ == "__main__":
    sys.exit(main())
