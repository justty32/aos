← [proto5 README](../README.md)｜規範 [spec/](../spec/README.md)

# proto5 教程

照順序做，每篇都接著上一篇開好的東西。每篇都有：目標、前提、能照抄的指令、每步你會看到什麼、「底下在幹嘛」、常見錯誤、收工。
指令從 repo 根目錄開始貼進 bash／zsh；工作目錄一律是 `$HOME/aos-try`（第 1 篇寫好 `env.sh`，之後每開一個新終端先 `. $HOME/aos-try/env.sh`）。

| # | 篇 | 一句話 |
|---|---|---|
| 01 | [設定、啟動與關閉 daemon 和 kernel](01-daemon-kernel.md) | 環境檔、`llm.json`、`kernel.json` 一次寫好（很久不動）；開機、檢查、關機、每天重開機 |
| 02 | [用 kernel 跑工作：一次性與反覆](02-kernel-jobs.md) | 不碰 agent，直接叫 kernel 跑程式：once、反覆到做完、一直失敗會被退件 |
| 03 | [從零開始第一個 agent，以及關掉它](03-first-agent.md) | `init`、`check`、`start`、`say --wait`、`listen`、`status`、`stop` |
| 04 | [給 agent 加工具、暫停它、救回它](04-tools-and-pause.md) | 自己寫一支工具；工具壞了會怎樣；`pause`／`continue`；端點壞了的連敗暫停 |
| 05 | [管一大堆 agent](05-many-agents.md) | cpu 開幾顆、一次操作一批、`aos-kernel ls` 看全局、health 三階段、`continue --all` |
| 06 | [附錄：不用 init，手寫一個 agent 家](06-appendix-manual-home.md) | 家就是一個資料夾加三份檔 |

只想最快看到 agent 回話：[proto5 README 的「五分鐘」](../README.md#五分鐘看到-agent-回話)，那段是 01＋03 的濃縮。

要查細節：每個指令與檔案格式的規範在 [spec/](../spec/README.md)；給使用者的精簡版是
[agent 家](../spec/agent/essentials.md) 與 [aos-agent 指令](../spec/aos-agent/essentials.md) 兩份「使用者只需要懂的」。
