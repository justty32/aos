#!/bin/sh
set -eu
A="__PLAY__/stations/6-agent/bob"
if [ -f "$A/agent.json" ]; then
  echo "bob 已經在 $A"
else
  "__R__/proto4-7/aos-user" "$A" new --name bob \
    --system "你是個簡潔、會用工具查證後再回答的助手。" --K "__K__"
fi
