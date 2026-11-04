# bigmem：ref 摺疊展開、SQLite 記憶世界與歷史歸檔。

test_bigmem_ref_auto() {
  local root got
  root=$(mktemp -d)
  mkdir -p "$root/agent"
  printf '[]\n' > "$root/agent/prompts.json"
  got=$(PYTHONDONTWRITEBYTECODE=1 python3 - "$HERE" "$root" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import ref
world=sys.argv[2]; home=os.path.join(world,"agent"); state={}
ctx=Ctx(world, home, state)
value={"blob":"記"*6100}
pointer=ref.on_act(ctx, "huge_json", {}, value, 1)
print(pointer["$ref"].startswith("ref://"), pointer["chars"] > 6000,
      len(pointer["preview"]) == 200,
      os.path.isfile(os.path.join(home,"refs",pointer["$ref"][6:]+".json")))
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "bigmem：超過 6000 字的 JSON 工具結果自動摺成 ref"
  else
    fail "bigmem：自動摺疊不對（$got）"
  fi
  rm -rf "$root"
}

test_bigmem_ref_expand() {
  local root got
  root=$(mktemp -d)
  mkdir -p "$root/agent/refs"
  printf '{"choices":[{"text":"abcdefghij"}]}\n' > "$root/agent/refs/abc123.json"
  got=$(PYTHONDONTWRITEBYTECODE=1 python3 - "$HERE" "$root" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import ref
ctx=Ctx(sys.argv[2], os.path.join(sys.argv[2],"agent"), {})
part=ref.run("ref_expand", {"ref":"ref://abc123", "path":"#/choices/0/text", "max_chars":5}, ctx)
bad=ref.run("ref_expand", {"ref":"ref://abc123", "path":"#/missing"}, ctx)
print(part["truncated"], part["returned_chars"] == 5,
      "不是完整 JSON" in part["note"], "error" in bad)
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "bigmem：ref_expand 可走 JSON 路徑、截字並清楚標片段"
  else
    fail "bigmem：ref_expand 不對（$got）"
  fi
  rm -rf "$root"
}

test_bigmem_ref_manual() {
  local root got
  root=$(mktemp -d)
  mkdir -p "$root/agent"
  printf '[{"role":"tool","content":"{\\"small\\": true}"}]\n' > "$root/agent/prompts.json"
  got=$(PYTHONDONTWRITEBYTECODE=1 python3 - "$HERE" "$root" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import ref
ctx=Ctx(sys.argv[2], os.path.join(sys.argv[2],"agent"), {})
saved=ref.run("ref_collapse", {"message_index":0}, ctx)
listed=ref.run("ref_list", {}, ctx)
content=json.load(open(os.path.join(ctx.home,"prompts.json"),encoding="utf-8"))[0]["content"]
print(saved["ref"].startswith("ref://"), json.loads(content)["$ref"] == saved["ref"],
      listed["total"] == 1, listed["refs"][0]["source"] == "對話 0")
PYEOF2
)
  if [ "$got" = "True True True True" ]; then
    ok "bigmem：ref_collapse 與 ref_list 找得到手動收起的 JSON"
  else
    fail "bigmem：手動摺疊或清單不對（$got）"
  fi
  rm -rf "$root"
}

test_bigmem_memory_put_find() {
  local root got
  root=$(mktemp -d)
  mkdir -p "$root/memory/.aos" "$root/memory/requests"
  printf 'aos-mem exec .\n' > "$root/memory/.aos/inst"
  printf '{"request":"put.json","op":"put","agent":"測試員","args":{"text":"雨天要帶黃色雨傘","tags":["天氣","雨傘"]}}\n' \
    > "$root/memory/requests/put.json"
  "$AOS" "$root/memory" >/dev/null 2>&1
  printf '{"request":"find.json","op":"find","agent":"另一位","args":{"query":"黃色","limit":10}}\n' \
    > "$root/memory/requests/find.json"
  "$AOS" "$root/memory" >/dev/null 2>&1
  got=$(python3 - "$root/memory" <<'PYEOF2'
import json, os, sqlite3, sys
h=sys.argv[1]
p=json.load(open(os.path.join(h,"results","put.json"),encoding="utf-8"))
f=json.load(open(os.path.join(h,"results","find.json"),encoding="utf-8"))
n=sqlite3.connect(os.path.join(h,"store.sqlite")).execute("select count(*) from memories").fetchone()[0]
print(p["ok"], bool(p["data"]["id"]), f["ok"], f["data"][0]["preview"] == "雨天要帶黃色雨傘", n == 1,
      os.path.isfile(os.path.join(h,"requests","done","put.json")))
PYEOF2
)
  if [ "$got" = "True True True True True True" ]; then
    ok "bigmem：aos-exec 推兩格後 SQLite 完成 put 再 find"
  else
    fail "bigmem：記憶世界 put→find 不對（$got）"
  fi
  rm -rf "$root"
}

test_bigmem_archive() {
  local root got
  root=$(mktemp -d)
  mkdir -p "$root/memory/.aos" "$root/agent"
  printf 'aos-mem exec .\n' > "$root/memory/.aos/inst"
  printf '[{"role":"user","content":"第一句"},{"role":"assistant","content":"第二句"},{"role":"user","content":"保留"}]\n' \
    > "$root/agent/prompts.json"
  printf '{"mem_dir":"../memory"}\n' > "$root/agent/llm.json"
  PYTHONDONTWRITEBYTECODE=1 python3 - "$HERE" "$root/agent" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, write_json
from packs import bigmem
world=sys.argv[2]; state={}; ctx=Ctx(world, world, state, pack="bigmem")
answer=bigmem.run("mem_archive_history", {"from":0,"to":1}, ctx)
assert answer.get("queued") and answer.get("messages") == 2
write_json(os.path.join(world,"state.json"), state)
PYEOF2
  "$AOS" "$root/memory" >/dev/null 2>&1
  PYTHONDONTWRITEBYTECODE=1 python3 - "$HERE" "$root/agent" <<'PYEOF2'
import os, sys
sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx
from packs import bigmem
world=sys.argv[2]; state=Ctx.read_json(os.path.join(world,"state.json"),{})
Ctx(world, world, state, [("bigmem",bigmem)], "bigmem").collect_results()
PYEOF2
  got=$(python3 - "$root" <<'PYEOF2'
import glob, json, os, sqlite3, sys
r=sys.argv[1]; h=os.path.join(r,"agent")
p=json.load(open(os.path.join(h,"prompts.json"),encoding="utf-8"))
side=glob.glob(os.path.join(h,"side","mem","*.json"))
kind=sqlite3.connect(os.path.join(r,"memory","store.sqlite")).execute("select kind from memories").fetchone()[0]
print(len(p) == 2, p[0]["content"].startswith("已歸檔 id="), p[1]["content"] == "保留",
      bool(side), kind == "history")
PYEOF2
)
  if [ "$got" = "True True True True True" ]; then
    ok "bigmem：歷史先入庫，共用層收回後才縮成一句"
  else
    fail "bigmem：歷史歸檔不對（$got）"
  fi
  rm -rf "$root"
}

test_bigmem_ref_auto
test_bigmem_ref_expand
test_bigmem_ref_manual
test_bigmem_memory_put_find
test_bigmem_archive
