"""verify4 shadow confusion: force-route foreign files through candidate spec.
accept = routed.status=='v2' AND verdict=='VERIFIED' (clean). REVIEW = flagged.
usage: python tools/verify4/confuse_shadow.py <backend_dir> <candidate> <sha8,sha8,...> <out.jsonl>"""
import json, os, sys, glob
sys.path.insert(0, sys.argv[1])
cand, sha8s, out_path = sys.argv[2], sys.argv[3].split(","), sys.argv[4]
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE","serve")
from app.services.statement_engine.serve import route_for_serve, v2_verdict, bank_mismatch
mani = {}
for m in glob.glob(os.path.join(os.path.dirname(__file__),".local","manifest_*.jsonl")):
    for l in open(m,encoding="utf-8"): d=json.loads(l); mani[d["sha8"]]=d["path"]
out=open(out_path,"w",encoding="utf-8"); acc=0
for s8 in sha8s:
    rec={"sha8":s8}
    p=mani.get(s8)
    if not p or not os.path.exists(p): rec["skip"]="no_path"; out.write(json.dumps(rec)+"\n"); continue
    try:
        routed,det,ms = route_for_serve(p, cand)
        rec["status"]=getattr(routed,"status",None); rec["verdict"]=v2_verdict(routed)
        rec["layout"]=getattr(routed,"layout_key",None) or getattr((routed or None),"layout",None)
        rec["mismatch"]=bank_mismatch(det,cand) if det else None
        rec["det_bank"]=getattr(det,"spec_bank",None) or getattr(det,"bank",None)
        rec["ms"]=ms
        if rec["status"]=="v2" and rec["verdict"]=="VERIFIED": rec["ACCEPT"]=True; acc+=1
    except Exception as e: rec["exc"]=type(e).__name__+":"+str(e)[:60]
    out.write(json.dumps(rec)+"\n"); out.flush()
out.write(json.dumps({"verdict_accepts":acc})+"\n"); out.close()
print("done",cand)
