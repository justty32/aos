#!/usr/bin/env bash
# proto2 煙霧測試：跑 aos-exec 的幾件事。有一項 FAIL 就退出 1。
HERE=$(cd "$(dirname "$0")" && pwd)
AOS="$HERE/aos-exec"
LOOP="$HERE/aos-loop"
AGENT="$HERE/aos-agent"
AUSER="$HERE/aos-user"
LLM="$HERE/aos-llm"
DKERNEL="$HERE/aos-daemon-kernel"
DAEMON="$HERE/aos-daemon"
unset AOS_DAEMON_DIR   # 別讓外面的環境把測試的請求丟進使用者真的 daemon 目錄
unset AOS_LLM_DIR      # 同理：aos-llm 沒給 --dir 時不該撿到使用者真的 LLM 資料夾
TEST_RUN_DIR=$(mktemp -d)
export TMPDIR="$TEST_RUN_DIR"   # 這輪所有暫存與 worker 都關在自己的資料夾裡
export PYTHONDONTWRITEBYTECODE=1  # 測試載入工具包時，不在 repo 留 __pycache__
PASSED=0
FAILED=0

# tests/*.sh 共用的 helper：
#   ok／fail：記一條通過或失敗。
#   start_fake_server：開假 OpenAI server；user 訊息寫 `CALL 工具 {json}` 可腳本化 tool_call。
#   make_world <名字>：從 git index 組一份 examples/agent＋examples/llm 複本，印出根路徑。
#   llm_tick／llm_pump：推 LLM 一格／推到收乾淨。
#   agent_tick：推 agent 一格。
#   say_and_wait：say 後交錯推 agent 與 LLM，等新的 outbox 或超時。
#   kill_workers：只收指定 LLM 複本的 worker。
ok() { PASSED=$((PASSED + 1)); echo "ok   $1"; }
fail() { FAILED=$((FAILED + 1)); echo "FAIL $1"; }

check() {  # check <名字> <期待退出碼> <實際退出碼>
  if [ "$2" = "$3" ]; then ok "$1"; else fail "$1（期待退出碼 $2，實際 $3）"; fi
}

# 記住開工時已經存在的進程。它們是別人的，不報錯，也絕不動。
strays() { pgrep -f 'aos-llm|aos-loop|aos-daemon-kernel|aos-agent' 2>/dev/null || true; }
BEFORE=$(strays)
if [ -z "$BEFORE" ]; then
  ok "開跑前沒有別的 aos 背景進程"
else
  ok "開跑前已有 aos 背景進程，已記下、不會動它們"
fi

# 1. 檔案能執行
OUT=$("$AOS" "$HERE/examples/hello.sh"); RC=$?
check "檔案能執行" 0 "$RC"
case "$OUT" in
  *"hello from hello.sh"*) ok "檔案的輸出有出來" ;;
  *) fail "檔案的輸出不對：$OUT" ;;
esac

# 2. 資料夾能跑 .aos/inst，多行命令都跑到，工作目錄是那個資料夾
OUT=$("$AOS" "$HERE/examples/folder"); RC=$?
check "資料夾能跑 .aos/inst" 0 "$RC"
case "$OUT" in
  *"第一句"*) ok "第一句有跑到" ;;
  *) fail "第一句沒跑到：$OUT" ;;
esac
case "$OUT" in
  *"第二句"*) ok "第二句有跑到" ;;
  *) fail "第二句沒跑到：$OUT" ;;
esac
case "$OUT" in
  *"$HERE/examples/folder"*) ok "工作目錄是那個資料夾" ;;
  *) fail "工作目錄不對：$OUT" ;;
esac

# 3. .aos/inst 裡 exit 3 就回 3
TMP=$(mktemp -d)
mkdir -p "$TMP/.aos"
echo "exit 3" > "$TMP/.aos/inst"
"$AOS" "$TMP" >/dev/null 2>&1; RC=$?
check ".aos/inst 裡 exit 3 回 3" 3 "$RC"
rm -rf "$TMP"

# 4. 路徑不存在回 2
"$AOS" "$HERE/沒有這個東西" 2>/dev/null; RC=$?
check "路徑不存在回 2" 2 "$RC"

# 5. 資料夾沒 .aos/inst 回 2
TMP=$(mktemp -d)
"$AOS" "$TMP" 2>/dev/null; RC=$?
check "資料夾沒 .aos/inst 回 2" 2 "$RC"
rmdir "$TMP"

# 6. aos-loop：自寫下一步的鏈跑兩步後因空停（範例複製到暫存資料夾跑，別弄髒範例）
TMP=$(mktemp -d)
cp -r "$HERE/examples/loop" "$TMP/loop"
OUT=$("$LOOP" "$TMP/loop" --stop-when-empty --interval 0 2>&1); RC=$?
check "aos-loop 自寫鏈跑完因空停回 0" 0 "$RC"
case "$OUT" in
  *"第一步"*"第二步"*) ok "兩步都跑到" ;;
  *) fail "兩步沒跑全：$OUT" ;;
esac
case "$OUT" in
  *"step 3 empty"*) ok "第三圈偵測到空才停" ;;
  *) fail "沒看到第三圈空的訊息：$OUT" ;;
esac
INST_LEFT=$(cat "$TMP/loop/.aos/inst")
if [ -z "$INST_LEFT" ]; then ok "跑完 .aos/inst 是空的"; else fail "跑完 .aos/inst 還有東西：$INST_LEFT"; fi
rm -rf "$TMP"

# 7. --steps 3 --interval 0，沒給 --stop-when-empty，空的也照跑滿三步
TMP=$(mktemp -d)
OUT=$("$LOOP" "$TMP" --steps 3 --interval 0 2>&1); RC=$?
check "沒 --stop-when-empty 時空的也跑滿 steps" 0 "$RC"
N=$(echo "$OUT" | grep -c "empty")
if [ "$N" = "3" ]; then ok "三步都印了 empty"; else fail "empty 次數不對（$N）：$OUT"; fi
rm -rf "$TMP"

# 8. 命令失敗（exit 5）不中斷迴圈，還是跑到給定步數（第一步失敗，後兩步空的也照跑）
TMP=$(mktemp -d)
mkdir -p "$TMP/.aos"
echo "exit 5" > "$TMP/.aos/inst"
OUT=$("$LOOP" "$TMP" --steps 3 --interval 0 2>&1); RC=$?
check "命令失敗不中斷迴圈，跑滿 steps" 0 "$RC"
case "$OUT" in
  *"step 1 exit 5"*) ok "失敗那步有印退出碼 5" ;;
  *) fail "沒看到失敗退出碼：$OUT" ;;
esac
case "$OUT" in
  *"step 2 empty"*"step 3 empty"*) ok "失敗之後迴圈還是繼續跑到第三步" ;;
  *) fail "迴圈在失敗後沒繼續跑：$OUT" ;;
esac
rm -rf "$TMP"

# 9. 不存在的資料夾回 2
"$LOOP" "$HERE/沒有這個資料夾" 2>/dev/null; RC=$?
check "aos-loop 資料夾不存在回 2" 2 "$RC"

# 10. 範例資料夾複本開箱即用：附帶的 .aos/inst（`aos-agent exec . --home agent`）不用額外設定
#     就能被 aos-loop --keep-inst 叫到；aos-loop 執行前會把自己所在目錄加進 PATH，複本放到
#     任意 mktemp -d 都找得到 aos-agent。先 say 一句話，第一格 idle 收信、第二格 llm 把請求
#     丟進 LLM 資料夾就換 wait——沒人在跑那個 LLM 資料夾也沒關係，只看 step 有沒有從 0 變 2、
#     請求檔有沒有真的落地。只複製範例的靜態檔，不碰執行時檔案。
TMP=$(mktemp -d)
TMPLLM=$(mktemp -d)
mkdir -p "$TMP/agent" "$TMP/.aos"
for f in system-prompt.json prompts.json tools.json; do
  cp "$HERE/examples/agent/agent/$f" "$TMP/agent/$f"
done
cp "$HERE/examples/agent/.aos/inst" "$TMP/.aos/inst"
printf '{"dir": "%s"}\n' "$TMPLLM" > "$TMP/agent/llm.json"
"$AUSER" say "$TMP" "哈囉" >/dev/null 2>&1
"$LOOP" "$TMP" --keep-inst --steps 2 --interval 0 >/dev/null 2>&1
STEP_NOW=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["step"])' "$TMP/agent/state.json")
if [ "$STEP_NOW" = "2" ]; then
  ok "範例資料夾複本開箱即用，aos-loop 靠附帶的 .aos/inst 跑了兩格"
else
  fail "範例複本沒跑到兩格：step=$STEP_NOW"
fi
if [ -n "$(find "$TMPLLM/requests" -maxdepth 1 -name '*.json' 2>/dev/null)" ]; then
  ok "第二格真的把請求丟進 llm.json 指的那個 LLM 資料夾"
else
  fail "請求沒落地"
fi
rm -rf "$TMP" "$TMPLLM"

# 11. 資料夾沒有 .aos/inst：aos-loop 要把這件事講清楚到 stderr
TMP=$(mktemp -d)
OUT=$("$LOOP" "$TMP" --steps 1 --interval 0 2>&1 >/dev/null)
case "$OUT" in
  *"沒有 .aos/inst"*) ok "aos-loop 沒 .aos/inst 時有講清楚" ;;
  *) fail "沒看到沒有 .aos/inst 的提示：$OUT" ;;
esac
rm -rf "$TMP"

