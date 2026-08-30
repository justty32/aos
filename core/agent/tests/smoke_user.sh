#!/usr/bin/env bash
# HOME 與 AOS_HOME 全程都指向本腳本建立的暫存目錄，絕不碰真正的 ~/.aos/。
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$SCRIPT_DIR/../../.." && pwd)
TEMP=$(mktemp -d)
export HOME="$TEMP"
export AOS_HOME="$TEMP"
SERVER_LOG="$TEMP/server.log"
PORT_FILE="$TEMP/port"
AOS="$REPO/build/bin/aos"
SERVER_PID=""

cleanup() {
    local pid
    while read -r pid; do
        [[ -n "$pid" ]] || continue
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done < <(jobs -pr)
    rm -rf -- "${TEMP:?}"
}
trap cleanup EXIT

unset AOS_FOLDER AOS_LLM_ENGINE AOS_LLM_PRIORITY AOS_LLM_KEY
export NO_PROXY="127.0.0.1,localhost"
export no_proxy="$NO_PROXY"

if [[ ! -x "$AOS" ]]; then
    echo "找不到可執行的 $AOS；請先從 repo 根目錄建置" >&2
    exit 1
fi

json_status() {
    python3 - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    print(json.load(source)["status"])
PY
}

count_messages() {
    find "$1" -maxdepth 1 -type f -name '*.md' -print | wc -l | tr -d '[:space:]'
}

echo "[1/3] 兩隻 agent 同回合 step，只有一隻拿到槽"
printf '%s\n' '{"lmstudio":{"max_inflight":1,"wait_ms":100}}' \
    > "$AOS_HOME/cpus.json"

python3 - "$PORT_FILE" "$SERVER_LOG" <<'PY' &
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

port_file, log_file = sys.argv[1:]
log_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        prompt = request["messages"][-1]["content"].strip().replace("\n", "\\n")
        with log_lock, open(log_file, "a", encoding="utf-8") as output:
            output.write(f"{time.time_ns()} start {prompt}\n")
        time.sleep(2)
        with log_lock, open(log_file, "a", encoding="utf-8") as output:
            output.write(f"{time.time_ns()} end {prompt}\n")

        response = json.dumps({
            "choices": [{"message": {"content": "假端點回覆：槽測試完成"}}]
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
with open(port_file, "w", encoding="utf-8") as output:
    output.write(str(server.server_port))
server.serve_forever()
PY
SERVER_PID=$!

for _ in {1..100}; do
    [[ -s "$PORT_FILE" ]] && break
    sleep 0.05
done
test -s "$PORT_FILE"
export AOS_LLM_URL="http://127.0.0.1:$(<"$PORT_FILE")/v1"

W1="$TEMP/w1"
W2="$TEMP/w2"
mkdir -p "$W1" "$W2"
(
    cd "$W1"
    "$AOS" agent init
    "$AOS" say "hi"
)
(
    cd "$W2"
    "$AOS" agent init
    "$AOS" say "hi"
)

(
    cd "$W1"
    "$AOS" agent step
) > "$TEMP/w1.out" 2> "$TEMP/w1.err" &
STEP1_PID=$!
(
    cd "$W2"
    "$AOS" agent step
) > "$TEMP/w2.out" 2> "$TEMP/w2.err" &
STEP2_PID=$!

if wait "$STEP1_PID"; then
    W1_EXIT=0
else
    W1_EXIT=$?
fi
if wait "$STEP2_PID"; then
    W2_EXIT=0
else
    W2_EXIT=$?
fi

case "$W1_EXIT:$W2_EXIT" in
    0:75)
        WIN_WORLD="$W1"
        WIN_NAME="w1"
        LOSE_WORLD="$W2"
        LOSE_NAME="w2"
        LOSE_ERR="$TEMP/w2.err"
        ;;
    75:0)
        WIN_WORLD="$W2"
        WIN_NAME="w2"
        LOSE_WORLD="$W1"
        LOSE_NAME="w1"
        LOSE_ERR="$TEMP/w1.err"
        ;;
    *)
        echo "退出碼不是恰好一個 0、一個 75：w1=$W1_EXIT w2=$W2_EXIT" >&2
        exit 1
        ;;
esac

python3 - "$LOSE_ERR" <<'PY'
import sys
from pathlib import Path

assert Path(sys.argv[1]).read_bytes() == b"waiting-llm\n"
PY

