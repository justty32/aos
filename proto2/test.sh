#!/usr/bin/env bash
# proto2 煙霧測試：跑 aos-exec 的幾件事。有一項 FAIL 就退出 1。
HERE=$(cd "$(dirname "$0")" && pwd)
AOS="$HERE/aos-exec"
LOOP="$HERE/aos-loop"
STEP="$HERE/aos-agent-step"
LLM="$HERE/aos-llm"
SAY="$HERE/aos-agent-say"
SPAWN="$HERE/aos-agent-spawn"
LISTEN="$HERE/aos-agent-listen"
TALK="$HERE/aos-agent-talk"
DKERNEL="$HERE/aos-daemon-kernel"
DAEMON="$HERE/aos-daemon"
unset AOS_DAEMON_DIR   # 別讓外面的環境把測試的請求丟進使用者真的 daemon 目錄
unset AOS_LLM_DIR      # 同理：aos-llm 沒給 --dir 時不該撿到使用者真的 LLM 資料夾
FAILED=0

check() {  # check <名字> <期待退出碼> <實際退出碼>
  if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1（期待退出碼 $2，實際 $3）"; FAILED=1; fi
}

# LLM 的請求現在是丟給背景 worker 打的，測試絕不能留下背景進程：開跑前後都掃一遍。
strays() { pgrep -f 'aos-llm|aos-loop|aos-daemon-kernel' 2>/dev/null | tr '\n' ' '; }
BEFORE=$(strays)
if [ -z "$BEFORE" ]; then
  echo "ok   開跑前沒有殘留的 aos 背景進程"
else
  echo "FAIL 開跑前就有殘留的 aos 進程（先收掉再跑）：$BEFORE"; FAILED=1
fi

# 1. 檔案能執行
OUT=$("$AOS" "$HERE/examples/hello.sh"); RC=$?
check "檔案能執行" 0 "$RC"
case "$OUT" in
  *"hello from hello.sh"*) echo "ok   檔案的輸出有出來" ;;
  *) echo "FAIL 檔案的輸出不對：$OUT"; FAILED=1 ;;
esac

# 2. 資料夾能跑 .aos/inst，多行命令都跑到，工作目錄是那個資料夾
OUT=$("$AOS" "$HERE/examples/folder"); RC=$?
check "資料夾能跑 .aos/inst" 0 "$RC"
case "$OUT" in
  *"第一句"*) echo "ok   第一句有跑到" ;;
  *) echo "FAIL 第一句沒跑到：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *"第二句"*) echo "ok   第二句有跑到" ;;
  *) echo "FAIL 第二句沒跑到：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *"$HERE/examples/folder"*) echo "ok   工作目錄是那個資料夾" ;;
  *) echo "FAIL 工作目錄不對：$OUT"; FAILED=1 ;;
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
  *"第一步"*"第二步"*) echo "ok   兩步都跑到" ;;
  *) echo "FAIL 兩步沒跑全：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *"step 3 empty"*) echo "ok   第三圈偵測到空才停" ;;
  *) echo "FAIL 沒看到第三圈空的訊息：$OUT"; FAILED=1 ;;
esac
INST_LEFT=$(cat "$TMP/loop/.aos/inst")
if [ -z "$INST_LEFT" ]; then echo "ok   跑完 .aos/inst 是空的"; else echo "FAIL 跑完 .aos/inst 還有東西：$INST_LEFT"; FAILED=1; fi
rm -rf "$TMP"

# 7. --steps 3 --interval 0，沒給 --stop-when-empty，空的也照跑滿三步
TMP=$(mktemp -d)
OUT=$("$LOOP" "$TMP" --steps 3 --interval 0 2>&1); RC=$?
check "沒 --stop-when-empty 時空的也跑滿 steps" 0 "$RC"
N=$(echo "$OUT" | grep -c "empty")
if [ "$N" = "3" ]; then echo "ok   三步都印了 empty"; else echo "FAIL empty 次數不對（$N）：$OUT"; FAILED=1; fi
rm -rf "$TMP"

# 8. 命令失敗（exit 5）不中斷迴圈，還是跑到給定步數（第一步失敗，後兩步空的也照跑）
TMP=$(mktemp -d)
mkdir -p "$TMP/.aos"
echo "exit 5" > "$TMP/.aos/inst"
OUT=$("$LOOP" "$TMP" --steps 3 --interval 0 2>&1); RC=$?
check "命令失敗不中斷迴圈，跑滿 steps" 0 "$RC"
case "$OUT" in
  *"step 1 exit 5"*) echo "ok   失敗那步有印退出碼 5" ;;
  *) echo "FAIL 沒看到失敗退出碼：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *"step 2 empty"*"step 3 empty"*) echo "ok   失敗之後迴圈還是繼續跑到第三步" ;;
  *) echo "FAIL 迴圈在失敗後沒繼續跑：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 9. 不存在的資料夾回 2
"$LOOP" "$HERE/沒有這個資料夾" 2>/dev/null; RC=$?
check "aos-loop 資料夾不存在回 2" 2 "$RC"

# 10. 範例資料夾複本開箱即用：附帶的 .aos/inst 不用額外設定就能被 aos-loop 叫到 step
#     （.aos/inst 現在只寫 aos-agent-step . --no-write-inst，aos-loop 執行前會把自己所在
#     目錄加進 PATH，複本放到任意 mktemp -d 都找得到指令，不用再跟 examples/ 保持同一層深度；
#     沒人跑 LLM 資料夾沒關係，第一格 idle 收信、第二格 llm 把請求丟出去就換 wait，
#     一樣算走了兩格，只看 state.json 的 step 有沒有從 0 變 2。靜態檔用 git 索引裡的內容組，不直接
#     cp 真的範例——README 教使用者拿 aos-loop --keep-inst 長期盯著真的範例跑，
#     state.json／hello.json 隨時可能正被用掉，cp 會撿到不確定的當下狀態）
TMP=$(mktemp -d)
TMPLLM=$(mktemp -d)
mkdir -p "$TMP/.aos/agent/new-prompts"
git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/new-prompts/hello.json \
  > "$TMP/.aos/agent/new-prompts/hello.json"
git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/state.json \
  > "$TMP/.aos/agent/state.json"
git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/prompts.json \
  > "$TMP/.aos/agent/prompts.json"
printf '{"dir": "%s"}\n' "$TMPLLM" > "$TMP/.aos/agent/llm.json"
cp "$HERE/examples/agent/.aos/agent/system-prompt.json" "$TMP/.aos/agent/system-prompt.json"
cp "$HERE/examples/agent/.aos/agent/tools.json" "$TMP/.aos/agent/tools.json"
cp "$HERE/examples/agent/notes.txt" "$TMP/notes.txt"
cp "$HERE/examples/agent/.aos/inst" "$TMP/.aos/inst"
"$LOOP" "$TMP" --keep-inst --steps 2 --interval 0 >/dev/null 2>&1
STEP_NOW=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["step"])' \
  "$TMP/.aos/agent/state.json")
if [ "$STEP_NOW" = "2" ]; then
  echo "ok   範例資料夾複本開箱即用，aos-loop 靠附帶的 .aos/inst 跑了兩格"
else
  echo "FAIL 範例複本沒跑到兩格：step=$STEP_NOW"; FAILED=1
fi
rm -rf "$TMP" "$TMPLLM"

# 11. 資料夾沒有 .aos/inst：aos-loop 要把這件事講清楚到 stderr
TMP=$(mktemp -d)
OUT=$("$LOOP" "$TMP" --steps 1 --interval 0 2>&1 >/dev/null)
case "$OUT" in
  *"沒有 .aos/inst"*) echo "ok   aos-loop 沒 .aos/inst 時有講清楚" ;;
  *) echo "FAIL 沒看到沒有 .aos/inst 的提示：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# ── LLM 資料夾與 aos-agent-step ─────────────────────────────────────────────
# 假的 OpenAI 伺服器：看到 messages 裡還沒有 tool 結果就回一個 tool_calls（say hi），
# 已經有 tool 結果就回純文字 done。這樣同一台可以服務好幾條鏈。故意在每則回覆夾帶
# reasoning_content（私有欄位）、done 那則再夾帶空的 tool_calls: []，測 aos-agent-step
# 存進 prompts.json 時會不會把這些濾掉。每則回覆都附一個固定的 usage（7/3/10，外加巢狀的
# completion_tokens_details.reasoning_tokens=5 跟頂層 prompt_cache_hit_tokens=4），
# 讓用量那些測試好算——帳本要把這些數字全部累加起來。body 裡有 "echo": true 就改回一句話，把收到的 model／
# temperature／Authorization 原樣講回去，這樣測得到引擎選擇、參數覆蓋、api_key_env。
# body 裡有 "sleep": N 就先睡 N 秒再回，這樣「同時最多跑幾個」看得出來；因此用
# ThreadingHTTPServer，慢的那發才不會把其他人一起卡住。
PORT=18080
FAKE=$(mktemp -d)
cat > "$FAKE/fake-llm.py" <<'PYEOF2'
import http.server, json, sys, time

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
        if data.get("echo"):
            message = {"role": "assistant", "reasoning_content": "blah",
                       "content": "model=%s temperature=%s auth=%s" % (
                           data.get("model"), data.get("temperature"),
                           self.headers.get("Authorization") or "-")}
        elif any(m.get("role") == "tool" for m in msgs):
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
  kill $FAKE_PID 2>/dev/null
  pkill -f "aos-llm worker /tmp/" 2>/dev/null
  if [ -n "$LIVE_AOSD" ]; then
    "$DKERNEL" stop "$LIVE_AOSD" >/dev/null 2>&1
    kill_clocks "$LIVE_AOSD"
  fi
}
trap cleanup EXIT
python3 - "$PORT" <<'PYEOF2' || { echo "FAIL 假 LLM 伺服器起不來"; exit 1; }
import socket, sys, time
for _ in range(60):
    try:
        socket.create_connection(("127.0.0.1", int(sys.argv[1])), 0.2).close()
        sys.exit(0)
    except OSError:
        time.sleep(0.05)
sys.exit(1)
PYEOF2
echo "ok   假 LLM 伺服器起來了"

