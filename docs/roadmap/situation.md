# 方向與現況盤點

← [roadmap 導覽](README.md)｜[文件索引](../README.md)

> 這個檔裝的是：一句話的方向，以及 `core/inst`／`core/tooljson`／`core/llms` 三個小專案的現況診斷——也就是「為什麼主線先做回合原語」。

## 一、一句話的方向

> aos 的本體是「**資料夾 + 回合 + inst**」。LLM、tool 這些都不是新機制，是疊在上面
> 的子命令。

所以主線**不是**繼續把 llmkit 移植完，而是**先把回合原語做出來**。移植出來的那兩個
小專案要等模型立起來之後，才知道它們該長什麼形狀。

這條路線有個容易被忽略的紅利：**因為 `inst` 跑的是 POSIX 指令，agent loop 不需要等
`core/llms`**——「呼叫一次模型」可以先用任何一支現成的 LLM CLI 頂著（[T5](stages.md#t5)）。自家
的 LLM CPU 是之後把它換掉（[T6](stages.md#t6)），不是前置條件。

這條路線已經改寫了 [overview.md](../overview.md) 的「一句話」：aos 原本寫成「一組 POSIX
小工具的集合」，T1 落地之後改成「一個資料夾的回合制執行器，外加一組 POSIX 小工具」。

## 二、現況盤點

### `core/inst` — 可用，而且它就是回合原語缺的那一半

`aos inst [file]`（[D8](decisions.md#d8) 已定要改名成 `aos exec`）目前的語意是：讀完整份 JSON（單筆物件或陣列）、**全部驗證通過才
開始執行**、依序 blocking 跑完。這正好就是一回合要的東西——「一批指令，要嘛整批合
法，要嘛一筆都不跑」。

關鍵的好消息：**folder 模式可以完全在 CLI 層做完**。凍結範圍是
`inst.cpp`／`format.cpp`／`exec.cpp`／`spawn_prep`／`wait`／`capi*`；
[`core/inst/src/run.cpp`](../../core/inst/src/run.cpp) 不在凍結名單裡
（見 [code map](../../wf/workflows/common/code-map.md)）。T1 不需要解凍任何東西。

### `core/tooljson` — 底下對，介面錯

有用的是 spec 載入、schema 驗證與 exec 配方的 **argv 展開**——那一步**正是「把一個
tool call 翻譯成一筆 instruction」**，是模型真正需要的東西。

錯的是 `Body::run(args_json)` 這個形狀：它假設工具由 tooljson 自己跑起來。在回合模型
裡 tooljson **不該執行任何東西**，它應該**產出 instruction** 交給 inst。目前
`ExecBody::run()` 還回一句「尚未實作」，等於這條錯路還沒鋪下去——這是運氣好。

### `core/llms` — 底下對，介面錯（同一個病）

有用的是 transport 那一層：curl、endpoint preset、串流、capability 三態。這些是實測
過會動的水電。

錯的是 `Bot::ask()` 這個形狀：**同步問一句、回一個 `Reply`、對話狀態留在記憶體裡**。
模型要的是反過來的東西——**一次 LLM 回合的產出是「下一回合的 instruction」，狀態留在
資料夾裡**。一支 `aos llm exec <folder>` 跑完就結束，記憶體什麼都不留。

### 一句話的診斷

> 兩個小專案都把自己寫成「**函式庫，等別人呼叫**」；模型要的是「**一顆 CPU，被 inst
> `exec` 起來，讀自己的 instruction 檔，寫下一回合**」。

失敗的是**介面與狀態放哪裡**，不是底下的水電。所以是改造，不是全部丟掉——見
[決策 D4](decisions.md#d4)。
