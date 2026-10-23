"""錯誤一行「程式名: 代號 原因」的代號檢查（代號照 10-23 命名統合（thinking/2026-10-23-naming）；使用者 10-22「錯誤訊息多代號也遵循」）。

各測試檔 import 時呼叫 install()：之後 subprocess.run 與 Popen.communicate 拿回來的文字 stderr，每一行開頭是
aos-exec／aos-loop／aos-fsm／aos-daemon／aos-tick 的「程式名: 」就檢查代號對不對得上原因開頭（對照表 CODES），再把代號拿掉，
讓既有的斷言照舊認「程式名: 原因」。對不上（該有沒有、不該有卻有、代號不對）丟 AssertionError。
subprocess.run 的結果另留一份原樣的 `raw_stderr`，要直接看代號的測試用它。"""
import re
import subprocess
import threading

# 原因開頭（regex）→ 可以的代號。順序有關：先比的先贏。None＝不是自己的錯、不帶代號。
_USAGE = [
    (r"usage: .*（不認得的旗標 ", {"FlagUnknown"}),
    (r"usage: ", {"ArgumentsBad"}),
]
_CFG = [
    (r"讀不到或不是 JSON：.*\[Errno 2\]", {"CfgMissing"}),   # 檔不在
    (r"讀不到或不是 JSON", {"CfgBad"}),
    (r"設定檔指不到", {"CfgMissing"}),
]
_LOOP = _USAGE + _CFG + [
    (r"(寫了 \S+ 卻)?沒設定 AOS_STACK", {"StackMissing"}),
    (r"起不了 aos-exec", {"LaunchFailed"}),
    (r"起不了子項", {"MkdirFailed", "WriteFailed", "LaunchFailed"}),
    (r"第 \d+ 拍 ", None),   # 那拍失敗：不是自己的錯
    (r"", {"CfgBad"}),
]
CODES = {
    "aos-exec": _USAGE + [
        (r"工作區不存在", {"WsMissing"}),
        (r"建不了 AOS_STACK", {"MkdirFailed"}),
        (r"入口不存在", {"EntryMissing"}),
        (r"入口(壞|讀不到)", {"EntryBad"}),
        (r"起不來", {"LaunchFailed"}),
        (r"\.env 讀不到", {"DotenvBad"}),
        (r"\.env 壞", {"DotenvBad"}),
        (r"單子跑不起來：(CwdMissing|OpenFailed|CommandMissing|CommandBad|LaunchFailed) ", {"LaunchFailed"}),
        (r"單子跑不起來：", {"EntryBad", "DirectiveBad"}),
    ],
    "aos-loop": _LOOP,
    "aos-daemon": _LOOP,
    "aos-fsm": _USAGE + _CFG + [
        (r"沒設定 AOS_STACK", {"StackMissing"}),
        (r"讀不了 ", {"StateBad"}),
        (r"查不到狀態", {"StateUnknown"}),
        (r"狀態 .*：起不了 aos-exec", {"LaunchFailed"}),
        (r"", {"CfgBad"}),
    ],
    "aos-tick": _USAGE + [
        (r"時鐘檔(讀不到|壞)", {"ClockBad"}),
        (r"時鐘檔寫不了", {"WriteFailed"}),
    ],
}
LINE = re.compile(r"(aos-exec|aos-loop|aos-fsm|aos-daemon|aos-tick): (?:([A-Z][A-Za-z]+) )?")


def expected(prog, reason):
    for head, codes in CODES[prog]:
        if re.match(head, reason):
            return codes
    return None


def check(stderr):
    """檢查並拿掉每一行的代號，回拿掉之後的 stderr。"""
    if not isinstance(stderr, str):
        return stderr
    out = []
    for line in stderr.split("\n"):
        m = LINE.match(line)
        if m:
            prog, code, reason = m.group(1), m.group(2), line[m.end():]
            want = expected(prog, reason)
            if want is None:
                if code is not None:
                    raise AssertionError("不該有代號：%r" % line)
            elif code not in want:
                raise AssertionError("代號應該是 %s：%r" % ("／".join(sorted(want)), line))
            line = "%s: %s" % (prog, reason)
        out.append(line)
    return "\n".join(out)


_installed = []
_inside_run = threading.local()   # subprocess.run 裡面也叫 communicate：那時不重複檢查


def install():
    if _installed:
        return
    _installed.append(True)
    run, communicate = subprocess.run, subprocess.Popen.communicate

    def run_checked(*a, **kw):
        _inside_run.on = True
        try:
            r = run(*a, **kw)
        finally:
            _inside_run.on = False
        r.raw_stderr = r.stderr
        r.stderr = check(r.stderr)
        return r

    def communicate_checked(self, *a, **kw):
        out, err = communicate(self, *a, **kw)
        if getattr(_inside_run, "on", False):
            return out, err
        return out, check(err)

    subprocess.run = run_checked
    subprocess.Popen.communicate = communicate_checked
