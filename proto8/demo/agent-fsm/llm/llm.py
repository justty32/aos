# llm.py 對象 動作 [鍵=值…] - agent-fsm 的 llm 入口（介面 aos-agent/llm，thinking 2026-11-04 aos-agent 03/02）。
# 對象：def＝定義裡的 ../.env（AOS_BRAIN_URL／MODEL／KEY ↔ 鍵 url／model／key）；stack＝正在跑那隻的副本 $AOS_STACK/llm.json（只放改過的鍵）。
# 動作：show（一行一個 鍵=值，key 印 ***；stack show＝定義被副本蓋過後的，哪些鍵來自副本印在 stderr）、set 鍵=值…（做完再 show）、reset（只有 stack：刪副本）。
# 錯：stderr 一行 `llm.py: 代號 原因`、退 1：ArgumentsBad、KeyUnknown、StackMissing、CfgBad、WriteFailed。
# 身體的承諾：brain.py 每格起來先讀 $AOS_STACK/llm.json，有的鍵蓋過環境變數（AOS_BRAIN_*）。
import json, os, sys

KEYS = {"url": "AOS_BRAIN_URL", "model": "AOS_BRAIN_MODEL", "key": "AOS_BRAIN_KEY"}   # show 的順序就是這個
SECRET = ("key",)


def die(code, reason):
    print("llm.py: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


def write(path, text):                               # N-05：先寫暫存再改名
    tmp = os.path.join(os.path.dirname(path) or ".", "." + os.path.basename(path) + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as e:
        die("WriteFailed", "%s：%s" % (path, e))


ENV = os.path.join(os.environ.get("AOS_CD") or ".", "..", ".env")


def read_env():
    out = {}
    try:
        with open(ENV, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return out
    except OSError as e:
        die("CfgBad", "%s：%s" % (ENV, e))
    for line in lines:
        k, eq, v = line.strip().partition("=")
        for key, var in KEYS.items():
            if eq and k.strip() == var:
                out[key] = v.strip()
    return out


def write_env(changes):
    try:
        with open(ENV, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []
    left = dict(changes)
    for i, line in enumerate(lines):
        k = line.strip().partition("=")[0].strip()
        for key, var in KEYS.items():
            if k == var and key in left:
                lines[i] = "%s=%s" % (var, left.pop(key))
    lines += ["%s=%s" % (KEYS[k], v) for k, v in left.items()]
    write(ENV, "\n".join(lines) + "\n")


def copy_path():
    stack = os.environ.get("AOS_STACK")
    if not stack:
        die("StackMissing", "沒設定 AOS_STACK（對象 stack 要它）")
    return os.path.join(stack, "llm.json")


def read_copy(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        die("CfgBad", "%s：%s" % (path, e))
    if not isinstance(d, dict):
        die("CfgBad", "%s：要是一層物件" % path)
    return d


def show(target):
    vals = read_env()
    if target == "stack":
        copy = read_copy(copy_path())
        vals.update({k: v for k, v in copy.items() if k in KEYS})
        if copy:
            print("副本：%s" % " ".join(k for k in KEYS if k in copy), file=sys.stderr)
    for k in KEYS:
        v = vals.get(k, "")
        print("%s=%s" % (k, "***" if k in SECRET and v else v))


def main(argv):
    if len(argv) < 2 or argv[0] not in ("def", "stack") or argv[1] not in ("show", "set", "reset"):
        die("ArgumentsBad", "用法：llm.py def|stack show|set 鍵=值…|reset")
    target, act, rest = argv[0], argv[1], argv[2:]
    if act == "show":
        if rest:
            die("ArgumentsBad", "show 不帶參數")
    elif act == "reset":
        if target != "stack" or rest:
            die("ArgumentsBad", "reset 只有 stack、不帶參數")
        try:
            os.remove(copy_path())
        except FileNotFoundError:
            pass
        except OSError as e:
            die("WriteFailed", str(e))
    else:
        changes = {}
        for a in rest:
            k, eq, v = a.partition("=")
            if not eq or not k:
                die("ArgumentsBad", "要寫成 鍵=值：%s" % a)
            if k not in KEYS:
                die("KeyUnknown", "%s（認得的：%s）" % (k, "、".join(KEYS)))
            changes[k] = v
        if not changes:
            die("ArgumentsBad", "set 至少一個 鍵=值")
        if target == "def":
            write_env(changes)
        else:
            path = copy_path()
            copy = read_copy(path)
            copy.update(changes)
            write(path, json.dumps(copy, ensure_ascii=False) + "\n")
    show(target)


main(sys.argv[1:])