W1_STATUS=$(json_status "$W1/.aos/agents/w1/status.json")
W2_STATUS=$(json_status "$W2/.aos/agents/w2/status.json")
WIN_STATUS=$(json_status "$WIN_WORLD/.aos/agents/$WIN_NAME/status.json")
LOSE_STATUS=$(json_status "$LOSE_WORLD/.aos/agents/$LOSE_NAME/status.json")
W1_SAY=$(count_messages "$W1/.aos/agents/w1/say")
W2_SAY=$(count_messages "$W2/.aos/agents/w2/say")
WIN_SAY=$(count_messages "$WIN_WORLD/.aos/agents/$WIN_NAME/say")
LOSE_SAY=$(count_messages "$LOSE_WORLD/.aos/agents/$LOSE_NAME/say")

test "$LOSE_STATUS" = "waiting-llm"
test "$WIN_STATUS" != "waiting-llm"
test "$LOSE_SAY" -eq 1
test "$WIN_SAY" -eq 0
grep -Fq "假端點回覆：槽測試完成" \
    "$WIN_WORLD/.aos/agents/$WIN_NAME/log.md"

printf '  w1: exit=%s status=%s say=%s\n' "$W1_EXIT" "$W1_STATUS" "$W1_SAY"
printf '  w2: exit=%s status=%s say=%s\n' "$W2_EXIT" "$W2_STATUS" "$W2_SAY"
printf '  敗方 stderr: %s\n' "$(<"$LOSE_ERR")"
echo "  勝方 log 命中：假端點回覆：槽測試完成"

kill "$SERVER_PID"
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=""

echo "[2/3] say 帶 from、信寄到 ~、在 ~ 讀得到"
W="$TEMP/W"
mkdir -p "$W"
(
    cd "$W"
    "$AOS" agent init
    "$AOS" say "hi"
)
W_ABS=$(cd "$W" && pwd -P)
W_SAY_DIR="$W/.aos/agents/W/say"
mapfile -t W_MESSAGES < <(find "$W_SAY_DIR" -maxdepth 1 -type f -name '*.md' -print)
test "${#W_MESSAGES[@]}" -eq 1
IFS= read -r FIRST_LINE < "${W_MESSAGES[0]}"
test "$FIRST_LINE" = "from: $W_ABS"

(
    cd "$W"
    "$AOS" say --to '~' "回報完成"
) > "$TEMP/say-to-user.out"
USER_SAY_DIR="$HOME/.aos/say"
mapfile -t USER_MESSAGES < <(find "$USER_SAY_DIR" -maxdepth 1 -type f -name '*.md' -print)
test "${#USER_MESSAGES[@]}" -eq 1
grep -Fxq "from: $W_ABS" "${USER_MESSAGES[0]}"
grep -Fq "回報完成" "${USER_MESSAGES[0]}"

echo "  agent say 訊息："
sed 's/^/    /' "${W_MESSAGES[0]}"
echo
echo "  寄給 ~ 的訊息："
sed 's/^/    /' "${USER_MESSAGES[0]}"
echo

(
    cd "$HOME"
    "$AOS" listen --once
) > "$TEMP/listen.out"
grep -Fq "回報完成" "$TEMP/listen.out"
echo "  HOME 下 listen --once："
sed 's/^/    /' "$TEMP/listen.out"

echo "[3/3] aos contact ls 第一列是 ~"
(
    cd "$W"
    "$AOS" contact ls
) > "$TEMP/contact-before.out"
test "$(awk 'NR == 2 {print $1}' "$TEMP/contact-before.out")" = "~"
test "$(awk 'NR == 2 {print $2}' "$TEMP/contact-before.out")" = "$HOME"

(
    cd "$W"
    "$AOS" contact add bob ../bob-world
) > "$TEMP/contact-add.out"
(
    cd "$W"
    "$AOS" contact ls
) > "$TEMP/contact-after.out"
test "$(awk 'NR == 2 {print $1}' "$TEMP/contact-after.out")" = "~"
test "$(awk 'NR == 2 {print $2}' "$TEMP/contact-after.out")" = "$HOME"
test "$(awk 'NR == 3 {print $1}' "$TEMP/contact-after.out")" = "bob"
! grep -Fq '"~"' "$W/.aos/contacts.json"

echo "  空通訊錄的 contact ls："
sed 's/^/    /' "$TEMP/contact-before.out"
echo "  加入 bob 後的 contact ls："
sed 's/^/    /' "$TEMP/contact-after.out"
echo "  contacts.json："
sed 's/^/    /' "$W/.aos/contacts.json"

echo "smoke_user OK：3/3 全部通過"
