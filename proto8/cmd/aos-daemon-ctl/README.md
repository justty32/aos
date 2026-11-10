# aos-daemon-ctl — 掛上 proc、起停、暫停、自檢與清理舊列

← [cmd](../README.md)

`bin/aos-daemon-ctl`（Python）往 daemon 的信箱投 procs_added／procs_removed 等信、`ping` 問它有沒有在回信、`ls` 讀它的表、`poke` 按門鈴叫它立刻看檔（11-09，碰 pid 的子命令；本體在 `py/daemon_ctl/poke.py`，[cmd/docs/03 的 poke](../docs/03-aos-daemon-ctl.md)）、`shutdown` 停這台 daemon 本身（11-10：確認它活著→寫它自己 ctl 的 stop→poke→等退出；本體在 `py/daemon_ctl/ctl.py` 的 `shutdown`，同一份 03）。**信一律直寄這台 daemon 的 ctl 信箱、不看 `AOS_KERNEL`**（使用者 11-07「aos-daemon-ctl 永遠直寄」）：這支＝人直接敲板子；要經判官（作業系統）就用 `aos-agent ctl`。`aos-daemon-ctl --help` 印頂層、`aos-daemon-ctl 子命令 --help` 印那個子命令的英文說明。是薄殼：找 daemon、讀表、寄信等回信的本體在 [`py/daemon_ctl/`](../../py/README.md)（找 daemon 在 `table.py`、判型組信在 `entry.py`、寄信等回信在 `post.py`；aos-agent、aos-eca-screen 也 import 它）。說明在 [cmd/docs/03](../docs/03-aos-daemon-ctl.md#aos-daemon-ctl)、[04（續）](../docs/04-aos-daemon-ctl續.md)。

`--timeout-s S` 是寄出後本機看多久信被認領，`--reply-to BOX` 只寄不等、由呼叫者讀回信。判官本身睡著或停著＝設計系統的人要管的風險，手動叫醒：`aos-daemon-ctl wake 名字`（停著用 `start`）。判官排隊、到期拒信與窗見 [kernel 模式](../../kernel/docs/02-kernel-modes.md)（那些只有經判官的 `aos-agent ctl` 用得到）。

`sleep` 也接受 `stopping`：送 SIGTERM（10 秒後仍在就 SIGKILL），原本 stop 中的列退後留 `stopped`，保留入口、用 `start` 再起。

`prune` 只查檔案與 stopped 原因，自檢表上可疑的列；`prune --older-than 7d` 預覽久未修改的 stopped／sleeping 列，加 `--apply` 才走 rm 下表，保留 stack／ws 的全部檔案。`--apply` 必須附門檻；細節見 [04 的 prune](../docs/04-aos-daemon-ctl續.md#prune自檢與清理舊列)。
