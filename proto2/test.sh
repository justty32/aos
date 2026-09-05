#!/usr/bin/env bash
# proto2 煙霧測試：跑 aos-exec 的幾件事。有一項 FAIL 就退出 1。
HERE=$(cd "$(dirname "$0")" && pwd)
AOS="$HERE/aos-exec"
LOOP="$HERE/aos-loop"
STEP="$HERE/aos-agent-step"
LLMSTEP="$HERE/aos-llm-step"
ASK="$HERE/aos-llm-ask"
SAY="$HERE/aos-agent-say"
SPAWN="$HERE/aos-agent-spawn"
LISTEN="$HERE/aos-agent-listen"
TALK="$HERE/aos-agent-talk"
DSTEP="$HERE/aos-daemon-step"
DREG="$HERE/aos-daemon-register"
DUNREG="$HERE/aos-daemon-unregister"
FAILED=0

check() {  # check <名字> <期待退出碼> <實際退出碼>
  if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1（期待退出碼 $2，實際 $3）"; FAILED=1; fi
}

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
# 存進 prompts.json 時會不會把這些濾掉。
PORT=18080
FAKE=$(mktemp -d)
cat > "$FAKE/fake-llm.py" <<'PYEOF2'
import http.server, json, sys

class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            data = {}
        msgs = data.get("messages") or []
        if any(m.get("role") == "tool" for m in msgs):
            message = {"role": "assistant", "content": "done", "tool_calls": [],
                       "reasoning_content": "blah"}
        else:
            message = {"role": "assistant", "content": None, "reasoning_content": "blah",
                       "tool_calls": [
                {"id": "call_1", "type": "function",
                 "function": {"name": "say", "arguments": "{\"text\": \"hi\"}"}}]}
        body = json.dumps({"choices": [{"index": 0, "message": message,
                                        "finish_reason": "stop"}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
PYEOF2
python3 "$FAKE/fake-llm.py" "$PORT" &
FAKE_PID=$!
trap 'kill $FAKE_PID 2>/dev/null' EXIT
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
prep_llm() {  # prep_llm <目標 LLM 資料夾>；engine 指到假伺服器（範例本體不碰）
  mkdir -p "$1/.aos/llm/requests"
  cp "$HERE/examples/llm/.aos/llm/engine.json" "$1/.aos/llm/engine.json"
  cp "$HERE/examples/llm/.aos/inst" "$1/.aos/inst"
  python3 - "$1/.aos/llm/engine.json" "$PORT" <<'PYEOF2'
import json, sys
p = sys.argv[1]
e = json.load(open(p, encoding="utf-8"))
e["base_url"] = "http://127.0.0.1:%s/v1" % sys.argv[2]
json.dump(e, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
}
now_state() {  # now_state <agent 資料夾>
  python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["state"])' "$1/.aos/agent/state.json"
}

# daemon 範例的複本。登記表也走 git 索引：own 的子 agent 會往真範例的 registry/ 塞新檔
# （使用者玩過就會多幾個），cp -r 會把那些也撿進來，測試就飄了。組完把兩條登記改成指向
# 這次的複本（用 aos-daemon-register 重寫，順便測到它寫的是絕對路徑）。
prep_daemon() {  # prep_daemon <目標 daemon 資料夾> [<要登記的資料夾>...]
  d="$1"; shift
  mkdir -p "$d/.aos/daemon/registry"
  git -C "$HERE/.." show :proto2/examples/daemon/.aos/inst > "$d/.aos/inst"
  for t in "$@"; do "$DREG" "$d" "$t" >/dev/null 2>&1; done
}

# 12. LLM 資料夾走一格：拿最舊的請求去打、回覆落在 results/、請求搬去 requests/done/
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo '{"messages": [{"role": "user", "content": "哈囉"}]}' \
  > "$TMP/llm/.aos/llm/requests/0001.json"
OUT=$("$LLMSTEP" "$TMP/llm" 2>&1); RC=$?
check "aos-llm-step 處理一個請求回 0" 0 "$RC"
case "$OUT" in
  *"0001.json ok"*) echo "ok   aos-llm-step 印了處理掉哪個請求" ;;
  *) echo "FAIL aos-llm-step 印的不對：$OUT"; FAILED=1 ;;
esac
if [ -f "$TMP/llm/.aos/llm/results/0001.json" ]; then
  echo "ok   回覆落在 results/ 同檔名"
else
  echo "FAIL results/0001.json 沒出現"; FAILED=1
fi
REQ_TOP=$(find "$TMP/llm/.aos/llm/requests" -maxdepth 1 -type f)
if [ -z "$REQ_TOP" ]; then echo "ok   requests/ 頂層清空了"; else echo "FAIL requests/ 頂層還有：$REQ_TOP"; FAILED=1; fi
if [ -f "$TMP/llm/.aos/llm/requests/done/0001.json" ]; then
  echo "ok   處理完的請求搬去 requests/done/"
else
  echo "FAIL requests/done/0001.json 不在"; FAILED=1
fi
CONTENT=$(python3 -c '
import json,sys
print(json.load(open(sys.argv[1]))["choices"][0]["message"]["content"] or "")' \
  "$TMP/llm/.aos/llm/results/0001.json")
if [ "$CONTENT" = "" ]; then
  echo "ok   results/ 裡是整包原始回覆（這則是 tool_calls，content 空的）"
else
  echo "FAIL results/ 內容不對：$CONTENT"; FAILED=1
fi

# 13. 沒請求就什麼都不做，印 idle
OUT=$("$LLMSTEP" "$TMP/llm" 2>&1); RC=$?
check "aos-llm-step 沒請求也回 0" 0 "$RC"
case "$OUT" in
  *"idle"*) echo "ok   沒請求時印 idle" ;;
  *) echo "FAIL 沒請求時印的不對：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 14. 壞掉的請求也要有結果，不然丟請求的人會等到天荒地老