# 組兩份範例的乾淨複本（agent 一份、LLM 一份，擺成兄弟目錄，agent 的 llm.json
# 就是範例裡那個 {"dir": "../llm"}），LLM 那份的 engine 指到假伺服器。故意不直接
# cp -r 真的範例資料夾：README「怎麼玩」教使用者拿 aos-loop --keep-inst 長期盯著
# 真的範例跑，這樣 hello.json／state.json／prompts.json 會被真的用起來、內容一直在動；
# 這裡改成用 git 索引裡的內容組出靜態檔，不受工作目錄當下狀態牽連，測試才穩定。
prep_agent() {  # prep_agent <目標 agent 資料夾>；它的 llm.json 一律指向旁邊的 ../llm
  mkdir -p "$1/.aos/agent/new-prompts"
  git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/new-prompts/hello.json \
    > "$1/.aos/agent/new-prompts/hello.json"
  git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/state.json \
    > "$1/.aos/agent/state.json"
  git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/prompts.json \
    > "$1/.aos/agent/prompts.json"
  cp "$HERE/examples/agent/.aos/agent/llm.json" "$1/.aos/agent/llm.json"
  cp "$HERE/examples/agent/.aos/agent/system-prompt.json" "$1/.aos/agent/system-prompt.json"
  cp "$HERE/examples/agent/.aos/agent/tools.json" "$1/.aos/agent/tools.json"
  cp "$HERE/examples/agent/notes.txt" "$1/notes.txt"
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
now_state() {  # now_state <agent 資料夾>
  python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["state"])' "$1/.aos/agent/state.json"
}

# 12. LLM 資料夾走一格：exec 把請求派給背景 worker，結果過幾格才回來、請求搬去 requests/done/
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"messages": [{"role": "user", "content": "哈囉"}]}' \
  > "$TMP/llm/requests/0001.json"
OUT=$("$LLM" exec "$TMP/llm" 2>&1); RC=$?
check "aos-llm exec 派一個請求回 0" 0 "$RC"
case "$OUT" in
  *"launch 0001.json engine=local priority=0 pid="*) echo "ok   exec 印了 launch／請求／引擎／優先級／pid" ;;
  *) echo "FAIL exec 的 launch 行不對：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *"tick 1 launched 1 running 1 queued 0"*) echo "ok   摘要行印了 tick／launched／running／queued" ;;
  *) echo "FAIL exec 摘要行不對：$OUT"; FAILED=1 ;;
esac
if [ -f "$TMP/llm/requests/running/0001.json" ]; then
  echo "ok   派出去的請求搬進 requests/running/"
else
  echo "FAIL requests/running/0001.json 不在"; FAILED=1
fi
RUNAOS=$(llm_field "$TMP/llm/requests/running/0001.json" \
  '"%s %s" % (d["aos"]["engine"], d["aos"]["pid"] > 0)')
if [ "$RUNAOS" = "local True" ]; then
  echo "ok   running 的請求多掛了 aos（engine／pid／priority／started）"
else
  echo "FAIL running 的 aos 區塊不對：$RUNAOS"; FAILED=1
fi
OUT=$(llm_pump "$TMP/llm")
case "$OUT" in
  *"done 0001.json ok tokens=10 took="*) echo "ok   結果回來那格印了 done／tokens／took" ;;
  *) echo "FAIL 沒收回結果：$OUT"; FAILED=1 ;;
esac
if [ -f "$TMP/llm/results/0001.json" ]; then
  echo "ok   回覆落在 results/ 同檔名"
else
  echo "FAIL results/0001.json 沒出現"; FAILED=1
fi
REQ_TOP=$(find "$TMP/llm/requests" -maxdepth 1 -type f)
if [ -z "$REQ_TOP" ]; then echo "ok   requests/ 頂層清空了"; else echo "FAIL requests/ 頂層還有：$REQ_TOP"; FAILED=1; fi
RUN_LEFT=$(find "$TMP/llm/requests/running" -maxdepth 1 -type f)
if [ -z "$RUN_LEFT" ]; then echo "ok   requests/running/ 也清空了"; else echo "FAIL running/ 還有：$RUN_LEFT"; FAILED=1; fi
if [ -f "$TMP/llm/requests/done/0001.json" ]; then
  echo "ok   處理完的請求搬去 requests/done/"
else
  echo "FAIL requests/done/0001.json 不在"; FAILED=1
fi
CONTENT=$(llm_content "$TMP/llm/results/0001.json")
if [ "$CONTENT" = "" ]; then
  echo "ok   results/ 裡是整包原始回覆（這則是 tool_calls，content 空的）"
else
  echo "FAIL results/ 內容不對：$CONTENT"; FAILED=1
fi
AOS_BLOCK=$(llm_field "$TMP/llm/results/0001.json" \
  '"%s %s %s" % (d["aos"]["engine"], d["aos"]["model"], d["aos"]["usage"]["total_tokens"])')
if [ "$AOS_BLOCK" = "local local 10" ]; then
  echo "ok   結果多掛了 aos 區塊（引擎／model／用量）"
else
  echo "FAIL 結果的 aos 區塊不對：$AOS_BLOCK"; FAILED=1
fi
# 結果是先寫 .tmp 再 rename 的，撿的人不會讀到半個檔——跑完不該留下任何 .tmp
TMPLEFT=$(find "$TMP/llm" -name '*.tmp')
if [ -z "$TMPLEFT" ]; then
  echo "ok   結果是原子寫的（沒有 .tmp 殘留，讀的人不會撿到半個檔）"
else
  echo "FAIL 有 .tmp 殘留：$TMPLEFT"; FAILED=1
fi

# 13. 沒請求就什麼都不做，摘要一樣印；state.json 的 served／errors 是收回結果那格算的
OUT=$("$LLM" exec "$TMP/llm" 2>&1); RC=$?
check "aos-llm exec 沒請求也回 0" 0 "$RC"
case "$OUT" in
  *"launched 0 running 0 queued 0"*) echo "ok   沒事做也照樣印摘要，tick 往前走" ;;
  *) echo "FAIL 沒請求時印的不對：$OUT"; FAILED=1 ;;
esac
STATE=$(llm_field "$TMP/llm/state.json" '"%s %s %s" % (d["tick"] >= 3, d["served"], d["errors"])')
if [ "$STATE" = "True 1 0" ]; then
  echo "ok   state.json 記著 tick／served／errors"
else
  echo "FAIL state.json 不對：$STATE"; FAILED=1
fi
rm -rf "$TMP"

# 14. 壞掉的請求也要有結果，不然丟請求的人會等到天荒地老（這個當格就了結，不用開 worker）
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo 'this is not json' > "$TMP/llm/requests/0001.json"
OUT=$("$LLM" exec "$TMP/llm" 2>&1); RC=$?
check "壞請求 aos-llm exec 還是回 0" 0 "$RC"
case "$OUT" in
  *"bad-json 0001.json"*) echo "ok   壞請求印了 bad-json" ;;
  *) echo "FAIL 壞請求印的不對：$OUT"; FAILED=1 ;;
esac
ERR=$(python3 -c '
import json,sys
print(json.load(open(sys.argv[1])).get("error", ""))' "$TMP/llm/results/0001.json" 2>/dev/null)
if [ -n "$ERR" ]; then echo "ok   壞請求的結果檔有 error：$ERR"; else echo "FAIL 壞請求沒寫出 error 結果"; FAILED=1; fi
if [ -f "$TMP/llm/requests/done/0001.json" ]; then
  echo "ok   壞請求一樣搬去 requests/done/，不會卡住下一個"
else
  echo "FAIL 壞請求沒搬走"; FAILED=1
fi
rm -rf "$TMP"

# 15. 打不通也要回一個帶 error 的結果、請求照樣搬走（以前是留在原地，害叫的人等到天荒地老）
TMP=$(mktemp -d)
mk_engines "$TMP/llm" '[{"name": "nope", "base_url": "http://127.0.0.1:1/v1", "model": "m"}]'
echo '{"messages": [{"role": "user", "content": "哈囉"}]}' \
  > "$TMP/llm/requests/0001.json"
OUT=$(llm_pump "$TMP/llm")
case "$OUT" in
  *"done 0001.json error"*) echo "ok   打不通那格印了 done ... error" ;;
  *) echo "FAIL 打不通印的不對：$OUT"; FAILED=1 ;;
esac
ERR=$(llm_field "$TMP/llm/results/0001.json" 'd["error"]' 2>/dev/null)
case "$ERR" in
  *"打不通"*) echo "ok   打不通的結果檔有 error：$ERR" ;;
  *) echo "FAIL 打不通沒寫出 error 結果：$ERR"; FAILED=1 ;;
esac
if [ -f "$TMP/llm/requests/done/0001.json" ]; then
  echo "ok   打不通的請求一樣搬去 done/，不會卡住後面的人"
else
  echo "FAIL 打不通的請求沒搬走"; FAILED=1
fi
ERRN=$(llm_field "$TMP/llm/usage/$(date +%Y-%m-%d).json" \
  'd["http://127.0.0.1:1/v1|m"]["errors"]')
if [ "$ERRN" = "1" ]; then echo "ok   打不通也記進當天的用量（errors=1）"; else echo "FAIL 用量沒記到打不通：$ERRN"; FAILED=1; fi
ST=$(llm_field "$TMP/llm/state.json" '"%s %s" % (d["served"], d["errors"])')
if [ "$ST" = "0 1" ]; then echo "ok   state.json 的 errors 是收回結果那格算的"; else echo "FAIL state 的 served/errors 不對：$ST"; FAILED=1; fi
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
  hi-*.json) echo "ok   write_request 的 name 當前綴用（$NAME）" ;;
  *) echo "FAIL write_request 的檔名不對：$NAME"; FAILED=1 ;;
esac
if [ -f "$TMP/llm/requests/$NAME" ]; then
  echo "ok   write_request 把請求寫進 requests/"
else
  echo "FAIL write_request 沒寫進 requests/：$NAME"; FAILED=1
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
  echo "ok   read_result 撿得回整包回覆，而且拿走就沒了"
else
  echo "FAIL read_result 不對：$OUT"; FAILED=1
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
  echo "ok   沒給就不硬塞 priority／engine，給了才寫進去（$KEYS）"
