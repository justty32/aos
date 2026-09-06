# code 工具包：每支工具各測一條。
test_code_pack() {
  local root got
  root=$(mktemp -d "$TEST_RUN_DIR/code_pack.XXXXXX")
  mkdir -p "$root/world/pkg" "$root/world/.aos-agent" "$root/home"
  cat > "$root/world/pkg/math.py" <<'PYEOF2'
class Calculator:
    def add(self, left, right):
        return left + right

def helper(value):
    return value
PYEOF2
  cat > "$root/world/.aos-agent/history.txt" <<'PYEOF2'
Calculator 這筆是 agent 自己的歷史，不是專案程式。
PYEOF2
  cat > "$root/world/main.py" <<'PYEOF2'
from pkg.math import Calculator

print(Calculator().add(1, 2))
PYEOF2
  cat > "$root/world/bad.py" <<'PYEOF2'
def broken(
PYEOF2

  got=$(python3 - "$HERE" "$root/world" "$root/home" <<'PYEOF2'
import importlib.util, json, os, sys

here, world, home = sys.argv[1:4]
spec = importlib.util.spec_from_file_location("code_pack", os.path.join(here, "packs", "code.py"))
code = importlib.util.module_from_spec(spec)
spec.loader.exec_module(code)

class Ctx:
    def __init__(self):
        self.world = world
        self.home = home

ctx = Ctx()
results = {}

outline = code.run("code_outline", {"path": "pkg/math.py"}, ctx)
results["outline"] = all(word in outline.get("text", "") for word in
                         ("class Calculator（第 1 行）", "  method add（第 2 行）",
                          "function helper（第 5 行）"))

search = code.run("code_search", {"query": "Calculator", "path": ".",
                                  "context": 1, "limit": 20}, ctx)
results["search"] = (search.get("matches") == 3 and "main.py:1" in search.get("text", "")
                     and "> 3| print(Calculator().add(1, 2))" in search.get("text", "")
                     and ".aos-agent" not in search.get("text", ""))

check = code.run("code_check", {"path": "pkg/math.py"}, ctx)
bad_check = code.run("code_check", {"path": "bad.py"}, ctx)
results["check"] = (check == {"ok": True} and bad_check.get("ok") is False
                    and 'bad.py", line 1' in bad_check.get("text", ""))

checkpoint = code.run("code_checkpoint", {"paths": ["pkg/math.py", "new.py"]}, ctx)
backup = os.path.join(home, ".aos-undo", "1", "pkg", "math.py")
results["checkpoint"] = (checkpoint.get("checkpoint") == 1 and checkpoint.get("files") == 2
                         and os.path.isfile(backup) and "原本不存在" in checkpoint.get("text", ""))

with open(os.path.join(world, "pkg", "math.py"), "w", encoding="utf-8") as f:
    f.write("def add(left: int, right: int) -> int:\n    return left + right\n")
with open(os.path.join(world, "new.py"), "w", encoding="utf-8") as f:
    f.write("answer = 3\n")
diff = code.run("code_diff", {}, ctx)
results["diff"] = (diff.get("changed_files") == 2 and "pkg/math.py：+2 -6" in diff.get("text", "")
                   and "new.py：+1 -0" in diff.get("text", ""))

undo = code.run("code_undo", {}, ctx)
with open(os.path.join(world, "pkg", "math.py"), encoding="utf-8") as f:
    restored = f.read()
results["undo"] = (undo.get("restored") == ["pkg/math.py"] and undo.get("removed") == ["new.py"]
                   and "class Calculator" in restored
                   and not os.path.exists(os.path.join(world, "new.py")))

print(json.dumps(results, sort_keys=True))
PYEOF2
)
  for tool in outline search check checkpoint diff undo; do
    if python3 -c 'import json,sys; raise SystemExit(0 if json.loads(sys.argv[1])[sys.argv[2]] else 1)' "$got" "$tool"; then
      ok "code：code_$tool 可用"
    else
      fail "code：code_$tool 不對（$got）"
    fi
  done
  rm -rf "$root"
}

test_code_pack
