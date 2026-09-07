# pyshop 工具包：工作室資產、scaffold 骨架與 run_checks 驗收。
pyshop_assert() {
  local got=$1 label=$2
  if [ "$got" = "True" ]; then ok "$label"; else fail "$label（$got）"; fi
}

pyshop_py() {  # pyshop_py <工作室根> <成員> <python 片段>；片段裡有 ctx 與 pyshop，印 True/False
  python3 - "$HERE" "$1" "$2" "$3" <<'PYEOF2'
import json, os, sys
here, root, member, snippet = sys.argv[1:5]
sys.path.insert(0, here)
from aos_agent import Ctx
from packs import pyshop
world = root if member == "owner" else os.path.join(root, "kids", member)
ctx = Ctx(world, world)
scope = {"ctx": ctx, "pyshop": pyshop, "json": json, "os": os, "root": root,
         "run": lambda tool, **args: pyshop.run(tool, args, ctx)}
exec(snippet, scope)
PYEOF2
}

test_pyshop_pack() {
  local root studio project got
  root=$(mktemp -d "$TEST_RUN_DIR/pyshop.XXXXXX")
  prep_llm "$root/llm"
  studio="$root/studio"
  export AOS_LLM_DIR="$root/llm"
  "$AUSER" team new "$studio" --preset studio --engine local \
    --budget '{"tokens":1000,"hours":2,"ticks":1000,"disk_mb":20,"mem_mb":64,"money_usd":1}' \
    >/dev/null 2>&1
  # 主線之後會在 team new 時整包複製；測試自己 cp 過去。
  cp -r "$HERE/presets/studio/assets" "$studio/team/assets"
  project="$studio/team/projects/ord-7"

  # 1. asset_list：列得出資產與第一行說明。
  got=$(pyshop_py "$studio" chief '
r = run("asset_list")
paths = [a["path"] for a in r.get("assets", [])]
notes = {a["path"]: a["note"] for a in r.get("assets", [])}
print(r.get("ok") is True
      and set(paths) >= {"README.md", "checks/README.md", "checks/run_tests.sh",
                         "checks/smoke_cli.sh", "snippets/cli_argparse.py",
                         "snippets/json_store.py", "snippets/test_template.py",
                         "snippets/readme_template.md"}
      and "py_compile" in notes["checks/run_tests.sh"]
      and "snippet" in notes["snippets/cli_argparse.py"])
')
  pyshop_assert "$got" "pyshop：asset_list 列出全部資產與一句說明"

  # 2. asset_get：讀得到內容；越界路徑被擋。
  got=$(pyshop_py "$studio" chief '
good = run("asset_get", path="snippets/json_store.py")
up = run("asset_get", path="../../../etc/passwd")
absolute = run("asset_get", path="/etc/passwd")
missing = run("asset_get", path="snippets/nope.py")
print(good.get("ok") is True and "def save(" in good.get("text", "")
      and up.get("ok") is False and "assets" in up.get("error", "")
      and absolute.get("ok") is False and missing.get("ok") is False)
')
  pyshop_assert "$got" "pyshop：asset_get 讀得到資產，../ 與絕對路徑被擋"

  # 3. scaffold：三個檔都生出來，再叫一次不蓋。
  got=$(pyshop_py "$studio" chief '
first = run("scaffold", order_id="ord-7", name="todo")
second = run("scaffold", order_id="ord-7", name="todo")
folder = os.path.join(root, "team", "projects", "ord-7")
files = sorted(os.listdir(folder))
program = open(os.path.join(folder, "todo.py"), encoding="utf-8").read()
test = open(os.path.join(folder, "test_todo.py"), encoding="utf-8").read()
readme = open(os.path.join(folder, "README.md"), encoding="utf-8").read()
print(first.get("ok") is True
      and sorted(first["created"]) == ["README.md", "test_todo.py", "todo.py"]
      and files == ["README.md", "test_todo.py", "todo.py"]
      and second.get("ok") is True and second["created"] == []
      and sorted(second["skipped"]) == ["README.md", "test_todo.py", "todo.py"]
      and "def save(" in program and "SNIPPET-MERGE" not in program
      and "這是 snippet" not in program
      and "MODULE = \"todo\"" in test
      and "todo.py" in readme and "{{NAME}}" not in readme)
')
  pyshop_assert "$got" "pyshop：scaffold 生出主程式、測試與 README，再叫一次不蓋"

  # 4. run_checks：scaffold 出來的骨架本身就要全過（語法、測試、冒煙）。
  got=$(pyshop_py "$studio" chief '
r = run("run_checks", order_id="ord-7", main="todo.py")
names = [s["name"] for s in r.get("steps", [])]
tails = " ".join(s["tail"] for s in r.get("steps", []))
print(r.get("ok") is True and names == ["run_tests", "smoke_cli"]
      and all(s["exit"] == 0 for s in r["steps"])
      and "總結：py_compile 過；unittest 過" in tails and "冒煙通過" in tails)
')
  pyshop_assert "$got" "pyshop：run_checks 對 scaffold 骨架全過（測試＋冒煙）"

  if [ -d "$project/__pycache__" ]; then
    fail "pyshop：run_checks 在專案目錄留下 __pycache__"
  else
    ok "pyshop：run_checks 跑完專案目錄沒有留 __pycache__"
  fi

  # 5. 把測試改壞：ok 變 false，tail 看得到 Traceback。
  cat >> "$project/test_todo.py" <<'PYEOF2'


class BrokenTest(unittest.TestCase):
    def test_boom(self):
        raise RuntimeError("故意壞掉")
PYEOF2
  got=$(pyshop_py "$studio" chief '
r = run("run_checks", order_id="ord-7")
step = r["steps"][0]
print(r.get("ok") is False and len(r["steps"]) == 1 and step["exit"] == 1
      and "Traceback" in step["tail"] and "故意壞掉" in step["tail"]
      and len(step["tail"]) <= 1500)
')
  pyshop_assert "$got" "pyshop：測試壞掉時 run_checks ok=false，tail 有 Traceback"

  # 6. 錯誤路徑：沒有這張單、壞單號、不認得的 kind、不在工作室裡都回 {"ok": false, "error"}。
  got=$(pyshop_py "$studio" chief '
no_order = run("run_checks", order_id="ord-none")
bad_id = run("scaffold", order_id="../escape", name="todo")
bad_name = run("scaffold", order_id="ord-8", name="9todo")
bad_kind = run("scaffold", order_id="ord-8", name="todo", kind="web")
bad_main = run("run_checks", order_id="ord-7", main="../todo.py")
unknown = run("nope")
print(all(r.get("ok") is False and r.get("error") for r in
          (no_order, bad_id, bad_name, bad_kind, bad_main, unknown))
      and not os.path.exists(os.path.join(root, "team", "projects", "ord-8")))
')
  pyshop_assert "$got" "pyshop：找不到單、壞名字、壞 kind、越界 main 都回 ok=false"

  got=$(python3 - "$HERE" "$root" <<'PYEOF2'
import os, sys
here, root = sys.argv[1:3]
sys.path.insert(0, here)
from aos_agent import Ctx
from packs import pyshop
lonely = os.path.join(root, "lonely")
os.makedirs(lonely, exist_ok=True)
ctx = Ctx(lonely, lonely)
r = pyshop.run("asset_list", {}, ctx)
print(r.get("ok") is False and "team" in r.get("error", ""))
PYEOF2
)
  pyshop_assert "$got" "pyshop：不在工作室裡就回沒有 team/ 的錯誤"

  "$AUSER" team stop "$studio" >/dev/null 2>&1
  unset AOS_LLM_DIR
  rm -rf "$root"
}

test_pyshop_pack
