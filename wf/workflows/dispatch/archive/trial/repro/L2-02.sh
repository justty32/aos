#!/bin/sh
# L2-02  新世界的預設工具裡沒有 `aos`，所以 boss agent 開箱即用時**根本無法派工**。
# L2-03  就算把 `aos` 登記進去，system prompt 也從不提通訊錄——agent 不知道 w1／w2 存在。
#
# 期待：一隻 boss agent 一開機就有「投遞給隊友」這個能力，並且知道隊上有誰。
# 實際：(1) `aos agent init` 只裝 cat／ls／sh 三個工具，沒有 aos、沒有 deliver、沒有 contact；
#           （repo 根 .aos/tools/ 裡的 aos.json、git.json 是人手加進版控的，不是預設）
#       (2) core/agent 裡只有 run_top.cpp 這個**頂層 CLI** 讀 contacts.json；
#           step.cpp／tools.cpp 組 system prompt 時只列工具、從不列聯絡人。
#       → 使用者得自己 `aos tool add aos` 再在人格或訊息裡把隊友名單抄一遍。
# 第二個斷言已於 2026-08-30 改成驗 system prompt（原本預設了通訊錄會被複製進 agent 資料夾）。
set -eu
AOS="${AOS_BIN:-aos}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/boss/.aos" "$ROOT/w1/.aos"
(cd "$ROOT/boss" && "$AOS" agent init --name boss >/dev/null)
(cd "$ROOT/w1"   && "$AOS" agent init --name w1   >/dev/null)
(cd "$ROOT/boss" && "$AOS" contact add w1 ../w1 --note "翻譯" >/dev/null)

echo "=== 全新世界的預設工具 ==="
(cd "$ROOT/boss" && "$AOS" tool ls)

echo
echo "=== 有 aos／deliver／contact 這類投遞工具嗎？ ==="
if (cd "$ROOT/boss" && "$AOS" tool ls) | grep -qE '^(aos|deliver|contact|say) '; then
  echo "PASS"
else
  echo "FAIL: 預設工具只有 cat／ls／sh，agent 沒有任何『寄信給隊友』的能力"
fi

echo
echo "=== 通訊錄裡明明有 w1 ==="
(cd "$ROOT/boss" && "$AOS" contact ls)

echo
echo "=== 但 agent 的 system prompt 提過 w1 嗎？ ==="
echo "（system prompt 由 core/agent/src/tools.cpp:system_prompt 組成：人格 + 工具清單，沒有聯絡人區塊）"
PERSONA="$ROOT/boss/.aos/agents/boss/persona.md"
[ -f "$PERSONA" ] && { echo "--- persona.md ---"; cat "$PERSONA"; }

CAP="$ROOT/request.json"
python3 - "$CAP" <<'PY' &
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

capture = sys.argv[1]

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        with open(capture, 'wb') as output:
            output.write(body)
        payload = json.dumps({
            "model": "fake",
            "choices": [{
                "message": {"role": "assistant", "content": "收到。"}
            }],
        }).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass

HTTPServer(('127.0.0.1', 18923), H).serve_forever()
PY
FAKE=$!
trap 'kill "$FAKE" 2>/dev/null; rm -rf "$ROOT"' EXIT

READY=0
ATTEMPT=0
while [ "$ATTEMPT" -lt 50 ]; do
  if python3 - <<'PY' >/dev/null 2>&1
import socket
with socket.create_connection(('127.0.0.1', 18923), timeout=0.1):
    pass
PY
  then
    READY=1
    break
  fi
  ATTEMPT=$((ATTEMPT + 1))
  sleep 0.1
done
if [ "$READY" -ne 1 ]; then
  echo "FAIL: 假 LLM 端點沒有啟動"
  exit 1
fi

(cd "$ROOT/boss" && "$AOS" say "請回覆。" >/dev/null)
(cd "$ROOT/boss" && \
  AOS_LLM_URL=http://127.0.0.1:18923/v1 AOS_LLM_MODEL=fake \
  "$AOS" run --step 1)

if [ -f "$CAP" ] && python3 - "$CAP" <<'PY'
import json
import sys

with open(sys.argv[1], encoding='utf-8') as source:
    request = json.load(source)
prompt = request['messages'][0]['content']
raise SystemExit(0 if '你可以聯絡這些人' in prompt and 'w1' in prompt else 1)
PY
then
  echo "PASS: system prompt 裡有通訊錄（agent 知道隊上有 w1）"
else
  echo "FAIL: system prompt 從不提通訊錄；agent 不知道隊上有誰"
  exit 1
fi