TMP=$(mktemp -d); prep_llm "$TMP/llm"
echo 'this is not json' > "$TMP/llm/.aos/llm/requests/0001.json"
"$LLMSTEP" "$TMP/llm" >/dev/null 2>&1; RC=$?
check "壞請求 aos-llm-step 還是回 0" 0 "$RC"
ERR=$(python3 -c '
import json,sys
print(json.load(open(sys.argv[1])).get("error", ""))' "$TMP/llm/.aos/llm/results/0001.json" 2>/dev/null)
if [ -n "$ERR" ]; then echo "ok   壞請求的結果檔有 error：$ERR"; else echo "FAIL 壞請求沒寫出 error 結果"; FAILED=1; fi
if [ -f "$TMP/llm/.aos/llm/requests/done/0001.json" ]; then
  echo "ok   壞請求一樣搬去 requests/done/，不會卡住下一個"
else
  echo "FAIL 壞請求沒搬走"; FAILED=1
fi
rm -rf "$TMP"

# 15. 打不通就把請求留在原地、退出碼 1，下一格再試
TMP=$(mktemp -d); prep_llm "$TMP/llm"
python3 - "$TMP/llm/.aos/llm/engine.json" <<'PYEOF2'
import json, sys
p = sys.argv[1]
e = json.load(open(p, encoding="utf-8"))
e["base_url"] = "http://127.0.0.1:1/v1"
json.dump(e, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PYEOF2
echo '{"messages": [{"role": "user", "content": "哈囉"}]}' \
  > "$TMP/llm/.aos/llm/requests/0001.json"
OUT=$("$LLMSTEP" "$TMP/llm" 2>&1); RC=$?
check "aos-llm-step 打不通回 1" 1 "$RC"
case "$OUT" in
  *"打不通"*) echo "ok   打不通有印白話" ;;
  *) echo "FAIL 打不通印的不對：$OUT"; FAILED=1 ;;
esac
if [ -f "$TMP/llm/.aos/llm/requests/0001.json" ]; then
  echo "ok   打不通時請求留在原地下一格再試"
else
  echo "FAIL 打不通時請求被搬走了"; FAILED=1
fi
rm -rf "$TMP"

# 16. aos-llm-ask：丟一個請求、等 aos-loop 那頭跑出結果、印出來、把結果檔拿走
TMP=$(mktemp -d); prep_llm "$TMP"
"$LOOP" "$TMP" --keep-inst --interval 0 --steps 20 >/dev/null 2>&1 &
ASK_LOOP=$!
OUT=$(echo '{"messages": [{"role": "user", "content": "哈囉"}]}' \
  | timeout 20 "$ASK" "$TMP" 2>/dev/null); RC=$?