# ── LLM 資料夾與 aos-agent ─────────────────────────────────────────────────
# 假的 OpenAI 伺服器：看到 messages 裡還沒有 tool 結果就回一個 tool_calls（say hi），
# 已經有 tool 結果就回純文字 done。這樣同一台可以服務好幾條鏈。故意在每則回覆夾帶
# reasoning_content（私有欄位）、done 那則再夾帶空的 tool_calls: []，測 aos-agent
# 存進 prompts.json 時會不會把這些濾掉。每則回覆都附一個固定的 usage（7/3/10，外加巢狀的
# completion_tokens_details.reasoning_tokens=5 跟頂層 prompt_cache_hit_tokens=4），
# 讓用量那些測試好算——帳本要把這些數字全部累加起來。body 裡有 "echo": true 就改回一句話，把收到的 model／
# temperature／Authorization 原樣講回去，這樣測得到引擎選擇、參數覆蓋、api_key_env。
# body 裡有 "sleep": N 就先睡 N 秒再回，這樣「同時最多跑幾個」看得出來；因此用
# ThreadingHTTPServer，慢的那發才不會把其他人一起卡住。
start_fake_server() {
if [ -n "${FAKE_PID:-}" ] && kill -0 "$FAKE_PID" 2>/dev/null; then
  return 0
fi
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
FAKE=$(mktemp -d)
cat > "$FAKE/fake-llm.py" <<'PYEOF2'
import http.server, json, re, sys, time

SEEN = {}

class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            data = {}
        msgs = data.get("messages") or []
        try:
            nap = float(data.get("sleep") or 0)
        except (TypeError, ValueError):
            nap = 0
        if nap > 0:
            time.sleep(nap)
        users = [m for m in msgs if m.get("role") == "user"]
        last_user = (users[-1].get("content") or "") if users else ""
        tools = [m for m in msgs if m.get("role") == "tool"]
        if "HTTP500" in last_user:
            body = "假伺服器故意回 500".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # 劇本：user 訊息裡寫 `CALL <工具> {參數}` 就照順序一次呼叫一個，
        # 呼叫完了再回一句「看完了：<最後一個工具結果>」。沒寫劇本就走老樣子。
        triggers = []
        for m in users:
            for line in (m.get("content") or "").splitlines():
                for hit in re.finditer(r"CALL\s+(\w+)\s*(\{[^}]*\})?", line):
                    triggers.append((hit.group(1), hit.group(2) or "{}"))
        if "EMPTY" in last_user:
            message = {"role": "assistant", "content": "", "tool_calls": []}
        elif "BROKEN" in last_user and not tools:
            # 模型把工具呼叫寫成文字（qwen 風格）：agent 要救回來當正式 tool_call
            message = {"role": "assistant", "tool_calls": [],
                       "content": '<tool_call>\n{"name": "say", "arguments": {"text": "救回來的"}}\n</tool_call>'}
        elif "PLAINTEXT" in last_user and not tools:
            # 另一種壞法：把工具名跟參數寫成 plaintext 區塊
            message = {"role": "assistant", "tool_calls": [],
                       "content": '### 行動計劃\n\n```plaintext\nsay:\n{\n  "text": "純文字救回"\n}\n```\n執行這一步。'}
        elif "GARBLED" in last_user:
            # 第一次回救不回來的壞文字，agent 同題重送後第二次才正常
            SEEN[last_user] = SEEN.get(last_user, 0) + 1
            if SEEN[last_user] == 1:
                message = {"role": "assistant", "tool_calls": [],
                           "content": '<tool_call>{"name": "say", "argu'}
            else:
                message = {"role": "assistant", "tool_calls": [], "content": "重送後正常"}
        elif data.get("echo"):
            message = {"role": "assistant", "reasoning_content": "blah",
                       "content": "model=%s temperature=%s auth=%s" % (
                           data.get("model"), data.get("temperature"),
                           self.headers.get("Authorization") or "-")}
        elif "THINK" in last_user:
            message = {"role": "assistant", "reasoning_content": "blah",
                       "content": "<think>偷偷想一下</think>\n真正的回答"}
        elif triggers and len(tools) < len(triggers):
            name, rest = triggers[len(tools)]
            message = {"role": "assistant", "content": None, "reasoning_content": "blah",
                       "tool_calls": [{"id": "call_%d" % (len(tools) + 1), "type": "function",
                                       "function": {"name": name, "arguments": rest}}]}
        elif triggers:
            message = {"role": "assistant", "reasoning_content": "blah", "tool_calls": [],
                       "content": "看完了：" + (tools[-1].get("content") or "")[:800]}
        elif tools:
            message = {"role": "assistant", "content": "done", "tool_calls": [],
                       "reasoning_content": "blah"}
        else:
            message = {"role": "assistant", "content": None, "reasoning_content": "blah",
                       "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "say", "arguments": "{\"text\": \"hi\"}"}}]}
        body = json.dumps({"choices": [{"index": 0, "message": message,
                                        "finish_reason": "stop"}],
                           "usage": {"prompt_tokens": 7, "completion_tokens": 3,
                                     "total_tokens": 10,
                                     "completion_tokens_details": {"reasoning_tokens": 5},
                                     "prompt_cache_hit_tokens": 4}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
PYEOF2
python3 "$FAKE/fake-llm.py" "$PORT" &
FAKE_PID=$!
LIVE_AOSD=""   # 有背景 kernel 在跑的時候記著它的 daemon 目錄，離場一定收掉
cleanup() {
  [ -z "${FAKE_PID:-}" ] || kill "$FAKE_PID" 2>/dev/null
  pkill -f "aos-llm worker $TEST_RUN_DIR/" 2>/dev/null
  if [ -n "$LIVE_AOSD" ]; then
    "$DKERNEL" stop "$LIVE_AOSD" >/dev/null 2>&1
    kill_clocks "$LIVE_AOSD"
  fi
}
trap cleanup EXIT
python3 - "$PORT" <<'PYEOF2' || { fail "假 LLM 伺服器起不來"; exit 1; }
import socket, sys, time
for _ in range(60):
    try:
        socket.create_connection(("127.0.0.1", int(sys.argv[1])), 0.2).close()
        sys.exit(0)
    except OSError:
        time.sleep(0.05)
sys.exit(1)
PYEOF2
ok "假 LLM 伺服器起來了"
}

start_fake_server

# 組兩份範例的乾淨複本（agent 一份、LLM 一份，擺成兄弟目錄，agent 的 llm.json
# 就是範例裡那個 {"dir": "../llm"}），LLM 那份的 engine 指到假伺服器。故意不直接
# cp -r 真的範例資料夾：README「怎麼玩」教使用者拿 aos-loop --keep-inst 長期盯著
# 真的範例跑，這樣 hello.json／state.json／prompts.json 會被真的用起來、內容一直在動；
# 這裡只複製幾個靜態設定，不讀也不碰執行時檔案。
prep_agent() {  # prep_agent <目標世界資料夾>；本體在 <世界>/agent/（--home agent），llm.json 指旁邊的 ../llm
  mkdir -p "$1/agent" "$1/.aos"
  for f in system-prompt.json prompts.json tools.json llm.json; do
    cp "$HERE/examples/agent/agent/$f" "$1/agent/$f"
  done
  cp "$HERE/examples/agent/.aos/inst" "$1/.aos/inst"
  cp "$HERE/examples/agent/notes.txt" "$1/notes.txt"
}
prep_flat() {  # prep_flat <目標世界資料夾>；home 用預設的 `.`，東西全攤在世界資料夾底下
  mkdir -p "$1/.aos"
  for f in system-prompt.json prompts.json tools.json llm.json; do
    cp "$HERE/examples/agent-flat/$f" "$1/$f"
  done
  cp "$HERE/examples/agent-flat/.aos/inst" "$1/.aos/inst"
}
prep_llm() {  # prep_llm <目標 LLM 資料夾>；引擎全指到假伺服器（範例本體不碰）
  mkdir -p "$1/requests" "$1/.aos"
  cp "$HERE/examples/llm/engines.json" "$1/engines.json"
  cp "$HERE/examples/llm/defaults.json" "$1/defaults.json"
  cp "$HERE/examples/llm/.aos/inst" "$1/.aos/inst"
  python3 - "$1/engines.json" "$PORT" <<'PYEOF2'
import json, sys
p = sys.argv[1]
engines = json.load(open(p, encoding="utf-8"))
for e in engines:
    e["base_url"] = "http://127.0.0.1:%s/v1" % sys.argv[2]
    e.pop("api_key_env", None)
json.dump(engines, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
}
mk_engines() {  # mk_engines <LLM 資料夾> <json 字串>；直接放一份自己寫的引擎清單
  mkdir -p "$1/requests" "$1/.aos"
  cp "$HERE/examples/llm/.aos/inst" "$1/.aos/inst"
  printf '%s\n' "$2" > "$1/engines.json"
}
llm_tick() {  # llm_tick <LLM 資料夾>；推一格，把那格的 stderr 印出來
  "$LLM" exec "$1" 2>&1 >/dev/null
}
llm_pump() {  # llm_pump <LLM 資料夾> [最多幾格]；一直推到沒東西在跑也沒東西排隊，印出所有 stderr
  local n=${2:-80} i=0 all="" line=""
  while [ "$i" -lt "$n" ]; do
    line=$("$LLM" exec "$1" 2>&1 >/dev/null)
    all="$all
$line"
    case "$line" in *"launched 0 running 0 queued 0"*) break ;; esac
    sleep 0.1
    i=$((i + 1))
  done
  # 收乾淨了再補一格：worker 是先寫結果再寫用量紙條的，補這格才保證帳也記完了
  all="$all
$("$LLM" exec "$1" 2>&1 >/dev/null)"
  printf '%s\n' "$all"
}
kill_workers() {  # kill_workers <LLM 資料夾>；把那個資料夾還在跑的 worker 收掉
  pkill -f "aos-llm worker $1" >/dev/null 2>&1
  sleep 0.2
}
llm_content() {  # llm_content <結果檔>；印出 choices[0].message.content
  python3 -c '
import json,sys
print(json.load(open(sys.argv[1]))["choices"][0]["message"]["content"] or "")' "$1"
}
llm_field() {  # llm_field <json 檔> <python 取值運算式，d 是整包>
  python3 -c '
import json,sys
d = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))' "$1" "$2"
}
now_state() {  # now_state <本體資料夾>；還沒走過就是 idle
  python3 -c '
import json,os,sys
p = sys.argv[1]
print(json.load(open(p))["state"] if os.path.isfile(p) else "idle")' "$1/state.json"
}
field() {  # field <json 檔> <鍵>
  python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]))' "$1" "$2"
}
agent_pump() {  # agent_pump <世界> <LLM 資料夾> [幾格]；agent 一格、LLM 收乾淨，來回幾次
  local n=${3:-12} i=0
  while [ "$i" -lt "$n" ]; do
    "$AGENT" exec "$1" >/dev/null 2>&1
    llm_pump "$2" >/dev/null
    i=$((i + 1))
  done
}
agent_tick() {  # agent_tick <世界>；推 agent 一格
  "$AGENT" exec "$1" >/dev/null 2>&1
}
make_world() {  # make_world <名字>；回根路徑，裡面有 agent/ 世界與 llm/ 世界
  local root
  root=$(mktemp -d "$TEST_RUN_DIR/$1.XXXXXX")
  prep_agent "$root/agent"
  prep_llm "$root/llm"
  printf '%s\n' "$root"
}
say_and_wait() {  # say_and_wait <agent 世界> <LLM 資料夾> <文字> [最多幾格]；回新 outbox 路徑
  local world=$1 llm=$2 words=$3 max=${4:-30} home before i fresh
  home=$(python3 - "$HERE" "$world" <<'PYEOF2'
import sys
sys.path.insert(0, sys.argv[1])
from aos_agent import resolve_home
print(resolve_home(sys.argv[2], None))
PYEOF2
)
  before=$(find "$home/outbox" -maxdepth 1 -name '*.json' 2>/dev/null | sort)
  "$AUSER" say "$world" "$words" >/dev/null 2>&1
  i=0
  while [ "$i" -lt "$max" ]; do
    agent_tick "$world"
    llm_pump "$llm" >/dev/null
    fresh=$(comm -13 <(printf '%s\n' "$before") <(find "$home/outbox" -maxdepth 1 -name '*.json' 2>/dev/null | sort) | head -1)
    if [ -n "$fresh" ]; then
      printf '%s\n' "$fresh"
      return 0
    fi
    i=$((i + 1))
  done
  return 1
}

# 12. LLM 資料夾走一格：exec 把請求派給背景 worker，結果過幾格才回來、請求搬去 requests/done/
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"messages": [{"role": "user", "content": "哈囉"}]}' \
  > "$TMP/llm/requests/0001.json"
OUT=$("$LLM" exec "$TMP/llm" 2>&1); RC=$?
check "aos-llm exec 派一個請求回 0" 0 "$RC"
case "$OUT" in
  *"launch 0001.json engine=local priority=0 pid="*) ok "exec 印了 launch／請求／引擎／優先級／pid" ;;
  *) fail "exec 的 launch 行不對：$OUT" ;;
esac
case "$OUT" in
  *"tick 1 launched 1 running 1 queued 0"*) ok "摘要行印了 tick／launched／running／queued" ;;
  *) fail "exec 摘要行不對：$OUT" ;;
esac
if [ -f "$TMP/llm/requests/running/0001.json" ]; then
  ok "派出去的請求搬進 requests/running/"
else
  fail "requests/running/0001.json 不在"
fi
RUNAOS=$(llm_field "$TMP/llm/requests/running/0001.json" \
  '"%s %s" % (d["aos"]["engine"], d["aos"]["pid"] > 0)')
if [ "$RUNAOS" = "local True" ]; then
  ok "running 的請求多掛了 aos（engine／pid／priority／started）"
else
  fail "running 的 aos 區塊不對：$RUNAOS"
fi
OUT=$(llm_pump "$TMP/llm")
case "$OUT" in
  *"done 0001.json ok tokens=10 took="*) ok "結果回來那格印了 done／tokens／took" ;;
  *) fail "沒收回結果：$OUT" ;;
esac
if [ -f "$TMP/llm/results/0001.json" ]; then
  ok "回覆落在 results/ 同檔名"
else
  fail "results/0001.json 沒出現"
fi
REQ_TOP=$(find "$TMP/llm/requests" -maxdepth 1 -type f)
if [ -z "$REQ_TOP" ]; then ok "requests/ 頂層清空了"; else fail "requests/ 頂層還有：$REQ_TOP"; fi
RUN_LEFT=$(find "$TMP/llm/requests/running" -maxdepth 1 -type f)
if [ -z "$RUN_LEFT" ]; then ok "requests/running/ 也清空了"; else fail "running/ 還有：$RUN_LEFT"; fi
if [ -f "$TMP/llm/requests/done/0001.json" ]; then
  ok "處理完的請求搬去 requests/done/"
else
  fail "requests/done/0001.json 不在"
fi
CONTENT=$(llm_content "$TMP/llm/results/0001.json")
if [ "$CONTENT" = "" ]; then
  ok "results/ 裡是整包原始回覆（這則是 tool_calls，content 空的）"
else
  fail "results/ 內容不對：$CONTENT"
fi
AOS_BLOCK=$(llm_field "$TMP/llm/results/0001.json" \
  '"%s %s %s" % (d["aos"]["engine"], d["aos"]["model"], d["aos"]["usage"]["total_tokens"])')
if [ "$AOS_BLOCK" = "local local 10" ]; then
  ok "結果多掛了 aos 區塊（引擎／model／用量）"
else
  fail "結果的 aos 區塊不對：$AOS_BLOCK"
fi
# 結果是先寫 .tmp 再 rename 的，撿的人不會讀到半個檔——跑完不該留下任何 .tmp
TMPLEFT=$(find "$TMP/llm" -name '*.tmp')
if [ -z "$TMPLEFT" ]; then
  ok "結果是原子寫的（沒有 .tmp 殘留，讀的人不會撿到半個檔）"
else
  fail "有 .tmp 殘留：$TMPLEFT"
fi

# 13. 沒請求就什麼都不做，摘要一樣印；state.json 的 served／errors 是收回結果那格算的
OUT=$("$LLM" exec "$TMP/llm" 2>&1); RC=$?
check "aos-llm exec 沒請求也回 0" 0 "$RC"
case "$OUT" in
  *"launched 0 running 0 queued 0"*) ok "沒事做也照樣印摘要，tick 往前走" ;;
  *) fail "沒請求時印的不對：$OUT" ;;
esac
STATE=$(llm_field "$TMP/llm/state.json" '"%s %s %s" % (d["tick"] >= 3, d["served"], d["errors"])')
if [ "$STATE" = "True 1 0" ]; then
  ok "state.json 記著 tick／served／errors"
else
  fail "state.json 不對：$STATE"
fi
rm -rf "$TMP"

# 14. 壞掉的請求也要有結果，不然丟請求的人會等到天荒地老（這個當格就了結，不用開 worker）
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo 'this is not json' > "$TMP/llm/requests/0001.json"
OUT=$("$LLM" exec "$TMP/llm" 2>&1); RC=$?
check "壞請求 aos-llm exec 還是回 0" 0 "$RC"
case "$OUT" in
  *"bad-json 0001.json"*) ok "壞請求印了 bad-json" ;;
  *) fail "壞請求印的不對：$OUT" ;;
esac
ERR=$(python3 -c '
import json,sys
print(json.load(open(sys.argv[1])).get("error", ""))' "$TMP/llm/results/0001.json" 2>/dev/null)
if [ -n "$ERR" ]; then ok "壞請求的結果檔有 error：$ERR"; else fail "壞請求沒寫出 error 結果"; fi
if [ -f "$TMP/llm/requests/done/0001.json" ]; then
  ok "壞請求一樣搬去 requests/done/，不會卡住下一個"
else
  fail "壞請求沒搬走"
fi
rm -rf "$TMP"

# 15. 打不通也要回一個帶 error 的結果、請求照樣搬走（以前是留在原地，害叫的人等到天荒地老）
TMP=$(mktemp -d)
mk_engines "$TMP/llm" '[{"name": "nope", "base_url": "http://127.0.0.1:1/v1", "model": "m"}]'
echo '{"messages": [{"role": "user", "content": "哈囉"}]}' \
  > "$TMP/llm/requests/0001.json"
OUT=$(llm_pump "$TMP/llm")
case "$OUT" in
  *"done 0001.json error"*) ok "打不通那格印了 done ... error" ;;
  *) fail "打不通印的不對：$OUT" ;;
esac
ERR=$(llm_field "$TMP/llm/results/0001.json" 'd["error"]' 2>/dev/null)
case "$ERR" in
  *"打不通"*) ok "打不通的結果檔有 error：$ERR" ;;
  *) fail "打不通沒寫出 error 結果：$ERR" ;;
esac
if [ -f "$TMP/llm/requests/done/0001.json" ]; then
  ok "打不通的請求一樣搬去 done/，不會卡住後面的人"
else
  fail "打不通的請求沒搬走"
fi
ERRN=$(llm_field "$TMP/llm/usage/$(date +%Y-%m-%d).json" \
  'd["by-model"]["http://127.0.0.1:1/v1|m"]["errors"]')
if [ "$ERRN" = "1" ]; then ok "打不通也記進當天的用量（errors=1）"; else fail "用量沒記到打不通：$ERRN"; fi
ST=$(llm_field "$TMP/llm/state.json" '"%s %s" % (d["served"], d["errors"])')
if [ "$ST" = "0 1" ]; then ok "state.json 的 errors 是收回結果那格算的"; else fail "state 的 served/errors 不對：$ST"; fi
rm -rf "$TMP"

# 16. aos_llm 小幫手：write_request 丟一個請求、exec 跑完 read_result 撿得回來（拿走就沒了）
TMP=$(mktemp -d); prep_llm "$TMP/llm"
NAME=$(python3 - "$HERE" "$TMP/llm" <<'PYEOF2'
import sys
sys.path.insert(0, sys.argv[1])
import aos_llm
print(aos_llm.write_request(sys.argv[2],
                            {"messages": [{"role": "user", "content": "哈囉"}]},
                            name="hi"))
PYEOF2
)
case "$NAME" in
  hi-*.json) ok "write_request 的 name 當前綴用（$NAME）" ;;
  *) fail "write_request 的檔名不對：$NAME" ;;
esac
if [ -f "$TMP/llm/requests/$NAME" ]; then
  ok "write_request 把請求寫進 requests/"
