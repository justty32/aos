"""ci 的隱藏測試（第二個模組）：python3 -B check_ranges.py <放 ranges.py 的資料夾>，印一行 JSON {"passed","total","fails"}。"""
import json
import sys

sys.path.insert(0, sys.argv[1])
P_OK = [("1-3,5", [1, 2, 3, 5]), ("7", [7]), ("", []), ("5,1-2", [1, 2, 5]), (" 1 - 3 , 5 ", [1, 2, 3, 5]),
        ("1-3,2-4", [1, 2, 3, 4]), ("3-3", [3]), ("0-2", [0, 1, 2])]
P_BAD = ["5-3", "a", "1-", "-1", "1,,2", "1-2-3", None, "1.5"]
F_OK = [([1, 2, 3, 5], "1-3,5"), ([], ""), ([5, 1, 2], "1-2,5"), ([1, 1, 2], "1-2"), ([4], "4"), ([1, 3, 5], "1,3,5"),
        ([1, 2], "1-2")]
F_BAD = [[-1], [1, "2"], [True], None, "1-3"]
fails = []
total = len(P_OK) + len(P_BAD) + len(F_OK) + len(F_BAD) + 1
try:
    from ranges import format_ranges, parse_ranges
except BaseException as e:  # noqa: BLE001
    print(json.dumps({"passed": 0, "total": total, "fails": ["import 失敗（要有 parse_ranges 與 format_ranges）：%r" % e]},
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
    call(parse_ranges, s, w)
for s in P_BAD:
    call(parse_ranges, s, bad=True)
for n, w in F_OK:
    call(format_ranges, n, w)
for n in F_BAD:
    call(format_ranges, n, bad=True)
try:
    bad_rt = [s for s in ("1-3,5", "2,4-9,11", "0") if format_ranges(parse_ranges(s)) != s]
    if bad_rt:
        fails.append("來回轉換不一致：format_ranges(parse_ranges(s)) != s，s=%r" % bad_rt)
except BaseException as e:  # noqa: BLE001
    fails.append("來回轉換丟出 %r" % e)
print(json.dumps({"passed": total - len(fails), "total": total, "fails": fails}, ensure_ascii=False))
