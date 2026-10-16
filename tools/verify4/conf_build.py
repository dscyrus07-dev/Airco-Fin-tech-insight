import json,glob,collections
mani={}
for m in glob.glob("tools/verify4/.local/manifest_*.jsonl"):
    for l in open(m,encoding="utf-8"): d=json.loads(l); mani[d["sha8"]]=d["path"]
by=collections.defaultdict(list)
MARK="unified all statements/"
for s8,p in mani.items():
    pp=p.replace("\\","/").lower()
    i=pp.find(MARK)
    if i>=0:
        folder=pp[i+len(MARK):].split("/")[0].replace(" ","_")
        by[folder].append(s8)
CAND={"dbs":"dbs_bank","federal":"federal_bank","dhanlaxmi":"dhanlaxmi_bank"}
for cand,folder in CAND.items():
    lst=[]
    for b,ss in sorted(by.items()):
        if b!=folder: lst.extend(ss[:10])
    open("tools/verify4/.local/conf_"+cand+".txt","w").write(",".join(lst))
    print(cand,len(lst))
