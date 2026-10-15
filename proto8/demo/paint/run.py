#!/usr/bin/env python3
"""畫家 demo：畫家 agent 透過工具叫畫筆 agent（agent 當工具）、同一個 frame 續聊、frame 放同名 brain.json 換腦。

    python3 proto8/demo/paint/run.py                   （假腦，約 10 秒）
    python3 proto8/demo/paint/run.py 腦設定.json       （換成那顆腦：畫家、畫筆都綁它；例 ../fsm/brains/lmstudio.json）

painter/、brush/ 是兩個定義資料夾，跑完一個字都沒變；所有東西寫在 mktemp 建的 frame 裡，跑完整個刪掉
（`--keep` 留著，印出路徑）。說明在 README.md。
"""
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))            # proto8/
PAINTER, BRUSH = os.path.join(HERE, "painter"), os.path.join(HERE, "brush")
T0 = time.monotonic()


def env():
    """PATH 前面接 proto8/bin（aos）、demo/bin（aos-demo）。"""
    path = os.pathsep.join([os.path.join(ROOT, "bin"), os.path.join(ROOT, "demo", "bin"), os.environ.get("PATH", "")])
    return dict(os.environ, PATH=path, PYTHONDONTWRITEBYTECODE="1")


def say(msg=""):
    for i, line in enumerate(str(msg).split("\n")):
        print(("[%4.1fs] " % (time.monotonic() - T0) if i == 0 else " " * 8) + line, flush=True)


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def tree_hash(top):
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(top)):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for n in sorted(files):
            h.update(os.path.relpath(os.path.join(d, n), top).encode())
            with open(os.path.join(d, n), "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def find_brain(arg):
    """腦設定的路徑：照 cwd 找，沒有再照本資料夾、demo/fsm 找（brains/xxx.json 放在那裡的也認得）。"""
    for base in (os.getcwd(), HERE, os.path.join(ROOT, "demo", "fsm")):
        p = os.path.join(base, arg)
        if os.path.isfile(p):
            return os.path.abspath(p)
    sys.exit("找不到腦設定：%s" % arg)


def bind_brain(frame, brain):
    """綁定（C-46：frame 放同名檔＝蓋過定義的）：
    ① frame/brain.json＝這顆腦 → 畫家用它；
    ② frame/tools/brush.json＝定義的 brush 工具多一步「把這顆腦 cp 進畫筆的 frame」→ 畫筆也用它（畫筆的 frame 是 work/<n>/，
       frame.json 指回 brush/，找不到畫家這邊的 brain.json，所以要在叫它那一步放進去）。"""
    shutil.copy(brain, os.path.join(frame, "brain.json"))
    tool = read(os.path.join(PAINTER, "tools", "brush.json"))
    tool["argv"][3] = "cp %s brain.json && %s" % (shlex.quote(brain), tool["argv"][3])
    write(os.path.join(frame, "tools", "brush.json"), tool)


def ask(frame, question):
    """呼叫畫家：寫 args.json，cd frame 跑 painter/loop.json（fsm 走到 done 就停，stop_on_end），讀 ret.json。"""
    write(os.path.join(frame, "args.json"), {"question": question})
    say("→ args.json %s；cd frame && aos loop painter/loop.json" % json.dumps({"question": question}, ensure_ascii=False))
    t = time.monotonic()
    rc = subprocess.run(["aos", "loop", os.path.join(PAINTER, "loop.json")], cwd=frame, env=env(),
                        stdout=subprocess.DEVNULL).returncode
    st = read(os.path.join(frame, "loop/state.json")) or {}
    say("  loop 退出 %d，%s、拍了 %s 次、%.1f 秒" % (rc, st.get("state"), st.get("runs"), time.monotonic() - t))
    ret = read(os.path.join(frame, "ret.json"))
    say("← ret.json：" + ("（沒有：沒走到 done）" if ret is None else
                          ret["reply"] if isinstance(ret.get("reply"), str) else json.dumps(ret, ensure_ascii=False)))
    return ret


def show_frame(frame):
    say("frame 裡的檔（畫家的 frame → work/<n>/＝畫筆那次的 frame → 再下一層 work/<n>/＝調色盤那次）：")
    for d, dirs, files in sorted(os.walk(frame)):
        dirs.sort()
        rel = os.path.relpath(d, frame)
        say("  %s/  %s" % ("." if rel == "." else rel, " ".join(sorted(files))))
    for n in sorted((x for x in os.listdir(os.path.join(frame, "work")) if x.isdigit()), key=int):
        w = os.path.join(frame, "work", n)
        say("  work/%s/frame.json %s｜args.taken.json %s" % (
            n, json.dumps(read(os.path.join(w, "frame.json")), ensure_ascii=False).replace(HERE + "/", ""),
            json.dumps(read(os.path.join(w, "args.taken.json")), ensure_ascii=False)))


def main():
    args = [a for a in sys.argv[1:] if a != "--keep"]
    keep = "--keep" in sys.argv[1:]
    brain = find_brain(args[0]) if args else None
    before = tree_hash(HERE)
    tmp = tempfile.mkdtemp(prefix="aos-paint-demo-")
    try:
        a = os.path.join(tmp, "A")
        write(os.path.join(a, "frame.json"), {"parent": PAINTER})
        say("== 1. 叫畫家（agent 當函數）：frame A＝%s，frame.json 指回定義資料夾 painter/" % a)
        if brain:
            bind_brain(a, brain)
            say("   換腦：frame A 放 brain.json（%s）、tools/brush.json（多 cp 這顆腦給畫筆）" % os.path.basename(brain))
        else:
            say("   腦：定義裡的 brain.json（假腦 paint/brains/fake.py）")
        ask(a, "幫我畫一隻貓")
        say("   畫家的 history：%s" % " → ".join(m["role"] for m in read(os.path.join(a, "history.json"))))
        show_frame(a)

        say()
        say("== 2. 同一個 frame 續聊：再寫一份 args.json（intake 接在 history 後面、清掉上一輪的 ret.json）")
        ask(a, "再畫一隻狗")
        say("   畫家的 history 現在 %d 則；畫筆這次在新的 work/2/（每次叫工具一個新 frame、新對話）"
            % len(read(os.path.join(a, "history.json"))))

        if not brain:
            say()
            say("== 3. 換腦（綁定）：frame B 放同名 brain.json（brains/fake_alt.json＝同一支假腦加 --name），蓋過定義的")
            b = os.path.join(tmp, "B")
            write(os.path.join(b, "frame.json"), {"parent": PAINTER})
            bind_brain(b, os.path.join(HERE, "brains", "fake_alt.json"))
            ask(b, "幫我畫一片海")

        say()
        say("== 定義資料夾 painter/、brush/ 有沒有被動到：%s" % ("沒有（雜湊一樣）" if tree_hash(HERE) == before else "有！"))
    finally:
        if keep:
            say("frame 留在 %s" % tmp)
        else:
            shutil.rmtree(tmp)
            say("暫存資料夾刪掉了")


if __name__ == "__main__":
    main()
