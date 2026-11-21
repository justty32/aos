"""Every knowledge path written in the knowledge itself, the tool descriptions and the templates' system texts points to something real: the file under proto8/knowledge/, and the #/place in it (json by RFC 6901, md by aos.mdpath)."""
import json
from pathlib import Path
import re
import sys
import unittest

PY = Path(__file__).resolve().parents[1]
ROOT = PY.parent
KNOW = ROOT / "knowledge"
sys.path.insert(0, str(PY))
from aos import mdpath  # noqa: E402

# 反引號裡的一整段：aos/….json 或 aos/….md，可帶 #/…（md 的位置可以有空白）；沒有反引號的只認到 .json／.md 為止（只查檔在不在）
TICKED = re.compile(r"`(aos/[^`\s#]+\.(?:json|md))(#/[^`]*)?`")
BARE = re.compile(r"(?<![\w/.-])(aos/[A-Za-z0-9_/.-]+\.(?:json|md))")

# 今天的庫本來就指不到的（不改知識庫；隊長決定怎麼處理）：{"寫著它的檔: 路徑": 原因}
KNOWN = {"knowledge/aos/errors.md: aos/tools/<tool>.json": "a placeholder (<tool> stands for any tool name), not a real path"}


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)


def sources():
    """(給人看的檔名, 文字) 逐一：知識庫 aos/ 的 json（所有字串值）與 md、工具說明的 description、範本的 system.txt。"""
    for p in sorted((KNOW / "aos").rglob("*")):
        if p.suffix == ".json":
            yield p, "\n".join(strings(json.loads(p.read_text(encoding="utf-8"))))
        elif p.suffix == ".md":
            yield p, p.read_text(encoding="utf-8")
    for p in sorted((PY / "tools").rglob("_tooldef.json")):
        d = json.loads(p.read_text(encoding="utf-8")).get("description")
        if isinstance(d, str):
            yield p, d
    for p in sorted((ROOT / "templates").rglob("system.txt")):
        yield p, p.read_text(encoding="utf-8")


def reach(file, toks):
    """file 的 toks 那一格讀得到嗎：回 None＝到了，否則一句原因。json 半路或終點是 {"$ref": …} 物件就算到。"""
    text = file.read_text(encoding="utf-8")
    if file.suffix == ".md":
        try:
            mdpath.get(text, toks)
            return None
        except mdpath.Missing as e:
            return e.reason
    cur = json.loads(text)
    for i, tok in enumerate(toks):
        if isinstance(cur, dict) and "$ref" in cur:
            return None
        if isinstance(cur, dict) and tok in cur:
            cur = cur[tok]
        elif isinstance(cur, list) and tok.isdigit() and int(tok) < len(cur):
            cur = cur[int(tok)]
        else:
            return "/%s has no %s" % ("/".join(toks[:i]), tok)
    return None


def found():
    """[(寫著它的檔, 路徑, 指不到的原因或 None)]。"""
    out = []
    for src, text in sources():
        seen = set()
        for m in TICKED.finditer(text):
            seen.add((m.group(1), m.group(2) or ""))
        for m in BARE.finditer(text):
            seen.add((m.group(1), ""))
        for path, place in sorted(seen):
            f = KNOW / path
            if not f.is_file():
                why = "no such file under proto8/knowledge"
            elif place:
                why = reach(f, mdpath.split(path + place)[1])
            else:
                why = None
            out.append((src.relative_to(ROOT).as_posix(), path + place, why))
    return out


class KnowledgePaths(unittest.TestCase):
    def test_every_path_is_there(self):
        hits = found()
        self.assertGreater(len(hits), 100)                 # the scan really finds paths
        bad = ["%s: %s (%s)" % (src, p, why) for src, p, why in hits if why and "%s: %s" % (src, p) not in KNOWN]
        self.assertEqual(bad, [])

    def test_known_list_is_still_needed(self):
        broken = {"%s: %s" % (src, p) for src, p, why in found() if why}
        self.assertEqual(sorted(set(KNOWN) - broken), [])  # fixed ones leave the list

    def test_the_finder(self):
        text = "see `aos/me.md#/What is in your stack` and aos/me.json, not py/aos/x.json or `aos/x.json is here`"
        self.assertEqual([m.groups() for m in TICKED.finditer(text)], [("aos/me.md", "#/What is in your stack")])
        self.assertEqual(BARE.findall(text), ["aos/me.md", "aos/me.json", "aos/x.json"])


if __name__ == "__main__":
    unittest.main()