else
  fail "write_request 沒寫進 requests/：$NAME"
fi
llm_pump "$TMP/llm" >/dev/null
OUT=$(python3 - "$HERE" "$TMP/llm" "$NAME" <<'PYEOF2'
import sys
sys.path.insert(0, sys.argv[1])
import aos_llm
first = aos_llm.read_result(sys.argv[2], sys.argv[3])
again = aos_llm.read_result(sys.argv[2], sys.argv[3])
print("%s %s" % (bool(first and first.get("choices")), again is None))
PYEOF2
)
if [ "$OUT" = "True True" ]; then
  ok "read_result 撿得回整包回覆，而且拿走就沒了"
else
  fail "read_result 不對：$OUT"
fi
rm -rf "$TMP"

# 17. aos_llm.write_request：priority／engine 有給才寫進請求，沒給就留白讓資料夾用自己的預設
TMP=$(mktemp -d); prep_llm "$TMP/llm"
KEYS=$(python3 - "$HERE" "$TMP/llm" <<'PYEOF2'
import json, os, sys
sys.path.insert(0, sys.argv[1])
import aos_llm
bare = aos_llm.write_request(sys.argv[2], {"messages": []})
full = aos_llm.write_request(sys.argv[2], {"messages": []}, priority=7, engine="deepseek-flash")
box = os.path.join(sys.argv[2], "requests")
out = []
for name in (bare, full):
    with open(os.path.join(box, name), encoding="utf-8") as f:
        out.append(",".join(sorted(json.load(f))))
print(" | ".join(out))
PYEOF2
)
if [ "$KEYS" = "messages | engine,messages,priority" ]; then
  ok "沒給就不硬塞 priority／engine，給了才寫進去（$KEYS）"
else
  fail "write_request 亂改請求的鍵：$KEYS"
fi
rm -rf "$TMP"

# 17b. strip_think：`<think>…</think>` 漏進 content 是 LLM 這一側的家務，預設就清掉
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"messages": [{"role": "user", "content": "THINK 給我答案"}]}' \
  > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null
C=$(llm_content "$TMP/llm/results/0001.json")
if [ "$C" = "真正的回答" ]; then
  ok "引擎預設 strip_think：</think> 前面那段思考在結果檔裡就被切掉了"
else
  fail "strip_think 沒清乾淨：$C"
fi
RC_KEEP=$(llm_field "$TMP/llm/results/0001.json" 'd["choices"][0]["message"].get("reasoning_content")')
if [ "$RC_KEEP" = "blah" ]; then
  ok "供應商自己的 reasoning_content 原樣留著，沒被動到"
else
  fail "reasoning_content 被動到了：$RC_KEEP"
fi
rm -rf "$TMP"

# 17c. 引擎寫 strip_think: false 就原樣不動
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"raw\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"strip_think\": false}]"
echo '{"messages": [{"role": "user", "content": "THINK 給我答案"}]}' \
  > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null
C=$(llm_content "$TMP/llm/results/0001.json")
case "$C" in
  *"<think>"*"真正的回答"*) ok "strip_think: false 就原樣把 <think> 留著" ;;
  *) fail "strip_think: false 不該清：$C" ;;
esac
rm -rf "$TMP"

# ── aos-agent：五格狀態機、信箱、工具包、子世界 ────────────────────────────
# 18. agent 跟 LLM 兩個資料夾交錯走：每圈各推一格，五格輪兩輪
#     idle（收信）→llm（丟請求）→wait（撿回覆）→act（跑工具）→collect（再掃信箱）→llm→wait→act→idle
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
"$AUSER" say "$W" "哈囉呀" >/dev/null 2>&1
SEQ=""
STEP_ERR=""
for i in 1 2 3 4 5 6 7 8; do
  SEQ="$SEQ$(now_state "$H") "
  ERR=$("$AGENT" exec "$W" 2>&1 >/dev/null)
  STEP_ERR="$STEP_ERR
$ERR"
  llm_pump "$TMP/llm" >/dev/null
done
SEQ="$SEQ$(now_state "$H")"
if [ "$SEQ" = "idle llm wait act collect llm wait act idle" ]; then
  ok "五格的 state 依序走完兩輪"
else
  fail "state 順序不對：$SEQ"
fi
# busy 只算真做事的格：8 格裡扣掉「idle -> idle」（沒信）跟「wait -> wait」（還沒等到）
BUSY_NOW=$(field "$H/state.json" busy)
IDLE_SPIN=$(printf '%s' "$STEP_ERR" | grep -c 'state idle -> idle')
WAIT_SPIN=$(printf '%s' "$STEP_ERR" | grep -c 'state wait -> wait')
WANT_BUSY=$((8 - IDLE_SPIN - WAIT_SPIN))
if [ "$BUSY_NOW" = "$WANT_BUSY" ] && [ "$BUSY_NOW" -le 8 ]; then
  ok "busy=$BUSY_NOW 等於 stderr 裡真做事的格數（8 格扣掉空轉的 idle/wait）"
else
  fail "busy 不對：busy=$BUSY_NOW 算出來該是 $WANT_BUSY"
