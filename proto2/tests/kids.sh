test_kids_pack() {
  local root world home checks
  root=$(make_world kids_pack)
  world="$root/agent"
  home="$world/agent"
  checks="$root/kids-checks.json"

  python3 - "$HERE" "$world" "$checks" <<'PYEOF2'
import glob
import json
import os
import sys

sys.path.insert(0, sys.argv[1])
from aos_agent import Ctx, resolve_home
from packs import kids

world, output = sys.argv[2:4]
home = resolve_home(world, None)
ctx = Ctx(world, home)
checks = {}

first = kids.run("spawn", {
    "name": "one", "persona": "第一個小孩", "packs": ["mailbox", "kids"],
    "clock": "shared", "task": "先算 17*23", "template": "not-there",
}, ctx)
one = first.get("path")
tools = ctx.read_json(os.path.join(one, "tools.json"), {})
task_mail = glob.glob(os.path.join(one, "inbox", "parent", "*.json"))
checks["spawn"] = (first.get("ok") is True and first.get("clock") == "shared"
                   and tools.get("packs") == ["mailbox", "kids"] and len(task_mail) == 1
                   and ctx.read_json(task_mail[0], {}).get("content") == "先算 17*23")

one_ctx = Ctx(one, one)
second = kids.run("spawn", {"name": "two", "persona": "第二層"}, one_ctx)
two = second.get("path")
two_ctx = Ctx(two, two)
third = kids.run("spawn", {"name": "three", "persona": "第三層"}, two_ctx)
checks["depth"] = (second.get("ok") is True and third.get("ok") is False
                   and "第 2 層" in third.get("message", "")
                   and not os.path.exists(os.path.join(two, "kids", "three")))

state = ctx.read_json(os.path.join(one, "state.json"), {})
state.update({"state": "wait", "busy": 4, "step": 9})
ctx.write_json(os.path.join(one, "state.json"), state)
os.makedirs(os.path.join(one, "outbox"), exist_ok=True)
ctx.write_json(os.path.join(one, "outbox", "0009.json"),
               {"role": "assistant", "content": "最後一句回報"})
listed = {row["name"]: row for row in kids.run("kids_list", {}, ctx)}
row = listed.get("one", {})
checks["list"] = (set(row) == {"name", "clock", "state", "busy", "step", "unread", "last", "paused"}
                  and row.get("clock") == "shared" and row.get("state") == "wait"
                  and row.get("busy") == 4 and row.get("step") == 9
                  and row.get("unread") == 1 and row.get("last") == "最後一句回報"
                  and row.get("paused") is False)

paused = kids.run("kids_pause", {"name": "one"}, ctx)
pause_list = {row["name"]: row for row in kids.run("kids_list", {}, ctx)}
pause_inst = open(os.path.join(world, ".aos", "inst"), encoding="utf-8").read()
resumed = kids.run("kids_resume", {"name": "one"}, ctx)
resume_list = {row["name"]: row for row in kids.run("kids_list", {}, ctx)}
resume_inst = open(os.path.join(world, ".aos", "inst"), encoding="utf-8").read()
checks["shared_clock"] = (paused.get("ok") and pause_list["one"]["paused"] is True
                          and "# aos-exec agent/kids/one" in pause_inst
                          and resumed.get("ok") and resume_list["one"]["paused"] is False
                          and "\naos-exec agent/kids/one\n" in "\n" + resume_inst)

own = kids.run("spawn", {"name": "solo", "persona": "自己走", "clock": "own"}, ctx)
clock_calls = []
ctx.pause_clock = lambda path: (clock_calls.append(("pause", path)) or (True, "own 暫停了"))
ctx.continue_clock = lambda path: (clock_calls.append(("continue", path)) or (True, "own 續跑了"))
own_pause = kids.run("kids_pause", {"name": "solo"}, ctx)
own_paused = {row["name"]: row for row in kids.run("kids_list", {}, ctx)}["solo"]["paused"]
own_resume = kids.run("kids_resume", {"name": "solo"}, ctx)
own_running = {row["name"]: row for row in kids.run("kids_list", {}, ctx)}["solo"]["paused"]
checks["own_clock"] = (own.get("ok") and own_pause.get("ok") and own_paused is True
                       and own_resume.get("ok") and own_running is False
                       and [call[0] for call in clock_calls] == ["pause", "continue"])

keep = kids.run("spawn", {"name": "keep", "persona": "留檔"}, ctx)
kept = kids.run("kids_kill", {"name": "keep"}, ctx)
registry = ctx.kids()
checks["kill_keep"] = (kept.get("ok") and kept.get("kept") is True
                       and os.path.isdir(keep["path"])
                       and registry["keep"].get("alive") is False)

drop = kids.run("spawn", {"name": "drop", "persona": "刪檔"}, ctx)
dropped = kids.run("kids_kill", {"name": "drop", "keep_files": False}, ctx)
checks["kill_drop"] = (dropped.get("ok") and dropped.get("kept") is False
                       and not os.path.exists(drop["path"])
                       and ctx.kids()["drop"].get("alive") is False)

told = kids.run("kids_tell", {"name": "one", "text": "再查一次"}, ctx)
told_mail = ctx.read_json(told.get("path"), {}) if told.get("path") else {}
checks["tell"] = (told.get("ok") and told_mail.get("content") == "再查一次"
                  and os.path.basename(os.path.dirname(told["path"])) == "parent")

kids.on_reply(one_ctx, {"role": "assistant", "content": "算好是 391"})
forwarded = glob.glob(os.path.join(home, "inbox", "kid-one", "*.json"))
forward_mail = ctx.read_json(forwarded[-1], {}) if forwarded else {}
checks["forward"] = (len(forwarded) == 1 and forward_mail.get("content") == "算好是 391"
                     and forward_mail.get("from") == "one"
                     and "直接正常回答" in kids.on_system_prompt(one_ctx)
                     and kids.on_system_prompt(ctx) == "")

top_registry = ctx.kids()
child_registry = one_ctx.kids()
needed = {"name", "clock", "created", "depth", "parent", "alive", "task"}
checks["registry"] = (needed <= set(top_registry["one"])
                      and top_registry["one"]["depth"] == 1
                      and top_registry["one"]["parent"] == world
                      and top_registry["one"]["task"] == "先算 17*23"
                      and child_registry["two"]["depth"] == 2
                      and child_registry["two"]["alive"] is True)

with open(output, "w", encoding="utf-8") as f:
    json.dump(checks, f, ensure_ascii=False)
PYEOF2

  kids_assert "$checks" spawn "kids：spawn 接 packs／task／template"
  kids_assert "$checks" depth "kids：第三層會被拒絕"
  kids_assert "$checks" list "kids：list 欄位、未讀與最後回話正確"
  kids_assert "$checks" shared_clock "kids：shared 小孩可暫停再續跑"
  kids_assert "$checks" own_clock "kids：own 小孩走 daemon 暫停與續跑接點"
  kids_assert "$checks" kill_keep "kids：kill 預設留檔"
  kids_assert "$checks" kill_drop "kids：kill 可明講刪檔"
  kids_assert "$checks" tell "kids：tell 寄進小孩的 parent 信箱"
  kids_assert "$checks" forward "kids：小孩回話自動轉寄給父"
  kids_assert "$checks" registry "kids：kids.json 名冊欄位與深度正確"
  rm -rf "$root"
}

kids_assert() {
  local file=$1 key=$2 label=$3 got
  got=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get(sys.argv[2]) is True)' "$file" "$key")
  if [ "$got" = "True" ]; then ok "$label"; else fail "$label"; fi
}

test_kids_pack
