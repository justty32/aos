#!/usr/bin/env python3
# Writes the text in 03-瘦身文字.json into the 40 _tooldef.json files of one proto8 folder (description and parameter descriptions only, layout kept). Usage: 03-套用.py <proto8 folder> [--skip NAME]...
import json, os, re, sys

here = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
skip = {args[i + 1] for i, a in enumerate(args) if a == "--skip" and i + 1 < len(args)}
rest = [a for i, a in enumerate(args) if a != "--skip" and (i == 0 or args[i - 1] != "--skip")]
home = rest[0] if len(rest) == 1 else sys.exit("usage: 03-套用.py <proto8 folder> [--skip NAME]...")
table = json.load(open(os.path.join(here, "03-瘦身文字.json")))


def swap(text, start, old, new, where):
    """Replace the first "description": <old> at or after start; the old string is matched as JSON text."""
    pat = re.compile(r'"description"\s*:\s*' + re.escape(json.dumps(old, ensure_ascii=False)))
    m = pat.search(text, start)
    if not m:
        sys.exit("%s: old description not found" % where)
    return text[:m.start()] + '"description": ' + json.dumps(new, ensure_ascii=False) + text[m.end():]


done = 0
for row in table["rows"]:
    if row["tool"] in skip:
        continue
    rel = os.path.normpath(os.path.join("thinking/2026-11/21/tool-desc-瘦身-1121", row["file_path"]))
    path = os.path.join(home, rel)
    text = open(path).read()
    td = json.loads(text)
    props = td.get("parameters", {}).get("properties", {})
    for name, new in row["params"].items():
        if name not in props:
            sys.exit("%s: no parameter %s" % (path, name))
        old = props[name].get("description")
        if old is None or old == new:
            continue
        m = re.search(r'"properties"\s*:', text)
        k = re.compile(r'"%s"\s*:\s*\{' % re.escape(name)).search(text, m.end() if m else 0)
        if not k:
            sys.exit("%s: parameter %s not found in the text" % (path, name))
        text = swap(text, k.end(), old, new, "%s#%s" % (path, name))
    if td["description"] != row["description"]:
        text = swap(text, 0, td["description"], row["description"], path)
    after = json.loads(text)
    assert after["description"] == row["description"], path
    for name, new in row["params"].items():
        assert after["parameters"]["properties"][name].get("description") == new, (path, name)
    with open(path, "w") as f:
        f.write(text)
    done += 1
print("%d tool definitions rewritten" % done)
