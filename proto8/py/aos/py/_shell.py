"""aos.py._shell - 整套 Python 庫的通用代理：一個 Python 呼叫翻成剛好一條 aos 指令（argv）、跑它、把結果照一條規則交回；也有 Text、Failed、Timeout、sh。

規則（thinking/2026-11/19/aos-pylib-1119/03 第三節細則表；使用者 11-19 裁定在同夾 07）：
    aos-agent --daemon D --target N  X Y  --flag v  ARG   <->   agent.attach(N, daemon=D).X.Y(ARG, flag=v)
  點下去的名字＝子指令（底線換連字號、結尾一個 _ 去掉）；位置參數放在旗標後面（數字轉字串、dict／list 轉 JSON；有一個以 - 開頭就先放 --）；
  名=True＝旗標（一個字母 -x、多字母 --名）、False／None＝不加；名=數字／字串＝--名 值；名=dict＝JSON；名=list／tuple＝旗標重複；
  保留字結尾加 _（from_=）；json=True＝加 --json、回解好的（JSONL＝list、空＝None）；沒給＝stdout 原樣（Text），空＝None。
  「指哪一個」的旗標（aos-agent 的 --daemon、--target）一律放在子指令前；它們由模組自己在 attach 時綁、或在呼叫時當關鍵字給。
錯誤只有一種 Failed（指令退非 0、或庫自己拒絕）；庫自己等太久＝Timeout（也是 TimeoutError）。錯誤行原樣帶上來、不改寫（N-43）。
echo：aos.py.echo 為真時每條指令先在 stderr 印一行 "$ ..."（庫預設關，aos-gdb 打開）。
硬規則：這裡不 import aos.gdb，也不記任何狀態；一個呼叫＝一條指令。"""
import json as _json
import os
import re
import shlex
import subprocess
import sys

ERROR_LINE = re.compile(r"^(?P<program>[^\s:]+): error: (?P<code>[A-Z][A-Za-z0-9]*)(?: (?P<reason>.*))?$")


def echo_on():
    pkg = sys.modules.get("aos.py")
    return bool(getattr(pkg, "echo", False))


def show(line):
    """echo 開著＝在 stderr 印一行（"$ 指令" 或 "# read 路徑"）。"""
    if echo_on():
        sys.stderr.write(line.rstrip("\n") + "\n")
        sys.stderr.flush()


class Text(str):
    """在 REPL 裡印出來跟在 shell 看到的一樣（不帶引號、換行不印成 \\n）的字串。"""

    def __repr__(self):
        return str(self).rstrip("\n")


class Failed(RuntimeError):
    """活的那一邊唯一的例外。str(e)＝一行英文：指令自己的錯誤行原樣，或「where: 為什麼不做」。
    e.program、e.code、e.reason＝錯誤行 `程式: error: 代號 原因` 拆出來的三段（拆不出來＝None）；e.argv、e.exit＝跑的那條指令與結束碼（不是指令失敗＝None）。"""

    def __init__(self, where, why=None, *, code=None, argv=None, exit=None):
        line = where if why is None else "%s: %s" % (where, why)
        super().__init__(line)
        m = ERROR_LINE.match(line)
        self.program = m.group("program") if m else where if why is not None else None
        self.code = m.group("code") if m else code
        self.reason = (m.group("reason") if m else why) if (m or why is not None) else None
        self.argv, self.exit = argv, exit


class Timeout(Failed, TimeoutError):
    """庫自己等的事情等太久（例 a.bp.timeout_s 設了、a.bp.resume() 等過頭）；except TimeoutError 也接得到。"""


def call(argv, input=None, quiet=False, detach=False):
    """跑一條指令（stdin 不給就接 /dev/null），回 stdout（Text，可能是空的）；退非 0 丟 Failed（帶它最後一行錯誤）。quiet＝不 echo。
    detach＝指令自己一個 session：終端機的 Ctrl-C 打不到它（a.bp 送控制指令時用，不會送一半）。"""
    argv = [str(a) for a in argv]
    if not quiet:
        show("$ " + shlex.join(argv))
    try:
        p = subprocess.run(argv, input=input, stdin=None if input is not None else subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=detach)
    except OSError as e:
        raise Failed(argv[0], "cannot run it (source $AOS_HOME/env.sh to put aos on PATH): %s" % e,
                     code="CommandMissing", argv=argv) from None
    if p.returncode:
        lines = [x for x in p.stderr.splitlines() if x.strip()]
        errors = [x for x in lines if ERROR_LINE.match(x)]
        line = errors[-1] if errors else lines[-1] if lines else None
        if line and ERROR_LINE.match(line):
            raise Failed(line, argv=argv, exit=p.returncode)
        raise Failed(os.path.basename(argv[0]), line or "exited %d" % p.returncode, argv=argv, exit=p.returncode)
    return Text(p.stdout)