else
  echo "FAIL write_request 亂改請求的鍵：$KEYS"; FAILED=1
fi
rm -rf "$TMP"

# 18. agent 跟 LLM 兩個資料夾交錯走：每圈各推一格，五格輪兩輪
#     idle→llm（丟請求）→wait（撿回覆）→act→collect→llm→wait→act→idle
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
SEQ=""
STEP_ERR=""
for i in 1 2 3 4 5 6 7 8; do
  SEQ="$SEQ$(now_state "$TMP/agent") "
  ERR=$("$STEP" "$TMP/agent" 2>&1 >/dev/null)
  STEP_ERR="$STEP_ERR
$ERR"
  llm_pump "$TMP/llm" >/dev/null
done
SEQ="$SEQ$(now_state "$TMP/agent")"
if [ "$SEQ" = "idle llm wait act collect llm wait act idle" ]; then
  echo "ok   五格的 state 依序走完兩輪"
else
  echo "FAIL state 順序不對：$SEQ"; FAILED=1
fi
# busy 只算真做事的格：8 格裡扣掉「idle -> idle」（沒信）跟「wait -> wait」（還沒等到）
# 這兩種空轉，剩下的才算 busy；假伺服器多快會影響 wait 空轉幾次，所以不寫死數字。
BUSY_NOW=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("busy"))' \
  "$TMP/agent/.aos/agent/state.json")
IDLE_SPIN=$(printf '%s' "$STEP_ERR" | grep -c 'state idle -> idle')
WAIT_SPIN=$(printf '%s' "$STEP_ERR" | grep -c 'state wait -> wait')
WANT_BUSY=$((8 - IDLE_SPIN - WAIT_SPIN))
if [ "$BUSY_NOW" = "$WANT_BUSY" ] && [ "$BUSY_NOW" -le 8 ]; then
  echo "ok   busy=$BUSY_NOW 等於 stderr 裡真做事的格數（8 格扣掉空轉的 idle/wait）"
else
  echo "FAIL busy 不對：busy=$BUSY_NOW 算出來該是 $WANT_BUSY"; FAILED=1
fi
SAID=$(cat "$TMP/agent/said.txt" 2>/dev/null)
if [ "$SAID" = "hi" ]; then echo "ok   say 工具真的寫了 said.txt"; else echo "FAIL said.txt 是 $SAID"; FAILED=1; fi
ROLES=$(python3 -c '
import json,sys
ms=json.load(open(sys.argv[1]))
print(" ".join((m.get("role") or "?") + ("+tool_calls" if m.get("tool_calls") else "") for m in ms))' \
  "$TMP/agent/.aos/agent/prompts.json")
if [ "$ROLES" = "user assistant+tool_calls tool assistant" ]; then
  echo "ok   prompts.json 四則訊息都在（含 tool_calls）"
else
  echo "FAIL prompts.json 內容不對：$ROLES"; FAILED=1
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
print(",".join(bad))' "$TMP/agent/.aos/agent/prompts.json")
if [ -z "$PRIVATE" ]; then
  echo "ok   assistant 訊息沒有 reasoning_content、也沒有空的 tool_calls key"
else
  echo "FAIL assistant 訊息還帶著私有欄位：$PRIVATE"; FAILED=1
fi
NP_TOP=$(find "$TMP/agent/.aos/agent/new-prompts" -maxdepth 1 -type f)
if [ -z "$NP_TOP" ]; then echo "ok   new-prompts/ 頂層收空了"; else echo "FAIL new-prompts/ 頂層還有檔：$NP_TOP"; FAILED=1; fi
if [ -f "$TMP/agent/.aos/agent/new-prompts/archived/hello.json" ]; then
  echo "ok   收過的信搬去 new-prompts/archived/"
else
  echo "FAIL archived/ 沒有 hello.json"; FAILED=1
fi
case "$(cat "$TMP/agent/.aos/inst")" in
  *aos-agent-step*) echo "ok   每格都把自己寫回 .aos/inst" ;;
  *) echo "FAIL .aos/inst 沒寫回"; FAILED=1 ;;
esac

# 下一次收信時 archived/ 會先被清掉：再丟一個新檔、跑一格 idle，archived 只剩新的那個
echo '{"role": "user", "content": "second"}' > "$TMP/agent/.aos/agent/new-prompts/second.json"
"$STEP" "$TMP/agent" >/dev/null 2>&1
ARCHIVED_LIST=$(ls "$TMP/agent/.aos/agent/new-prompts/archived")
if [ "$ARCHIVED_LIST" = "second.json" ]; then
  echo "ok   下一輪收信前先清空 archived，只剩這輪收的、上一輪的 hello.json 不見了"
else
  echo "FAIL archived/ 內容不對：$ARCHIVED_LIST"; FAILED=1
fi
rm -rf "$TMP"

# 19. --no-write-inst 就真的不寫
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
"$STEP" "$TMP/agent" --no-write-inst >/dev/null 2>&1
if [ ! -e "$TMP/agent/.aos/inst" ]; then echo "ok   --no-write-inst 不寫 .aos/inst"; else echo "FAIL --no-write-inst 還是寫了"; FAILED=1; fi
rm -rf "$TMP"

# 20. 兩個 aos-loop 各轉各的：agent 那圈 step 自己寫回 .aos/inst，LLM 那圈在背景一直撿請求
#     （agent 只要 8 格就走得完，給 30 格是留給「這格 wait 還沒等到」的空轉，
#     多出來的格數在 idle 空等，不影響結果）
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
"$LOOP" "$TMP/llm" --keep-inst --steps 2000 --interval 0 >/dev/null 2>&1 &
LLM_LOOP=$!
echo "$STEP ." > "$TMP/agent/.aos/inst"
"$LOOP" "$TMP/agent" --steps 30 --interval 0.05 >/dev/null 2>&1
kill $LLM_LOOP 2>/dev/null; wait $LLM_LOOP 2>/dev/null
if [ "$(cat "$TMP/agent/said.txt" 2>/dev/null)" = "hi" ] && [ "$(now_state "$TMP/agent")" = "idle" ]; then
  echo "ok   兩個 aos-loop 交錯跑完同一條鏈"
else
  echo "FAIL aos-loop 沒跑完：said=$(cat "$TMP/agent/said.txt" 2>/dev/null) state=$(now_state "$TMP/agent")"; FAILED=1
fi
rm -rf "$TMP"

# 21. 推薦用法：.aos/inst 寫一次，aos-loop --keep-inst 不清空，step 也不用寫回
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
"$LOOP" "$TMP/llm" --keep-inst --steps 2000 --interval 0 >/dev/null 2>&1 &
LLM_LOOP=$!
cp "$HERE/examples/agent/.aos/inst" "$TMP/agent/.aos/inst"
"$LOOP" "$TMP/agent" --steps 30 --interval 0.05 --keep-inst >/dev/null 2>&1
kill $LLM_LOOP 2>/dev/null; wait $LLM_LOOP 2>/dev/null
if [ "$(cat "$TMP/agent/said.txt" 2>/dev/null)" = "hi" ] && [ "$(now_state "$TMP/agent")" = "idle" ]; then
  echo "ok   --keep-inst + --no-write-inst 也跑得完"
else
  echo "FAIL --keep-inst 那條鏈沒跑完：state=$(now_state "$TMP/agent")"; FAILED=1
fi
case "$(cat "$TMP/agent/.aos/inst")" in
  *aos-agent-step*) echo "ok   --keep-inst 跑完 .aos/inst 原樣還在" ;;
  *) echo "FAIL --keep-inst 把 .aos/inst 弄掉了"; FAILED=1 ;;
esac
rm -rf "$TMP"

# ── 一個檔可以多則、回話落地、say／listen／talk ──────────────────────────────
# 22. new-prompts 裡一個檔放一串（兩則）訊息，跑一格 idle 就收成兩則
TMP=$(mktemp -d); prep_agent "$TMP/agent"
rm -f "$TMP/agent/.aos/agent/new-prompts/hello.json"
echo '[{"role": "user", "content": "一"}, {"role": "user", "content": "二"}, 3]' \
  > "$TMP/agent/.aos/agent/new-prompts/pair.json"
"$STEP" "$TMP/agent" --no-write-inst >/dev/null 2>&1
N=$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))))' \
  "$TMP/agent/.aos/agent/new-prompts.json")
if [ "$N" = "2" ]; then
  echo "ok   一個檔放一串就收成兩則（陣列裡不是物件的那項跳過）"
else
  echo "FAIL 一串收成 $N 則"; FAILED=1
fi
rm -rf "$TMP"