fi
SAID=$(cat "$W/said.txt" 2>/dev/null)
if [ "$SAID" = "hi" ]; then ok "tools[] 裡的 say 工具（shell 指令）真的寫了 said.txt"; else fail "said.txt 是 $SAID"; fi
ROLES=$(python3 -c '
import json,sys
ms=json.load(open(sys.argv[1]))
print(" ".join((m.get("role") or "?") + ("+tool_calls" if m.get("tool_calls") else "") for m in ms))' \
  "$H/prompts.json")
if [ "$ROLES" = "user assistant+tool_calls tool assistant" ]; then
  ok "prompts.json 四則訊息都在（含 tool_calls），new-prompts.json 已經不需要了"
else
  fail "prompts.json 內容不對：$ROLES"
fi
FIRST=$(python3 -c '
import json,sys
print(json.load(open(sys.argv[1]))[0]["content"])' "$H/prompts.json")
if [ "$FIRST" = "[user] 哈囉呀" ]; then
  ok "來源 user 的信短路：內容直接接進記憶（前面加 [user]）"
else
  fail "user 短路的訊息不對：$FIRST"
fi
if [ -z "$(find "$H/inbox/user" -maxdepth 1 -name '*.json' 2>/dev/null)" ] \
   && [ -n "$(find "$H/inbox/user/read" -maxdepth 1 -name '*.json' 2>/dev/null)" ]; then
  ok "user 的信當場搬進 inbox/user/read/"
else
  fail "user 的信沒搬進 read/"
fi
PRIVATE=$(python3 -c '
import json,sys
ms=json.load(open(sys.argv[1]))
bad=[]
for m in ms:
    if m.get("role") == "assistant":
        if "reasoning_content" in m:
            bad.append("reasoning_content")
        if "tool_calls" in m and not m["tool_calls"]:
            bad.append("empty-tool_calls-key")
print(",".join(bad))' "$H/prompts.json")
if [ -z "$PRIVATE" ]; then
  ok "assistant 訊息沒有 reasoning_content、也沒有空的 tool_calls key"
else
  fail "assistant 訊息還帶著私有欄位：$PRIVATE"
fi
NREP=$(find "$H/outbox" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
REP=$(python3 -c '
import glob,json,sys
print(json.load(open(sorted(glob.glob(sys.argv[1]+"/*.json"))[0], encoding="utf-8"))["content"])' "$H/outbox")
if [ "$NREP" = "1" ] && [ "$REP" = "done" ]; then
  ok "沒工具可跑那格把話落進 outbox/（一個檔，content 是 done）"
else
  fail "outbox 不對：$NREP 個檔，content=$REP"
fi
# 送出去的 body：system 訊息帶著預設包的 prompt，工具清單外加 tools[] 的 say
REQ=$(ls "$TMP/llm/requests/done"/*.json 2>/dev/null | head -1)
SYS=$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
m=d["messages"][0]
markers=("信箱", "交流：", "檔案與短指令", "自我檢查", "記憶就是", "子 agent", "成本：")
print("%s|%s" % (m["role"], "".join(k for k in markers if k in m["content"])))' "$REQ")
if [ "$SYS" = "system|信箱交流：檔案與短指令自我檢查記憶就是子 agent成本：" ]; then
  ok "system 訊息有預設七個工具包的 prompt"
else
  fail "system 訊息不對：$SYS"
fi
NAMES=$(python3 -c '
import json,sys
d=json.load(open(sys.argv[1]))
print(" ".join(sorted(t["function"]["name"] for t in d.get("tools") or [])))' "$REQ")
WANT_NAMES="cost_recent cost_summary edit inbox_list inbox_read inbox_read_all inbox_sources kids_kill kids_list kids_pause kids_resume kids_tell ls mail_broadcast mail_reply mail_send mail_wait mail_who memory_forget memory_list memory_replace_old memory_summarize_old note_find note_read note_save read say self_cost self_note self_status self_time self_who sh spawn write"
if [ "$NAMES" = "$WANT_NAMES" ]; then
  ok "工具清單＝預設七包的工具＋tools[] 的 say"
else
  fail "工具清單不對：$NAMES"
fi
rm -rf "$TMP"

# 18b. LLM 回 500：agent 當格把原因送進 outbox，listen 用 agent!> 印出來
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
"$AUSER" say "$W" "HTTP500" >/dev/null 2>&1
"$AGENT" exec "$W" >/dev/null 2>&1
"$AGENT" exec "$W" >/dev/null 2>&1
llm_pump "$TMP/llm" >/dev/null
"$AGENT" exec "$W" >/dev/null 2>&1
ERRMSG=$(python3 -c '
import glob,json,sys
files=glob.glob(sys.argv[1]+"/*.json")
d=json.load(open(files[0], encoding="utf-8")) if files else {}
print("%s|%s" % (d.get("error") is True, d.get("content") or ""))' "$H/outbox")
case "$ERRMSG" in
  True\|*"LLM 出錯：HTTP 500"*) ok "LLM 回 500 時，agent 把原因寫進 error outbox" ;;
  *) fail "LLM 500 沒送進 outbox：$ERRMSG" ;;
esac
OUT=$("$AUSER" listen "$W" --once)
case "$OUT" in
  *"agent!> （LLM 出錯：HTTP 500"*) ok "listen 用 agent!> 印 LLM 錯誤" ;;
  *) fail "listen 的錯誤前綴不對：$OUT" ;;
esac
rm -rf "$TMP"

# 18c. 沒有 LLM 鐘：下一格立刻說卡在哪、回 idle，原請求留在 LLM requests/
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
"$AUSER" say "$W" "這句沒有人推 LLM" >/dev/null 2>&1
"$AGENT" exec "$W" >/dev/null 2>&1
"$AGENT" exec "$W" >/dev/null 2>&1
"$AGENT" exec "$W" >/dev/null 2>&1
TIMEOUT_MSG=$(python3 -c '
import glob,json,sys
files=glob.glob(sys.argv[1]+"/*.json")
d=json.load(open(files[0], encoding="utf-8")) if files else {}
print("%s|%s" % (d.get("error") is True, d.get("content") or ""))' "$H/outbox")
NREQ=$(find "$TMP/llm/requests" -maxdepth 1 -name '*.json' | wc -l)
if [ "$(now_state "$H")" = "idle" ] && [ "$NREQ" = "1" ]; then
  ok "LLM 缺鐘下一格就回 idle，原請求仍留在原地"
else
  fail "LLM 沒鐘超時狀態不對：state=$(now_state "$H") requests=$NREQ"
fi
case "$TIMEOUT_MSG" in
  True\|*"LLM 的鐘沒有在跑"*) ok "LLM 沒鐘時 outbox 直接講卡在哪" ;;
  *) fail "LLM 沒鐘沒有 outbox 提示：$TIMEOUT_MSG" ;;
esac
rm -rf "$TMP"

# 18d. 模型回空 content 且沒工具：不產生空 outbox，empty_replies 加一
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
"$AUSER" say "$W" "EMPTY" >/dev/null 2>&1
"$AGENT" exec "$W" >/dev/null 2>&1
"$AGENT" exec "$W" >/dev/null 2>&1
llm_pump "$TMP/llm" >/dev/null
"$AGENT" exec "$W" >/dev/null 2>&1
OUT=$("$AGENT" exec "$W" 2>&1 >/dev/null)
NREP=$(find "$H/outbox" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
EMPTY_N=$(field "$H/state.json" empty_replies)
if [ "$NREP" = "0" ] && [ "$EMPTY_N" = "1" ]; then
  ok "模型回空白不寫 outbox，state.json 的 empty_replies 加一"
else
  fail "空白回覆處理不對：outbox=$NREP empty_replies=$EMPTY_N"
fi
case "$OUT" in
  *"模型回空白"*) ok "模型回空白時 stderr 有講一句" ;;
  *) fail "模型回空白時 stderr 沒提示：$OUT" ;;
esac
rm -rf "$TMP"

# 19. 預設 home（`.`，東西平鋪在世界資料夾底下）也走得動
TMP=$(mktemp -d); W="$TMP/w"; prep_flat "$W"; prep_llm "$TMP/llm"
"$AUSER" say "$W" "嗨" >/dev/null 2>&1
agent_pump "$W" "$TMP/llm" 8
if [ -f "$W/state.json" ] && [ -f "$W/prompts.json" ] && [ -d "$W/inbox/user/read" ]; then
  ok "home 預設是 . 時，state.json／prompts.json／inbox 都在世界資料夾底下"
else
  fail "平鋪的 home 檔案位置不對：$(ls -A "$W")"
fi
NFLAT=$(find "$W/outbox" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
if [ "$NFLAT" -ge 1 ]; then ok "平鋪的 agent 也回得了話"; else fail "平鋪的 agent 沒回話：state=$(now_state "$W")"; fi
rm -rf "$TMP"

# 20. --home 撈得到：say 沒給 --home 時，去世界的 .aos/inst 把 `--home agent` 撈出來
TMP=$(mktemp -d); prep_agent "$TMP/w"; prep_flat "$TMP/f"
"$AUSER" say "$TMP/w" "有 home" >/dev/null 2>&1
"$AUSER" say "$TMP/f" "沒 home" >/dev/null 2>&1
if [ -n "$(find "$TMP/w/agent/inbox/user" -maxdepth 1 -name '*.json' 2>/dev/null)" ]; then
  ok "say 從 .aos/inst 撈到 --home agent，信丟進 agent/inbox/user/"
else
  fail "say 沒撈到 --home：$(find "$TMP/w" -name '*.json')"
fi
if [ -n "$(find "$TMP/f/inbox/user" -maxdepth 1 -name '*.json' 2>/dev/null)" ]; then
  ok "inst 沒寫 --home 就用預設的 ."
else
  fail "預設 home 不對：$(find "$TMP/f" -name '*.json')"
fi
"$AUSER" say "$TMP/w" --home agent "明講 home" >/dev/null 2>&1
NW=$(find "$TMP/w/agent/inbox/user" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NW" = "2" ]; then ok "明講 --home 也走同一個地方"; else fail "明講 --home 丟錯地方（$NW）"; fi
rm -rf "$TMP"

# 21. 推薦用法：.aos/inst 寫一次，兩個 aos-loop --keep-inst 各轉各的，整條鏈自己跑完
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
"$AUSER" say "$W" "跑一輪" >/dev/null 2>&1
"$LOOP" "$TMP/llm" --keep-inst --steps 2000 --interval 0 >/dev/null 2>&1 &
LLM_LOOP=$!
"$LOOP" "$W" --keep-inst --steps 30 --interval 0.05 >/dev/null 2>&1
kill $LLM_LOOP 2>/dev/null; wait $LLM_LOOP 2>/dev/null
if [ "$(cat "$W/said.txt" 2>/dev/null)" = "hi" ] && [ "$(now_state "$H")" = "idle" ]; then
  ok "兩個 aos-loop --keep-inst 交錯跑完同一條鏈"
else
  fail "aos-loop 沒跑完：said=$(cat "$W/said.txt" 2>/dev/null) state=$(now_state "$H")"
fi
case "$(cat "$W/.aos/inst")" in
  *"aos-agent exec . --home agent"*) ok "--keep-inst 跑完 .aos/inst 原樣還在" ;;
  *) fail ".aos/inst 被動到了：$(cat "$W/.aos/inst")" ;;
esac
rm -rf "$TMP"

# ── 信箱 ────────────────────────────────────────────────────────────────────
# 22. 非 user 的來源不進 prompt：只給一句摘要，模型自己用信箱工具去讀，讀完搬進 read/
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
mkdir -p "$H/inbox/team"
echo '{"from": "bob", "time": "2026-09-06T10:00:00", "content": "專案要延一週"}' \
  > "$H/inbox/team/m1.json"
"$AUSER" say "$W" 'CALL inbox_list {"source": "team"} 然後 CALL inbox_read_all {"source": "team"}' >/dev/null 2>&1
agent_pump "$W" "$TMP/llm" 14
SUMMARY=$(python3 -c '
import json,sys
ms=json.load(open(sys.argv[1]))
print([m["content"] for m in ms if m["role"] == "user" and m["content"].startswith("你有新信")][0])' \
  "$H/prompts.json" 2>/dev/null)
if [ "$SUMMARY" = "你有新信：team 1 封。用信箱工具去讀。" ]; then
  ok "team 的信只變成一句摘要，信的內容沒被塞進 prompt"
else
  fail "摘要訊息不對：$SUMMARY"
fi
if grep -q "專案要延一週" "$H/prompts.json"; then
  ok "信的內容是模型用信箱工具讀回來的（出現在 tool 結果裡）"
else
  fail "模型沒把 team 的信讀回來"
fi
if [ -f "$H/inbox/team/read/m1.json" ] && [ ! -f "$H/inbox/team/m1.json" ]; then
  ok "讀過的信搬進 inbox/team/read/"
else
  fail "team 的信沒搬進 read/"
fi
LASTREP=$(python3 -c '
import glob,json,sys
print(json.load(open(sorted(glob.glob(sys.argv[1]+"/*.json"))[-1], encoding="utf-8"))["content"])' "$H/outbox")
case "$LASTREP" in
  *"專案要延一週"*) ok "模型最後把信的內容講了出來" ;;
  *) fail "最後那句沒提到信：$LASTREP" ;;
esac
rm -rf "$TMP"

# 23. 同一封未讀信只通知一次：模型不去讀，idle 也不會一直把它重新叫醒（不然錢燒不完）
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
mkdir -p "$H/inbox/team"
echo '{"from": "bob", "time": "2026-09-06T10:00:00", "content": "沒人要理我"}' \
  > "$H/inbox/team/m1.json"
agent_pump "$W" "$TMP/llm" 10
BUSY_A=$(field "$H/state.json" busy)
agent_pump "$W" "$TMP/llm" 5
BUSY_B=$(field "$H/state.json" busy)
if [ "$(now_state "$H")" = "idle" ] && [ "$BUSY_A" = "$BUSY_B" ]; then
  ok "通知過的未讀信不會再叫一次 LLM（busy 停在 $BUSY_A）"
else
  fail "未讀信一直重新叫 LLM：state=$(now_state "$H") busy $BUSY_A -> $BUSY_B"
fi
if [ -f "$H/inbox/team/m1.json" ]; then
  ok "沒讀的信還留在未讀裡（模型隨時可以用工具去讀）"
else
  fail "沒讀的信不見了"
fi
ANN=$(python3 -c '
import json,sys;print(",".join(json.load(open(sys.argv[1])).get("announced") or []))' "$H/state.json")
if [ "$ANN" = "team/m1.json" ]; then ok "state.json 的 announced 記著通知過哪封"; else fail "announced 不對：$ANN"; fi
# 再來一封新的就會再叫一次
echo '{"from": "bob", "content": "這封是新的"}' > "$H/inbox/team/m2.json"
"$AGENT" exec "$W" >/dev/null 2>&1
if [ "$(now_state "$H")" = "llm" ]; then ok "來了新的一封就會再叫一次 LLM"; else fail "新信沒叫醒：$(now_state "$H")"; fi
rm -rf "$TMP"

# 24. 一個信件檔可以放一串（陣列），user 短路時每則各算一句
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"
mkdir -p "$H/inbox/user"
echo '[{"from": "u", "content": "一"}, {"from": "u", "content": "二"}, 3]' \
  > "$H/inbox/user/pair.json"
"$AGENT" exec "$W" >/dev/null 2>&1
CONTENTS=$(python3 -c '
import json,sys
print(" ".join(m["content"] for m in json.load(open(sys.argv[1]))))' "$H/prompts.json")
if [ "$CONTENTS" = "[user] 一 [user] 二" ]; then
  ok "一個信件檔放一串就收成兩則（陣列裡不是物件的那項跳過）"
else
  fail "一串收成：$CONTENTS"
fi
rm -rf "$TMP"

# 25. aos-user say：一句話寫成 inbox/user/ 的一封信
TMP=$(mktemp -d); prep_agent "$TMP/w"
"$AUSER" say "$TMP/w" "嗨呀" 2>/dev/null
NFILE=$(find "$TMP/w/agent/inbox/user" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NFILE" = "1" ]; then ok "aos-user say 寫出一封信"; else fail "say 寫了 $NFILE 個檔"; fi
SAID=$(python3 -c '
import glob,json,sys
m=json.load(open(sorted(glob.glob(sys.argv[1]+"/*.json"))[0], encoding="utf-8"))
print(m.get("from"), m.get("content"), bool(m.get("time")))' "$TMP/w/agent/inbox/user")
if [ "$SAID" = "user 嗨呀 True" ]; then ok "信的格式是 from／time／content"; else fail "信的內容不對：$SAID"; fi
rm -rf "$TMP"

# ── 工具包：fs／self ────────────────────────────────────────────────────────
# 26. fs 包的 sh：在世界資料夾裡跑一句指令，回 exit／stdout／stderr
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
"$AUSER" say "$W" 'CALL sh {"command": "cat notes.txt"}' >/dev/null 2>&1
agent_pump "$W" "$TMP/llm" 10
SH=$(python3 -c '
import json,sys
for m in json.load(open(sys.argv[1])):
    if m.get("role") == "tool":
        d = json.loads(m["content"])
        print(d["exit"], "notes" if "普通檔案" in d["stdout"] else d["stdout"][:40])
        break' "$H/prompts.json")
if [ "$SH" = "0 notes" ]; then
  ok "sh 在世界資料夾裡跑指令，回退出碼跟 stdout"
else
  fail "sh 的結果不對：$SH"
fi
rm -rf "$TMP"

# 27. status：人看的頂層不超過十欄；self 包另補記憶估算
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
"$AUSER" say "$W" 'CALL self_status' >/dev/null 2>&1
agent_pump "$W" "$TMP/llm" 10
KEYS=$(python3 -c '
import json,sys
for m in json.load(open(sys.argv[1])):
    if m.get("role") == "tool":
        print(",".join(sorted(json.loads(m["content"]))))
        break' "$H/prompts.json")
WANT="clock,history_chars,history_pct,history_tokens,last_error,memory,question_steps,recent_question_steps,status,steps,today,waiting"
if [ "$KEYS" = "$WANT" ]; then ok "self_status 有新狀態與記憶估算"; else fail "self_status 的鍵不對：$KEYS"; fi
OUT=$("$AUSER" status "$W"); RC=$?
check "aos-user status 退 0" 0 "$RC"
STATUS_KEYS=$(python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print(len(d),",".join(d))' <<< "$OUT")
case "$STATUS_KEYS" in
  9\ status,waiting,clock,last_error,steps,question_steps,today,recent_question_steps,memory)
    ok "aos-user status 九欄一眼列出狀態、等待、鐘、錯誤、格數與今日用量" ;;
  *) fail "status 印的不對：$OUT" ;;
esac
mkdir -p "$TMP/llm/usage"
python3 - "$TMP/llm/usage/$(date +%Y-%m-%d).json" <<'PYEOF2'
import json, sys
json.dump({"by-model": {
             "http://one/v1|m1": {"requests": 2, "errors": 0, "total_tokens": 11},
             "http://two/v1|m2": {"requests": 3, "errors": 1, "total_tokens": 29}},
           "by-requester": {"team/a": {"requests": 5, "total_tokens": 40}}},
          open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
OUT=$("$AUSER" status "$W")
TU=$(python3 -c '
import json,sys
d=(json.loads(sys.stdin.read()).get("today") or {})
print("%s %s" % (d.get("tokens"), d.get("token_limit")))' <<< "$OUT")
if [ "$TU" = "40 None" ]; then
  ok "status 顯示今日 token 與硬上限（$TU）"
else
  fail "今日用量不對：$TU"
fi
rm -rf "$TMP"

# ── say／listen／talk ───────────────────────────────────────────────────────
# 29. aos-user listen --once 把既有的印出來就走
TMP=$(mktemp -d); prep_agent "$TMP/w"; mkdir -p "$TMP/w/agent/outbox"
echo '{"role": "assistant", "content": "done"}' > "$TMP/w/agent/outbox/0008.json"
OUT=$(timeout 10 "$AUSER" listen "$TMP/w" --once); RC=$?
check "listen --once 退出 0" 0 "$RC"
case "$OUT" in
  *"--- reply 0008 ---"*"done"*) ok "listen --once 印得出 outbox 裡的回話" ;;
  *) fail "listen --once 印的不對：$OUT" ;;
esac
rm -rf "$TMP"

# 30. aos-user listen --new --once：跳過既有的，等到新的那則才印、才退出
TMP=$(mktemp -d); mkdir -p "$TMP/outbox"
echo '{"role": "assistant", "content": "舊的"}' > "$TMP/outbox/0001.json"
( sleep 1; echo '{"role": "assistant", "content": "新的"}' > "$TMP/outbox/0002.json" ) &
OUT=$(timeout 10 "$AUSER" listen "$TMP" --new --once); RC=$?
check "listen --new --once 等到新的就退出 0" 0 "$RC"
case "$OUT" in
  *"舊的"*) fail "--new 不該印既有的：$OUT" ;;
  *"--- reply 0002 ---"*"新的"*) ok "listen --new --once 只印新出現的那則" ;;
  *) fail "listen --new --once 印的不對：$OUT" ;;
esac
rm -rf "$TMP"

# 31. aos-user talk：打一句、等到回話印出來
TMP=$(mktemp -d); mkdir -p "$TMP/inbox/user" "$TMP/outbox"
( for i in $(seq 1 100); do
    if [ -n "$(find "$TMP/inbox/user" -maxdepth 1 -name '*.json' 2>/dev/null)" ]; then
      echo '{"role": "assistant", "content": "我在"}' > "$TMP/outbox/9999.json"
      break
    fi
    sleep 0.1
  done ) &
OUT=$(printf '哈囉\n/quit\n' | timeout 10 "$AUSER" talk "$TMP"); RC=$?
check "talk 打完 /quit 退出 0" 0 "$RC"
case "$OUT" in
  *"agent> 我在"*) ok "talk 印出了 agent 的回話" ;;
  *) fail "talk 沒印出回話：$OUT" ;;
esac
rm -rf "$TMP"

# ── 子世界：aos-user spawn ─────────────────────────────────────────────────
# 32. shared 鐘：子長在 <home>/kids/<名字>/、自己是一個合法世界、父的 inst 尾巴掛上它
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
"$AUSER" spawn "$W" kid1 "你是小幫手 kid1" 2>/dev/null; RC=$?
check "spawn shared 回 0" 0 "$RC"
KID="$H/kids/kid1"
MISSING=""
for f in system-prompt.json prompts.json tools.json state.json llm.json .aos/inst; do
  [ -f "$KID/$f" ] || MISSING="$MISSING $f"
done
if [ -z "$MISSING" ]; then ok "子 agent 五個檔加 .aos/inst 都在（子的 home 是預設的 .）"; else fail "子少了：$MISSING"; fi
if [ "$(cat "$KID/.aos/inst")" = "aos-agent exec ." ]; then
  ok "子的 .aos/inst 是 aos-agent exec ."
else
  fail "子的 inst 不對：$(cat "$KID/.aos/inst")"
fi
LLMDIR=$(python3 -c '
import json,os,sys
d=json.load(open(sys.argv[1]+"/llm.json", encoding="utf-8"))["dir"]
print(d if os.path.isdir(os.path.join(sys.argv[1], d)) else "")' "$KID")
if [ -n "$LLMDIR" ]; then
  ok "子的 llm.json（$LLMDIR）解出來真的是那個 LLM 資料夾"
else
  fail "子的 llm.json 指到不存在的地方"
fi
PACKS=$(python3 -c '
import json,sys;print(",".join(json.load(open(sys.argv[1]))["packs"]))' "$KID/tools.json")
if [ "$PACKS" = "mailbox,communication,fs,self,memory,kids,cost" ]; then ok "子抄到父的工具包"; else fail "子的 packs 不對：$PACKS"; fi
LAST=$(tail -1 "$W/.aos/inst")
if [ "$LAST" = "aos-exec agent/kids/kid1" ]; then
  ok "shared 鐘掛在父的 .aos/inst 最後一行（路徑相對於世界資料夾）"
else
  fail "父的 inst 最後一行是「$LAST」"
fi
"$AOS" "$KID" >/dev/null 2>&1; RC=$?
check "子資料夾本身就是合法世界，aos-exec 跑得動" 0 "$RC"
if [ "$(field "$KID/state.json" step)" = "1" ]; then ok "aos-exec 推了子一格"; else fail "子沒被推動"; fi

# 33. own 鐘：只建資料夾，父的 inst 不動它
"$AUSER" spawn "$W" kid2 "你是 kid2" --clock own 2>/dev/null; RC=$?
check "spawn own 回 0" 0 "$RC"
if [ -f "$H/kids/kid2/.aos/inst" ] && ! grep -q "kids/kid2" "$W/.aos/inst"; then
  ok "own 鐘的子建好了但沒掛進父的 inst"
else
  fail "own 鐘的子不該進父的 inst：$(cat "$W/.aos/inst")"
fi

# 34. 同名再生一次退 2；子名有奇怪字元退 2
"$AUSER" spawn "$W" kid1 "重複的" 2>/dev/null; RC=$?
check "同名再 spawn 一次回 2" 2 "$RC"
"$AUSER" spawn "$W" "bad/name" "壞名字" 2>/dev/null; RC=$?
check "子名有斜線回 2" 2 "$RC"

# 35. 父走三格：shared 的 kid1 跟著走三格，own 的 kid2 一格都沒走
"$AUSER" say "$H/kids/kid1" "kid1 你好" 2>/dev/null
"$AUSER" say "$H/kids/kid2" "kid2 你好" 2>/dev/null
STEP_K1_BEFORE=$(field "$H/kids/kid1/state.json" step)
"$LOOP" "$W" --keep-inst --steps 3 --interval 0 >/dev/null 2>&1
STEP_P=$(field "$H/state.json" step)
STEP_1=$(field "$H/kids/kid1/state.json" step)
STEP_2=$(field "$H/kids/kid2/state.json" step)
if [ "$STEP_P" = "3" ]; then ok "父自己走了三格"; else fail "父走了 $STEP_P 格"; fi
if [ "$STEP_1" = "$((STEP_K1_BEFORE + 3))" ]; then ok "shared 的 kid1 跟著父走了三格"; else fail "kid1 走到 $STEP_1 格"; fi
if [ "$STEP_2" = "0" ]; then ok "own 的 kid2 一格都沒走（時間跟父脫節）"; else fail "kid2 走了 $STEP_2 格"; fi

# 36. 子真的能透過同一個 LLM 資料夾工作：父帶著跑，kid1 的 outbox/ 要冒出回話
"$LOOP" "$TMP/llm" --keep-inst --steps 2000 --interval 0 >/dev/null 2>&1 &
LLM_LOOP=$!
"$LOOP" "$W" --keep-inst --steps 30 --interval 0.05 >/dev/null 2>&1
kill $LLM_LOOP 2>/dev/null; wait $LLM_LOOP 2>/dev/null
NREP=$(find "$H/kids/kid1/outbox" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
if [ "$NREP" -ge 1 ]; then
  ok "kid1 靠父的鐘跑完一輪，outbox/ 有回話（共用同一個 LLM 資料夾）"
else
  fail "kid1 沒有回話：state=$(now_state "$H/kids/kid1")"
fi
rm -rf "$TMP"

# 37. kids 包的兩個工具：模型自己叫 spawn 生小孩、kids_list 看得到
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
"$AUSER" say "$W" 'CALL spawn {"name": "kid9", "persona": "你是 kid9", "clock": "shared"} 然後 CALL kids_list' >/dev/null 2>&1
agent_pump "$W" "$TMP/llm" 14
if [ -f "$H/kids/kid9/system-prompt.json" ]; then
  ok "模型自己叫 spawn 就生得出 kid9"
else
  fail "spawn 工具沒生出 kid9"
fi
KL=$(python3 -c '
import json,sys
ts=[m for m in json.load(open(sys.argv[1])) if m.get("role") == "tool"]
print(json.loads(ts[-1]["content"])[0]["name"])' "$H/prompts.json" 2>/dev/null)
if [ "$KL" = "kid9" ]; then ok "kids_list 列得出 kid9"; else fail "kids_list 不對：$KL"; fi
rm -rf "$TMP"

# 38. 舊的五支腳本已經拆成 aos-agent（自己跑）＋ aos-user（人用）＋ packs/（工具包）
GONE=""
for f in aos-agent-step aos-agent-say aos-agent-listen aos-agent-talk aos-agent-spawn; do
  [ -e "$HERE/$f" ] && GONE="$GONE $f"
done
if [ -z "$GONE" ]; then ok "舊的 aos-agent-* 五支腳本都不在了"; else fail "舊腳本還在：$GONE"; fi
MISSP=""
for f in aos-agent aos-user aos_agent.py packs/mailbox.py packs/fs.py packs/self.py packs/kids.py; do
  [ -e "$HERE/$f" ] || MISSP="$MISSP $f"
done
if [ -z "$MISSP" ] && [ ! -e "$HERE/packs/shell.py" ]; then ok "新版面在，shell.py 已收進 fs.py"; else fail "新版面不對，少了：$MISSP"; fi
OUT=$("$AGENT" say x 2>&1); RC=$?
if [ "$RC" != "0" ]; then ok "aos-agent 不吃人用的子命令（say 在 aos-user）"; else fail "aos-agent 還吃 say"; fi

# 39. 自己加一個工具包：<home>/packs/hello.py 放進去、tools.json 列上，模型就叫得動
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
mkdir -p "$H/packs"
cat > "$H/packs/hello.py" <<'PACKEOF'
PROMPT = "打招呼：hello 這個工具會跟一個人打招呼。"
TOOLS = [{"name": "hello",
          "description": "跟某個人打招呼。",
          "parameters": {"type": "object",
                         "properties": {"who": {"type": "string"}},
                         "required": ["who"]}}]


def run(name, args, ctx):
    if name != "hello":
        return {"error": "hello 包沒有這個工具：%s" % name}
    return {"greeting": "哈囉 %s，我住在 %s" % (args.get("who") or "", ctx.home)}
PACKEOF
python3 - "$H/tools.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["packs"].append("hello")
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
"$AUSER" say "$W" 'CALL hello {"who": "阿明"}' >/dev/null 2>&1
agent_pump "$W" "$TMP/llm" 10
GREET=$(python3 -c '
import json,sys
for m in json.load(open(sys.argv[1])):
    if m.get("role") == "tool":
        print(json.loads(m["content"])["greeting"])
        break' "$H/prompts.json")
case "$GREET" in
  "哈囉 阿明，我住在 "*) ok "自己加的工具包 <home>/packs/hello.py 叫得動（$GREET）" ;;
  *) fail "自己加的工具包沒跑起來：$GREET" ;;
esac
REQ=$(ls "$TMP/llm/requests/done"/*.json 2>/dev/null | head -1)
if grep -q "打招呼：hello" "$REQ"; then
  ok "自己加的工具包的預設 prompt 也併進 system 訊息"
else
  fail "自己加的工具包 PROMPT 沒併進去"
fi
rm -rf "$TMP"

# 40. tools.json 列了一個不存在的工具包：印一句就跳過，agent 照樣跑
TMP=$(mktemp -d); W="$TMP/w"; H="$W/agent"; prep_agent "$W"; prep_llm "$TMP/llm"
python3 - "$H/tools.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
d["packs"].append("nosuchpack")
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
"$AUSER" say "$W" "哈囉" >/dev/null 2>&1
"$AGENT" exec "$W" >/dev/null 2>&1
OUT=$("$AGENT" exec "$W" 2>&1 >/dev/null); RC=$?
check "有認不得的工具包時 exec 還是回 0" 0 "$RC"
case "$OUT" in
  *"認不得的工具包：nosuchpack"*) ok "認不得的工具包印一句到 stderr 就跳過" ;;
  *) fail "沒講認不得的工具包：$OUT" ;;
esac
if [ "$(now_state "$H")" = "wait" ]; then ok "agent 照樣走到 wait"; else fail "agent 卡住了：$(now_state "$H")"; fi
rm -rf "$TMP"

# ── daemon：常駐 kernel＋一個世界一個時鐘 ───────────────────────────────────
# 幫手：做一個每格往 count.txt 加一行的世界、把某個 daemon 目錄裡的時鐘全砍掉
# （測試絕不能留背景進程）、讀最新一筆處理完的請求結果、算 count.txt 幾行。
make_clock_world() {  # make_clock_world <資料夾>
  mkdir -p "$1/.aos"
  printf 'echo x >> count.txt\n' > "$1/.aos/inst"
}
kill_clocks() {  # kill_clocks <daemon 目錄>
  python3 - "$1" <<'PYEOF2'
import glob, json, os, signal, sys
for p in glob.glob(os.path.join(sys.argv[1], "clocks", "*.json")):
    try:
        os.killpg(int(json.load(open(p, encoding="utf-8"))["pid"]), signal.SIGKILL)
    except Exception:
        pass
PYEOF2
}
last_result() {  # last_result <daemon 目錄>：印最後處理完的那筆 ok|訊息（照改動時間挑，
                 # 因為測試會故意塞檔名很怪的壞請求）
  python3 - "$1" <<'PYEOF2'
import glob, json, os, sys
files = sorted(glob.glob(os.path.join(sys.argv[1], "requests", "done", "*.json")),
               key=os.path.getmtime)
r = (json.load(open(files[-1], encoding="utf-8")).get("result") or {}) if files else {}
print(("ok" if r.get("ok") else "fail") + "|" + (r.get("message") or "沒有結果"))
PYEOF2
}
nlines() { if [ -f "$1/count.txt" ]; then wc -l < "$1/count.txt"; else echo 0; fi; }
clock_id() {  # 路徑 → 時鐘檔名：percent-encoding，超過 200 bytes 退 sha256
  python3 - "$1" <<'PYEOF2'
import hashlib, sys, urllib.parse
p = sys.argv[1]
e = urllib.parse.quote(p, safe="")
print(e if len(e.encode("utf-8")) <= 200 else hashlib.sha256(p.encode("utf-8")).hexdigest())
PYEOF2
}
field_of() {  # field_of <daemon 目錄> <世界> <欄位> [預設]
  python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2], sys.argv[3]))' \
    "$1/clocks/$(clock_id "$2").json" "$3" "${4:-}" 2>/dev/null
}
pid_of()      { field_of "$1" "$2" pid; }
state_of()    { field_of "$1" "$2" state; }
dir_of()      { field_of "$1" "$2" dir; }
restarts_of() { field_of "$1" "$2" restarts 0; }

# 35. 沒給 daemon 目錄也沒設 AOS_DAEMON_DIR：兩支都退 2
"$DKERNEL" ls >/dev/null 2>&1; RC=$?
check "kernel 沒 daemon 目錄退 2" 2 "$RC"
"$DAEMON" register /tmp >/dev/null 2>&1; RC=$?
check "aos-daemon 沒 daemon 目錄退 2" 2 "$RC"

# 36. register 一格就開出一個真的時鐘：請求檔進去、clocks/ 出來、世界真的被推
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_clock_world "$TMP/w"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; RC=$?
check "kernel 沒在跑時 aos-daemon 只丟請求、回 0" 0 "$RC"
NREQ=$(find "$AOSD/requests" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NREQ" = "1" ]; then ok "請求檔丟進 requests/"; else fail "requests/ 裡有 $NREQ 個檔"; fi
OUT=$(AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick 2>&1); RC=$?
check "kernel tick 回 0" 0 "$RC"
case "$OUT" in
  *"register"*"ok"*) ok "tick 印了處理掉哪個請求" ;;
  *) fail "tick 印的不對：$OUT" ;;
esac
CID=$(clock_id "$TMP/w")
if [ -f "$AOSD/clocks/$CID.json" ]; then
  ok "時鐘檔名就是路徑換算來的 id（$CID）"
else
  fail "$AOSD/clocks/$CID.json 沒出現"
fi
CDIR=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["dir"])' "$AOSD/clocks/$CID.json" 2>/dev/null)
CIV=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["interval"])' "$AOSD/clocks/$CID.json" 2>/dev/null)
if [ "$CDIR" = "$TMP/w" ] && [ "$(state_of "$AOSD" "$TMP/w")" = "running" ] && [ "$CIV" = "0.2" ]; then
  ok "時鐘檔記著 dir／state running／--config 的 interval"
else
  fail "時鐘檔內容不對：dir=$CDIR state=$(state_of "$AOSD" "$TMP/w") interval=$CIV"
fi
if [ -f "$AOSD/logs/$CID.log" ]; then ok "時鐘的輸出落在 logs/$CID.log"; else fail "logs/$CID.log 沒出現"; fi
REQ_TOP=$(find "$AOSD/requests" -maxdepth 1 -name '*.json' | wc -l)
DONE_N=$(find "$AOSD/requests/done" -maxdepth 1 -name '*.json' | wc -l)
if [ "$REQ_TOP" = "0" ] && [ "$DONE_N" = "1" ]; then
  ok "處理完的請求從 requests/ 搬去 requests/done/"
else
  fail "requests 頂層 $REQ_TOP 個、done $DONE_N 個"
fi
case "$(last_result "$AOSD")" in
  ok\|*) ok "done 裡的 result 是 ok" ;;
  *) fail "result 不是 ok：$(last_result "$AOSD")" ;;
esac
sleep 0.8
if [ "$(nlines "$TMP/w")" -ge 2 ]; then
  ok "時鐘是個真的 aos-loop 進程，世界一直被推（count.txt $(nlines "$TMP/w") 行）"
else
  fail "世界沒被推：count.txt $(nlines "$TMP/w") 行"
fi
CPID=$(pid_of "$AOSD" "$TMP/w")
"$DAEMON" unregister "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1
AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1
sleep 0.3
if [ ! -f "$AOSD/clocks/$CID.json" ] && ! kill -0 "$CPID" 2>/dev/null; then
  ok "unregister 把時鐘檔刪掉、進程也收掉了"
else
  fail "unregister 後檔或進程還在（pid $CPID）"
fi
kill_clocks "$AOSD"; rm -rf "$TMP"

# 37. 各種錯：資料夾不存在、重複登記、對不存在的時鐘動手、暫停兩次、壞請求檔、不認識的 op
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_clock_world "$TMP/w"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
tick() { AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1; }
"$DAEMON" register "$TMP/沒這個資料夾" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*找不到*) ok "register 不存在的資料夾：ok=false" ;;
  *) fail "應該要 fail：$(last_result "$AOSD")" ;;
esac
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; tick
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*已經有時鐘*) ok "同一個路徑只能有一個時鐘，重複登記 ok=false" ;;
  *) fail "重複登記應該要 fail：$(last_result "$AOSD")" ;;
esac
"$DAEMON" unregister "$TMP/沒登記過" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*沒有時鐘*) ok "unregister 沒登記過的：ok=false" ;;
  *) fail "應該要 fail：$(last_result "$AOSD")" ;;
esac
"$DAEMON" pause "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
"$DAEMON" pause "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*本來就暫停*) ok "暫停兩次：第二次 ok=false" ;;
  *) fail "應該要 fail：$(last_result "$AOSD")" ;;
esac
"$DAEMON" continue "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
"$DAEMON" continue "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*本來就在跑*) ok "續跑兩次：第二次 ok=false" ;;
  *) fail "應該要 fail：$(last_result "$AOSD")" ;;
esac
printf 'this is not json\n' > "$AOSD/requests/99999999-000000-000000.json"; tick
case "$(last_result "$AOSD")" in
  fail\|*讀不成*) ok "壞掉的請求檔：ok=false，一樣搬去 done/" ;;
  *) fail "壞請求應該要 fail：$(last_result "$AOSD")" ;;
esac
printf '{"op": "亂搞", "dir": "%s"}\n' "$TMP/w" > "$AOSD/requests/99999999-000001-000000.json"; tick
case "$(last_result "$AOSD")" in
  fail\|*不認識*) ok "不認識的 op：ok=false" ;;
  *) fail "怪 op 應該要 fail：$(last_result "$AOSD")" ;;
esac
if [ "$(id -u)" != "0" ]; then
  printf '{"user": "nobody"}\n' > "$TMP/asuser.json"
  make_clock_world "$TMP/w2"
  "$DAEMON" register "$TMP/w2" --config "$TMP/asuser.json" --daemon "$AOSD" >/dev/null 2>&1; tick
  case "$(last_result "$AOSD")" in
    fail\|*root*) ok "不是 root 又要換身份：ok=false，講清楚要 root" ;;
    *) fail "換身份的錯誤訊息不對：$(last_result "$AOSD")" ;;
  esac
fi
kill_clocks "$AOSD"; unset -f tick; rm -rf "$TMP"

# 38. 時鐘掛了 kernel 每格巡邏時自動重開；重開不了才標 dead，而且下一格還會再試
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_clock_world "$TMP/w"; make_clock_world "$TMP/gone2"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1
AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1
CPID=$(pid_of "$AOSD" "$TMP/w")
kill -KILL "-$CPID" 2>/dev/null
sleep 0.3
A=$(nlines "$TMP/w")
OUT=$(AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick 2>&1)
NPID=$(pid_of "$AOSD" "$TMP/w")
if [ "$(state_of "$AOSD" "$TMP/w")" = "running" ] && [ -n "$NPID" ] \
   && [ "$NPID" != "$CPID" ] && kill -0 "$NPID" 2>/dev/null; then
  ok "時鐘掛了下一格就自動重開（$CPID → $NPID），state 還是 running"
else
  fail "沒自動重開：state=$(state_of "$AOSD" "$TMP/w") 舊 $CPID 新 $NPID"
fi
if [ "$(restarts_of "$AOSD" "$TMP/w")" = "1" ]; then
  ok "時鐘檔的 restarts 加到 1"
else
  fail "restarts 是 $(restarts_of "$AOSD" "$TMP/w")"
fi
case "$OUT" in
  *"restart $TMP/w"*"(restarts 1)"*) ok "log 記了 restart 跟第幾次" ;;
  *) fail "restart 的 log 不對：$OUT" ;;
esac
sleep 0.8
if [ "$(nlines "$TMP/w")" -gt "$A" ]; then
  ok "重開的時鐘接著原本的進度繼續推（$A → $(nlines "$TMP/w") 行）"
else
  fail "重開了卻沒在推：$A → $(nlines "$TMP/w")"
fi
OUT=$(AOS_DAEMON_DIR="$AOSD" "$DKERNEL" ls 2>&1)
case "$OUT" in
  *RESTARTS*) ok "ls 有 RESTARTS 這欄" ;;
  *) fail "ls 沒有 RESTARTS 欄：$OUT" ;;
esac
# 重開不了（資料夾沒了）才標 dead，但每格都還在試，資料夾回來就自己 running
"$DAEMON" register "$TMP/gone2" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1
AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1
GPID=$(pid_of "$AOSD" "$TMP/gone2")
GWORLD="$TMP/gone2"
kill -KILL "-$GPID" 2>/dev/null; rm -rf "$GWORLD"; sleep 0.3
OUT=$(AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick 2>&1)
GERR=$(field_of "$AOSD" "$GWORLD" error)
if [ "$(state_of "$AOSD" "$GWORLD")" = "dead" ] && [ "$GERR" = "資料夾不見了" ]; then
  ok "重開不了才標 dead，error 寫著為什麼"
else
  fail "該 dead 卻是 $(state_of "$AOSD" "$GWORLD")（error=$GERR）"
fi
case "$OUT" in
  *"重開不了"*) ok "第一次標 dead 有記一行 log" ;;
  *) fail "標 dead 沒記 log：$OUT" ;;
esac
OUT=$(AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick 2>&1)
case "$OUT" in
  *"重開不了"*) fail "dead 每格都刷一行 log：$OUT" ;;
  *) ok "dead 之後每格再試但不再刷 log" ;;
esac
make_clock_world "$GWORLD"
AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1
GPID2=$(pid_of "$AOSD" "$GWORLD")
if [ "$(state_of "$AOSD" "$GWORLD")" = "running" ] && kill -0 "$GPID2" 2>/dev/null; then
  ok "資料夾回來了，下一格就自己從 dead 變回 running（pid $GPID2）"
else
  fail "資料夾回來卻是 $(state_of "$AOSD" "$GWORLD")（pid $GPID2）"
fi
kill_clocks "$AOSD"; rm -rf "$TMP"

# 39. own 的子 agent 會自己跟 daemon 要時鐘；沒設 AOS_DAEMON_DIR 就只警告一句
TMP=$(mktemp -d); AOSD="$TMP/aosd"; prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
OUT=$(AOS_DAEMON_DIR="$AOSD" "$AUSER" spawn "$TMP/agent" kid "你是 own 的小孩" --clock own 2>&1); RC=$?
check "有 AOS_DAEMON_DIR 時 own spawn 回 0" 0 "$RC"
REQOP=$(python3 - "$AOSD" <<'PYEOF2'
import glob, json, os, sys
files = sorted(glob.glob(os.path.join(sys.argv[1], "requests", "*.json")))
d = json.load(open(files[-1], encoding="utf-8")) if files else {}
print("%s %s" % (d.get("op"), d.get("dir")))
PYEOF2
)
if [ "$REQOP" = "register $TMP/agent/agent/kids/kid" ]; then
  ok "own 的子丟了一個 register 請求給 daemon"
else
  fail "請求內容不對：$REQOP（$OUT）"
fi
OUT=$("$AUSER" spawn "$TMP/agent" kid2 "你是 own 的小孩" --clock own 2>&1); RC=$?
check "沒 AOS_DAEMON_DIR 時 own spawn 還是回 0" 0 "$RC"
case "$OUT" in
  *"沒設 AOS_DAEMON_DIR"*) ok "沒設 AOS_DAEMON_DIR 就警告一句、資料夾照樣建好" ;;
  *) fail "沒警告：$OUT" ;;
esac
if [ -f "$TMP/agent/agent/kids/kid2/state.json" ]; then ok "kid2 的資料夾還是完整的"; else fail "kid2 沒建起來"; fi
rm -rf "$TMP"

# 40. 真的把 kernel 開起來跑一輪：start → register → 世界動 → pause 停住 → continue 又動
#     → stop 一起收掉。整段大約 6 秒，trap 保證不留背景進程。
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_clock_world "$TMP/w"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
LIVE_AOSD="$AOSD"
"$DKERNEL" start "$AOSD" --interval 0.2 >/dev/null 2>&1; RC=$?
check "kernel start 回 0" 0 "$RC"
KREADY=$(python3 -c '
import json,os,sys
d=json.load(open(sys.argv[1], encoding="utf-8")); pid=int(d.get("pid") or 0)
try: os.kill(pid, 0); alive=True
except OSError: alive=False
print("%s %s" % (alive, int(d.get("tick") or 0) >= 1))' "$AOSD/kernel.json")
if [ "$KREADY" = "True True" ]; then
  ok "start 回來時 kernel pid 活著而且第一格已跑完"
else
  fail "start 太早回來：$KREADY"
fi
AOS_DAEMON_DIR="$AOSD" "$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --timeout 5 >/dev/null 2>&1; RC=$?
check "start 後立刻 register 一定成功" 0 "$RC"
"$DKERNEL" start "$AOSD" >/dev/null 2>&1; RC=$?
check "已經在跑時再 start 一次退 1" 1 "$RC"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ "$(nlines "$TMP/w")" -ge 2 ] && break
  sleep 0.2
done
if [ "$(nlines "$TMP/w")" -ge 2 ]; then ok "常駐 kernel 開的時鐘真的在推世界"; else fail "世界沒動"; fi
AOS_DAEMON_DIR="$AOSD" "$DAEMON" pause "$TMP/w" --timeout 5 >/dev/null 2>&1; RC=$?
check "pause 回 0" 0 "$RC"
A=$(nlines "$TMP/w"); sleep 1; B=$(nlines "$TMP/w")
if [ "$A" = "$B" ]; then ok "暫停以後世界不動了（SIGSTOP，$A 行沒變）"; else fail "暫停了還在長：$A → $B"; fi
AOS_DAEMON_DIR="$AOSD" "$DAEMON" continue "$TMP/w" --timeout 5 >/dev/null 2>&1; RC=$?
check "continue 回 0" 0 "$RC"
sleep 1; C=$(nlines "$TMP/w")
if [ "$C" -gt "$B" ]; then ok "續跑以後世界又動了（$B → $C）"; else fail "續跑後沒動：$B → $C"; fi
OUT=$("$DKERNEL" ls "$AOSD" 2>&1)
case "$OUT" in
  *"kernel: 跑著"*running*"$TMP/w"*) ok "ls 印得出 kernel pid 跟跑著的時鐘" ;;
  *) fail "ls 印的不對：$OUT" ;;
esac
CPID=$(pid_of "$AOSD" "$TMP/w")
"$DKERNEL" stop "$AOSD" >/dev/null 2>&1; RC=$?
check "kernel stop 回 0" 0 "$RC"
sleep 0.3
if ! kill -0 "$CPID" 2>/dev/null; then ok "kernel 收工時把時鐘一起收掉"; else fail "時鐘 pid $CPID 還活著"; fi
KPID=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("pid"))' "$AOSD/kernel.json")
if [ "$KPID" = "None" ]; then ok "kernel.json 的 pid 收工時清掉了"; else fail "kernel.json 還寫著 pid=$KPID"; fi
"$DKERNEL" stop "$AOSD" >/dev/null 2>&1; RC=$?
check "沒在跑時 stop 退 1" 1 "$RC"
kill_clocks "$AOSD"; LIVE_AOSD=""; rm -rf "$TMP"

# 41. 重啟接得上：kernel 不在的時候時鐘死光，start 起來要把它們接回來繼續推
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_clock_world "$TMP/w"; make_clock_world "$TMP/gone"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1
"$DAEMON" register "$TMP/gone" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1
AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1
OLDPID=$(pid_of "$AOSD" "$TMP/w")
kill -KILL "-$OLDPID" 2>/dev/null
kill -KILL "-$(pid_of "$AOSD" "$TMP/gone")" 2>/dev/null
rm -rf "$TMP/gone"
sleep 0.3
A=$(nlines "$TMP/w")
LIVE_AOSD="$AOSD"
"$DKERNEL" start "$AOSD" --interval 0.2 >/dev/null 2>&1
for _ in 1 2 3 4 5 6 7 8 9 10; do
  NEWPID=$(pid_of "$AOSD" "$TMP/w")
  [ -n "$NEWPID" ] && [ "$NEWPID" != "$OLDPID" ] && break
  sleep 0.2
done
if [ -n "$NEWPID" ] && [ "$NEWPID" != "$OLDPID" ] && kill -0 "$NEWPID" 2>/dev/null; then
  ok "start 把死掉的時鐘接回來了（$OLDPID → $NEWPID）"
else
  fail "時鐘沒被接回來：舊 $OLDPID 新 $NEWPID"
fi
sleep 0.8
if [ "$(nlines "$TMP/w")" -gt "$A" ]; then
  ok "接回來的時鐘接著原本的進度繼續推（$A → $(nlines "$TMP/w") 行）"
else
  fail "接回來卻沒在推：$A → $(nlines "$TMP/w")"
fi
if [ "$(state_of "$AOSD" "$TMP/gone")" = "dead" ]; then
  ok "資料夾不見了的時鐘接不回來，標成 dead"
else
  fail "資料夾不見了卻是 $(state_of "$AOSD" "$TMP/gone")"
fi
"$DKERNEL" resume "$AOSD" >/dev/null 2>&1
if [ "$(pid_of "$AOSD" "$TMP/w")" = "$NEWPID" ]; then
  ok "再 resume 一次只會認領活著的時鐘，不會重複開"
else
  fail "resume 又開了一個：$(pid_of "$AOSD" "$TMP/w")"
fi
case "$(cat "$AOSD/kernel.log")" in
  *"tick 0 resume"*) ok "kernel.log 記了 tick 0 resume" ;;
  *) fail "kernel.log 沒有 resume 那行：$(cat "$AOSD/kernel.log")" ;;
esac
"$DKERNEL" stop "$AOSD" >/dev/null 2>&1
sleep 0.3
if [ -f "$AOSD/clocks/$(clock_id "$TMP/w").json" ]; then
  ok "stop 只殺進程、時鐘檔留著（下次 start 才接得回來）"
else
  fail "stop 把時鐘檔刪了"
fi
if [ "$(state_of "$AOSD" "$TMP/w")" = "running" ]; then
  ok "stop 不改時鐘檔的狀態（還是 running）"
else
  fail "stop 把狀態改成 $(state_of "$AOSD" "$TMP/w")"
fi
OUT=$("$DKERNEL" ls "$AOSD" 2>&1)
case "$OUT" in
  *"kernel: 沒在跑"*stopped*"$TMP/w"*) ok "kernel 不在時 ls 把它顯示成 stopped" ;;
  *) fail "ls 沒顯示 stopped：$OUT" ;;
esac
case "$OUT" in
  *dead*"$TMP/gone"*) ok "ls 也印得出重開不了的 dead 時鐘" ;;
  *) fail "ls 沒印出 dead 的：$OUT" ;;
esac
kill_clocks "$AOSD"; LIVE_AOSD=""; rm -rf "$TMP"

# 42. 鐘的 id 是 percent-encoding：不同路徑不會撞名，怪字元也存得回來
TMP=$(mktemp -d); AOSD="$TMP/aosd"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
W1="$TMP/a/b__c"; W2="$TMP/a__b/c"; W3="$TMP/pct % and space"
make_clock_world "$W1"; make_clock_world "$W2"; make_clock_world "$W3"
for W in "$W1" "$W2" "$W3"; do
  "$DAEMON" register "$W" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1
done
AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1
NCLK=$(find "$AOSD/clocks" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NCLK" = "3" ] && [ "$(dir_of "$AOSD" "$W1")" = "$W1" ] \
   && [ "$(dir_of "$AOSD" "$W2")" = "$W2" ]; then
  ok "a/b__c 跟 a__b/c 各自一個時鐘檔，不會撞名（$NCLK 個）"
else
  fail "撞名了：$NCLK 個檔，dir1=$(dir_of "$AOSD" "$W1") dir2=$(dir_of "$AOSD" "$W2")"
fi
ID3=$(clock_id "$W3")
BACK=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1]))' "$ID3")
if [ -f "$AOSD/clocks/$ID3.json" ] && [ "$BACK" = "$W3" ] \
   && [ "$(dir_of "$AOSD" "$W3")" = "$W3" ] && [ -f "$AOSD/logs/$ID3.log" ]; then
  ok "有 % 跟空白的路徑：id 解得回來（$ID3），log 檔名也是同一個 id"
else
  fail "% 空白的路徑沒 round-trip：id=$ID3 解回=$BACK dir=$(dir_of "$AOSD" "$W3")"
fi
kill_clocks "$AOSD"; rm -rf "$TMP"

# 43. 暫停的鐘不受 kernel 開關影響：要 continue 或重新 register 才會再跑
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_clock_world "$TMP/w"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
tick() { AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1; }
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; tick
"$DAEMON" pause "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
CPID=$(pid_of "$AOSD" "$TMP/w")
kill -KILL "-$CPID" 2>/dev/null   # stop 收掉暫停中的鐘就長這樣
sleep 0.3
tick
if [ "$(state_of "$AOSD" "$TMP/w")" = "paused" ]; then
  ok "暫停的鐘進程沒了也不會被標 dead，還是 paused"
else
  fail "暫停的鐘變成 $(state_of "$AOSD" "$TMP/w")"
fi
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*"已經有時鐘了（paused）"*) ok "對暫停的鐘 register：ok=false，叫你用 continue" ;;
  *) fail "register 暫停的鐘結果不對：$(last_result "$AOSD")" ;;
esac
OUT=$("$DKERNEL" resume "$AOSD" 2>&1)
if [ "$(state_of "$AOSD" "$TMP/w")" = "paused" ] && [ "$(pid_of "$AOSD" "$TMP/w")" = "$CPID" ]; then
  ok "kernel 起來時的 resume 不會幫暫停的鐘重開（pid 還是舊的 $CPID）"
else
  fail "resume 動了暫停的鐘：state=$(state_of "$AOSD" "$TMP/w") pid=$(pid_of "$AOSD" "$TMP/w")"
fi
case "$OUT" in
  *"tick 0 keep-paused"*) ok "resume 記了 tick 0 keep-paused" ;;
  *) fail "resume 的 log 不對：$OUT" ;;
esac
A=$(nlines "$TMP/w")
"$DAEMON" continue "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  ok\|*"重新開了一個"*) ok "continue 對進程已經沒了的暫停鐘：重開一個" ;;
  *) fail "continue 的結果不對：$(last_result "$AOSD")" ;;
esac
NPID=$(pid_of "$AOSD" "$TMP/w")
sleep 0.8
if [ "$(state_of "$AOSD" "$TMP/w")" = "running" ] && [ "$NPID" != "$CPID" ] \
   && kill -0 "$NPID" 2>/dev/null && [ "$(nlines "$TMP/w")" -gt "$A" ]; then
  ok "continue 之後世界又在長了（$A → $(nlines "$TMP/w") 行，pid $CPID → $NPID）"
else
  fail "continue 沒把它救回來：state=$(state_of "$AOSD" "$TMP/w") pid=$NPID 行數 $A → $(nlines "$TMP/w")"
fi
kill_clocks "$AOSD"; unset -f tick; rm -rf "$TMP"

# ── aos-llm v0：多引擎、優先級、用量、send/usage/ls ─────────────────────────
# 44. 優先級：三個請求 p=0/5/1，local 一次只跑一個，派工順序要是 5 → 1 → 0
TMP=$(mktemp -d); prep_llm "$TMP/llm"
Q="$TMP/llm/requests"
echo '{"priority": 0, "messages": [{"role": "user", "content": "低"}]}' > "$Q/a-p0.json"
echo '{"priority": 5, "messages": [{"role": "user", "content": "高"}]}' > "$Q/b-p5.json"
echo '{"priority": 1, "messages": [{"role": "user", "content": "中"}]}' > "$Q/c-p1.json"
SEQ=$(llm_pump "$TMP/llm" | sed -n 's/.*launch \([a-z]-p[0-9]\)\.json .*/ \1/p' | tr -d '\n')
if [ "$SEQ" = " b-p5 c-p1 a-p0" ]; then
  ok "優先級高的先做，同級照先來後到（$SEQ）"
else
  fail "優先級順序不對：$SEQ"
fi
rm -rf "$TMP"

# 45. 指定 engine：按名字挑，model 一律由引擎說了算（請求寫 model 也沒用）
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"model-a\"},
 {\"name\": \"two\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"model-b\", \"api_key_env\": \"AOS_TEST_KEY\"}]"
echo '{"echo": true, "model": "使用者亂寫的", "messages": []}' > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null
C=$(llm_content "$TMP/llm/results/0001.json")
case "$C" in
  "model=model-a "*) ok "不指定就用第一個引擎，model 由引擎決定（$C）" ;;
  *) fail "預設引擎不對：$C" ;;
esac
echo '{"engine": "two", "echo": true, "messages": []}' > "$TMP/llm/requests/0002.json"
AOS_TEST_KEY=sekret llm_pump "$TMP/llm" >/dev/null
C=$(llm_content "$TMP/llm/results/0002.json")
case "$C" in
  "model=model-b "*"auth=Bearer sekret") ok "指名 engine 就換一台，api_key_env 有變成 Authorization" ;;
  *) fail "指名引擎不對：$C" ;;
esac
E=$(llm_field "$TMP/llm/results/0002.json" 'd["aos"]["engine"]')
if [ "$E" = "two" ]; then ok "結果的 aos.engine 記著用了哪台"; else fail "aos.engine 不對：$E"; fi
rm -rf "$TMP"

# 46. 參數覆蓋：引擎 params ← 請求 params ← 請求頂層鍵，後面蓋前面
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"e\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"params\": {\"temperature\": 0.1}}]"
echo '{"echo": true, "messages": []}' > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null
case "$(llm_content "$TMP/llm/results/0001.json")" in
  *"temperature=0.1"*) ok "沒指定就吃引擎的 params" ;;
  *) fail "引擎 params 沒生效：$(llm_content "$TMP/llm/results/0001.json")" ;;
esac
echo '{"echo": true, "params": {"temperature": 0.5}, "messages": []}' > "$TMP/llm/requests/0002.json"
llm_pump "$TMP/llm" >/dev/null
case "$(llm_content "$TMP/llm/results/0002.json")" in
  *"temperature=0.5"*) ok "請求的 params 蓋掉引擎的" ;;
  *) fail "請求 params 沒蓋過去" ;;
