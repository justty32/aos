← [spec 總導航](../README.md)

# daemon：所有 cpu 的父行程

← [proto5 README](../../README.md)｜範式：[cpu.md](../cpu/README.md)｜客戶：[kernel](../kernel/README.md)｜跑一次：[aos-exec.md](../aos-exec/README.md)

> 第 1 版，2026-09-23 定稿，2026-09-24 fix-r4 改命令列；已實作（[`aos_daemon.py`](../../lib/aos_daemon.py)，入口 `aos-daemon`）。輪次、審查與實作沿革在檔尾〈沿革〉（09-24 試玩 r3 搬）。

一句話：**daemon 只管 cpu 行程的生死——啟動、重拉、停止，也就是當爸爸。誰叫它把一個 aos-exec 目標拉起來當孩子，
它就拉；孩子死了看要不要再拉；要停就照階梯把孩子都停掉。** 它不認識 kernel、不看孩子在做什麼、不轉發任何工作。
它自己的家也照 [cpu 範式](../cpu/README.md)長：`info`／`state`／`requests`／`responses`，訊息是 JSON-RPC。

---

## 8. 已拍板的前提（使用者定的，不重問）

daemon 是所有 cpu 的父行程、最單純；IPC 用 pipe，只管生死；`spawn` 有 `restart:true`；家照 cpu 範式、JSON-RPC；
同名不同目標＝`NameTaken`。daemon 永遠以一般使用者跑，不用 root、不 sudo、不切使用者；隔離交給工具那層的 bwrap 牢
（見 [notes/2026-09-24-agent-access](../../notes/2026-09-24-agent-access/README.md)）——2026-09-24 使用者裁決，撤掉
「daemon 要 sudo 切使用者所以跟 kernel 分開」這條理由（見 [daemon-split-review](../../notes/2026-09-24-daemon-split-review/README.md)）。

## 7. 這份沒管的

適用範圍同範式 §8（同一台 POSIX 機器；fork／waitpid／flock／訊號都是 POSIX 的）。孩子在做什麼（kernel／cpu 範式）；誰該被拉、幾顆（kernel 的 `info.cpus`）；多機（以後 socket）。
沒有 `aos-daemon-ctl`：客戶端就是往 `D/requests/` 放檔，kernel 的 boot／tick 已經在做；人要看就 `cat D/state.json`，
要停就放一份 `stop-*.json` 或 Ctrl-C（09-24 補：或 `aos-daemon halt`，§6）。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔（`history.md`、`impl-notes.md`、`rulings.md` 等）。

| 檔 | 內容 |
|---|---|
| [terms.md](terms.md) | §0 名詞（白話） |
| [home.md](home.md) | §1 家；§1.1 `info.json`；§1.2 `state.json`（孩子表） |
| [spawn.md](spawn.md) | §2 孩子怎麼拉 |
| [methods.md](methods.md) | §3 `D/requests/` 認的 method |
| [loop.md](loop.md) | §4 一圈：主人每圈做的事 |
| [shutdown.md](shutdown.md) | §5 停機：照階梯把孩子停掉 |
| [lifecycle.md](lifecycle.md) | §6 主人的一生：§6.1 啟動；§6.2 退出碼與 stderr |
| [choices.md](choices.md) | §9 我自己選的（等使用者確認） |
| [impl-notes.md](impl-notes.md) | 實作補記（2026-09-24） |
| [history.md](history.md) | 沿革 |