# 23. aos-agent-say：一句話丟進 new-prompts/
TMP=$(mktemp -d)
"$SAY" "$TMP" "嗨呀" 2>/dev/null
NFILE=$(find "$TMP/.aos/agent/new-prompts" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NFILE" = "1" ]; then echo "ok   aos-agent-say 寫出一個檔"; else echo "FAIL say 寫了 $NFILE 個檔"; FAILED=1; fi
SAID=$(python3 -c '
import glob,json,sys
m=json.load(open(sorted(glob.glob(sys.argv[1]+"/*.json"))[0], encoding="utf-8"))
print(m.get("role"), m.get("content"))' "$TMP/.aos/agent/new-prompts")
if [ "$SAID" = "user 嗨呀" ]; then echo "ok   say 寫的內容是 user／嗨呀"; else echo "FAIL say 內容不對：$SAID"; FAILED=1; fi
rm -rf "$TMP"

# 24. 完整鏈跑完，agent 的回話落在 replies/
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
for i in 1 2 3 4 5 6 7 8; do
  "$STEP" "$TMP/agent" --no-write-inst >/dev/null 2>&1
  llm_pump "$TMP/llm" >/dev/null
done
NREP=$(find "$TMP/agent/.aos/agent/replies" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NREP" = "1" ]; then echo "ok   replies/ 只有一個回話檔"; else echo "FAIL replies/ 有 $NREP 個檔"; FAILED=1; fi
REP=$(python3 -c '
import glob,json,sys
print(json.load(open(sorted(glob.glob(sys.argv[1]+"/*.json"))[0], encoding="utf-8"))["content"])' \
  "$TMP/agent/.aos/agent/replies")
if [ "$REP" = "done" ]; then echo "ok   回話檔的 content 是 done"; else echo "FAIL 回話檔 content 是 $REP"; FAILED=1; fi

# 25. aos-agent-listen --once 把既有的印出來就走
OUT=$(timeout 10 "$LISTEN" "$TMP/agent" --once); RC=$?
check "listen --once 退出 0" 0 "$RC"
case "$OUT" in
  *"--- reply "*"done"*) echo "ok   listen --once 印得出 done" ;;
  *) echo "FAIL listen --once 印的不對：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 26. aos-agent-listen --new --once：跳過既有的，等到新的那則才印、才退出
TMP=$(mktemp -d); mkdir -p "$TMP/.aos/agent/replies"
echo '{"role": "assistant", "content": "舊的"}' > "$TMP/.aos/agent/replies/0001.json"
( sleep 1; echo '{"role": "assistant", "content": "新的"}' > "$TMP/.aos/agent/replies/0002.json" ) &
OUT=$(timeout 10 "$LISTEN" "$TMP" --new --once); RC=$?
check "listen --new --once 等到新的就退出 0" 0 "$RC"
case "$OUT" in
  *"舊的"*) echo "FAIL --new 不該印既有的：$OUT"; FAILED=1 ;;
  *"--- reply 0002 ---"*"新的"*) echo "ok   listen --new --once 只印新出現的那則" ;;
  *) echo "FAIL listen --new --once 印的不對：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 27. aos-agent-talk：打一句、等到回話印出來
TMP=$(mktemp -d); mkdir -p "$TMP/.aos/agent/new-prompts" "$TMP/.aos/agent/replies"
( for i in $(seq 1 100); do
    if [ -n "$(find "$TMP/.aos/agent/new-prompts" -maxdepth 1 -name '*.json' 2>/dev/null)" ]; then
      echo '{"role": "assistant", "content": "我在"}' > "$TMP/.aos/agent/replies/9999.json"
      break
    fi
    sleep 0.1
  done ) &
OUT=$(printf '哈囉\n/quit\n' | timeout 10 "$TALK" "$TMP"); RC=$?
check "talk 打完 /quit 退出 0" 0 "$RC"
case "$OUT" in
  *"agent> 我在"*) echo "ok   talk 印出了 agent 的回話" ;;
  *) echo "FAIL talk 沒印出回話：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# ── 子世界：aos-agent-spawn ──────────────────────────────────────────────────
# 28. shared 鐘：子的檔都在、llm.json 解得到真的 LLM 資料夾、工具抄父的、父的 inst 尾巴掛上子
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
cp "$HERE/examples/agent/.aos/inst" "$TMP/agent/.aos/inst"
"$SPAWN" "$TMP/agent" kid1 "你是小幫手 kid1" 2>/dev/null; RC=$?
check "spawn shared 回 0" 0 "$RC"
MISSING=""
for f in system-prompt.json prompts.json tools.json state.json llm.json; do
  [ -f "$TMP/agent/kid1/.aos/agent/$f" ] || MISSING="$MISSING $f"
done
[ -f "$TMP/agent/kid1/.aos/inst" ] || MISSING="$MISSING .aos/inst"
if [ -z "$MISSING" ]; then echo "ok   子 agent 五個檔加 .aos/inst 都在"; else echo "FAIL 子少了：$MISSING"; FAILED=1; fi
LLMDIR=$(python3 -c '
import json,os,sys
d=json.load(open(sys.argv[1]+"/.aos/agent/llm.json", encoding="utf-8"))["dir"]
print(d if os.path.isdir(os.path.join(sys.argv[1], d)) else "")' "$TMP/agent/kid1")
if [ -n "$LLMDIR" ]; then
  echo "ok   子的 llm.json（$LLMDIR）解出來真的是那個 LLM 資料夾"
else
  echo "FAIL 子的 llm.json 指到不存在的地方"; FAILED=1
fi
if cmp -s "$TMP/agent/kid1/.aos/agent/tools.json" "$TMP/agent/.aos/agent/tools.json"; then
  echo "ok   子的 tools.json 跟父一模一樣"
else
  echo "FAIL 子的 tools.json 跟父不一樣"; FAILED=1
fi
LAST=$(tail -1 "$TMP/agent/.aos/inst")
if [ "$LAST" = "aos-exec kid1" ]; then
  echo "ok   shared 鐘掛在父的 .aos/inst 最後一行"
else
  echo "FAIL 父的 inst 最後一行是「$LAST」"; FAILED=1
fi

# 29. own 鐘：只建資料夾，父的 inst 不動它
"$SPAWN" "$TMP/agent" kid2 "你是 kid2" --clock own 2>/dev/null; RC=$?
check "spawn own 回 0" 0 "$RC"
if [ -f "$TMP/agent/kid2/.aos/inst" ] && ! grep -q "aos-exec kid2" "$TMP/agent/.aos/inst"; then
  echo "ok   own 鐘的子建好了但沒掛進父的 inst"
else
  echo "FAIL own 鐘的子不該進父的 inst：$(cat "$TMP/agent/.aos/inst")"; FAILED=1
fi

# 30. 同名再生一次退 2；子名有奇怪字元退 2
"$SPAWN" "$TMP/agent" kid1 "重複的" 2>/dev/null; RC=$?
check "同名再 spawn 一次回 2" 2 "$RC"
"$SPAWN" "$TMP/agent" "bad/name" "壞名字" 2>/dev/null; RC=$?
check "子名有斜線回 2" 2 "$RC"

# 31. 父走三格：shared 的 kid1 跟著走三格，own 的 kid2 一格都沒走
"$SAY" "$TMP/agent/kid1" "kid1 你好" 2>/dev/null
"$SAY" "$TMP/agent/kid2" "kid2 你好" 2>/dev/null
"$LOOP" "$TMP/agent" --keep-inst --steps 3 --interval 0 >/dev/null 2>&1
STEP_P=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["step"])' "$TMP/agent/.aos/agent/state.json")
STEP_1=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["step"])' "$TMP/agent/kid1/.aos/agent/state.json")
STEP_2=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["step"])' "$TMP/agent/kid2/.aos/agent/state.json")
if [ "$STEP_P" = "3" ]; then echo "ok   父自己走了三格"; else echo "FAIL 父走了 $STEP_P 格"; FAILED=1; fi
if [ "$STEP_1" = "3" ]; then echo "ok   shared 的 kid1 跟著父走了三格"; else echo "FAIL kid1 走了 $STEP_1 格"; FAILED=1; fi
if [ "$STEP_2" = "0" ]; then echo "ok   own 的 kid2 一格都沒走（時間跟父脫節）"; else echo "FAIL kid2 走了 $STEP_2 格"; FAILED=1; fi

# 32. 子真的能透過同一個 LLM 資料夾工作：父帶著跑，kid1 的 replies/ 要冒出回話
"$LOOP" "$TMP/llm" --keep-inst --steps 2000 --interval 0 >/dev/null 2>&1 &
LLM_LOOP=$!
"$LOOP" "$TMP/agent" --keep-inst --steps 30 --interval 0.05 >/dev/null 2>&1
kill $LLM_LOOP 2>/dev/null; wait $LLM_LOOP 2>/dev/null
NREP=$(find "$TMP/agent/kid1/.aos/agent/replies" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
if [ "$NREP" -ge 1 ]; then
  echo "ok   kid1 靠父的鐘跑完一輪，replies/ 有回話（共用同一個 LLM 資料夾）"
else
  echo "FAIL kid1 沒有回話：state=$(now_state "$TMP/agent/kid1")"; FAILED=1
fi
rm -rf "$TMP"

# 33. tools.json 裡的 spawn 工具，command 直接餵 JSON 就能生出子 agent
TMP=$(mktemp -d); prep_agent "$TMP/agent"
CMD=$(python3 -c '
import json,sys
print([t for t in json.load(open(sys.argv[1], encoding="utf-8")) if t["name"]=="spawn"][0]["command"])' \
  "$TMP/agent/.aos/agent/tools.json")
OUT=$(cd "$TMP/agent" && PATH="$HERE:$PATH" sh -c "$CMD" <<'JSONEOF'
{"name": "kid3", "persona": "你是小幫手"}
JSONEOF
)
if [ -f "$TMP/agent/kid3/.aos/agent/system-prompt.json" ]; then
  echo "ok   spawn 工具的 command 直接跑就生得出 kid3"
else
  echo "FAIL spawn 工具沒生出 kid3：$OUT"; FAILED=1
fi
case "$OUT" in
  *"建好了"*) echo "ok   spawn 工具把結果講回給模型聽" ;;
  *) echo "FAIL spawn 工具沒把話講回來：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 34. shared 鐘子空轉：沒人跟它說話，父推它走幾格它就跟著走幾格，但都是 idle -> idle，busy 不漲
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
cp "$HERE/examples/agent/.aos/inst" "$TMP/agent/.aos/inst"
"$SPAWN" "$TMP/agent" kid1 "你是小幫手 kid1" 2>/dev/null
"$LOOP" "$TMP/agent" --keep-inst --steps 3 --interval 0 >/dev/null 2>&1
KID_STEP=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["step"])' \
  "$TMP/agent/kid1/.aos/agent/state.json")
KID_BUSY=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("busy"))' \
  "$TMP/agent/kid1/.aos/agent/state.json")
if [ "$KID_STEP" = "3" ] && [ "$KID_BUSY" = "0" ]; then
  echo "ok   shared 子空轉三格：沒信可收，step=3 busy=0"
else
  echo "FAIL 子空轉的 step/busy 不對：step=$KID_STEP busy=$KID_BUSY"; FAILED=1
fi
rm -rf "$TMP"

