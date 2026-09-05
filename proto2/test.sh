#!/usr/bin/env bash
# proto2 煙霧測試：跑 aos-exec 的幾件事。有一項 FAIL 就退出 1。
HERE=$(cd "$(dirname "$0")" && pwd)
AOS="$HERE/aos-exec"
LOOP="$HERE/aos-loop"
STEP="$HERE/aos-agent-step"
SAY="$HERE/aos-agent-say"
LISTEN="$HERE/aos-agent-listen"
TALK="$HERE/aos-agent-talk"
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
#     （複本放在 examples/ 底下同一層，跟真正的 examples/agent 保持一樣的相對深度——
#     .aos/inst 裡是 ../../aos-agent-step，複本要是搬到別的深度這條相對路徑就失效；
#     LLM 打不通沒關係，第一格 idle 收信、第二格 llm 失敗 state 不動，一樣算走了兩格，
#     只看 state.json 的 step 有沒有從 0 變 2。靜態檔用 git 索引裡的內容組，不直接
#     cp 真的範例——README 教使用者拿 aos-loop --keep-inst 長期盯著真的範例跑，
#     state.json／hello.json 隨時可能正被用掉，cp 會撿到不確定的當下狀態）
TMP=$(mktemp -d -p "$HERE/examples")
mkdir -p "$TMP/.aos/agent/new-prompts"
git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/new-prompts/hello.json \
  > "$TMP/.aos/agent/new-prompts/hello.json"
git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/state.json \
  > "$TMP/.aos/agent/state.json"
git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/prompts.json \
  > "$TMP/.aos/agent/prompts.json"
cp "$HERE/examples/agent/.aos/agent/engine.json" "$TMP/.aos/agent/engine.json"
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
rm -rf "$TMP"

# 11. 資料夾沒有 .aos/inst：aos-loop 要把這件事講清楚到 stderr
TMP=$(mktemp -d)
OUT=$("$LOOP" "$TMP" --steps 1 --interval 0 2>&1 >/dev/null)
case "$OUT" in
  *"沒有 .aos/inst"*) echo "ok   aos-loop 沒 .aos/inst 時有講清楚" ;;
  *) echo "FAIL 沒看到沒有 .aos/inst 的提示：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# ── aos-agent-step ──────────────────────────────────────────────────────────
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