check "aos-llm-ask 等到回覆退出 0" 0 "$RC"
case "$OUT" in
  *"choices"*) echo "ok   aos-llm-ask 把整包回覆印出來了" ;;
  *) echo "FAIL aos-llm-ask 印的不對：$OUT"; FAILED=1 ;;
esac
RES_LEFT=$(find "$TMP/.aos/llm/results" -maxdepth 1 -name '*.json' 2>/dev/null)
if [ -z "$RES_LEFT" ]; then
  echo "ok   結果被 aos-llm-ask 拿走了（拿走就沒了）"
else
  echo "FAIL 結果檔還留著：$RES_LEFT"; FAILED=1
fi
wait $ASK_LOOP 2>/dev/null
rm -rf "$TMP"

# 17. aos-llm-ask --no-wait：只丟不等，把檔名印到 stdout
TMP=$(mktemp -d); prep_llm "$TMP/llm"
OUT=$(echo '{"messages": []}' | "$ASK" "$TMP/llm" --no-wait 2>/dev/null); RC=$?
check "aos-llm-ask --no-wait 退出 0" 0 "$RC"
if [ -f "$TMP/llm/.aos/llm/requests/$OUT" ]; then
  echo "ok   --no-wait 印的檔名就是丟出去那個請求"
else
  echo "FAIL --no-wait 印的檔名對不上：$OUT"; FAILED=1
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
  "$LLMSTEP" "$TMP/llm" >/dev/null 2>&1
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
"$LOOP" "$TMP/llm" --keep-inst --steps 200 --interval 0 >/dev/null 2>&1 &
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
"$LOOP" "$TMP/llm" --keep-inst --steps 200 --interval 0 >/dev/null 2>&1 &
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
  "$LLMSTEP" "$TMP/llm" >/dev/null 2>&1
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
"$LOOP" "$TMP/llm" --keep-inst --steps 400 --interval 0 >/dev/null 2>&1 &
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

# ── daemon 資料夾 ───────────────────────────────────────────────────────────
# 35. daemon 走一格：登記表上的 agent 跟 llm 各被推一格
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
cp "$HERE/examples/agent/.aos/inst" "$TMP/agent/.aos/inst"
prep_daemon "$TMP/daemon" "$TMP/agent" "$TMP/llm"
echo '{"messages": [{"role": "user", "content": "哈囉"}]}' \
  > "$TMP/llm/.aos/llm/requests/0001.json"
OUT=$("$DSTEP" "$TMP/daemon" 2>&1); RC=$?
check "aos-daemon-step 走一格回 0" 0 "$RC"
AG_STEP=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["step"])' \
  "$TMP/agent/.aos/agent/state.json")
if [ "$AG_STEP" = "1" ]; then echo "ok   登記表上的 agent 被推了一格"; else echo "FAIL agent 走了 $AG_STEP 格：$OUT"; FAILED=1; fi
if [ -f "$TMP/llm/.aos/llm/results/0001.json" ]; then
  echo "ok   登記表上的 LLM 資料夾也被推了一格（請求變成結果了）"
else
  echo "FAIL LLM 資料夾沒被推到：$OUT"; FAILED=1
fi
NEXIT=$(echo "$OUT" | grep -c "tick 1 .* exit 0")
if [ "$NEXIT" = "2" ]; then echo "ok   stderr 兩個登記各印一行 exit 0"; else echo "FAIL exit 0 的行數不對（$NEXIT）：$OUT"; FAILED=1; fi
TICK=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["tick"])' \
  "$TMP/daemon/.aos/daemon/state.json")
if [ "$TICK" = "1" ]; then echo "ok   daemon 自己的 state.json tick 是 1"; else echo "FAIL tick 是 $TICK"; FAILED=1; fi
rm -rf "$TMP"

