#!/bin/bash
# 收 e-upper 暫存樹：兩台 daemon 都 shutdown（只用自己 stack 的絕對路徑）
E=$HOME/.aos/scratch/aos-base-audit-1119/e-upper
timeout 60 aos-daemon-ctl -d $E/tree/.stack shutdown
timeout 60 aos-daemon-ctl -d $E/tree/llms/stacks/llm shutdown
