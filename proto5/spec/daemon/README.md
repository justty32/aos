← [spec 總導航](../README.md)

# daemon：所有 cpu 的父行程

← [proto5 README](../../README.md)｜範式：[cpu.md](../cpu/README.md)｜客戶：[kernel](../kernel/README.md)｜跑一次：[aos-exec.md](../aos-exec/README.md)

> 第 1 版，2026-09-23 定稿，2026-09-24 fix-r4 改命令列；**2026-09-24 proto5-2 池式納入**：按池管、宣告式、`spawn` 換成 `scale`、有 `ls`／`kill`、退避與節流、批次階梯。
> 已實作（[`aos_daemon.py`](../../lib/aos_daemon.py) 與 `aos_daemon_*.py`，入口 `aos-daemon`）。沿革在 [history.md](history.md)。

一句話：**daemon 只管 cpu 行程的生死——啟動、重拉、停止，也就是當爸爸。** 它手上是一份「每池要哪幾號」的宣告（誰送來的 `scale` 單），
每一圈把實際的孩子往宣告靠：少了補、多了收、死了等一下再拉。它不認識 kernel、不看孩子在做什麼、不轉發任何工作。
它自己的家也照 [cpu 範式](../cpu/README.md)長：`info`／`state`／`requests`／`responses`，訊息是 JSON-RPC。

---

## 8. 已拍板的前提（使用者定的，不重問）

daemon 是所有 cpu 的父行程、最單純；IPC 用 pipe，只管生死；家照 cpu 範式、JSON-RPC；同一個池名換了主人＝`NameTaken`。
daemon 永遠以一般使用者跑，不用 root、不 sudo、不切使用者；隔離交給工具那層的 bwrap 牢
（見 [notes/2026-09-24-agent-access](../../notes/2026-09-24-agent-access/README.md)）——2026-09-24 使用者裁決，撤掉
「daemon 要 sudo 切使用者所以跟 kernel 分開」這條理由（見 [daemon-split-review](../../notes/2026-09-24-daemon-split-review/README.md)）。
**2026-09-24 使用者定的池式**：宣告式（kernel 只說「P 要 N 顆」，daemon 補、重拉（節流）、收）；daemon 內部按池管、可帶多池；指令全帶 `--pool`；
孩子表不整份重寫；階梯批次做。（第 1 版的「`spawn` 有 `restart:true`」因此拿掉。）

## 7. 這份沒管的

適用範圍同範式 §8（同一台 POSIX 機器；fork／waitpid／flock／訊號都是 POSIX 的）。孩子在做什麼（kernel／cpu 範式）；
誰該被拉、幾顆（kernel 的池表，[kernel §1.1](../kernel/info.md)）；多機（以後 socket）。
沒有 `aos-daemon-ctl`：客戶端就是往 `D/requests/` 放檔；人要看用 `aos-daemon ls`（偷看 `pools/*/summary.json`），要停用 `aos-daemon halt` 或 Ctrl-C。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔。

| 檔 | 內容 |
|---|---|
| [terms.md](terms.md) | §0 名詞（白話） |
| [home.md](home.md) | §1 家；§1.1 `info.json`；§1.3 `state.json`；崩了會怎樣 |
| [pools.md](pools.md) | §1.2 池：`pool.json`（宣告）、`kids/<i>.json`（一顆一檔）、`summary.json`（摘要）、池怎麼拿掉 |
| [spawn.md](spawn.md) | §2 孩子怎麼拉：fd 0 一條 pipe、`go` 握手、拉不起來 |
| [methods.md](methods.md) | §3 `D/requests/` 認的 method：`scale`、`kill`、`ls`、`stop`、`ack` |
| [loop.md](loop.md) | §4 一圈：狀態圖、按池對帳、退避、令牌桶、開檔數 |
| [shutdown.md](shutdown.md) | §5 停機與階梯：批次做、`halt` 後 `pool.json` 留著、跟 kernel 停機的順序 |
| [lifecycle.md](lifecycle.md) | §6 主人的一生：用法總表、`halt`；§6.1 啟動（照 `pool.json` 拉回來）；§6.2 退出碼 |
| [cli.md](cli.md) | §6.3 `ls`（`running N（含 restarting M）`）、`scale`、`kill` |
| [choices.md](choices.md) | §9 我自己選的（等使用者確認） |
| [impl-notes.md](impl-notes.md) | 實作補記（2026-09-24） |
| [history.md](history.md) | 沿革 |