# 36. every：登記寫 2 就兩格推一次，daemon 走四格它只走兩格
TMP=$(mktemp -d)
mkdir -p "$TMP/daemon/.aos/daemon/registry" "$TMP/fast/.aos" "$TMP/slow/.aos"
printf 'echo x >> count.txt\n' > "$TMP/fast/.aos/inst"
printf 'echo x >> count.txt\n' > "$TMP/slow/.aos/inst"
"$DREG" "$TMP/daemon" "$TMP/fast" >/dev/null 2>&1
"$DREG" "$TMP/daemon" "$TMP/slow" --every 2 >/dev/null 2>&1
OUT=$(for i in 1 2 3 4; do "$DSTEP" "$TMP/daemon"; done 2>&1)
NFAST=$(wc -l < "$TMP/fast/count.txt")
NSLOW=$(wc -l < "$TMP/slow/count.txt")
if [ "$NFAST" = "4" ] && [ "$NSLOW" = "2" ]; then
  echo "ok   every 1 的走四格、every 2 的只走兩格"
else
  echo "FAIL every 不對：fast=$NFAST slow=$NSLOW"; FAILED=1
fi
NSKIP=$(echo "$OUT" | grep -c "slow skip")
if [ "$NSKIP" = "2" ]; then echo "ok   沒輪到的那兩格印了 skip"; else echo "FAIL skip 行數不對（$NSKIP）：$OUT"; FAILED=1; fi
rm -rf "$TMP"