# ── daemon：常駐 kernel＋一個世界一個時鐘 ───────────────────────────────────
# 幫手：做一個每格往 count.txt 加一行的世界、把某個 daemon 目錄裡的時鐘全砍掉
# （測試絕不能留背景進程）、讀最新一筆處理完的請求結果、算 count.txt 幾行。
make_world() {  # make_world <資料夾>
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
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_world "$TMP/w"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; RC=$?
check "kernel 沒在跑時 aos-daemon 只丟請求、回 0" 0 "$RC"
NREQ=$(find "$AOSD/requests" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NREQ" = "1" ]; then echo "ok   請求檔丟進 requests/"; else echo "FAIL requests/ 裡有 $NREQ 個檔"; FAILED=1; fi
OUT=$(AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick 2>&1); RC=$?
check "kernel tick 回 0" 0 "$RC"
case "$OUT" in
  *"register"*"ok"*) echo "ok   tick 印了處理掉哪個請求" ;;
  *) echo "FAIL tick 印的不對：$OUT"; FAILED=1 ;;
esac
CID=$(clock_id "$TMP/w")
if [ -f "$AOSD/clocks/$CID.json" ]; then
  echo "ok   時鐘檔名就是路徑換算來的 id（$CID）"
else
  echo "FAIL $AOSD/clocks/$CID.json 沒出現"; FAILED=1
fi
CDIR=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["dir"])' "$AOSD/clocks/$CID.json" 2>/dev/null)
CIV=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["interval"])' "$AOSD/clocks/$CID.json" 2>/dev/null)
if [ "$CDIR" = "$TMP/w" ] && [ "$(state_of "$AOSD" "$TMP/w")" = "running" ] && [ "$CIV" = "0.2" ]; then
  echo "ok   時鐘檔記著 dir／state running／--config 的 interval"
else
  echo "FAIL 時鐘檔內容不對：dir=$CDIR state=$(state_of "$AOSD" "$TMP/w") interval=$CIV"; FAILED=1
fi
if [ -f "$AOSD/logs/$CID.log" ]; then echo "ok   時鐘的輸出落在 logs/$CID.log"; else echo "FAIL logs/$CID.log 沒出現"; FAILED=1; fi
REQ_TOP=$(find "$AOSD/requests" -maxdepth 1 -name '*.json' | wc -l)
DONE_N=$(find "$AOSD/requests/done" -maxdepth 1 -name '*.json' | wc -l)
if [ "$REQ_TOP" = "0" ] && [ "$DONE_N" = "1" ]; then
  echo "ok   處理完的請求從 requests/ 搬去 requests/done/"
else
  echo "FAIL requests 頂層 $REQ_TOP 個、done $DONE_N 個"; FAILED=1
fi
case "$(last_result "$AOSD")" in
  ok\|*) echo "ok   done 裡的 result 是 ok" ;;
  *) echo "FAIL result 不是 ok：$(last_result "$AOSD")"; FAILED=1 ;;
esac
sleep 0.8
if [ "$(nlines "$TMP/w")" -ge 2 ]; then
  echo "ok   時鐘是個真的 aos-loop 進程，世界一直被推（count.txt $(nlines "$TMP/w") 行）"
else
  echo "FAIL 世界沒被推：count.txt $(nlines "$TMP/w") 行"; FAILED=1
fi
CPID=$(pid_of "$AOSD" "$TMP/w")
"$DAEMON" unregister "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1
AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1
sleep 0.3
if [ ! -f "$AOSD/clocks/$CID.json" ] && ! kill -0 "$CPID" 2>/dev/null; then
  echo "ok   unregister 把時鐘檔刪掉、進程也收掉了"
else
  echo "FAIL unregister 後檔或進程還在（pid $CPID）"; FAILED=1
fi
kill_clocks "$AOSD"; rm -rf "$TMP"

# 37. 各種錯：資料夾不存在、重複登記、對不存在的時鐘動手、暫停兩次、壞請求檔、不認識的 op
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_world "$TMP/w"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
tick() { AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1; }
"$DAEMON" register "$TMP/沒這個資料夾" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*找不到*) echo "ok   register 不存在的資料夾：ok=false" ;;
  *) echo "FAIL 應該要 fail：$(last_result "$AOSD")"; FAILED=1 ;;
esac
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; tick
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*已經有時鐘*) echo "ok   同一個路徑只能有一個時鐘，重複登記 ok=false" ;;
  *) echo "FAIL 重複登記應該要 fail：$(last_result "$AOSD")"; FAILED=1 ;;
esac
"$DAEMON" unregister "$TMP/沒登記過" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*沒有時鐘*) echo "ok   unregister 沒登記過的：ok=false" ;;
  *) echo "FAIL 應該要 fail：$(last_result "$AOSD")"; FAILED=1 ;;
esac
"$DAEMON" pause "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
"$DAEMON" pause "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*本來就暫停*) echo "ok   暫停兩次：第二次 ok=false" ;;
  *) echo "FAIL 應該要 fail：$(last_result "$AOSD")"; FAILED=1 ;;
esac
"$DAEMON" continue "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
"$DAEMON" continue "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*本來就在跑*) echo "ok   續跑兩次：第二次 ok=false" ;;
  *) echo "FAIL 應該要 fail：$(last_result "$AOSD")"; FAILED=1 ;;
esac
printf 'this is not json\n' > "$AOSD/requests/99999999-000000-000000.json"; tick
case "$(last_result "$AOSD")" in
  fail\|*讀不成*) echo "ok   壞掉的請求檔：ok=false，一樣搬去 done/" ;;
  *) echo "FAIL 壞請求應該要 fail：$(last_result "$AOSD")"; FAILED=1 ;;
esac
printf '{"op": "亂搞", "dir": "%s"}\n' "$TMP/w" > "$AOSD/requests/99999999-000001-000000.json"; tick
case "$(last_result "$AOSD")" in
  fail\|*不認識*) echo "ok   不認識的 op：ok=false" ;;
  *) echo "FAIL 怪 op 應該要 fail：$(last_result "$AOSD")"; FAILED=1 ;;
esac
if [ "$(id -u)" != "0" ]; then
  printf '{"user": "nobody"}\n' > "$TMP/asuser.json"
  make_world "$TMP/w2"
  "$DAEMON" register "$TMP/w2" --config "$TMP/asuser.json" --daemon "$AOSD" >/dev/null 2>&1; tick
  case "$(last_result "$AOSD")" in
    fail\|*root*) echo "ok   不是 root 又要換身份：ok=false，講清楚要 root" ;;
    *) echo "FAIL 換身份的錯誤訊息不對：$(last_result "$AOSD")"; FAILED=1 ;;
  esac
fi
kill_clocks "$AOSD"; unset -f tick; rm -rf "$TMP"

# 38. 時鐘掛了 kernel 每格巡邏時自動重開；重開不了才標 dead，而且下一格還會再試
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_world "$TMP/w"; make_world "$TMP/gone2"
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
  echo "ok   時鐘掛了下一格就自動重開（$CPID → $NPID），state 還是 running"
else
  echo "FAIL 沒自動重開：state=$(state_of "$AOSD" "$TMP/w") 舊 $CPID 新 $NPID"; FAILED=1
fi
if [ "$(restarts_of "$AOSD" "$TMP/w")" = "1" ]; then
  echo "ok   時鐘檔的 restarts 加到 1"
else
  echo "FAIL restarts 是 $(restarts_of "$AOSD" "$TMP/w")"; FAILED=1
fi
case "$OUT" in
  *"restart $TMP/w"*"(restarts 1)"*) echo "ok   log 記了 restart 跟第幾次" ;;
  *) echo "FAIL restart 的 log 不對：$OUT"; FAILED=1 ;;
esac
sleep 0.8
if [ "$(nlines "$TMP/w")" -gt "$A" ]; then
  echo "ok   重開的時鐘接著原本的進度繼續推（$A → $(nlines "$TMP/w") 行）"
else
  echo "FAIL 重開了卻沒在推：$A → $(nlines "$TMP/w")"; FAILED=1
fi
OUT=$(AOS_DAEMON_DIR="$AOSD" "$DKERNEL" ls 2>&1)
case "$OUT" in
  *RESTARTS*) echo "ok   ls 有 RESTARTS 這欄" ;;
  *) echo "FAIL ls 沒有 RESTARTS 欄：$OUT"; FAILED=1 ;;
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
  echo "ok   重開不了才標 dead，error 寫著為什麼"
else
  echo "FAIL 該 dead 卻是 $(state_of "$AOSD" "$GWORLD")（error=$GERR）"; FAILED=1
fi
case "$OUT" in
  *"重開不了"*) echo "ok   第一次標 dead 有記一行 log" ;;
  *) echo "FAIL 標 dead 沒記 log：$OUT"; FAILED=1 ;;
esac
OUT=$(AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick 2>&1)
case "$OUT" in
  *"重開不了"*) echo "FAIL dead 每格都刷一行 log：$OUT"; FAILED=1 ;;
  *) echo "ok   dead 之後每格再試但不再刷 log" ;;
esac
make_world "$GWORLD"
AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1
GPID2=$(pid_of "$AOSD" "$GWORLD")
if [ "$(state_of "$AOSD" "$GWORLD")" = "running" ] && kill -0 "$GPID2" 2>/dev/null; then
  echo "ok   資料夾回來了，下一格就自己從 dead 變回 running（pid $GPID2）"
else
  echo "FAIL 資料夾回來卻是 $(state_of "$AOSD" "$GWORLD")（pid $GPID2）"; FAILED=1
fi
kill_clocks "$AOSD"; rm -rf "$TMP"

# 39. own 的子 agent 會自己跟 daemon 要時鐘；沒設 AOS_DAEMON_DIR 就只警告一句
TMP=$(mktemp -d); AOSD="$TMP/aosd"; prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
OUT=$(AOS_DAEMON_DIR="$AOSD" "$SPAWN" "$TMP/agent" kid --clock own "你是 own 的小孩" 2>&1); RC=$?
check "有 AOS_DAEMON_DIR 時 own spawn 回 0" 0 "$RC"
REQOP=$(python3 - "$AOSD" <<'PYEOF2'
import glob, json, os, sys
files = sorted(glob.glob(os.path.join(sys.argv[1], "requests", "*.json")))
d = json.load(open(files[-1], encoding="utf-8")) if files else {}
print("%s %s" % (d.get("op"), d.get("dir")))
PYEOF2
)
if [ "$REQOP" = "register $TMP/agent/kid" ]; then
  echo "ok   own 的子丟了一個 register 請求給 daemon"