def sh(command):
    """跑一段 shell（sh -c），回 stdout（Text；空＝None）；REPL 裡順手打 shell 用。"""
    show("$ " + command)
    out = call(["sh", "-c", command], quiet=True)
    return out if out else None


def word(name):
    """Python 名字 → 子指令或旗標名：結尾一個 _ 去掉（保留字用），底線換連字號。"""
    if name.endswith("_"):
        name = name[:-1]
    return name.replace("_", "-")


def value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dict, list, tuple)):
        return _json.dumps(v, ensure_ascii=False)
    return str(v)


def flags_of(kw):
    """關鍵字參數 → 旗標（照呼叫寫的順序）。"""
    out = []
    for k, v in kw.items():
        f = word(k)
        flag = "-" + f if len(f) == 1 else "--" + f
        if v is None or v is False:
            continue
        if v is True:
            out.append(flag)
        elif isinstance(v, (list, tuple)):
            for x in v:
                out += [flag, value(x)]
        else:
            out += [flag, value(v)]
    return out


def args_of(args):
    pos = [value(a) for a in args]
    return (["--"] + pos) if any(a.startswith("-") for a in pos) else pos


def argv_of(prog, head, words, args, kw):
    """整條 argv：程式、「指哪一個」的旗標、子指令、旗標、位置參數。"""
    return [prog] + list(head) + [word(w) for w in words] + flags_of(kw) + args_of(args)


def result(out, as_json):
    """stdout → 回傳值：json＝解好的（整份一個 JSON；不是就一行一個＝list；空＝None）；不是 json＝Text，空＝None。"""
    if not out.strip():
        return None
    if not as_json:
        return out
    try:
        return _json.loads(out)
    except ValueError:
        pass
    try:
        return [_json.loads(x) for x in out.splitlines() if x.strip()]
    except ValueError as e:
        raise Failed("aos.py", "the output is not JSON or JSON lines: %s" % e, code="JsonBad") from None


def run(prog, head, words, args, kw):
    """跑一個代理呼叫：json=True 另外拿出來翻成 --json。"""
    kw = dict(kw)
    as_json = kw.pop("json", None) is True
    if as_json:
        kw["json"] = True
    return result(call(argv_of(prog, head, words, args, kw)), as_json)


class Proxy:
    """點一下多一段子指令、叫它＝跑那一條；repr 只印它會跑的那條（不跑）。
    pointing＝這支指令「指哪一個」的關鍵字（例 ("daemon", "target")）：呼叫時給了就放到子指令前。
    top＝第一段子指令可用的名字（None＝不查）；底線開頭的名字不翻（照 Python 的錯）。"""

    def __init__(self, prog, head=(), words=(), pointing=(), top=None):
        self._prog, self._head, self._words, self._pointing, self._top = prog, tuple(head), tuple(words), tuple(pointing), top

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if not self._words and self._top is not None and word(name) not in self._top():
            raise AttributeError("%s has no subcommand %s (%s)" % (self._prog, word(name), ", ".join(self._top())))
        return Proxy(self._prog, self._head, self._words + (name,), self._pointing, self._top)

    def __dir__(self):
        return sorted(n.replace("-", "_") for n in self._top()) if (not self._words and self._top) else []

    def __call__(self, *args, **kw):
        head = list(self._head)
        for p in self._pointing:
            if p in kw:
                v = kw.pop(p)
                if v is not None:
                    head += ["--" + word(p), value(v)]
        return run(self._prog, head, self._words, args, kw)

    def __repr__(self):
        return "<%s>" % " ".join([self._prog] + [shlex.quote(h) for h in self._head] + [word(w) for w in self._words])