# 37. register／unregister：檔案出現、消失，同名跟不存在都退 2
TMP=$(mktemp -d)
mkdir -p "$TMP/daemon" "$TMP/target/.aos"
printf 'true\n' > "$TMP/target/.aos/inst"
"$DREG" "$TMP/daemon" "$TMP/target" >/dev/null 2>&1; RC=$?
check "aos-daemon-register 回 0" 0 "$RC"
REGFILE="$TMP/daemon/.aos/daemon/registry/target.json"
if [ -f "$REGFILE" ]; then echo "ok   名字沒給就用目標資料夾的 basename"; else echo "FAIL $REGFILE 沒出現"; FAILED=1; fi
REGDIR=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["dir"])' "$REGFILE")
case "$REGDIR" in
  /*) echo "ok   登記表裡的 dir 是絕對路徑" ;;
  *) echo "FAIL 登記表的 dir 不是絕對路徑：$REGDIR"; FAILED=1 ;;
esac
"$DREG" "$TMP/daemon" "$TMP/target" >/dev/null 2>&1; RC=$?
check "同名再登記一次退 2" 2 "$RC"
"$DREG" "$TMP/daemon" "$TMP/target" --name second --every 3 >/dev/null 2>&1
EVERY=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["every"])' \
  "$TMP/daemon/.aos/daemon/registry/second.json")
if [ "$EVERY" = "3" ]; then echo "ok   --name 換名字、--every 有寫進去"; else echo "FAIL every=$EVERY"; FAILED=1; fi
"$DUNREG" "$TMP/daemon" target >/dev/null 2>&1; RC=$?
check "aos-daemon-unregister 回 0" 0 "$RC"
if [ ! -f "$REGFILE" ]; then echo "ok   取消登記後檔案不見了"; else echo "FAIL $REGFILE 還在"; FAILED=1; fi
"$DUNREG" "$TMP/daemon" target >/dev/null 2>&1; RC=$?
check "取消不存在的登記退 2" 2 "$RC"
rm -rf "$TMP"

# 38. 登記的資料夾不見了：印一行、其他登記照推、整格還是回 0
TMP=$(mktemp -d)
mkdir -p "$TMP/daemon/.aos/daemon/registry" "$TMP/good/.aos"
printf 'echo x >> count.txt\n' > "$TMP/good/.aos/inst"
"$DREG" "$TMP/daemon" "$TMP/good" >/dev/null 2>&1
printf '{"dir": "%s/沒有這個資料夾", "every": 1}\n' "$TMP" \
  > "$TMP/daemon/.aos/daemon/registry/aaa-missing.json"
OUT=$("$DSTEP" "$TMP/daemon" 2>&1); RC=$?
check "有壞登記時 aos-daemon-step 還是回 0" 0 "$RC"
case "$OUT" in
  *"找不到資料夾"*) echo "ok   找不到的登記有印一行" ;;
  *) echo "FAIL 沒印找不到資料夾：$OUT"; FAILED=1 ;;
esac
if [ -f "$TMP/good/count.txt" ]; then echo "ok   壞登記不影響後面的登記照推"; else echo "FAIL good 沒被推到：$OUT"; FAILED=1; fi
rm -rf "$TMP"

# 39. 一個 loop 推完整條鏈：只轉 daemon，agent 跟 LLM 都靠它推，replies/ 要冒出回話
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
cp "$HERE/examples/agent/.aos/inst" "$TMP/agent/.aos/inst"
prep_daemon "$TMP/daemon" "$TMP/agent" "$TMP/llm"
"$SAY" "$TMP/agent" "在嗎" >/dev/null 2>&1
"$LOOP" "$TMP/daemon" --keep-inst --steps 15 --interval 0 >/dev/null 2>&1
NREP=$(find "$TMP/agent/.aos/agent/replies" -maxdepth 1 -name '*.json' 2>/dev/null | wc -l)
if [ "$NREP" -ge 1 ]; then
  echo "ok   一個 aos-loop 只推 daemon，整條鏈就跑完了（agent 有回話）"
else
  echo "FAIL 整條鏈沒跑完：state=$(now_state "$TMP/agent")"; FAILED=1
fi
rm -rf "$TMP"

# 40. own 的子 agent 自動登記給父的 daemon，生出來就有人推
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
cp "$HERE/examples/agent/.aos/inst" "$TMP/agent/.aos/inst"
prep_daemon "$TMP/daemon"
git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/daemon.json \
  > "$TMP/agent/.aos/agent/daemon.json"
OUT=$("$SPAWN" "$TMP/agent" kid --clock own "你是 own 的小孩" 2>&1); RC=$?
check "有 daemon.json 時 own spawn 回 0" 0 "$RC"
KIDREG="$TMP/daemon/.aos/daemon/registry/agent-kid.json"
if [ -f "$KIDREG" ]; then echo "ok   own 的子自動登記成 <父名>-<子名>（agent-kid）"; else echo "FAIL $KIDREG 沒出現：$OUT"; FAILED=1; fi
KIDDIR=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["dir"])' "$KIDREG" 2>/dev/null)
if [ "$KIDDIR" = "$TMP/agent/kid" ]; then echo "ok   登記指到子的絕對路徑"; else echo "FAIL 登記的路徑是 $KIDDIR"; FAILED=1; fi
KIDD=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["dir"])' \
  "$TMP/agent/kid/.aos/agent/daemon.json" 2>/dev/null)
if [ "$KIDD" = "../../daemon" ]; then echo "ok   子也抄到一份換算過的 daemon.json"; else echo "FAIL 子的 daemon.json 是 $KIDD"; FAILED=1; fi
"$LOOP" "$TMP/daemon" --keep-inst --steps 3 --interval 0 >/dev/null 2>&1
KID_STEP=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["step"])' \
  "$TMP/agent/kid/.aos/agent/state.json")
if [ "$KID_STEP" -ge 1 ]; then echo "ok   daemon 轉起來，own 的子自己走了 $KID_STEP 格"; else echo "FAIL own 的子沒走：step=$KID_STEP"; FAILED=1; fi
rm -rf "$TMP"

# 41. 父沒有 daemon.json：own 的子照舊不登記，只叫人自己開 loop
TMP=$(mktemp -d); prep_agent "$TMP/agent"; prep_llm "$TMP/llm"
prep_daemon "$TMP/daemon"
OUT=$("$SPAWN" "$TMP/agent" kid --clock own "你是 own 的小孩" 2>&1)
NREG=$(find "$TMP/daemon/.aos/daemon/registry" -name '*.json' | wc -l)
if [ "$NREG" = "0" ]; then echo "ok   父沒有 daemon.json 就不登記"; else echo "FAIL 竟然登記了 $NREG 個"; FAILED=1; fi
case "$OUT" in
  *"自己開 aos-loop"*) echo "ok   沒 daemon 時還是叫人自己開 loop" ;;
  *) echo "FAIL 沒印自己開 loop：$OUT"; FAILED=1 ;;
esac
if [ ! -f "$TMP/agent/kid/.aos/agent/daemon.json" ]; then echo "ok   父沒 daemon.json 子也不會憑空多一份"; else echo "FAIL 子多了 daemon.json"; FAILED=1; fi
rm -rf "$TMP"

kill $FAKE_PID 2>/dev/null
trap - EXIT
rm -rf "$FAKE"

exit $FAILED