else
  echo "FAIL 請求內容不對：$REQOP（$OUT）"; FAILED=1
fi
OUT=$("$SPAWN" "$TMP/agent" kid2 --clock own "你是 own 的小孩" 2>&1); RC=$?
check "沒 AOS_DAEMON_DIR 時 own spawn 還是回 0" 0 "$RC"
case "$OUT" in
  *"沒設 AOS_DAEMON_DIR"*) echo "ok   沒設 AOS_DAEMON_DIR 就警告一句、資料夾照樣建好" ;;
  *) echo "FAIL 沒警告：$OUT"; FAILED=1 ;;
esac
if [ -f "$TMP/agent/kid2/.aos/agent/state.json" ]; then echo "ok   kid2 的資料夾還是完整的"; else echo "FAIL kid2 沒建起來"; FAILED=1; fi
rm -rf "$TMP"

# 40. 真的把 kernel 開起來跑一輪：start → register → 世界動 → pause 停住 → continue 又動
#     → stop 一起收掉。整段大約 6 秒，trap 保證不留背景進程。
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_world "$TMP/w"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
LIVE_AOSD="$AOSD"
"$DKERNEL" start "$AOSD" --interval 0.2 >/dev/null 2>&1; RC=$?
check "kernel start 回 0" 0 "$RC"
"$DKERNEL" start "$AOSD" >/dev/null 2>&1; RC=$?
check "已經在跑時再 start 一次退 1" 1 "$RC"
AOS_DAEMON_DIR="$AOSD" "$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --timeout 5 >/dev/null 2>&1; RC=$?
check "kernel 跑著時 register 等得到 ok 回 0" 0 "$RC"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ "$(nlines "$TMP/w")" -ge 2 ] && break
  sleep 0.2
done
if [ "$(nlines "$TMP/w")" -ge 2 ]; then echo "ok   常駐 kernel 開的時鐘真的在推世界"; else echo "FAIL 世界沒動"; FAILED=1; fi
AOS_DAEMON_DIR="$AOSD" "$DAEMON" pause "$TMP/w" --timeout 5 >/dev/null 2>&1; RC=$?
check "pause 回 0" 0 "$RC"
A=$(nlines "$TMP/w"); sleep 1; B=$(nlines "$TMP/w")
if [ "$A" = "$B" ]; then echo "ok   暫停以後世界不動了（SIGSTOP，$A 行沒變）"; else echo "FAIL 暫停了還在長：$A → $B"; FAILED=1; fi
AOS_DAEMON_DIR="$AOSD" "$DAEMON" continue "$TMP/w" --timeout 5 >/dev/null 2>&1; RC=$?
check "continue 回 0" 0 "$RC"
sleep 1; C=$(nlines "$TMP/w")
if [ "$C" -gt "$B" ]; then echo "ok   續跑以後世界又動了（$B → $C）"; else echo "FAIL 續跑後沒動：$B → $C"; FAILED=1; fi
OUT=$("$DKERNEL" ls "$AOSD" 2>&1)
case "$OUT" in
  *"kernel: 跑著"*running*"$TMP/w"*) echo "ok   ls 印得出 kernel pid 跟跑著的時鐘" ;;
  *) echo "FAIL ls 印的不對：$OUT"; FAILED=1 ;;
esac
CPID=$(pid_of "$AOSD" "$TMP/w")
"$DKERNEL" stop "$AOSD" >/dev/null 2>&1; RC=$?
check "kernel stop 回 0" 0 "$RC"
sleep 0.3
if ! kill -0 "$CPID" 2>/dev/null; then echo "ok   kernel 收工時把時鐘一起收掉"; else echo "FAIL 時鐘 pid $CPID 還活著"; FAILED=1; fi
KPID=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("pid"))' "$AOSD/kernel.json")
if [ "$KPID" = "None" ]; then echo "ok   kernel.json 的 pid 收工時清掉了"; else echo "FAIL kernel.json 還寫著 pid=$KPID"; FAILED=1; fi
"$DKERNEL" stop "$AOSD" >/dev/null 2>&1; RC=$?
check "沒在跑時 stop 退 1" 1 "$RC"
kill_clocks "$AOSD"; LIVE_AOSD=""; rm -rf "$TMP"

# 41. 重啟接得上：kernel 不在的時候時鐘死光，start 起來要把它們接回來繼續推
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_world "$TMP/w"; make_world "$TMP/gone"
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
  echo "ok   start 把死掉的時鐘接回來了（$OLDPID → $NEWPID）"
else
  echo "FAIL 時鐘沒被接回來：舊 $OLDPID 新 $NEWPID"; FAILED=1
fi
sleep 0.8
if [ "$(nlines "$TMP/w")" -gt "$A" ]; then
  echo "ok   接回來的時鐘接著原本的進度繼續推（$A → $(nlines "$TMP/w") 行）"
else
  echo "FAIL 接回來卻沒在推：$A → $(nlines "$TMP/w")"; FAILED=1
fi
if [ "$(state_of "$AOSD" "$TMP/gone")" = "dead" ]; then
  echo "ok   資料夾不見了的時鐘接不回來，標成 dead"
else
  echo "FAIL 資料夾不見了卻是 $(state_of "$AOSD" "$TMP/gone")"; FAILED=1
fi
"$DKERNEL" resume "$AOSD" >/dev/null 2>&1
if [ "$(pid_of "$AOSD" "$TMP/w")" = "$NEWPID" ]; then
  echo "ok   再 resume 一次只會認領活著的時鐘，不會重複開"
else
  echo "FAIL resume 又開了一個：$(pid_of "$AOSD" "$TMP/w")"; FAILED=1
fi
case "$(cat "$AOSD/kernel.log")" in
  *"tick 0 resume"*) echo "ok   kernel.log 記了 tick 0 resume" ;;
  *) echo "FAIL kernel.log 沒有 resume 那行：$(cat "$AOSD/kernel.log")"; FAILED=1 ;;
esac
"$DKERNEL" stop "$AOSD" >/dev/null 2>&1
sleep 0.3
if [ -f "$AOSD/clocks/$(clock_id "$TMP/w").json" ]; then
  echo "ok   stop 只殺進程、時鐘檔留著（下次 start 才接得回來）"
else
  echo "FAIL stop 把時鐘檔刪了"; FAILED=1
fi
if [ "$(state_of "$AOSD" "$TMP/w")" = "running" ]; then
  echo "ok   stop 不改時鐘檔的狀態（還是 running）"
else
  echo "FAIL stop 把狀態改成 $(state_of "$AOSD" "$TMP/w")"; FAILED=1
fi
OUT=$("$DKERNEL" ls "$AOSD" 2>&1)
case "$OUT" in
  *"kernel: 沒在跑"*stopped*"$TMP/w"*) echo "ok   kernel 不在時 ls 把它顯示成 stopped" ;;
  *) echo "FAIL ls 沒顯示 stopped：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *dead*"$TMP/gone"*) echo "ok   ls 也印得出重開不了的 dead 時鐘" ;;
  *) echo "FAIL ls 沒印出 dead 的：$OUT"; FAILED=1 ;;
esac
kill_clocks "$AOSD"; LIVE_AOSD=""; rm -rf "$TMP"

# 42. 鐘的 id 是 percent-encoding：不同路徑不會撞名，怪字元也存得回來
TMP=$(mktemp -d); AOSD="$TMP/aosd"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
W1="$TMP/a/b__c"; W2="$TMP/a__b/c"; W3="$TMP/pct % and space"
make_world "$W1"; make_world "$W2"; make_world "$W3"
for W in "$W1" "$W2" "$W3"; do
  "$DAEMON" register "$W" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1
done
AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1
NCLK=$(find "$AOSD/clocks" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NCLK" = "3" ] && [ "$(dir_of "$AOSD" "$W1")" = "$W1" ] \
   && [ "$(dir_of "$AOSD" "$W2")" = "$W2" ]; then
  echo "ok   a/b__c 跟 a__b/c 各自一個時鐘檔，不會撞名（$NCLK 個）"
else
  echo "FAIL 撞名了：$NCLK 個檔，dir1=$(dir_of "$AOSD" "$W1") dir2=$(dir_of "$AOSD" "$W2")"; FAILED=1
fi
ID3=$(clock_id "$W3")
BACK=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.unquote(sys.argv[1]))' "$ID3")
if [ -f "$AOSD/clocks/$ID3.json" ] && [ "$BACK" = "$W3" ] \
   && [ "$(dir_of "$AOSD" "$W3")" = "$W3" ] && [ -f "$AOSD/logs/$ID3.log" ]; then
  echo "ok   有 % 跟空白的路徑：id 解得回來（$ID3），log 檔名也是同一個 id"
else
  echo "FAIL % 空白的路徑沒 round-trip：id=$ID3 解回=$BACK dir=$(dir_of "$AOSD" "$W3")"; FAILED=1
fi
kill_clocks "$AOSD"; rm -rf "$TMP"

# 43. 暫停的鐘不受 kernel 開關影響：要 continue 或重新 register 才會再跑
TMP=$(mktemp -d); AOSD="$TMP/aosd"; make_world "$TMP/w"
printf '{"interval": 0.2}\n' > "$TMP/cfg.json"
tick() { AOS_DAEMON_DIR="$AOSD" "$DKERNEL" tick >/dev/null 2>&1; }
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; tick
"$DAEMON" pause "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
CPID=$(pid_of "$AOSD" "$TMP/w")
kill -KILL "-$CPID" 2>/dev/null   # stop 收掉暫停中的鐘就長這樣
sleep 0.3
tick
if [ "$(state_of "$AOSD" "$TMP/w")" = "paused" ]; then
  echo "ok   暫停的鐘進程沒了也不會被標 dead，還是 paused"
else
  echo "FAIL 暫停的鐘變成 $(state_of "$AOSD" "$TMP/w")"; FAILED=1
fi
"$DAEMON" register "$TMP/w" --config "$TMP/cfg.json" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  fail\|*"已經有時鐘了（paused）"*) echo "ok   對暫停的鐘 register：ok=false，叫你用 continue" ;;
  *) echo "FAIL register 暫停的鐘結果不對：$(last_result "$AOSD")"; FAILED=1 ;;
