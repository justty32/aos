#!/usr/bin/env bash
# 啟動 litellm proxy，預設吃同目錄的 litellm.yaml。
#
# 用 uv run 臨時把 litellm 拉進來跑，不用先裝、也不用維護 venv。
#
# litellm 釘死 1.87.5（它自己釘 fastapi==0.124.4、uvicorn==0.33.0），原因：
# - 2026-09-20 實測 ChatGPT 訂閱（chatgpt/ provider）非串流 chat completion 只有這版能用；
#   1.93.0 起到 1.103.0.dev2 都壞：後端 response.completed 的 output 是空的，新版的
#   responses→chat 橋接撈不回串流裡的內容，回 "Unknown items in responses API response: []"。
#   串流（stream: true）新舊版都通。等新版修好再考慮升。
# - 1.88～1.92 PyPI 上沒有，1.87.5 下一版就是 1.93.0。
# 舊教訓（2026-08-06，當時是用 fastapi<0.130 間接釘出 1.87.5）：
# - fastapi>=0.130 拿掉私有 API get_flat_dependant，舊 litellm 開機就 crash（1.93+ 已改依 fastapi>=0.136）。
# - fastapi<0.119 會讓 uv 反向解析回 litellm 1.79.x，那版 Ollama function calling 是用文字塞
#   system prompt 讓模型自己接龍 JSON，3 個工具以上就常常漏答成純文字。
set -euo pipefail
CONFIG="${1:-$(dirname "$0")/litellm.yaml}"
PORT="${2:-4000}"
exec uv run --no-project --with 'litellm[proxy]==1.87.5' \
    litellm --config "$CONFIG" --port "$PORT"
