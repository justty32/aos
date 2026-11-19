# 測：八份知識檔裡寫的 aos/X.json#/Y 參照，檔與鍵是否真的在（用法：clean python3 此檔 KNOWLEDGE_DIR）
import json, os, re, sys
K = sys.argv[1]
files = ["kernel","mailbox","body","clock","status","errors","definition","world","_description"]
def load(p):
    d = json.load(open(p))
    # $ref 展開一層
    if isinstance(d, dict):
        for k, v in list(d.items()):
            if isinstance(v, dict) and "$ref" in v:
                try: d[k] = json.load(open(os.path.join(os.path.dirname(p), v["$ref"])))
                except Exception as e: d[k] = "REFBAD %s" % e
    return d
bad = 0
for f in files:
    text = json.dumps(load(os.path.join(K, "aos", f + ".json")), ensure_ascii=False)
    for m in sorted(set(re.findall(r"aos/[A-Za-z0-9_/.-]+?\.json(?:#/[A-Za-z0-9_/-]+)?", text))):
        path, _, ptr = m.partition("#/")
        full = os.path.join(K, path)
        if not os.path.exists(full):
            print("%s: MISSING FILE %s" % (f, m)); bad += 1; continue
        if ptr:
            d = load(full)
            for part in ptr.split("/"):
                if isinstance(d, dict) and part in d: d = d[part]
                else:
                    print("%s: MISSING KEY %s" % (f, m)); bad += 1; break
print("bad", bad)
