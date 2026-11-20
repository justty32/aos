#!/usr/bin/env python3
# Writes the text in 03-瘦身文字.json into the 40 _tooldef.json files of one proto8 folder (description and parameter descriptions only). Usage: 03-套用.py <proto8 folder>
import json, os, sys

here = os.path.dirname(os.path.abspath(__file__))
home = sys.argv[1] if len(sys.argv) == 2 else sys.exit("usage: 03-套用.py <proto8 folder>")
table = json.load(open(os.path.join(here, "03-瘦身文字.json")))
for row in table["rows"]:
    rel = os.path.normpath(os.path.join("thinking/2026-11/21/tool-desc-瘦身-1121", row["file_path"]))
    path = os.path.join(home, rel)
    td = json.load(open(path))
    td["description"] = row["description"]
    props = td.get("parameters", {}).get("properties", {})
    for name, text in row["params"].items():
        if name not in props:
            sys.exit("%s: no parameter %s" % (path, name))
        props[name]["description"] = text
    with open(path, "w") as f:
        json.dump(td, f, ensure_ascii=False, indent=1)
        f.write("\n")
print("%d tool definitions rewritten" % len(table["rows"]))
