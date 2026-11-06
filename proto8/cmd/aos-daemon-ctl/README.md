# aos-daemon-ctl — 把 proc 掛到 aos-daemon 上、起停、暫停

← [cmd](../README.md)

`bin/aos-daemon-ctl`（Python）往 daemon 的信箱投 procs_added／procs_removed 等信、`ping` 問它有沒有在回信、`ls` 讀它的表（設了 `$AOS_KERNEL` 信改寄判官，寄前印一行 `warning: routing via AOS_KERNEL=…`）。`aos-daemon-ctl --help` 印頂層、`aos-daemon-ctl 子命令 --help` 印那個子命令的英文說明。是薄殼：找 daemon、讀表、寄信等回信的本體在 [`py/daemon_ctl/`](../../py/README.md)（找 daemon 在 `table.py`、判型組信在 `entry.py`、寄信等回信在 `post.py`；aos-agent、aos-eca-screen 也 import 它）。說明在 [cmd/docs/03](../docs/03-aos-daemon-ctl.md#aos-daemon-ctl)、[04（續）](../docs/04-aos-daemon-ctl續.md)。

add／start／wake 可用 `--queue-wait-s S` 設信裡的判官排隊期限（非負秒，0＝不排；沒給＝不過期），`--timeout-s S` 是寄出後本機觀察多久，兩者各管一事。`--reply-to BOX` 只寄不等，由呼叫者讀回信。`AOS_KERNEL` 只作信箱路由，不認 kernel 身份；喚醒收件者用 `AOS_KERNEL= aos-daemon-ctl wake NAME`。判官先來先掛、到期拒信與窗見 [kernel 模式](../../kernel/docs/02-kernel-modes.md)，逾時撤信與晚套競態見 [aos-agent 限制](../aos-agent/docs/02-已知限制.md)。