esac
OUT=$("$DKERNEL" resume "$AOSD" 2>&1)
if [ "$(state_of "$AOSD" "$TMP/w")" = "paused" ] && [ "$(pid_of "$AOSD" "$TMP/w")" = "$CPID" ]; then
  echo "ok   kernel 起來時的 resume 不會幫暫停的鐘重開（pid 還是舊的 $CPID）"
else
  echo "FAIL resume 動了暫停的鐘：state=$(state_of "$AOSD" "$TMP/w") pid=$(pid_of "$AOSD" "$TMP/w")"; FAILED=1
fi
case "$OUT" in
  *"tick 0 keep-paused"*) echo "ok   resume 記了 tick 0 keep-paused" ;;
  *) echo "FAIL resume 的 log 不對：$OUT"; FAILED=1 ;;
esac
A=$(nlines "$TMP/w")
"$DAEMON" continue "$TMP/w" --daemon "$AOSD" >/dev/null 2>&1; tick
case "$(last_result "$AOSD")" in
  ok\|*"重新開了一個"*) echo "ok   continue 對進程已經沒了的暫停鐘：重開一個" ;;
  *) echo "FAIL continue 的結果不對：$(last_result "$AOSD")"; FAILED=1 ;;
esac
NPID=$(pid_of "$AOSD" "$TMP/w")
sleep 0.8
if [ "$(state_of "$AOSD" "$TMP/w")" = "running" ] && [ "$NPID" != "$CPID" ] \
   && kill -0 "$NPID" 2>/dev/null && [ "$(nlines "$TMP/w")" -gt "$A" ]; then
  echo "ok   continue 之後世界又在長了（$A → $(nlines "$TMP/w") 行，pid $CPID → $NPID）"
else
  echo "FAIL continue 沒把它救回來：state=$(state_of "$AOSD" "$TMP/w") pid=$NPID 行數 $A → $(nlines "$TMP/w")"; FAILED=1
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
  echo "ok   優先級高的先做，同級照先來後到（$SEQ）"
else
  echo "FAIL 優先級順序不對：$SEQ"; FAILED=1
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
  "model=model-a "*) echo "ok   不指定就用第一個引擎，model 由引擎決定（$C）" ;;
  *) echo "FAIL 預設引擎不對：$C"; FAILED=1 ;;
esac
echo '{"engine": "two", "echo": true, "messages": []}' > "$TMP/llm/requests/0002.json"
AOS_TEST_KEY=sekret llm_pump "$TMP/llm" >/dev/null
C=$(llm_content "$TMP/llm/results/0002.json")
case "$C" in
  "model=model-b "*"auth=Bearer sekret") echo "ok   指名 engine 就換一台，api_key_env 有變成 Authorization" ;;
  *) echo "FAIL 指名引擎不對：$C"; FAILED=1 ;;
esac
E=$(llm_field "$TMP/llm/results/0002.json" 'd["aos"]["engine"]')
if [ "$E" = "two" ]; then echo "ok   結果的 aos.engine 記著用了哪台"; else echo "FAIL aos.engine 不對：$E"; FAILED=1; fi
rm -rf "$TMP"

# 46. 參數覆蓋：引擎 params ← 請求 params ← 請求頂層鍵，後面蓋前面
TMP=$(mktemp -d)
mk_engines "$TMP/llm" "[{\"name\": \"e\", \"base_url\": \"http://127.0.0.1:$PORT/v1\", \"model\": \"m\", \"params\": {\"temperature\": 0.1}}]"
echo '{"echo": true, "messages": []}' > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null
case "$(llm_content "$TMP/llm/results/0001.json")" in
  *"temperature=0.1"*) echo "ok   沒指定就吃引擎的 params" ;;
  *) echo "FAIL 引擎 params 沒生效：$(llm_content "$TMP/llm/results/0001.json")"; FAILED=1 ;;
esac
echo '{"echo": true, "params": {"temperature": 0.5}, "messages": []}' > "$TMP/llm/requests/0002.json"
llm_pump "$TMP/llm" >/dev/null
case "$(llm_content "$TMP/llm/results/0002.json")" in
  *"temperature=0.5"*) echo "ok   請求的 params 蓋掉引擎的" ;;
  *) echo "FAIL 請求 params 沒蓋過去"; FAILED=1 ;;
esac
echo '{"echo": true, "params": {"temperature": 0.5}, "temperature": 0.9, "messages": []}' \
  > "$TMP/llm/requests/0003.json"
llm_pump "$TMP/llm" >/dev/null
case "$(llm_content "$TMP/llm/results/0003.json")" in
  *"temperature=0.9"*) echo "ok   請求頂層的 temperature 又蓋掉 params 裡的" ;;
  *) echo "FAIL 頂層鍵沒蓋過 params"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 47. 不認得的引擎：回一個 error 結果、請求搬走，不會卡住
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"engine": "沒這台", "messages": []}' > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null; RC=$?
check "不認得的引擎還是回 0" 0 "$RC"
ERR=$(llm_field "$TMP/llm/results/0001.json" 'd["error"]' 2>/dev/null)
case "$ERR" in
  *"不認得這個引擎"*) echo "ok   不認得的引擎有回 error：$ERR" ;;
  *) echo "FAIL 不認得的引擎沒回 error：$ERR"; FAILED=1 ;;
esac
if [ -f "$TMP/llm/requests/done/0001.json" ]; then
  echo "ok   不認得引擎的請求一樣搬去 done/"
else
  echo "FAIL 不認得引擎的請求沒搬走"; FAILED=1
fi
rm -rf "$TMP"

# 48. 用量按天累加，key 是 endpoint|model
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"messages": []}' > "$TMP/llm/requests/0001.json"
llm_pump "$TMP/llm" >/dev/null
echo '{"messages": []}' > "$TMP/llm/requests/0002.json"
llm_pump "$TMP/llm" >/dev/null
USAGE="$TMP/llm/usage/$(date +%Y-%m-%d).json"
U=$(llm_field "$USAGE" '"%s %s %s %s %s" % tuple(d["http://127.0.0.1:'"$PORT"'/v1|local"][k] for k in ("requests","errors","prompt_tokens","completion_tokens","total_tokens"))')
if [ "$U" = "2 0 14 6 20" ]; then
  echo "ok   用量兩次累加起來，key 是 endpoint|model（$U）"
else
  echo "FAIL 用量累加不對：$U"; FAILED=1
fi
# 帳本是算錢用的：模型回的 usage 裡每個數字都要累加，巢狀的攤成點號鍵
R=$(llm_field "$USAGE" 'd["http://127.0.0.1:'"$PORT"'/v1|local"]["completion_tokens_details.reasoning_tokens"]')
if [ "$R" = "10" ]; then
  echo "ok   巢狀的思考 token 攤成 completion_tokens_details.reasoning_tokens 也累加（$R）"
else
  echo "FAIL 思考 token 沒累加：$R"; FAILED=1
fi
C=$(llm_field "$USAGE" 'd["http://127.0.0.1:'"$PORT"'/v1|local"]["prompt_cache_hit_tokens"]')
if [ "$C" = "8" ]; then
  echo "ok   供應商自己多回的 prompt_cache_hit_tokens 也累加（$C）"
else
  echo "FAIL 快取命中沒累加：$C"; FAILED=1
fi
TK=$(llm_field "$USAGE" 'd["http://127.0.0.1:'"$PORT"'/v1|local"]["took_ms"] >= 0')
if [ "$TK" = "True" ]; then echo "ok   took_ms 也記在同一列"; else echo "FAIL took_ms 不在：$TK"; FAILED=1; fi
KEYS=$(llm_field "$USAGE" 'len(d)')
if [ "$KEYS" = "1" ]; then echo "ok   同一個 endpoint+model 只佔一列"; else echo "FAIL 用量鍵數不對：$KEYS"; FAILED=1; fi

# 49. aos-llm usage：印得出那張表
OUT=$("$LLM" usage --dir "$TMP/llm" 2>&1); RC=$?
check "aos-llm usage 退 0" 0 "$RC"
case "$OUT" in
  *"http://127.0.0.1:$PORT/v1|local"*) echo "ok   usage 表印出了 endpoint|model 那一列" ;;
  *) echo "FAIL usage 印的不對：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *"completion_tokens_details.reasoning_tokens"*"prompt_cache_hit_tokens"*)
    echo "ok   usage 表把供應商多回的欄位也印成一欄（思考、快取）" ;;
  *) echo "FAIL usage 沒印出多出來的欄位：$OUT"; FAILED=1 ;;
esac
OUT=$("$LLM" usage 1999-01-01 --dir "$TMP/llm" 2>&1)
case "$OUT" in
  *"沒有用量紀錄"*) echo "ok   沒紀錄那天講一句就好" ;;
  *) echo "FAIL 沒紀錄那天印的不對：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 50. aos-llm 沒給 --dir 也沒設 AOS_LLM_DIR：退 2；send 這個薄包裝已經拿掉了
TMP=$(mktemp -d)
echo '{"messages": []}' > "$TMP/req.json"
OUT=$("$LLM" ls 2>&1); RC=$?
check "aos-llm ls 沒有 LLM 目錄退 2" 2 "$RC"
case "$OUT" in
  *"AOS_LLM_DIR"*) echo "ok   沒目錄時有講 AOS_LLM_DIR" ;;
  *) echo "FAIL 沒目錄時印的不對：$OUT"; FAILED=1 ;;
esac
OUT=$("$LLM" send "$TMP/req.json" 2>&1); RC=$?
if [ "$RC" != "0" ]; then
  echo "ok   aos-llm send 沒了，叫它退 $RC"
else
  echo "FAIL aos-llm send 還在"; FAILED=1
fi
case "$OUT" in
  *"exec"*) echo "ok   叫錯子命令會把還有哪些子命令印出來（exec／usage／ls）" ;;
  *) echo "FAIL 叫錯子命令印的不對：$OUT"; FAILED=1 ;;
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
  *"執行中：2 個"*) echo "ok   ls 數得出執行中幾個（走 AOS_LLM_DIR）" ;;
  *) echo "FAIL ls 的執行中不對：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *"b-p7.json"*"engine=deepseek-flash"*"pid="*) echo "ok   執行中那塊印了引擎跟 pid" ;;
  *) echo "FAIL 執行中那塊印的不對：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *"排隊中：1 個"*"c-wait.json"*"priority=0*"*"engine=local*"*)
    echo "ok   排隊中那塊印了補出來的預設值（帶 *）" ;;
  *) echo "FAIL ls 的排隊中不對：$OUT"; FAILED=1 ;;
