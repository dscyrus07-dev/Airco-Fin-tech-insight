# bank_doc.py — emit docs/onboarding/banks/<id>.md from eval + audit artifacts.
# usage: python bank_doc.py <bank_id> <STATUS> [reason]
import os, sys, json, glob, subprocess

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")
DOCS = os.path.abspath(os.path.join(HERE, "..", "..", "docs", "onboarding", "banks"))

bid, status = sys.argv[1], sys.argv[2]
reason = " ".join(sys.argv[3:])

ev = json.load(open(os.path.join(LOCAL, "eval", f"{bid}.json")))
aud_p = os.path.join(LOCAL, "eval", f"{bid}.audit.json")
aud = json.load(open(aud_p)) if os.path.exists(aud_p) else None
stats = {r["bank_id"]: r for r in json.load(open(os.path.join(LOCAL, "bank_stats.json")))}
st = stats.get(bid, {})
folders = json.load(open(os.path.join(LOCAL, "folders.json")))
aliases = [k for k, v in folders.items() if v["bank_id"] == bid]

vm = ev["verdicts"]
L = []
A = L.append
A(f"# {bid} — onboarding notes")
A("")
A(f"Status: **{status}**" + (f" — {reason}" if reason else ""))
A("")
A(f"Folders: {', '.join(aliases)}")
A(f"Files: {ev['total']} pdf | {ev['text_n']} text | {ev['scanned_n']} scanned | {ev['locked_n']} locked")
A("")
A("## Fingerprints")
A("")
fps = st.get("_fps", {})
A(f"distinct fingerprints: {st.get('fingerprints_n', '?')} | top share: {st.get('top_fingerprint_share', '?')}%")
for sig, n in list(fps.items())[:12]:
    A(f"- `{sig}` x{n}")
if len(fps) > 12: A(f"- ... +{len(fps)-12} more")
A("")
A("## Current behaviour (V2_MODE=shadow)")
A("")
A(f"- probed: {ev['probed_n']} | detected-correct: {ev['det_ok_pct']}% "
  f"(wrong: {ev['det_wrong']}, none: {ev['det_none']})")
A(f"- tier: {ev['tier']} | rows read: {ev['rows_total']}")
A(f"- verdicts: {vm or '{}'}")
A(f"- fallback reasons: {ev['fb'] or '{}'}")
A(f"- cross-bank false accepts on pooled other-bank files: {ev['xcheck_false_accept_n']}")
if ev["xcheck_false_accepts"]:
    for x in ev["xcheck_false_accepts"][:10]:
        A(f"  - {x['sha8']} from {x['folder']} via {x['via']}")
A("")
if aud:
    A("## Independent audit (hold-out VERIFIED sample)")
    A("")
    A(f"- sampled: {aud['sampled']} of {aud['verified_pool']} VERIFIED | ok: {aud['ok']} | disagreements: {aud['bad']}")
    for b in aud.get("bad_detail", []):
        A(f"  - {json.dumps({k: v for k, v in b.items() if k != 'sha8'})}")
    A("")
os.makedirs(DOCS, exist_ok=True)
open(os.path.join(DOCS, f"{bid}.md"), "w", encoding="utf-8").write("\n".join(L))
print("wrote", f"docs/onboarding/banks/{bid}.md")