esac
echo '{"echo": true, "params": {"temperature": 0.5}, "temperature": 0.9, "messages": []}' \
  > "$TMP/llm/requests/0003.json"
llm_pump "$TMP/llm" >/dev/null
case "$(llm_content "$TMP/llm/results/0003.json")" in
  *"temperature=0.9"*) ok "請求頂層的 temperature 又蓋掉 params 裡的" ;;
  *) fail "頂層鍵沒蓋過 params" ;;
esac
rm -rf "$TMP"

# 47. 不認得的引擎：回一個 error 結果、請求搬走，不會卡住
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"engine": "沒這台", "messages": []}' > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null; RC=$?
check "不認得的引擎還是回 0" 0 "$RC"
ERR=$(llm_field "$TMP/llm/results/0001.json" 'd["error"]' 2>/dev/null)
case "$ERR" in
  *"不認得這個引擎"*) ok "不認得的引擎有回 error：$ERR" ;;
  *) fail "不認得的引擎沒回 error：$ERR" ;;
esac
if [ -f "$TMP/llm/requests/done/0001.json" ]; then
  ok "不認得引擎的請求一樣搬去 done/"
else
  fail "不認得引擎的請求沒搬走"
fi
rm -rf "$TMP"

# 48. 用量按天累加，key 是 endpoint|model
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"messages": []}' > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null
echo '{"messages": []}' > "$TMP/llm/requests/0002.json"
llm_pump "$TMP/llm" >/dev/null
USAGE="$TMP/llm/usage/$(date +%Y-%m-%d).json"
U=$(llm_field "$USAGE" '"%s %s %s %s %s" % tuple(d["by-model"]["http://127.0.0.1:'"$PORT"'/v1|local"][k] for k in ("requests","errors","prompt_tokens","completion_tokens","total_tokens"))')
if [ "$U" = "2 0 14 6 20" ]; then
  ok "用量兩次累加起來，key 是 endpoint|model（$U）"