esac
case "$OUT" in
  *"engine local: running 1/1"*"engine deepseek-flash: running 1/2"*)
    echo "ok   ls 每台引擎一行 running r/max" ;;
  *) echo "FAIL ls 的引擎那幾行不對：$OUT"; FAILED=1 ;;
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
  *"engines.json"*) echo "ok   不是 LLM 資料夾時講的是「沒有 engines.json」" ;;
  *) echo "FAIL 印的不對：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 53. agent 那頭：llm.json 的 priority/engine 抄進請求，撿回結果後 state.json 記 last_usage
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
python3 - "$TMP/agent/.aos/agent/llm.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]
c = json.load(open(p, encoding="utf-8"))
c["priority"] = 3
c["engine"] = "local"
json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
"$STEP" "$TMP/agent" --no-write-inst >/dev/null 2>&1   # idle 收信
"$STEP" "$TMP/agent" --no-write-inst >/dev/null 2>&1   # llm 丟請求
REQ=$(find "$TMP/llm/requests" -maxdepth 1 -name '*.json' | head -1)
P=$(llm_field "$REQ" '"%s %s" % (d["priority"], d["engine"])')
if [ "$P" = "3 local" ]; then
  echo "ok   llm.json 的 priority／engine 抄進 agent 丟的請求了"
else
  echo "FAIL agent 請求沒帶上 priority／engine：$P"; FAILED=1
fi
llm_pump "$TMP/llm" >/dev/null
"$STEP" "$TMP/agent" --no-write-inst >/dev/null 2>&1   # wait 撿回覆
LU=$(llm_field "$TMP/agent/.aos/agent/state.json" 'd["last_usage"]["total_tokens"]')
if [ "$LU" = "10" ]; then
  echo "ok   agent 的 state.json 記下了上一次的用量 last_usage"
else
  echo "FAIL state.json 沒記 last_usage：$LU"; FAILED=1
fi
rm -rf "$TMP"

# 54. agent 沒有 llm.json、也沒 AOS_LLM_DIR、旁邊也沒 ../llm：講清楚退 2
TMP=$(mktemp -d); prep_agent "$TMP/deep/agent"
rm "$TMP/deep/agent/.aos/agent/llm.json"
python3 -c '
import json,sys
json.dump({"state": "llm", "step": 1, "busy": 1, "request": ""},
          open(sys.argv[1], "w"))' "$TMP/deep/agent/.aos/agent/state.json"
OUT=$("$STEP" "$TMP/deep/agent" --no-write-inst 2>&1 >/dev/null); RC=$?
check "找不到 LLM 資料夾退 2" 2 "$RC"
case "$OUT" in
  *"AOS_LLM_DIR"*) echo "ok   找不到 LLM 資料夾時有講 AOS_LLM_DIR" ;;
  *) echo "FAIL 找不到 LLM 資料夾印的不對：$OUT"; FAILED=1 ;;
esac
AOS_LLM_DIR="$TMP/llmx" "$STEP" "$TMP/deep/agent" --no-write-inst >/dev/null 2>&1; RC=$?
check "設了 AOS_LLM_DIR 就走得動" 0 "$RC"
if [ -n "$(find "$TMP/llmx/requests" -maxdepth 1 -name '*.json' 2>/dev/null)" ]; then
  echo "ok   請求丟進 AOS_LLM_DIR 指的那個世界"
else
  echo "FAIL 請求沒丟進 AOS_LLM_DIR"; FAILED=1
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
  echo "ok   defaults.json 的 engine／priority 補上去了（$D）"
else
  echo "FAIL defaults.json 沒補進去：$D"; FAILED=1
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
  echo "ok   沒 defaults.json 就是第一台引擎＋priority 0（$D）"
else
  echo "FAIL 預設值退化不對：$D"; FAILED=1
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
    echo "ok   ls 把資料夾預設補的 priority／engine 印成帶 * 的值，排序也照補完的算" ;;
  *) echo "FAIL ls 沒印出補完的預設值：$FIRST"; FAILED=1 ;;
esac
QFIRST=$(echo "$OUT" | sed -n '/排隊中/{n;p;}')
case "$QFIRST" in
  *"b-nokey.json"*) echo "ok   排隊那塊第一行就是下一個會被派的（預設 priority 5 贏過寫死的 1）" ;;
  *) echo "FAIL 排隊順序不對：$QFIRST"; FAILED=1 ;;
esac
L=$(llm_tick "$TMP/llm")
case "$L" in
  *"launch b-nokey.json"*"priority=5"*) echo "ok   exec 真的先派預設 priority 比較高的那個" ;;
  *) echo "FAIL 預設 priority 沒進排序：$L"; FAILED=1 ;;
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
    echo "ok   一次只跑一個：第一格開 a、b 留在隊伍裡" ;;
  *) echo "FAIL max_concurrent=1 第一格不對：$OUT"; FAILED=1 ;;
esac
if [ -f "$TMP/llm/requests/b.json" ] && [ ! -f "$TMP/llm/requests/running/b.json" ]; then
  echo "ok   排不到的請求原封不動留在 requests/ 頂層"
else
  echo "FAIL b.json 不該被派出去"; FAILED=1
fi
OUT=$(llm_tick "$TMP/llm")
case "$OUT" in
  *"launched 0 running 1 queued 1"*) echo "ok   a 還在打的時候，b 就是等，exec 自己不等網路" ;;
  *) echo "FAIL 該等的時候沒等：$OUT"; FAILED=1 ;;
esac
OUT=$(llm_pump "$TMP/llm" 120)
case "$OUT" in
  *"done a.json ok"*"launch b.json"*"done b.json ok"*)
    echo "ok   a 做完那格才把 b 派出去，兩個都收得回來" ;;
  *) echo "FAIL 排隊的沒接上：$OUT"; FAILED=1 ;;
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
  *"tick 1 launched 2 running 2 queued 0"*) echo "ok   max_concurrent=2 一格就把兩個都派出去" ;;
  *) echo "FAIL max_concurrent=2 沒同時派：$OUT"; FAILED=1 ;;
esac
llm_pump "$TMP/llm" 120 >/dev/null
if [ -f "$TMP/llm/results/a.json" ] && [ -f "$TMP/llm/results/b.json" ]; then
  echo "ok   兩個一起跑的結果都回得來"
else
  echo "FAIL 同時跑的結果沒都回來"; FAILED=1
fi
N=$(llm_field "$TMP/llm/usage/$(date +%Y-%m-%d).json" \
  'd["http://127.0.0.1:'"$PORT"'/v1|m"]["requests"]')
if [ "$N" = "2" ]; then echo "ok   兩個 worker 的用量紙條都折進當天帳本了（requests=2）"; else echo "FAIL 用量沒折進去：$N"; FAILED=1; fi
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
  *"tick 1 launched 3 running 3 queued 1"*) echo "ok   ds 開兩個、lm 開一個，第四個排隊" ;;
  *) echo "FAIL 兩台引擎的額度沒各算各的：$OUT"; FAILED=1 ;;
esac
LSOUT=$("$LLM" ls --dir "$TMP/llm" 2>&1)
case "$LSOUT" in
  *"engine ds: running 2/2"*"engine lm: running 1/1"*) echo "ok   ls 看得出兩台各自跑滿了" ;;
  *) echo "FAIL ls 的引擎額度不對：$LSOUT"; FAILED=1 ;;
esac
llm_pump "$TMP/llm" 120 >/dev/null
NRES=$(find "$TMP/llm/results" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NRES" = "4" ]; then echo "ok   四個請求最後都做完了"; else echo "FAIL 只做完 $NRES 個"; FAILED=1; fi
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
    echo "ok   額度只有一個時，先派 priority 高的" ;;
  *) echo "FAIL 額度內的優先級不對：$OUT"; FAILED=1 ;;
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
  *"died gone.json"*) echo "ok   worker 死了下一格就發現（印 died）" ;;
  *) echo "FAIL 沒發現 worker 死掉：$OUT"; FAILED=1 ;;
esac
ERR=$(llm_field "$TMP/llm/results/gone.json" 'd["error"]')
if [ "$ERR" = "worker died" ]; then
  echo "ok   死掉的請求補了一個 worker died 的結果，不會有人等到天荒地老"
else
  echo "FAIL 死掉的結果不對：$ERR"; FAILED=1
fi
if [ -f "$TMP/llm/requests/done/gone.json" ] && [ ! -f "$TMP/llm/requests/running/gone.json" ]; then
  echo "ok   死掉的請求從 running/ 搬去 done/，running/ 不會卡著"
else
  echo "FAIL 死掉的請求沒搬走"; FAILED=1
fi
E=$(llm_field "$TMP/llm/usage/$(date +%Y-%m-%d).json" \
  'd["http://127.0.0.1:'"$PORT"'/v1|m"]["errors"]')
if [ "$E" = "1" ]; then echo "ok   死掉也記進當天用量（errors=1）"; else echo "FAIL 用量沒記到死掉：$E"; FAILED=1; fi
ST=$(llm_field "$TMP/llm/state.json" '"%s %s" % (d["served"], d["errors"])')
if [ "$ST" = "0 1" ]; then echo "ok   state.json 的 errors 也算到了"; else echo "FAIL state 不對：$ST"; FAILED=1; fi
kill_workers "$TMP/llm"
rm -rf "$TMP"

# 63. 跑完不留背景進程：worker／loop／kernel 都收乾淨了
sleep 0.5
AFTER=$(strays)
if [ -z "$AFTER" ]; then
  echo "ok   跑完沒有留下 aos 背景進程"
else
  echo "FAIL 跑完還有殘留的 aos 進程：$AFTER"; FAILED=1
fi

cleanup
trap - EXIT
rm -rf "$FAKE"

exit $FAILED
