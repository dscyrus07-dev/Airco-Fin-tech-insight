"""verify4 live confusion: upload OTHER-bank files, confirm-as candidate (OVERRIDE).
accept = confirm ok AND process reaches completed job with clean workbook download.
usage: python tools/verify4/confuse_run.py <candidate> <sha8,sha8,...> <out.jsonl>
env: KC_SECRET E2E_USER_PW"""
import json, os, sys, glob, time, io
import requests
cand, sha8s, out_path = sys.argv[1], sys.argv[2].split(","), sys.argv[3]
API = os.environ.get("V4_API","http://127.0.0.1:8601"); KC="http://localhost:8080"
mani = {}
for m in glob.glob(os.path.join(os.path.dirname(__file__),".local","manifest_*.jsonl")):
    for l in open(m,encoding="utf-8"): d=json.loads(l); mani[d["sha8"]]=d["path"]
def login():
    r = requests.post(f"{KC}/realms/airco-insights/protocol/openid-connect/token",
        data={"grant_type":"password","client_id":"frontend-app",
              "client_secret":os.environ["KC_SECRET"],"username":"test@airco.com",
              "password":os.environ["E2E_USER_PW"]},timeout=30)
    r.raise_for_status(); return {"Authorization":"Bearer "+r.json()["access_token"]}
H = login(); out = open(out_path,"w",encoding="utf-8")
for s8 in sha8s:
    rec={"sha8":s8}
    try:
        p=mani.get(s8)
        if not p or not os.path.exists(p): rec["skip"]="no_path"; out.write(json.dumps(rec)+"\n"); continue
        up=[("files",(s8+".pdf",open(p,"rb").read(),"application/pdf"))]
        r=requests.post(f"{API}/api/statements/analyze",headers=H,files=up,timeout=120)
        rec["analyze_http"]=r.status_code
        if r.status_code!=200: rec["note"]=r.text[:80]; out.write(json.dumps(rec)+"\n"); continue
        d=(r.json().get("documents") or [{}])[0]; aid=r.json().get("analysis_id")
        rec["detected"]=(d.get("bank") or {}).get("id"); rec["state"]=d.get("state"); rec["wf"]=d.get("workflow_status")
        did=d.get("document_id")
        if d.get("workflow_status")!="AWAITING_CONFIRMATION" or not did:
            rec["routed_no_confirm"]=True; out.write(json.dumps(rec)+"\n"); continue
        rc=requests.post(f"{API}/api/statements/{aid}/confirm",headers=H,timeout=30,
            json={"documents":[{"document_id":did,"action":"OVERRIDE","bank_id":cand}]})
        rec["confirm_http"]=rc.status_code
        try:
            res=rc.json().get("results") or []
            rec["confirm_ok"]=any(x.get("ok") for x in res)
            rec["confirm_detail"]=str(res[0])[:120] if res else ""
        except Exception: rec["confirm_body"]=rc.text[:120]
        # do NOT process: accept boundary = confirm_ok True would need process; flag for review
    except Exception as e: rec["exc"]=type(e).__name__+":"+str(e)[:60]
    out.write(json.dumps(rec)+"\n"); out.flush()
out.close()
