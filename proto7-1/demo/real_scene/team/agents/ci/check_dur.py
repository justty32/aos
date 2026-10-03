"""ci 的隱藏測試：python3 -B check_dur.py <放 dur.py 的資料夾>，stdout 印一行 JSON {"passed","total","fails"}。"""
import json
import sys

sys.path.insert(0, sys.argv[1])
P_OK = [("1h30m", 5400), ("45s", 45), ("2h5s", 7205), ("0s", 0), ("10m", 600), ("1d", 86400),
        ("1d2h", 93600), ("  1h ", 3600), ("1H30M", 5400), ("100s", 100), ("1h0m", 3600)]
P_BAD = ["", "10", "h", "1x", "1m1h", "1h1h", "-5s", "1.5h", "1h 30m", "abc", "01h", None]
F_OK = [(5400, "1h30m"), (45, "45s"), (0, "0s"), (86400, "1d"), (93600, "1d2h"), (90061, "1d1h1m1s"), (60, "1m")]
F_BAD = [-1, 1.5, "60", True, None]
fails = []
total = len(P_OK) + len(P_BAD) + len(F_OK) + len(F_BAD) + 1
try:
    from dur import format_duration, parse_duration
except BaseException as e:  # noqa: BLE001  匯入就壞
    print(json.dumps({"passed": 0, "total": total, "fails": ["import 失敗（要有 parse_duration 與 format_duration）：%r" % e]},
                     ensure_ascii=False))
    sys.exit(0)


def call(fn, arg, want=None, bad=False):
    name = "%s(%r)" % (fn.__name__, arg)
    try:
        got = fn(arg)
    except ValueError as e:
        if not bad:
            fails.append("%s 應為 %r，實際丟出 %r" % (name, want, e))
        return
    except BaseException as e:  # noqa: BLE001
        fails.append("%s 應%s，實際丟出 %r" % (name, "丟 ValueError" if bad else "為 %r" % (want,), e))
        return
    if bad:
        fails.append("%s 應丟 ValueError，實際回 %r" % (name, got))
    elif got != want or type(got) is not type(want):
        fails.append("%s 應為 %r，實際回 %r" % (name, want, got))


for s, w in P_OK:
    call(parse_duration, s, w)
for s in P_BAD:
    call(parse_duration, s, bad=True)
for n, w in F_OK:
    call(format_duration, n, w)
for n in F_BAD:
    call(format_duration, n, bad=True)
try:
    rt = [n for n in (1, 59, 61, 3599, 3601, 86399, 100000, 1234567) if parse_duration(format_duration(n)) != n]
    if rt:
        fails.append("來回轉換不一致：parse_duration(format_duration(n)) != n，n=%r" % rt)
except BaseException as e:  # noqa: BLE001
    fails.append("來回轉換丟出 %r" % e)
print(json.dumps({"passed": total - len(fails), "total": total, "fails": fails}, ensure_ascii=False))
