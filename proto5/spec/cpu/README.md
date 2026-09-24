← [spec 總導航](../README.md)

# cpu 範式與 exec cpu

← [proto5 README](../../README.md)｜跑一次：[aos-exec.md](../aos-exec/README.md)｜inst 長相：[inst-posix.md](../inst-posix/README.md)｜上層：[kernel](../kernel/README.md)、[daemon](../daemon/README.md)

> 第 1 版，2026-09-23 定稿，2026-09-24 fix-r4 改命令列；已實作（[`aos_home.py`](../../lib/aos_home.py)、[`aos_client.py`](../../lib/aos_client.py)、[`aos_exec_cpu.py`](../../lib/aos_exec_cpu.py)，入口 `aos-cpu`）。輪次、審查與實作沿革在檔尾〈沿革〉（09-24 試玩 r3 搬）。

一句話：**一顆 exec cpu 是一個資料夾加一個主人行程：逐件把 `requests/` 裡的工作 request 照 `aos-exec`
跑一次，回音寫到 `responses/` 同名檔；反覆、排程都是 kernel 的事，cpu 只做一次。**

問模型、跑工具、agent 走一格，全是 aos-exec 的目標、全是程式；能力差別在程式跟 cpu 的環境（§4.1），不在 cpu 的種類。
kernel 跟 daemon 的家也照這個範式長，它們多認的 method 各在自己那份。

## 9. 已拍板的前提（使用者定的，不重問）

規則一是軟性的（硬性以後走 FUSE）；cpu 聽命執行不自己迴圈；IPC 用 pipe（多機以後再 socket）；
JSON-RPC 2.0；所有**工作** request 的 method 都是 `aos-exec`（`ack`／`stop` 是管理用的）；params 就是 aos-exec 的 argv（`target`＋旗標），不包 inst 內容；
cpu 的環境就是工作的環境（llm cpu＝環境裡有 `llm-http` 的普通 exec cpu）；daemon 的 `spawn` 有 `restart:true`。

## 8. 這份沒管的

**適用範圍**：同一台 POSIX 機器、大家都直接摸得到各家的檔案。多機（socket）、Windows 都是以後另訂，
這份寫的 fd／訊號／flock／`link` 都是 POSIX 的。

誰拉 cpu 起來、怎麼知道它死了、`restart`、停機階梯（[daemon](../daemon/README.md)）；誰決定哪個目標去哪顆、
一次性還是反覆、專門打 LLM 的 cpu 怎麼保留（[kernel](../kernel/README.md)）；agent 怎麼用 aos-exec 取代原本的 llm／tool cpu（agent）。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔（`history.md`、`impl-notes.md`、`rulings.md` 等）。

| 檔 | 內容 |
|---|---|
| [terms.md](terms.md) | §0 名詞（白話） |
| [layout.md](layout.md) | §1 資料夾與規則一；§2 `info.json` 與 `state.json` |
| [messages.md](messages.md) | §3 JSON-RPC 2.0 信封：§3.1 怎麼放單、§3.2 error.code 編法、§3.3 `ack` |
| [methods.md](methods.md) | §4 exec cpu 認的 method：§4.1 `aos-exec`、§4.2 `stop`、§4.3 壞單也回音 |
| [stop.md](stop.md) | §5 停下來：溫和停、第二次訊號強制停、主人被 KILL、誰負責發 |
| [lifecycle.md](lifecycle.md) | §6 主人的一生：啟動、開機對帳、迴圈；§7 退出碼與 stderr |
| [choices.md](choices.md) | §10 我自己選的（等使用者確認） |
| [impl-notes.md](impl-notes.md) | 實作補記（2026-09-24） |
| [history.md](history.md) | 沿革 |
