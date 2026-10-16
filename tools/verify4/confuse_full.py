"""verify4 live confusion, full path: analyze -> OVERRIDE-as-candidate -> process -> poll.
accept = job completed AND workbook downloaded (presented-as-clean) OR engine_meta
verdict VERIFIED on routed spec != candidate. WRONG_ACCEPT flag printed at end.
usage: python tools/verify4/confuse_full.py <candidate> <sha8,sha8,...> <out.jsonl>"""
import json, os, sys, glob, time
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
H = login(); out = open(out_path,"w",encoding="utf-8"); wrong=[]
for s8 in sha8s:
    rec={"sha8":s8}
    try:
        p=mani.get(s8)
        if not p or not os.path.exists(p): rec["skip"]="no_path"; out.write(json.dumps(rec)+"\n"); out.flush(); continue
        up=[("files",(s8+".pdf",open(p,"rb").read(),"application/pdf"))]
        r=requests.post(f"{API}/api/statements/analyze",headers=H,files=up,timeout=120)
        rec["analyze_http"]=r.status_code
        if r.status_code!=200: rec["note"]=r.text[:80]; out.write(json.dumps(rec)+"\n"); out.flush(); continue
        aj=r.json(); d=(aj.get("documents") or [{}])[0]; aid=aj.get("analysis_id")
        rec["detected"]=(d.get("bank") or {}).get("id"); rec["state"]=d.get("state")
        did=d.get("document_id")
        if d.get("workflow_status")!="AWAITING_CONFIRMATION" or not did:
            rec["no_confirm_needed"]=d.get("workflow_status"); out.write(json.dumps(rec)+"\n"); out.flush(); continue
        rc=requests.post(f"{API}/api/statements/{aid}/confirm",headers=H,timeout=30,
            json={"documents":[{"document_id":did,"action":"OVERRIDE","bank_id":cand}]})
        rec["confirm_http"]=rc.status_code
        res=(rc.json() if rc.headers.get("content-type","").startswith("application/json") else {})
        rr=res.get("results") or []
        if not any(x.get("ok") for x in rr):
            rec["confirm_rejected"]=str(rr)[:120]; out.write(json.dumps(rec)+"\n"); out.flush(); continue
        rp=requests.post(f"{API}/api/statements/{aid}/process",headers=H,timeout=30,
            json={"document_ids":[did],"full_name":"V4 Confuse"})
        started=(rp.json().get("started") or [])
        if not started: rec["proc_skipped"]=str(rp.json())[:120]; out.write(json.dumps(rec)+"\n"); out.flush(); continue
        job=started[0]["job_id"]; rec["job"]=job
        t0=time.time(); st="?"
        while time.time()-t0<300:
            j=requests.get(f"{API}/api/v1/jobs/{job}",headers=H,timeout=30).json()
            st=j.get("status")
            if st in ("completed","failed"):
                rec["job_status"]=st; rec["job_err"]=(j.get("error") or j.get("error_message") or "")[:100]
                em=(j.get("result_data") or {}).get("statement_engine") or {}
                rec["eng"]={k:em.get(k) for k in ("verdict","engine","routed_bank") if em.get(k)}
                break
            time.sleep(4)
        else: rec["job_status"]="timeout"
        if rec.get("job_status")=="completed":
            rd=requests.get(f"{API}/api/v1/jobs/{job}/download",headers=H,timeout=60)
            rec["dl"]=rd.status_code
            if rd.status_code==200 and rd.content[:2]==b"PK":
                rec["ACCEPT"]=True; wrong.append(s8)
    except Exception as e: rec["exc"]=type(e).__name__+":"+str(e)[:60]
    out.write(json.dumps(rec)+"\n"); out.flush()
out.write(json.dumps({"WRONG_ACCEPTS":wrong})+"\n"); out.close()
