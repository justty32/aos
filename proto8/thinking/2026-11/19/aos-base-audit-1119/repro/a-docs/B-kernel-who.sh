#!/bin/bash
# 測：設了 AOS_KERNEL 而那個 kernel 不答（忙／睡），agent 的 mailbox_peek、clock_register（給了 box）都因內部 ctl who 先問 kernel 而 KernelFailed
# 用法：~/.aos/scratch/aos-base-audit-1119/bin/clean bash 此檔
set -u
W=$(mktemp -d "$HOME/.aos/scratch/aos-base-audit-1119/a-docs/forkB/who.XXXX")
mkdir -p "$W/d" "$W/me"
aos-post init "$W/silent" >/dev/null          # 沒人服務的 kernel 信箱（等於 kernel_gate 正在 turn 中）
aos-post init "$W/me/queue" >/dev/null
export AOS_STACK=$W/me AOS_DAEMON=$W/d AOS_KERNEL=$W/silent AOS_WS=$W
echo "--- aos-agent ctl who"
time timeout 20 aos-agent ctl who --json; echo "exit $?"
echo "--- tool mailbox_peek"
echo "{}" | timeout 20 aos-exec "$AOS_HOME/lib/tools/agent/mailbox_peek"; echo "exit $?"
echo "--- tool clock_register add WITH box"
echo "{\"op\":\"add\",\"name\":\"x\",\"every\":5,\"text\":\"hi\",\"box\":\"$W/me/queue\"}" | timeout 20 aos-exec "$AOS_HOME/lib/tools/agent/clock_register"; echo "exit $?"