else
  fail "用量累加不對：$U"
fi
# 帳本是算錢用的：模型回的 usage 裡每個數字都要累加，巢狀的攤成點號鍵
R=$(llm_field "$USAGE" 'd["by-model"]["http://127.0.0.1:'"$PORT"'/v1|local"]["completion_tokens_details.reasoning_tokens"]')
if [ "$R" = "10" ]; then
  ok "巢狀的思考 token 攤成 completion_tokens_details.reasoning_tokens 也累加（$R）"
else
  fail "思考 token 沒累加：$R"
fi
C=$(llm_field "$USAGE" 'd["by-model"]["http://127.0.0.1:'"$PORT"'/v1|local"]["prompt_cache_hit_tokens"]')
if [ "$C" = "8" ]; then
  ok "供應商自己多回的 prompt_cache_hit_tokens 也累加（$C）"
else
  fail "快取命中沒累加：$C"
fi
TK=$(llm_field "$USAGE" 'd["by-model"]["http://127.0.0.1:'"$PORT"'/v1|local"]["took_ms"] >= 0')
if [ "$TK" = "True" ]; then ok "took_ms 也記在同一列"; else fail "took_ms 不在：$TK"; fi
KEYS=$(llm_field "$USAGE" '"%s %s" % (len(d["by-model"]), len(d["by-requester"]))')
if [ "$KEYS" = "1 2" ]; then ok "同一個 endpoint+model 佔一列，兩個 requester 各自分帳"; else fail "用量鍵數不對：$KEYS"; fi

