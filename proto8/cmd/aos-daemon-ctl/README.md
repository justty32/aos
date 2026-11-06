# aos-daemon-ctl — 把 proc 掛到 aos-daemon 上、起停、暫停

← [cmd](../README.md)

`bin/aos-daemon-ctl`（Python）往 daemon 的信箱投 procs_added／procs_removed 等信、`ping` 問它有沒有在回信、`ls` 讀它的表。是薄殼：找 daemon、讀表、寄信等回信的本體在 [`py/daemon_ctl.py`](../../py/README.md)（aos-agent、aos-eca-screen 也 import 它）。說明在 [cmd/docs/03](../docs/03-aos-daemon-ctl.md#aos-daemon-ctl)、[04（續）](../docs/04-aos-daemon-ctl續.md)。