# 組一份範例的乾淨複本、把 engine 指到假伺服器（範例本體不碰）。故意不直接
# cp -r 真的範例資料夾：README「怎麼玩」教使用者拿 aos-loop --keep-inst 長期盯著
# 真的範例跑，這樣 hello.json／state.json／prompts.json 會被真的用起來、內容一直在動；
# 這裡改成用 git 索引裡的內容組出靜態檔，不受工作目錄當下狀態牽連，測試才穩定。
prep_agent() {  # prep_agent <目標資料夾>
  mkdir -p "$1/.aos/agent/new-prompts"
  git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/new-prompts/hello.json \
    > "$1/.aos/agent/new-prompts/hello.json"
  git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/state.json \
    > "$1/.aos/agent/state.json"
  git -C "$HERE/.." show :proto2/examples/agent/.aos/agent/prompts.json \
    > "$1/.aos/agent/prompts.json"
  cp "$HERE/examples/agent/.aos/agent/engine.json" "$1/.aos/agent/engine.json"
  cp "$HERE/examples/agent/.aos/agent/system-prompt.json" "$1/.aos/agent/system-prompt.json"
  cp "$HERE/examples/agent/.aos/agent/tools.json" "$1/.aos/agent/tools.json"
  cp "$HERE/examples/agent/notes.txt" "$1/notes.txt"
  python3 - "$1/.aos/agent/engine.json" "$PORT" <<'PYEOF2'
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

# 12. 連跑六格：idle→llm→act→collect→llm→act→idle
TMP=$(mktemp -d); prep_agent "$TMP/agent"
SEQ=""
for i in 1 2 3 4 5 6; do
  SEQ="$SEQ$(now_state "$TMP/agent") "
  "$STEP" "$TMP/agent" >/dev/null 2>&1
done
SEQ="$SEQ$(now_state "$TMP/agent")"
if [ "$SEQ" = "idle llm act collect llm act idle" ]; then
  echo "ok   六格的 state 依序走完"
else
  echo "FAIL state 順序不對：$SEQ"; FAILED=1
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

# 13. --no-write-inst 就真的不寫
TMP=$(mktemp -d); prep_agent "$TMP/agent"
"$STEP" "$TMP/agent" --no-write-inst >/dev/null 2>&1
if [ ! -e "$TMP/agent/.aos/inst" ]; then echo "ok   --no-write-inst 不寫 .aos/inst"; else echo "FAIL --no-write-inst 還是寫了"; FAILED=1; fi
rm -rf "$TMP"

# 14. aos-loop 接得起來：step 自己寫回 .aos/inst，跑滿六步同一條鏈
TMP=$(mktemp -d); prep_agent "$TMP/agent"
mkdir -p "$TMP/agent/.aos"; echo "$STEP ." > "$TMP/agent/.aos/inst"
"$LOOP" "$TMP/agent" --steps 6 --interval 0 >/dev/null 2>&1
if [ "$(cat "$TMP/agent/said.txt" 2>/dev/null)" = "hi" ] && [ "$(now_state "$TMP/agent")" = "idle" ]; then
  echo "ok   aos-loop 六步跑完同一條鏈"
else
  echo "FAIL aos-loop 沒跑完：said=$(cat "$TMP/agent/said.txt" 2>/dev/null) state=$(now_state "$TMP/agent")"; FAILED=1
fi
rm -rf "$TMP"

# 15. 推薦用法：.aos/inst 寫一次，aos-loop --keep-inst 不清空，step 也不用寫回
TMP=$(mktemp -d); prep_agent "$TMP/agent"
mkdir -p "$TMP/agent/.aos"; echo "$STEP . --no-write-inst" > "$TMP/agent/.aos/inst"
"$LOOP" "$TMP/agent" --steps 6 --interval 0 --keep-inst >/dev/null 2>&1
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
# 16. new-prompts 裡一個檔放一串（兩則）訊息，跑一格 idle 就收成兩則
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

# 17. aos-agent-say：一句話丟進 new-prompts/
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

# 18. 完整鏈跑完，agent 的回話落在 replies/
TMP=$(mktemp -d); prep_agent "$TMP/agent"
for i in 1 2 3 4 5 6; do "$STEP" "$TMP/agent" --no-write-inst >/dev/null 2>&1; done
NREP=$(find "$TMP/agent/.aos/agent/replies" -maxdepth 1 -name '*.json' | wc -l)
if [ "$NREP" = "1" ]; then echo "ok   replies/ 只有一個回話檔"; else echo "FAIL replies/ 有 $NREP 個檔"; FAILED=1; fi
REP=$(python3 -c '
import glob,json,sys
print(json.load(open(sorted(glob.glob(sys.argv[1]+"/*.json"))[0], encoding="utf-8"))["content"])' \
  "$TMP/agent/.aos/agent/replies")
if [ "$REP" = "done" ]; then echo "ok   回話檔的 content 是 done"; else echo "FAIL 回話檔 content 是 $REP"; FAILED=1; fi

# 19. aos-agent-listen --once 把既有的印出來就走
OUT=$(timeout 10 "$LISTEN" "$TMP/agent" --once); RC=$?
check "listen --once 退出 0" 0 "$RC"
case "$OUT" in
  *"--- reply "*"done"*) echo "ok   listen --once 印得出 done" ;;
  *) echo "FAIL listen --once 印的不對：$OUT"; FAILED=1 ;;
esac
rm -rf "$TMP"

# 20. aos-agent-listen --new --once：跳過既有的，等到新的那則才印、才退出
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

# 21. aos-agent-talk：打一句、等到回話印出來
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

kill $FAKE_PID 2>/dev/null
trap - EXIT
rm -rf "$FAKE"

exit $FAILED
