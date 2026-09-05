#!/bin/sh
# play-team：指揮一隊。一個主 agent（lead）派兩個子 agent，各住自己的資料夾、
# 各自由 daemon 起 `aos run <子> --register`（子自己那筆鐘在登記表上），
# 做完把結果寫回主指定的落點，主等兩邊都好了再合併寫總結。
#
# 全程用 LLM 世界的假後端 `echo:`，不打任何網路。
# 「先玩清單」第二級劇本（ideas 13）。撞到的東西記在
# proto/examples/team/FINDINGS-team.md。
#
# 跑法：proto/play-team.sh
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
AOS_PY="$HERE/aos.py"
BIN="$HERE/bin"
TEAM="$HERE/examples/team"
LEAD="$TEAM/lead"
WA="$TEAM/workers/a"
WB="$TEAM/workers/b"
AOS="python3 $AOS_PY"

MAX_SECONDS=300          # 五分鐘上限
EVERY=3                  # 每 3 秒印一次現況
STAMP="$(date +%Y%m%d-%H%M%S)"
LOGDIR="$HERE/play-logs/team-$STAMP"

SERVE_PID=""
cleanup() {
  [ -n "$SERVE_PID" ] && kill "$SERVE_PID" 2>/dev/null || true
  $AOS daemon stop >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "############################################################"
echo "== 0. 清乾淨（三塊地的 .aos/、落點、state、報告、暫存家） =="
echo "############################################################"
# work/ 的兩個小檔會被主改掉（貼 docstring），所以留一份原版，每次跑之前還原
if [ ! -d "$LEAD/.pristine" ]; then
  mkdir -p "$LEAD/.pristine"
  cp "$LEAD/work/"*.py "$LEAD/.pristine/"
  echo "第一次跑：把 work/ 的原版存進 $LEAD/.pristine/"
fi
cp "$LEAD/.pristine/"*.py "$LEAD/work/"
rm -rf "$LEAD/.aos" "$WA/.aos" "$WB/.aos" \
       "$LEAD/out" "$LEAD/state" "$WA/state" "$WB/state" \
       "$LEAD/report.md" "$TEAM/.home"
mkdir -p "$TEAM/.home"
export AOS_HOME="$TEAM/.home"
echo "AOS_HOME=$AOS_HOME（這個劇本自己的暫存家，不碰使用者的 ~）"

echo
echo "############################################################"
echo "== 1. init 三塊地 =="
echo "############################################################"
$AOS init "$LEAD"
$AOS init "$WA"
$AOS init "$WB"

echo
echo "== 工具白名單：三塊地都只給 $BIN（那支 aos 殼）跟 /usr/bin /bin =="
for L in "$LEAD" "$WA" "$WB"; do
  cat > "$L/.aos/config.json" <<JSON
{
  "format_version": 1,
  "path": ["$BIN", "/usr/bin", "/bin"],
  "max_parallel": 4,
  "inst_timeout_ms": 60000,
  "inbox_max": 1000
}
JSON
done

echo
echo "############################################################"
echo "== 2. 起 LLM 世界（假後端 echo:，不打網路） =="
echo "############################################################"
$AOS llm init >/dev/null
LLMWORLD="$AOS_HOME/.aos/llm"
echo "LLM 世界：$LLMWORLD"
$AOS llm serve --land "$LLMWORLD" --steps 3000 --every 200 \
  > "$AOS_HOME/llm-serve.log" 2>&1 &
SERVE_PID=$!
echo "aos llm serve 起來了（pid $SERVE_PID，紀錄在 $AOS_HOME/llm-serve.log）"
echo "  註：LLM 世界那支不在登記表上，也不是 daemon 起的（見 FINDINGS-team F-3）"

echo
echo "############################################################"
echo "== 3. 起 daemon =="
echo "############################################################"
$AOS daemon start --every 200

echo
echo "############################################################"
echo "== 4. 起 lead（只登記鐘，讓 daemon 去起它那支 aos run） =="
echo "############################################################"
$AOS daemon add "$LEAD" --every 300
echo "子地不用先登記：主的兩個 call（mode:async）步會替它們登，daemon 再去起。"

echo
echo "############################################################"
echo "== 5. 每 $EVERY 秒看一次現況（最多 $MAX_SECONDS 秒） =="
echo "############################################################"
T0=$(date +%s)
ROUND=0
WHY_STOP="lead 收工"
while :; do
  NOW=$(date +%s)
  ELAPSED=$((NOW - T0))
  ROUND=$((ROUND + 1))
  echo
  echo "---------- 第 $ROUND 次巡（第 ${ELAPSED} 秒） ----------"
  $AOS daemon ls || true
  for L in "$LEAD" "$WA" "$WB"; do
    $AOS status "$L" || true
  done

  if [ -f "$LEAD/state/done.json" ]; then
    WHY_STOP="lead 寫出 state/done.json（總結做完了）"
    break
  fi
  if [ -f "$LEAD/.aos/stopped.json" ]; then
    WHY_STOP="lead 那支 run 停了（.aos/stopped.json 出現）"
    break
  fi
  if [ "$ELAPSED" -ge "$MAX_SECONDS" ]; then
    WHY_STOP="到了 $MAX_SECONDS 秒上限，lead 還沒收工"
    break
  fi
  sleep "$EVERY"
done

echo
echo "############################################################"
echo "== 6. 最後一次現況 =="
echo "############################################################"
$AOS daemon ls || true
for L in "$LEAD" "$WA" "$WB"; do
  $AOS status "$L" || true
done

echo
echo "############################################################"
echo "== 7. 收尾：一次全停（aos daemon stop） =="
echo "############################################################"
$AOS daemon stop || true
echo "-- 全停之後的登記表 --"
$AOS daemon ls || true
if kill -0 "$SERVE_PID" 2>/dev/null; then
  echo "！LLM 世界那支 aos llm serve（pid $SERVE_PID）還活著——daemon stop 停不到它。"
  kill "$SERVE_PID" 2>/dev/null || true
  SERVE_PID=""
  echo "  （這支腳本自己把它殺掉了。見 FINDINGS-team F-3）"
else
  echo "LLM 世界那支已經不在了。"
fi

echo
echo "############################################################"
echo "== 8. 這一趟長什麼樣 =="
echo "############################################################"
LEAD="$LEAD" WA="$WA" WB="$WB" WHY_STOP="$WHY_STOP" ELAPSED="$ELAPSED" \
AOS_HOME="$AOS_HOME" python3 - <<'PY'
import json, os

def j(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default

LEAD = os.environ["LEAD"]; WA = os.environ["WA"]; WB = os.environ["WB"]
HOME = os.environ["AOS_HOME"]

def land_line(tag, root):
    baton = j(os.path.join(root, ".aos", "series.json"), {}) or {}
    stopped = j(os.path.join(root, ".aos", "stopped.json"))
    done = j(os.path.join(root, "state", "done.json"))
    srs = baton.get("series") or []
    cursors = "、".join("%s(%s)" % (s.get("cursor"), s.get("status")) for s in srs) or "（沒有串）"
    rounds = (done or {}).get("rounds")
    print("  %-6s 格數 %-4s 圈數 %-4s 游標 %-22s 停止原因 %s"
          % (tag, baton.get("tick", "-"), rounds if rounds is not None else "-",
             cursors, (stopped or {}).get("reason", "（沒有停止原因檔）")))
    if stopped and stopped.get("message"):
        print("         └ %s" % stopped["message"][:160])
    return baton, stopped, done

print("為什麼停：%s（跑了 %s 秒）" % (os.environ["WHY_STOP"], os.environ["ELAPSED"]))
print()
print("三塊地：")
lead_b, lead_s, lead_d = land_line("主 lead", LEAD)
a_b, a_s, a_d = land_line("子 A", WA)
b_b, b_s, b_d = land_line("子 B", WB)

print()
print("圈數：主 %s 圈（一次 LLM 總結）、子 A %s 圈、子 B %s 圈"
      % ((lead_d or {}).get("rounds", "0（沒收工）"),
         (a_d or {}).get("rounds", "?"), (b_d or {}).get("rounds", "?")))

first = (lead_d or {}).get("first_back")
print("誰先好：%s" % ("子 %s" % first if first else "（主沒走到總結那步，看不出來）"))
for who, path in (("A", os.path.join(LEAD, "out", "a.done.json")),
                  ("B", os.path.join(LEAD, "out", "b.done.json"))):
    st = path + ".status.json"
    if os.path.exists(st):
        print("  子 %s 的落點：壞了（%s）" % (who, (j(st) or {}).get("reason")))
    elif os.path.exists(path):
        print("  子 %s 的落點：好了，%.3f（mtime）" % (who, os.path.getmtime(path)))
    else:
        print("  子 %s 的落點：還是空的（還沒好）" % who)

print()
stuck = []
for tag, baton, stopped in (("主 lead", lead_b, lead_s), ("子 A", a_b, a_s), ("子 B", b_b, b_s)):
    for s in (baton.get("series") or []):
        if s.get("status") == "failed":
            stuck.append("%s 的串停在 `%s`（%s）" % (tag, s.get("cursor"),
                         (s.get("fail_reason") or {}).get("reason")))
        elif s.get("status") == "running":
            stuck.append("%s 的串還停在 `%s`（沒走完）" % (tag, s.get("cursor")))
print("有沒有人卡住：%s" % ("沒有，三塊地的串都走完了" if not stuck else "有——" + "；".join(stuck)))

reg = j(os.path.join(HOME, ".aos", "registry.json"), {}) or {}
print()
print("登記表（全停之後）：daemon_pid=%s" % reg.get("daemon_pid"))
for e in reg.get("entries", []):
    print("  %-8s pid %-6s 鐘 %-30s %s"
          % (e.get("state"), e.get("pid"), json.dumps(e.get("clock"), ensure_ascii=False),
             e.get("path")))
print("  （LLM 世界 %s 不在這張表上）" % os.path.join(HOME, ".aos", "llm"))

print()
rep = os.path.join(LEAD, "report.md")
if os.path.exists(rep):
    print("== 主寫的 report.md ==")
    with open(rep, "r", encoding="utf-8") as f:
        print(f.read().rstrip())
else:
    print("（沒有 report.md——主沒走到總結那步）")

print()
print("== work/ 現在長什麼樣（前三行） ==")
for name in ("a.py", "b.py"):
    p = os.path.join(LEAD, "work", name)
    print("-- %s --" % name)
    try:
        with open(p, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 3:
                    break
                print("   " + line.rstrip())
    except OSError as e:
        print("   讀不到：%s" % e)
PY

echo
echo "############################################################"
echo "== 9. 把接力棒與狀態檔收進 $LOGDIR =="
echo "############################################################"
mkdir -p "$LOGDIR"
for pair in "lead:$LEAD" "worker-a:$WA" "worker-b:$WB"; do
  tag="${pair%%:*}"
  root="${pair#*:}"
  mkdir -p "$LOGDIR/$tag"
  for f in series.json stopped.json daemon-run.log; do
    [ -f "$root/.aos/$f" ] && cp "$root/.aos/$f" "$LOGDIR/$tag/" || true
  done
  [ -d "$root/state" ] && cp -r "$root/state" "$LOGDIR/$tag/state" || true
  [ -d "$root/.aos/calls" ] && cp -r "$root/.aos/calls" "$LOGDIR/$tag/calls" || true
done
mkdir -p "$LOGDIR/home"
for f in registry.json config.json ledger.jsonl daemon.log; do
  [ -f "$AOS_HOME/.aos/$f" ] && cp "$AOS_HOME/.aos/$f" "$LOGDIR/home/" || true
done
[ -f "$AOS_HOME/llm-serve.log" ] && cp "$AOS_HOME/llm-serve.log" "$LOGDIR/home/" || true
[ -d "$LEAD/out" ] && cp -r "$LEAD/out" "$LOGDIR/lead-out" || true
[ -f "$LEAD/report.md" ] && cp "$LEAD/report.md" "$LOGDIR/" || true
echo "收好了：$LOGDIR"
find "$LOGDIR" -type f | sed "s|$LOGDIR/|  |" | sort