# 49. aos-llm usage：印得出那張表
OUT=$("$LLM" usage --dir "$TMP/llm" 2>&1); RC=$?
check "aos-llm usage 退 0" 0 "$RC"
case "$OUT" in
  *"http://127.0.0.1:$PORT/v1|local"*) ok "usage 表印出了 endpoint|model 那一列" ;;
  *) fail "usage 印的不對：$OUT" ;;
esac
case "$OUT" in
  *"completion_tokens_details.reasoning_tokens"*"prompt_cache_hit_tokens"*)
    ok "usage 表把供應商多回的欄位也印成一欄（思考、快取）" ;;
  *) fail "usage 沒印出多出來的欄位：$OUT" ;;
esac
OUT=$("$LLM" usage 1999-01-01 --dir "$TMP/llm" 2>&1)
case "$OUT" in
  *"沒有用量紀錄"*) ok "沒紀錄那天講一句就好" ;;
  *) fail "沒紀錄那天印的不對：$OUT" ;;
esac
rm -rf "$TMP"

# 50. aos-llm 沒給 --dir 也沒設 AOS_LLM_DIR：退 2；send 這個薄包裝已經拿掉了
TMP=$(mktemp -d)
echo '{"messages": []}' > "$TMP/req.json"
OUT=$("$LLM" ls 2>&1); RC=$?
check "aos-llm ls 沒有 LLM 目錄退 2" 2 "$RC"
case "$OUT" in
  *"AOS_LLM_DIR"*) ok "沒目錄時有講 AOS_LLM_DIR" ;;
  *) fail "沒目錄時印的不對：$OUT" ;;
esac
OUT=$("$LLM" send "$TMP/req.json" 2>&1); RC=$?
if [ "$RC" != "0" ]; then
  ok "aos-llm send 沒了，叫它退 $RC"
else
  fail "aos-llm send 還在"
fi
case "$OUT" in
  *"exec"*) ok "叫錯子命令會把還有哪些子命令印出來（exec／usage／ls）" ;;
  *) fail "叫錯子命令印的不對：$OUT" ;;
esac

# 51. aos-llm ls：執行中一塊、排隊中一塊，最後每台引擎一行 running r/max
prep_llm "$TMP/llm"
python3 - "$TMP/llm/engines.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]
engines = json.load(open(p, encoding="utf-8"))
engines[0]["max_concurrent"] = 1
json.dump(engines, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
export AOS_LLM_DIR="$TMP/llm"
Q="$TMP/llm/requests"
echo '{"sleep": 3, "messages": []}' > "$Q/a-slow.json"
echo '{"priority": 7, "engine": "deepseek-flash", "sleep": 3, "messages": []}' > "$Q/b-p7.json"
echo '{"messages": []}' > "$Q/c-wait.json"
llm_tick "$TMP/llm" >/dev/null
OUT=$("$LLM" ls 2>&1); RC=$?
check "aos-llm ls 退 0" 0 "$RC"
case "$OUT" in
  *"執行中：2 個"*) ok "ls 數得出執行中幾個（走 AOS_LLM_DIR）" ;;
  *) fail "ls 的執行中不對：$OUT" ;;
esac
case "$OUT" in
  *"b-p7.json"*"engine=deepseek-flash"*"pid="*) ok "執行中那塊印了引擎跟 pid" ;;
  *) fail "執行中那塊印的不對：$OUT" ;;
esac
case "$OUT" in
  *"排隊中：1 個"*"c-wait.json"*"priority=0*"*"engine=local*"*)
    ok "排隊中那塊印了補出來的預設值（帶 *）" ;;
  *) fail "ls 的排隊中不對：$OUT" ;;
esac
case "$OUT" in
  *"engine local: running 1/1"*"engine deepseek-flash: running 1/10"*)
    ok "ls 每台引擎一行 running r/max" ;;
  *) fail "ls 的引擎那幾行不對：$OUT" ;;
esac
llm_pump "$TMP/llm" 120 >/dev/null
kill_workers "$TMP/llm"
unset AOS_LLM_DIR
rm -rf "$TMP"

# 52. 不是 LLM 資料夾（沒有 engines.json）就退 1——唯一會退非 0 的情況
TMP=$(mktemp -d)
OUT=$("$LLM" exec "$TMP" 2>&1); RC=$?
check "沒有 engines.json 的資料夾退 1" 1 "$RC"
case "$OUT" in
  *"engines.json"*) ok "不是 LLM 資料夾時講的是「沒有 engines.json」" ;;
  *) fail "印的不對：$OUT" ;;
esac
rm -rf "$TMP"

# 53. agent 那頭：llm.json 的 priority/engine 抄進請求，撿回結果後 state.json 記 last_usage
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
python3 - "$TMP/agent/agent/llm.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]
c = json.load(open(p, encoding="utf-8"))
c["priority"] = 3
c["engine"] = "local"
json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
"$AUSER" say "$TMP/agent" "哈囉" >/dev/null 2>&1
"$AGENT" exec "$TMP/agent" >/dev/null 2>&1   # idle 收信
"$AGENT" exec "$TMP/agent" >/dev/null 2>&1   # llm 丟請求
REQ=$(find "$TMP/llm/requests" -maxdepth 1 -name '*.json' | head -1)
P=$(llm_field "$REQ" '"%s %s" % (d["priority"], d["engine"])')
if [ "$P" = "3 local" ]; then
  ok "llm.json 的 priority／engine 抄進 agent 丟的請求了"
