# prof.py: sum time and token use per kind and name from one agent stack observed.jsonl (aos-vs-c-1119 probe-c).
# probe-c: sum observed.jsonl by kind/name (no stock tool does this)
import json,sys,collections
for f in sys.argv[1:]:
    agg=collections.defaultdict(lambda:[0,0.0,0])
    for l in open(f):
        r=json.loads(l)
        if r["kind"] in ("think","tool"):
            k=(r["kind"], r.get("name") or r.get("endpoint"))
            agg[k][0]+=1; agg[k][1]+=r.get("elapsed_ms",0); agg[k][2]+=(r.get("usage") or {}).get("total_tokens",0)
    print(f.split("/")[-2]); [print("  %-6s %-12s n=%-3d ms=%-8.0f tok=%d"%(k[0],k[1],*v)) for k,v in sorted(agg.items(), key=lambda kv:-kv[1][1])]
