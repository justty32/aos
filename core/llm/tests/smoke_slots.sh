#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$SCRIPT_DIR/../../.." && pwd)
TEMP=$(mktemp -d)
AOS_TEST_HOME="$TEMP/aos-home"
SERVER_LOG="$TEMP/server.log"
PORT_FILE="$TEMP/port"
mkdir -p "$AOS_TEST_HOME"

cleanup() {
    local pids
    pids=$(jobs -pr)
    if [[ -n "$pids" ]]; then
        kill $pids 2>/dev/null || true
        wait $pids 2>/dev/null || true
    fi
    rm -rf -- "${TEMP:?}"
}
trap cleanup EXIT

export PATH="$REPO/build/bin:$PATH"
export AOS_HOME="$AOS_TEST_HOME"

if ! command -v aos >/dev/null ||
   ! aos --help 2>&1 | grep -Eq '^  llm[[:space:]]'; then
    echo "aos llm 尚未實作，跳過"
    exit 0
fi

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
        time.sleep(1)
        with log_lock, open(log_file, "a", encoding="utf-8") as output:
            output.write(f"{time.time_ns()} end {prompt}\n")

        response = json.dumps({
            "choices": [{"message": {"content": "ok"}}]
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

for _ in {1..100}; do
    [[ -s "$PORT_FILE" ]] && break
    sleep 0.05
done
test -s "$PORT_FILE"
export AOS_LLM_URL="http://127.0.0.1:$(<"$PORT_FILE")/v1"

slot_field() {
    local table=$1
    local cpu=$2
    local field=$3
    awk -v cpu="$cpu" -v field="$field" \
        '$1 == cpu {print $field}' <<<"$table"
}

wait_for_start() {
    local prompt=$1
    for _ in {1..100}; do
        grep -q " start $prompt\$" "$SERVER_LOG" 2>/dev/null && return
        sleep 0.02
    done
    return 1
}

echo "[1/4] 兩個 aos llm 搶一個槽"
printf '%s\n' '{"lmstudio":{"max_inflight":1,"wait_ms":3000}}' \
    > "$AOS_HOME/cpus.json"
: > "$SERVER_LOG"
printf 'A\n' | aos llm > "$TEMP/one-a.out" &
FIRST_PID=$!
wait_for_start A
sleep 0.2
printf 'B\n' | aos llm > "$TEMP/one-b.out" &
SECOND_PID=$!
sleep 0.1
kill -0 "$FIRST_PID"
SLOTS=$(aos llm --slots)
printf '%s\n' "$SLOTS"
wait "$FIRST_PID"
wait "$SECOND_PID"
test "$(<"$TEMP/one-a.out")" = "ok"
test "$(<"$TEMP/one-b.out")" = "ok"
MAX_RUNNING=$(awk '
    $2 == "start" {running++; if (running > maximum) maximum = running}
    $2 == "end" {running--}
    END {print maximum + 0}
' "$SERVER_LOG")
test "$MAX_RUNNING" -eq 1
echo "  端點最大同時呼叫數: $MAX_RUNNING"

echo "[2/4] wait_ms=100 時第二個呼叫退回 waiting-llm"
printf '%s\n' '{"lmstudio":{"max_inflight":1,"wait_ms":100}}' \
    > "$AOS_HOME/cpus.json"
: > "$SERVER_LOG"
printf 'A\n' | aos llm > "$TEMP/two-a.out" &
FIRST_PID=$!
wait_for_start A
sleep 0.2
set +e
printf 'B\n' | aos llm > "$TEMP/two-b.out" 2> "$TEMP/two-b.err"
SECOND_STATUS=$?
set -e
test "$SECOND_STATUS" -eq 75
python3 - "$TEMP/two-b.err" <<'PY'
import sys
from pathlib import Path

assert Path(sys.argv[1]).read_bytes() == b"waiting-llm\n"
PY
wait "$FIRST_PID"
echo "  第二個 exit=$SECOND_STATUS, stderr=$(<"$TEMP/two-b.err")"

echo "[3/4] 世界層 max_inflight 只能把使用者層上限往下限"
WORLD="$TEMP/world"
mkdir -p "$WORLD/.aos"
printf '%s\n' '{"lmstudio":{"max_inflight":1,"wait_ms":2000}}' \
    > "$AOS_HOME/cpus.json"
printf '%s\n' '{"lmstudio":{"max_inflight":0}}' \
    > "$WORLD/.aos/llm.json"
set +e
(
    cd "$WORLD"
    printf 'blocked\n' | aos llm
) > "$TEMP/three-zero.out" 2> "$TEMP/three-zero.err"
ZERO_STATUS=$?
set -e
test "$ZERO_STATUS" -eq 75
printf '%s\n' '{"lmstudio":{"max_inflight":5}}' \
    > "$WORLD/.aos/llm.json"
WORLD_SLOTS=$(cd "$WORLD" && aos llm --slots)
printf '%s\n' "$WORLD_SLOTS"
test "$(slot_field "$WORLD_SLOTS" lmstudio 4)" -eq 1
echo "  世界層 0 時 exit=$ZERO_STATUS；世界層 5 時 MAX 仍為 1"

echo "[4/4] pi 的 step 佔住 deepseek 一個槽"
printf '%s\n' \
    '{"deepseek":{"max_inflight":3,"wait_ms":2000},"lmstudio":{"max_inflight":1,"wait_ms":2000}}' \
    > "$AOS_HOME/cpus.json"
FAKE_PI="$TEMP/fake-pi"
cat > "$FAKE_PI" <<'SH'
#!/usr/bin/env bash
sleep 2
printf '%s\n' '{"type":"turn_end","message":{"content":[{"type":"text","text":"好"}]}}'
SH
chmod +x "$FAKE_PI"
export AOS_PI_BIN="$FAKE_PI"
PI_WORLD="$TEMP/pi-world"
mkdir -p "$PI_WORLD"
(
    cd "$PI_WORLD"
    aos agent init --engine pi
    aos say "測試"
)
(
    cd "$PI_WORLD"
    AOS_TURN=1 aos agent step
) > "$TEMP/pi-step.out" 2> "$TEMP/pi-step.err" &
STEP_PID=$!
sleep 0.8
kill -0 "$STEP_PID"
DURING_SLOTS=$(cd "$PI_WORLD" && aos llm --slots)
printf '%s\n' "$DURING_SLOTS"
test "$(slot_field "$DURING_SLOTS" deepseek 2)" -eq 1
wait "$STEP_PID"
AFTER_SLOTS=$(cd "$PI_WORLD" && aos llm --slots)
printf '%s\n' "$AFTER_SLOTS"
test "$(slot_field "$AFTER_SLOTS" deepseek 2)" -eq 0

echo "smoke OK"