else
  fail "agent 請求沒帶上 priority／engine：$P"
fi
llm_pump "$TMP/llm" >/dev/null
"$AGENT" exec "$TMP/agent" >/dev/null 2>&1   # wait 撿回覆
LU=$(llm_field "$TMP/agent/agent/state.json" 'd["last_usage"]["total_tokens"]')
if [ "$LU" = "10" ]; then
  ok "agent 的 state.json 記下了上一次的用量 last_usage"
else
  fail "state.json 沒記 last_usage：$LU"
fi
rm -rf "$TMP"

# 54. agent 沒有 llm.json、也沒 AOS_LLM_DIR、旁邊也沒 ../llm：講清楚退 2
TMP=$(mktemp -d); prep_agent "$TMP/deep/agent"
rm "$TMP/deep/agent/agent/llm.json"
python3 -c '
import json,sys
json.dump({"state": "llm", "step": 1, "busy": 1, "request": ""},
          open(sys.argv[1], "w"))' "$TMP/deep/agent/agent/state.json"
OUT=$("$AGENT" exec "$TMP/deep/agent" 2>&1 >/dev/null); RC=$?
check "找不到 LLM 資料夾退 2" 2 "$RC"
case "$OUT" in
  *"AOS_LLM_DIR"*) ok "找不到 LLM 資料夾時有講 AOS_LLM_DIR" ;;
  *) fail "找不到 LLM 資料夾印的不對：$OUT" ;;
esac
AOS_LLM_DIR="$TMP/llmx" "$AGENT" exec "$TMP/deep/agent" >/dev/null 2>&1; RC=$?
check "設了 AOS_LLM_DIR 就走得動" 0 "$RC"
if [ -n "$(find "$TMP/llmx/requests" -maxdepth 1 -name '*.json' 2>/dev/null)" ]; then
  ok "請求丟進 AOS_LLM_DIR 指的那個世界"
else
  fail "請求沒丟進 AOS_LLM_DIR"
fi
rm -rf "$TMP"

# 55. 請求沒寫 priority／engine：用這個 LLM 資料夾自己的 defaults.json 補
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"model-a\"},
 {\"name\": \"two\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"model-b\"}]"
echo '{"engine": "two", "priority": 4}' > "$TMP/llm/defaults.json"
echo '{"echo": true, "messages": []}' > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null; RC=$?
check "沒寫 priority／engine 的請求照樣做得完，回 0" 0 "$RC"
D=$(llm_field "$TMP/llm/results/0001.json" \
  '"%s %s %s" % (d["aos"]["engine"], d["aos"]["model"], d["aos"]["priority"])')
if [ "$D" = "two model-b 4" ]; then
  ok "defaults.json 的 engine／priority 補上去了（$D）"
else
  fail "defaults.json 沒補進去：$D"
fi
rm -rf "$TMP"

# 56. 沒有 defaults.json：engine 退成 engines.json 第一台、priority 退成 0
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"model-a\"},
 {\"name\": \"two\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"model-b\"}]"
echo '{"echo": true, "messages": []}' > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null; RC=$?
check "沒有 defaults.json 也走得動，回 0" 0 "$RC"
D=$(llm_field "$TMP/llm/results/0001.json" \
  '"%s %s %s" % (d["aos"]["engine"], d["aos"]["model"], d["aos"]["priority"])')
if [ "$D" = "one model-a 0" ]; then
  ok "沒 defaults.json 就是第一台引擎＋priority 0（$D）"
else
  fail "預設值退化不對：$D"
fi
rm -rf "$TMP"

# 57. 預設值會排進優先級：defaults 說 priority 5，寫死 priority 1 的那個要排在後面；
#     aos-llm ls 把補出來的值印成 `值*`
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"engine": "local", "priority": 5}' > "$TMP/llm/defaults.json"
Q="$TMP/llm/requests"
echo '{"priority": 1, "messages": []}' > "$Q/a-p1.json"
echo '{"messages": []}' > "$Q/b-nokey.json"
OUT=$("$LLM" ls --dir "$TMP/llm" 2>&1)
FIRST=$(echo "$OUT" | sed -n 's/^  \(b-nokey.*\)$/\1/p')
case "$FIRST" in
  *"b-nokey.json"*"priority=5*"*"engine=local*"*)
    ok "ls 把資料夾預設補的 priority／engine 印成帶 * 的值，排序也照補完的算" ;;
  *) fail "ls 沒印出補完的預設值：$FIRST" ;;
esac
QFIRST=$(echo "$OUT" | sed -n '/排隊中/{n;p;}')
case "$QFIRST" in
  *"b-nokey.json"*) ok "排隊那塊第一行就是下一個會被派的（預設 priority 5 贏過寫死的 1）" ;;
  *) fail "排隊順序不對：$QFIRST" ;;
esac
L=$(llm_tick "$TMP/llm")
case "$L" in
  *"launch b-nokey.json"*"priority=5"*) ok "exec 真的先派預設 priority 比較高的那個" ;;
  *) fail "預設 priority 沒進排序：$L" ;;
esac
llm_pump "$TMP/llm" >/dev/null
rm -rf "$TMP"

# ── aos-llm exec：一台引擎一次跑幾個（max_concurrent）與 worker 死掉 ────────
# 58. max_concurrent=1：兩個慢請求，第一格只開一個、另一個排隊；做完下一格才輪到它
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 1}]"
echo '{"sleep": 2, "messages": []}' > "$TMP/llm/requests/a.json"
echo '{"sleep": 2, "messages": []}' > "$TMP/llm/requests/b.json"
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"launch a.json"*"tick 1 launched 1 running 1 queued 1"*)
    ok "一次只跑一個：第一格開 a、b 留在隊伍裡" ;;
  *) fail "max_concurrent=1 第一格不對：$OUT" ;;
esac
if [ -f "$TMP/llm/requests/b.json" ] && [ ! -f "$TMP/llm/requests/running/b.json" ]; then
  ok "排不到的請求原封不動留在 requests/ 頂層"
else
  fail "b.json 不該被派出去"
fi
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"launched 0 running 1 queued 1"*) ok "a 還在打的時候，b 就是等，exec 自己不等網路" ;;
  *) fail "該等的時候沒等：$OUT" ;;
esac
OUT=$(llm_pump "$TMP/llm" 120)
case "$OUT" in
  *"done a.json ok"*"launch b.json"*"done b.json ok"*)
    ok "a 做完那格才把 b 派出去，兩個都收得回來" ;;
  *) fail "排隊的沒接上：$OUT" ;;
esac
kill_workers "$TMP/llm"
rm -rf "$TMP"

# 59. max_concurrent=2：同一格就把兩個都開出去，兩份結果都回得來
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 2}]"
echo '{"sleep": 2, "messages": []}' > "$TMP/llm/requests/a.json"
echo '{"sleep": 2, "messages": []}' > "$TMP/llm/requests/b.json"
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"tick 1 launched 2 running 2 queued 0"*) ok "max_concurrent=2 一格就把兩個都派出去" ;;
  *) fail "max_concurrent=2 沒同時派：$OUT" ;;
esac
llm_pump "$TMP/llm" 120 >/dev/null
if [ -f "$TMP/llm/results/a.json" ] && [ -f "$TMP/llm/results/b.json" ]; then
  ok "兩個一起跑的結果都回得來"
else
  fail "同時跑的結果沒都回來"
fi
N=$(llm_field "$TMP/llm/usage/$(date +%Y-%m-%d).json" \
  'd["by-model"]["http://127.0.0.1:'"$PORT"'/v1|m"]["requests"]')
if [ "$N" = "2" ]; then ok "兩個 worker 的用量紙條都折進當天帳本了（requests=2）"; else fail "用量沒折進去：$N"; fi
kill_workers "$TMP/llm"
rm -rf "$TMP"

# 60. 兩台引擎各有各的額度（ds 2、lm 1）：四個請求混著來，第一格開三個、剩一個排隊
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"ds\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m1\", \"max_concurrent\": 2},
 {\"name\": \"lm\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m2\", \"max_concurrent\": 1}]"
for n in a b; do echo '{"engine": "ds", "sleep": 2, "messages": []}' > "$TMP/llm/requests/$n.json"; done
for n in c d; do echo '{"engine": "lm", "sleep": 2, "messages": []}' > "$TMP/llm/requests/$n.json"; done
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"tick 1 launched 3 running 3 queued 1"*) ok "ds 開兩個、lm 開一個，第四個排隊" ;;
  *) fail "兩台引擎的額度沒各算各的：$OUT" ;;
esac
LSOUT=$("$LLM" ls --dir "$TMP/llm" 2>&1)
case "$LSOUT" in
  *"engine ds: running 2/2"*"engine lm: running 1/1"*) ok "ls 看得出兩台各自跑滿了" ;;
  *) fail "ls 的引擎額度不對：$LSOUT" ;;
esac
llm_pump "$TMP/llm" 120 >/dev/null
NRES=$(find "$TMP/llm/results" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NRES" = "4" ]; then ok "四個請求最後都做完了"; else fail "只做完 $NRES 個"; fi
kill_workers "$TMP/llm"
rm -rf "$TMP"

# 61. 同一台引擎裡優先級照樣算：額度只有 1，先派 priority 高的那個
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 1}]"
echo '{"priority": 1, "sleep": 2, "messages": []}' > "$TMP/llm/requests/low.json"
echo '{"priority": 9, "sleep": 2, "messages": []}' > "$TMP/llm/requests/high.json"
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"launch high.json engine=one priority=9"*"queued 1"*)
    ok "額度只有一個時，先派 priority 高的" ;;
  *) fail "額度內的優先級不對：$OUT" ;;
esac
llm_pump "$TMP/llm" 120 >/dev/null
kill_workers "$TMP/llm"
rm -rf "$TMP"

# 62. worker 被 SIGKILL 掉：下一格補一個 "worker died" 的結果、搬去 done/、用量記一筆 error
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 1}]"
echo '{"sleep": 20, "messages": []}' > "$TMP/llm/requests/gone.json"
llm_tick "$TMP/llm" >/dev/null
WPID=$(llm_field "$TMP/llm/requests/running/gone.json" 'd["aos"]["pid"]')
kill -9 "$WPID" 2>/dev/null; sleep 0.3
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"died gone.json"*) ok "worker 死了下一格就發現（印 died）" ;;
  *) fail "沒發現 worker 死掉：$OUT" ;;
esac
ERR=$(llm_field "$TMP/llm/results/gone.json" 'd["error"]')
if [ "$ERR" = "worker died" ]; then
  ok "死掉的請求補了一個 worker died 的結果，不會有人等到天荒地老"
else
  fail "死掉的結果不對：$ERR"
fi
if [ -f "$TMP/llm/requests/done/gone.json" ] && [ ! -f "$TMP/llm/requests/running/gone.json" ]; then
  ok "死掉的請求從 running/ 搬去 done/，running/ 不會卡著"
else
  fail "死掉的請求沒搬走"
fi
E=$(llm_field "$TMP/llm/usage/$(date +%Y-%m-%d).json" \
  'd["by-model"]["http://127.0.0.1:'"$PORT"'/v1|m"]["errors"]')
if [ "$E" = "1" ]; then ok "死掉也記進當天用量（errors=1）"; else fail "用量沒記到死掉：$E"; fi
ST=$(llm_field "$TMP/llm/state.json" '"%s %s" % (d["served"], d["errors"])')
if [ "$ST" = "0 1" ]; then ok "state.json 的 errors 也算到了"; else fail "state 不對：$ST"; fi
kill_workers "$TMP/llm"
rm -rf "$TMP"

# 62b. result 被 consumer 先拿走：完成標記仍讓下一格正常收尾，不補 worker died、不灌水
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"one\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"max_concurrent\": 1}]"
echo '{"echo": true, "messages": []}' > "$TMP/llm/requests/race.json"
llm_tick "$TMP/llm" >/dev/null
for _ in $(seq 1 100); do
  [ -f "$TMP/llm/results/race.json" ] && break
  sleep 0.02
done
TAKEN=$(python3 - "$HERE" "$TMP/llm" <<'PYEOF2'
import sys
sys.path.insert(0, sys.argv[1])
import aos_llm
print(aos_llm.read_result(sys.argv[2], "race.json") is not None)
PYEOF2
)
for _ in $(seq 1 100); do
  [ -f "$TMP/llm/requests/running/race.json.done" ] && break
  sleep 0.02
done
OUT=$(llm_tick "$TMP/llm")
RACE_STATE=$(llm_field "$TMP/llm/state.json" '"%s %s" % (d["served"], d["errors"])')
RACE_BOOK=$(llm_field "$TMP/llm/usage/$(date +%Y-%m-%d).json" \
  '"%s %s" % (d["by-model"]["http://127.0.0.1:'"$PORT"'/v1|m"]["requests"], d["by-model"]["http://127.0.0.1:'"$PORT"'/v1|m"]["errors"])')
if [ "$TAKEN" = "True" ] && [ "$RACE_STATE" = "1 0" ] && [ "$RACE_BOOK" = "1 0" ] \
   && [ -f "$TMP/llm/requests/done/race.json" ] && [ ! -f "$TMP/llm/results/race.json" ]; then
  ok "result 先被拿走仍靠完成標記正常收尾，帳本只算一次"
else
  fail "result 所有權競速沒修好：taken=$TAKEN state=$RACE_STATE book=$RACE_BOOK out=$OUT"
fi
case "$OUT" in
  *"worker died"*|*"died race.json"*) fail "result 被拿走後誤判 worker died：$OUT" ;;
  *) ok "result 被拿走後下一格沒有補 worker died" ;;
esac
rm -rf "$TMP"

# 各工具包自己的測試。glob 會按檔名排序，大家共用上面的 helper 與計數。
for f in proto2/tests/*.sh; do
  if [ -n "$AOS_TEST_ONLY" ]; then
    case " $AOS_TEST_ONLY " in *" $(basename "$f" .sh) "*) ;; *) continue ;; esac
  fi
  source "$f"
done

# 63. 只檢查這輪新開的背景進程；開工前就有的管家進程不算，也不動。
sleep 0.5
AFTER=$(strays)
NEW_PIDS=""
for pid in $AFTER; do
  if ! printf '%s\n' "$BEFORE" | grep -qx "$pid"; then
    NEW_PIDS="$NEW_PIDS $pid"
  fi
done
if [ -z "$NEW_PIDS" ]; then ok "這輪沒有留下新的 aos 背景進程"; else fail "這輪留下新的 aos 進程：$NEW_PIDS"; fi

cleanup
trap - EXIT
rm -rf "$TEST_RUN_DIR"

TOTAL=$((PASSED + FAILED))
if [ "$FAILED" = "0" ]; then
  echo "全部通過：$TOTAL 條"
  exit 0
fi
echo "測試結果：$PASSED 條通過，$FAILED 條失敗，共 $TOTAL 條"
exit 1
