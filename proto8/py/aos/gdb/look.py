"""aos.gdb.look - aos-gdb 的檢閱薄殼與小零件：跑一條指令（印出來、失敗丟 Failed）、讀 stack 裡的檔（stage、history、observed、最後一次問腦、信箱、stderr）、why() 的結果長相。

停住時人看的全在 stack 的普通檔（thinking/2026-11/19/aos-gdb-1119/07 第三節）；這裡每個方法只讀一個檔或跑一條 aos 指令，不解讀、不改。
Look 是 aos.gdb.Agent 的底：需要 self.stack、self.agent()。丙（外面的觀察者）之後可以把同一個物件交給條件函式用（Argon A8）。"""
import json
import os
import shlex
import subprocess


class Failed(RuntimeError):
    """一條指令失敗或 aos.gdb 拒絕：str() 是一行英文（指令自己的錯誤行，或為什麼不做）。"""

    def __init__(self, what, why):
        super().__init__(why if what is None else "%s: %s" % (what, why))


class Text(str):
    """在 REPL 裡直接印出原樣（不加引號、不跳脫換行）的字串。"""

    def __repr__(self):
        return str(self).rstrip("\n")


def run(argv, echo=True, input=None):
    """跑一條指令；echo＝先印 "$ 指令"。回 stdout（Text）；退非 0 丟 Failed（帶 stderr 最後一行）。"""
    if echo:
        print("$ " + " ".join(shlex.quote(a) for a in argv))
    try:
        p = subprocess.run(argv, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as e:
        raise Failed(argv[0], "cannot run it (source $AOS_HOME/env.sh to put aos on PATH): %s" % e) from None
    if p.returncode:
        last = [x for x in p.stderr.splitlines() if x.strip()]
        if last and last[-1].startswith(os.path.basename(argv[0]) + ":"):
            raise Failed(None, last[-1])           # 它自己的錯誤行已經帶程式名
        raise Failed(argv[0], last[-1] if last else "exited %d" % p.returncode)
    return Text(p.stdout)


def sh(command, echo=True):
    """跑一段 shell（sh -c），回 stdout；在 REPL 裡順手打 shell 指令用。"""
    if echo:
        print("$ " + command)
    return run(["sh", "-c", command], echo=False)


def _tail_jsonl(path, n):
    try:
        with open(path, encoding="utf-8") as f:
            lines = [x for x in f.read().splitlines() if x.strip()]
    except FileNotFoundError:
        return []
    out = []
    for x in lines[-n:] if n else lines:
        try:
            out.append(json.loads(x))
        except ValueError:
            out.append({"unreadable": x})
    return out


class Why:
    """why() 的結果：paused（現在停著沒）、current（最後一張字條是不是這次停的原因）、notes（上次 resume 之後的字條）。"""

    def __init__(self, name, paused, current, notes):
        self.name, self.paused, self.current, self.notes = name, paused, current, notes

    def __bool__(self):
        return bool(self.notes)

    def __repr__(self):
        if not self.paused:
            head = "%s is not paused" % self.name
        elif self.current:
            head = "%s is paused by a trigger" % self.name
        elif self.notes:
            head = "%s is paused, but ctl was used after the last trigger note (by hand or by someone else); the notes may be old" % self.name
        else:
            head = "%s is paused, with no trigger note (paused by hand, or by something that leaves no note)" % self.name
        lines = [head]
        for n in self.notes:
            d = n.get("detail", {})
            what = " ".join("%s=%s" % (k, json.dumps(d[k], ensure_ascii=False)) for k in ("name", "code", "arguments", "content") if k in d)
            lines.append("  %s %s %s: %s%s%s" % (n.get("at", "?"), n.get("by", "?"), n.get("trigger", "?"), n.get("about") or n.get("event"),
                                                " [blocked]" if n.get("blocked") else "",
                                                " (pause failed: %s)" % n.get("why") if n.get("kind") == "pause_failed" else ""))
            if what:
                lines.append("      " + what)
        return "\n".join(lines)


class Look:
    """讀 stack 的檔；需要 self.stack 與 self.agent()。"""

    def path(self, rel=""):
        return os.path.join(self.stack, rel)

    def file(self, rel):
        """stack 裡任一個檔的內容（Text）；沒有＝None。"""
        try:
            with open(self.path(rel), encoding="utf-8", errors="replace") as f:
                return Text(f.read())
        except FileNotFoundError:
            return None

    def where(self):
        """停在哪一格（stage.txt）。"""
        s = self.file("stage.txt")
        return None if s is None else s.strip()

    def state(self, *parts):
        """aos-agent ctl state [PART...]（不給＝總覽；"all"＝全部）。"""
        return self.agent("ctl", "state", *parts)

    def history(self, n=5):
        """history.jsonl 最後 n 則（0＝全部）。"""
        return _tail_jsonl(self.path("history.jsonl"), n)

    def observed(self, n=5):
        """observed.jsonl 最後 n 筆（每次想、每次工具的流水帳）。"""
        return _tail_jsonl(self.path("observed.jsonl"), n)

    def request(self):
        """最後一次問腦的整份（think/request.json）；沒有＝None。"""
        t = self.file(os.path.join("think", "request.json"))
        return None if t is None else json.loads(t)

    def queue(self):
        """信箱裡還沒收的信（queue/new/ 的檔名）。"""
        try:
            return sorted(n for n in os.listdir(self.path(os.path.join("queue", "new"))) if not n.startswith("."))
        except FileNotFoundError:
            return []

    def stderr(self, n=20):
        """stderr.txt 最後 n 行。"""
        t = self.file("stderr.txt")
        return Text("") if t is None else Text("\n".join(t.splitlines()[-n:]) + "\n")

    def notes(self):
        """gdb/log.jsonl 全部（字條與 resume 紀錄，舊的在前）。"""
        from aos.gdb import trigger
        return trigger.read_log(self.stack)
