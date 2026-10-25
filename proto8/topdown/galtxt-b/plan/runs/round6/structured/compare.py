#!/usr/bin/env python3
"""compare.py - 結構化場景（round6 structured.md）的「對下游不變」比對：四題（train/set）＋examples 兩題，各跑一次 brief/_entry，
把 brief.json 拿掉 cells_used 後跟 before/<題名>.json（改成結構化之前的 brief 產出）比——json.dump(indent=1) 的文字逐字相同才算過。

用法：python3 compare.py [--snap] [--brief <brief 資料夾>]
  --snap   把這次的產出寫進 before/（只在改表示法之前跑一次；之後不要再 snap）
  --brief  要跑的 brief 資料夾（預設＝本樹的 brief/）
另外跑一次 GALTXT_OFF_SAMPLES=1（第一題）比 before/<題名>.off_samples.json。
退 0＝全部逐字相同；退 1＝有 diff（印出第一個不同的地方）。"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GB = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
BEFORE = os.path.join(HERE, "before")


def questions():
    out = []
    for d in ("train/set", "examples"):
        for n in sorted(os.listdir(os.path.join(GB, d))):
            if n.endswith(".json"):
                out.append((n[:-5], os.path.join(GB, d, n)))
    return out


def build(brief_dir, qpath, env_extra=None):
    with tempfile.TemporaryDirectory() as t:
        ws, stack = os.path.join(t, "ws"), os.path.join(t, "stack")
        os.makedirs(os.path.join(ws, "new"))
        os.makedirs(stack)
        with open(qpath, encoding="utf-8") as f, open(os.path.join(ws, "new", os.path.basename(qpath)), "w", encoding="utf-8") as g:
            g.write(f.read())
        env = {k: v for k, v in os.environ.items() if not k.startswith("GALTXT_")}
        env.update({"AOS_WS": ws, "AOS_STACK": stack + "/"}, **(env_extra or {}))
        r = subprocess.run([sys.executable, "_entry"], cwd=brief_dir, env=env, capture_output=True, text=True)
        if r.returncode:
            sys.exit("compare: brief 失敗 %s：%s" % (qpath, r.stderr.strip()))
        with open(os.path.join(stack, "brief.json"), encoding="utf-8") as f:
            return json.load(f)


def text(b):
    return json.dumps({k: v for k, v in b.items() if k != "cells_used"}, ensure_ascii=False, indent=1)


def main():
    args = sys.argv[1:]
    snap = "--snap" in args
    brief_dir = args[args.index("--brief") + 1] if "--brief" in args else os.path.join(GB, "brief")
    cases = [(n, p, None, n) for n, p in questions()]
    cases.append((cases[0][0], cases[0][1], {"GALTXT_OFF_SAMPLES": "1"}, cases[0][0] + ".off_samples"))
    os.makedirs(BEFORE, exist_ok=True)
    bad = 0
    for name, path, extra, key in cases:
        got = build(brief_dir, path, extra)
        ref = os.path.join(BEFORE, key + ".json")
        if snap:
            with open(ref, "w", encoding="utf-8") as f:
                f.write(text(got) + "\n")
            print("snap  %s" % key)
            continue
        with open(ref, encoding="utf-8") as f:
            want = f.read().rstrip("\n")
        now = text(got)
        if now == want:
            print("same  %s（cells_used %d 格）" % (key, len(got.get("cells_used") or {})))
        else:
            bad += 1
            i = next((k for k in range(min(len(now), len(want))) if now[k] != want[k]), min(len(now), len(want)))
            print("DIFF  %s 第 %d 字起：改前 %r／改後 %r" % (key, i, want[i - 40:i + 40], now[i - 40:i + 40]))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
