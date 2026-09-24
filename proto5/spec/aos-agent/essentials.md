← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 使用者只需要懂的（09-24 試玩 r2 補）

日常只用這幾個指令，每個都用 `--target DIR` 指 agent 家，省略＝目前資料夾（細節在 §1；09-24 fix-r4 改）：

| 指令 | 做什麼 |
|---|---|
| `aos-agent init [--target DIR]` | 生一個最小可跑的 agent 家（§1.1） |
| `aos-agent start`／`stop [--target DIR]` | 向 kernel 登記／撤銷（§11；要 `AOS_KERNEL_HOME`，stop 沒設就用 `tick.json` 記的） |
| `aos-agent say "文字" [--target DIR] [--wait [秒]]` | 投一則話；`--wait` 等到回話印出來（§1.2） |
| `aos-agent listen [--target DIR] [--last｜--wait [秒]｜--follow]` | 看回話：最後一則／等下一則／一直印（§1.5） |
| `aos-agent status [--target DIR]` | 現在在哪、在等什麼、最近的錯、kernel 那邊的狀態（§1.3） |
| `aos-agent pause [--target DIR]` | 手動暫停：還登記著，但每格什麼都不做（§1.6） |
| `aos-agent continue [--target DIR]` | 解除手動暫停與連敗暫停（§1.4） |

它停下來、不往前走的五種樣子，和怎麼恢復：

| 樣子 | 怎麼看出來 | 怎麼恢復 |
|---|---|---|
| **手動暫停**（09-24 fix-r4 補）：人打了 `pause` | `status` 第一行 `手動暫停`；家裡有 `paused` 檔 | `aos-agent continue` |
| **連敗暫停**：問模型連續失敗 3 次 | `status` 第一行 `連敗暫停`、`wait` 行寫「連敗暫停」；`log/agent.err` 有 `stuck` 行 | 修好原因（endpoint、模型代號、逾時），`aos-agent continue` |
| **bad**：設定讀驗錯（info／工具檔壞了）連退 1 達 kernel 的 `bad_after` 次 | `aos-kernel ls` 那行 `bad  看 <agent>/log/agent.err`；`status` 的 `kernel` 行也看得到 | 照 agent.err 修好，`aos-agent stop` 再 `start` |
| **沒在跑**：daemon 重開過、kernel 沒 boot | `aos-kernel ls` 的 cpu 行 `missing` 並附提示 | `aos-kernel boot --target K --daemon-target D` |
| **沒登記**：`stop` 過或從沒 `start` | `status` 的 `kernel` 行寫「沒登記」 | `aos-agent start` |

`info.json` 各格與工具檔的格式在 [agent.md 的「使用者只需要懂的」](../agent/README.md)。
下面 §2～§10 是走一格、送批、收回、崩潰恢復的機制，日常不用讀；有東西卡住又不是上表五種，再往下看。
