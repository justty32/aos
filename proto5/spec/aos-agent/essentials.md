← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 使用者只需要懂的（09-24 試玩 r2 補）

日常只用這幾個指令，每個都用 `--target DIR` 指 agent 家，省略＝目前資料夾（細節在 §1；09-24 fix-r4 改）：

| 指令 | 做什麼 |
|---|---|
| `aos-agent init [--target DIR] [--force]` | 生一個最小可跑的 agent 家；資料夾裡已有別的東西要加 `--force`（§1.1） |
| `aos-agent check [--target DIR] [--probe]` | start 之前先查一遍：K 的設定（K 自己找）、池、模型代號、工具找不找得到；`--probe` 真的打一次模型（§1.7；09-24 advice-r1 從 `aos-kernel check --agent` 搬來） |
| `aos-agent start`／`stop [--target DIR]` | 向 kernel 登記／撤銷（§11；要 `AOS_KERNEL_HOME`，stop 沒設就用 `tick.json` 記的）；已登記的 `start` 印 `already started`、退 0 |
| `aos-agent say "文字" [--target DIR] [--wait [秒]]` | 投一則話；`--wait` 等到回話印出來（§1.2） |
| `aos-agent listen [--target DIR] --last [N]｜--wait [秒]｜--follow` | 看回話：最後 N 則／等下一則／一直印，三選一要給；加 `--show-calls` 連叫了哪些工具一起看（`--show-calls-full` 看完整參數與回傳）（§1.5） |
| `aos-agent talk [--target DIR] [--wait 秒] [--show-calls]` | 來回對話：打一行、等回話、再打一行；`/status`、`/context`、`/history` 等 slash 指令，Ctrl-C 離開（§1.9；09-24 talk 補） |
| `aos-agent status [--target DIR]` | 現在在哪、在等什麼、最近的錯、kernel 那邊的狀態（§1.3） |
| `aos-agent pause [--target DIR]` | 手動暫停：還登記著，但每格什麼都不做（§1.6） |
| `aos-agent continue [--target DIR]` | 解除手動暫停與連敗暫停；先標「已解除暫停，等下一次成功」，真的成功了才標「已恢復」（§1.4） |
| `aos-agent continue --all` | llm.json 是共用的，一壞全部一起暫停：這個把 kernel 帳本裡所有登記的 agent 一次解開（§1.4；09-24 fix-r5 補） |

它停下來、不往前走的樣子，和怎麼恢復（09-24 fix-r5 多兩種會自己好的）：

| 樣子 | 怎麼看出來 | 怎麼恢復 |
|---|---|---|
| **手動暫停**（09-24 fix-r4 補）：人打了 `pause` | `status` 第一行 `手動暫停`；家裡有 `paused` 檔 | `aos-agent continue` |
| **重試中**（09-24 fix-r5 補）：問模型失敗 1、2 次，還會自己再試 | `status` 第一行 `重試中（連敗 N/3）` | 不用做什麼；原因沒修好第 3 次就變連敗暫停 |
| **連敗暫停**：問模型連續失敗 3 次 | `status` 第一行 `連敗暫停`、`wait` 行寫「連敗暫停」；`log/agent.err` 有 `stuck` 行；`aos-kernel ls` 的 proc 表備註欄標 `連敗暫停中` | 修好原因（endpoint、模型代號、逾時），`aos-agent continue`（好幾個一起就 `continue --all`） |
| **恢復中**（09-24 fix-r5 補）：某顆 cpu 死了、daemon 正在重拉 | `status`／`aos-kernel ls` 第一行 `恢復中（llm cpu dead，daemon 重拉中）` | 不用做什麼，通常幾秒內好 |
| **bad**：設定讀驗錯（info／工具檔壞了）連退 1 達 kernel 的 `bad_after` 次 | `aos-kernel ls` 的 proc 表狀態 `bad`、表下一行 `agent-<名> 壞了，看 <agent>/log/agent.err`；`status` 的 `kernel` 行也看得到 | 照 agent.err 修好，`aos-agent stop` 再 `start` |
| **沒在跑**：daemon 沒開、kernel 沒 boot、或沒人替 kernel 開 tick | `aos-kernel ls` 第一行 `daemon 沒在跑`、`停機中`、`daemon … 沒在替這個 kernel 開 tick` 之類（2026-09-24 one-boot 改） | `aos up --target K` |
| **沒登記**：`stop` 過或從沒 `start` | `status` 的 `kernel` 行寫「沒登記」 | `aos-agent start` |

`info.json` 各格與工具檔的格式在 [agent.md 的「使用者只需要懂的」](../agent/README.md)。
下面 §2～§10 是走一格、送批、收回、崩潰恢復的機制，日常不用讀；有東西卡住又不是上表那幾種，再往下看。
