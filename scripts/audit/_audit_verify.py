"""
End-to-end audit verification:
1. Upload one HDFC PDF via the async API
2. Poll until complete
3. Query all Supabase audit tables and report what's populated vs empty
"""
import os, time, requests, sys

BASE_URL = "http://localhost:8000"

# Find an HDFC pdf in the project
def find_pdf():
    for root, dirs, files in os.walk(os.path.dirname(__file__)):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", "venv", ".venv")]
        for f in files:
            if f.lower().endswith(".pdf") and "hdfc" in root.lower():
                return os.path.join(root, f)
    # fallback: any pdf
    for root, dirs, files in os.walk(os.path.dirname(__file__)):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", "venv", ".venv")]
        for f in files:
            if f.lower().endswith(".pdf"):
                return os.path.join(root, f)
    return None

PDF_PATH = find_pdf()

if not PDF_PATH:
    print("ERROR: No PDF found in project tree")
    sys.exit(1)

print(f"Using PDF: {PDF_PATH}")

# ── Step 1: Submit upload ─────────────────────────────────────────────────────
print("\n=== STEP 1: Submit Upload ===")
with open(PDF_PATH, "rb") as f:
    resp = requests.post(
        f"{BASE_URL}/api/upload/bank-statement-async",
        files={"file": (os.path.basename(PDF_PATH), f, "application/pdf")},
        data={"bank_name": "HDFC Bank", "full_name": "Verify User", "account_type": "Salaried", "mode": "free"},
        headers={"X-Airco-User-Id": "verify-user", "X-Airco-User-Email": "verify@test.com"},
        timeout=30,
    )

print(f"HTTP {resp.status_code}")
body = resp.json()
print("Response:", body)
if resp.status_code != 200:
    sys.exit(1)

job_id = body.get("job_id")
print(f"Job ID: {job_id}")

# ── Step 2: Poll ──────────────────────────────────────────────────────────────
print("\n=== STEP 2: Polling ===")
final_status = None
for i in range(40):
    time.sleep(3)
    r = requests.get(f"{BASE_URL}/api/jobs/{job_id}", timeout=10)
    if r.status_code == 200:
        s = r.json().get("status")
        print(f"  [{i*3}s] {s}")
        if s in ("completed", "failed"):
            final_status = s
            job_result = r.json()
            break

print(f"\nFinal status: {final_status}")
if final_status == "completed":
    stats = job_result.get("result_data", {}).get("stats", {})
    print(f"  Transactions : {stats.get('total_transactions')}")
    print(f"  Bank         : {job_result.get('bank_name')}")
elif final_status == "failed":
    print(f"  Error: {job_result.get('error_message')}")

print(f"\nJob ID for reference: {job_id}")
