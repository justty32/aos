test_fs_pack() {
  local root got
  root=$(mktemp -d)
  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import importlib.util
import os
import sys

here, world = sys.argv[1:3]
spec = importlib.util.spec_from_file_location("fs_pack", os.path.join(here, "packs", "fs.py"))
fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fs)


class Ctx:
    def __init__(self, path):
        self.world = path

    @staticmethod
    def truncate(text, n=4000):
        return text if len(text) <= n else text[:n] + "…（截斷）"


ctx = Ctx(world)


def result(label, condition):
    print(label + "=" + ("ok" if condition else "bad"))


# write：覆蓋時會建父資料夾；append 會接在後面。
w1 = fs.run("write", {"path": "sub/a.txt", "text": "一\n二\n三\n"}, ctx)
w2 = fs.run("write", {"path": "sub/a.txt", "text": "四\n", "append": True}, ctx)
result("write", w1 == {"path": "sub/a.txt", "bytes": 12, "mode": "overwrite"}
       and w2["mode"] == "append"
       and open(os.path.join(world, "sub/a.txt"), encoding="utf-8").read() == "一\n二\n三\n四\n")

# read：只回指定行；沒讀完時會說下一段從哪開始。
r = fs.run("read", {"path": "sub/a.txt", "start": 2, "count": 2}, ctx)
result("read", r["text"] == "二\n三\n" and r["start"] == 2 and r["end"] == 3
       and r["total"] == 4 and r["truncated"] and "start=4" in r["note"])

# read 邊界：單行超過 4000 字也會明講截斷，叫模型縮範圍。
open(os.path.join(world, "large.txt"), "w", encoding="utf-8").write("x" * 5000 + "\n")
r = fs.run("read", {"path": "large.txt"}, ctx)
result("read_boundary", r["truncated"] and "縮小" in r["note"] and len(r["text"]) < 4100)

# ls：不遞迴、預設藏點檔，all 才看得到。
open(os.path.join(world, ".hidden"), "w", encoding="utf-8").write("h")
l1 = fs.run("ls", {}, ctx)
l2 = fs.run("ls", {"all": True}, ctx)
result("ls", "sub" in l1["text"] and "a.txt" not in l1["text"]
       and ".hidden" not in l1["text"] and ".hidden" in l2["text"])

# ls 邊界：超過 200 個只列前 200 個，並說還有多少。
many = os.path.join(world, "many")
os.mkdir(many)
for i in range(203):
    open(os.path.join(many, "%03d" % i), "w").close()
l = fs.run("ls", {"path": "many"}, ctx)
result("ls_boundary", l["total"] == 203 and l["shown"] == 200
       and l["truncated"] and "還有 3 個" in l["note"])

# edit：剛好一次才換，並回起始行。
e = fs.run("edit", {"path": "sub/a.txt", "old": "二\n三", "new": "貳\n參"}, ctx)
result("edit", e["line"] == 2 and e["replaced_chars"] == 3
       and "貳\n參" in open(os.path.join(world, "sub/a.txt"), encoding="utf-8").read())

# edit 邊界：零次、多次都報錯，而且不改檔。
path = os.path.join(world, "repeat.txt")
open(path, "w", encoding="utf-8").write("aa aa")
before = open(path, encoding="utf-8").read()
e0 = fs.run("edit", {"path": "repeat.txt", "old": "zz", "new": "x"}, ctx)
e2 = fs.run("edit", {"path": "repeat.txt", "old": "aa", "new": "x"}, ctx)
result("edit_boundary", "0 次" in e0["error"] and "2 次" in e2["error"]
       and open(path, encoding="utf-8").read() == before)

# sh：cwd 是世界，stdin 有送進去，退出碼、秒數與兩條輸出都有回來。
s = fs.run("sh", {"command": "read x; printf '%s:%s' \"$PWD\" \"$x\"; printf err >&2; exit 7",
                  "stdin": "hello\n"}, ctx)
result("sh", s["exit"] == 7 and s["stdout"] == world + ":hello" and s["stderr"] == "err"
       and isinstance(s["seconds"], float))

# sh 邊界：兩邊只留最後 1500 字。
s = fs.run("sh", {"command": "python3 -c \"import sys; print('a'*1600, end=''); print('b'*1700, end='', file=sys.stderr)\""}, ctx)
result("sh_tail", len(s["stdout"]) == 1500 and set(s["stdout"]) == {"a"}
       and len(s["stderr"]) == 1500 and set(s["stderr"]) == {"b"}
       and s["stdout_truncated"] and s["stderr_truncated"])

# sh 邊界：真的逾時會很快停，並叫模型改用 run_long；最長 120 秒。
s = fs.run("sh", {"command": "sleep 2", "timeout": 0.1}, ctx)
smax = fs.run("sh", {"command": "true", "timeout": 121}, ctx)
result("sh_timeout", s["exit"] is None and "run_long" in s["error"] and s["seconds"] < 1
       and "最長 120" in smax["error"])

# 同時開 fs、shell 時，把 fs 排前面就由 fs 接 sh。
sys.path.insert(0, here)
from aos_agent import load_packs, pack_owners, write_json_atomic
home = os.path.join(world, "agent")
os.makedirs(home)
write_json_atomic(os.path.join(home, "tools.json"), {"packs": ["fs", "shell"], "tools": []})
loaded, _ = load_packs(home)
result("coexist", pack_owners(loaded)["sh"][0] == "fs")
PYEOF2
)
  local key
  for key in write read read_boundary ls ls_boundary edit edit_boundary sh sh_tail sh_timeout coexist; do
    if printf '%s\n' "$got" | grep -qx "$key=ok"; then
      ok "fs：$key"
    else
      fail "fs：$key（$got）"
    fi
  done
  rm -rf "$root"
}

test_fs_pack
