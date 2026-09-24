← [本提案](README.md)

# 其他四個角色：順帶可得或先不做

主方案（當一種 cpu）做完，下面幾個多半只是「在它上面再包一層」。

## 1. 當純模型後端（先不做）

**怎麼接**：llm.json 一筆 `{"kind": "claude-cli", "model": "sonnet"}`，aos-llm call 不打 HTTP，改跑
`claude -p --tools "" --no-session-persistence --json-schema <assistant message 的形狀>`，把整段記憶與工具清單寫成文字餵進去，要它回 `{"content", "tool_calls"}`。
aos 照舊自己跑工具，它只當「會回 tool_calls 的模型」。

**要改**：`lib/aos_llm_call.py` 讀設定時認 `kind`（現在每筆都**必須**有 `endpoint`，整份一起驗——舊程式看到新的一筆會整份拒收）、多一條不走 HTTP 的路（約 80 行）；`aos-agent check --probe` 對這種代號不能真的問（會花錢），改成只查 `claude --version`。

**為什麼先不做**：它最強的地方（自己的工具、session）全被關掉，只剩「用訂閱額度當 API」；每一格都重送整段記憶、起一次 claude（每次多幾秒），比 HTTP 慢又不省。tool_calls 的 id、arguments 要靠 schema 硬逼，出錯率高。
六軸：少 －、穩 －、省 ○、快 －、懂 ○、安 ＋（沒工具）。

## 2. 當 agent 的一個工具（主方案做完就有）

**怎麼接**：一個工具檔 `tools/delegate.json`，`_meta.argv` 指一支小程式：寫任務書、`aos-kernel add --once --pool claude`、**馬上回單號**；另一支 `delegate_status` 查回音、讀結果。
工具本身在 default 池跑、幾毫秒；真正的活在 claude 池。這樣不違反「沒有同步工具」，也不會讓一顆 default cpu 陪它等半小時。

**要改**：兩支小程式＋工具檔，可以當成 `proto5/tools/` 下的第二個工具包（約 120 行）；不動 aos-agent。
**權限的洞**：工具要能寫 `K/requests/`，也就是拿得到 `AOS_KERNEL_HOME`；而能放任意 inst＝能跑任意指令。agent-access 的方向是工具**拿不到** K。
所以 `delegate` 要做成**受信任的投遞入口**：只收任務書文字，池、模型、程式、工作區、額度寫死在入口那邊，由牢外的程式替它放單（[cost-safety §2](cost-safety.md#2-誰能叫它們)）；光把花錢的池藏在另一個 K 不算權限。
六軸：少 －、穩 ＋、省 ○、快 ○、懂 ＋、安 ○。

## 3. 當一個 agent 的大腦（可選）

使用者先前說過「拿這兩個很成熟的 cli 來作為 aos-agent 的備用」，後來改成「不必同一個 agent 家」。這裡留一份做法，要的時候照做。

**怎麼切換**：llm.json 一筆 `{"kind": "claude-cli", ...}`，agent 的 `info.llm.model` 換成那個代號、`llm.pool` 換成 `claude`、`llm.timeout_ms` 拉到 30 分鐘。**aos-agent、kernel、daemon 都不用知道**，換回來也是改這三格。

**一格怎麼跑**：think 那件工作照舊是 `aos-llm call`，只是它改成「把新進來的 user 話交給 claude 做完一整輪」，claude 用自己的工具做事，最後回一則**沒有 tool_calls** 的 assistant——aos-agent 看到就結清回 idle。
`say`／`listen`／`status`／`pause`／`continue`、連敗暫停、逾時，全照舊。`listen --show-calls` 看不到它內部叫了什麼（`--output-format json` 不含過程）。

**上下文**：session id 存在**那則 assistant message 的一個額外欄位**（例如 `"aos_brain": {"session": "…"}`）——規範本來就「其他 key 原樣留著、不驗」（[agent info §3.2](../../spec/agent/info.md)）。
下一次往回找最後一則帶 `aos_brain` 的 assistant，`--resume <它> --fork-session`，只把那之後的新 user 話送過去；找不到（剛從 HTTP 大腦換過來）就把人格＋整段記憶攤平成文字當第一則。
好處：session id 跟記憶**同一次寫進去**，崩在中間不會對不上；aos 的 `history.json` 是對話的真相（人看的、listen 讀的），它們的 session 是「腦內細節」。
**要補一個洞**：換回 HTTP 大腦時，這個額外欄位會被原樣送給 endpoint，有的端點會拒收——aos-llm 的 HTTP 路**只拿掉 `aos_brain` 這一格**（約 5 行）；不能只留四格，那會破壞「其他欄位原樣透傳」的現有契約。

**重跑的風險**：think 逾時、`Interrupted`（算失敗）與 `stopped`（不算失敗）之後，下一格都會**重問**（[collect §6.1](../../spec/aos-agent/collect.md)、[settle](../../spec/aos-agent/settle.md)）——對 HTTP 模型無害，對 claude 是「整件事再做一次」，加一句「上次被中斷」擋不住重複改檔。
安全的做法是：這種大腦的 think **結果不明就停下來等人**，不自動重問——**這要改 aos-agent**（依大腦種類決定要不要自動重問），不能承諾只改 aos-llm。
**要改**：aos_llm_call 認 `kind`＋新模組 `aos_llm_cli.py`（組提示、跑、解析、帶 session，約 150 行）＋HTTP 路清欄位＋check 的 probe＋aos-agent 的「結果不明不重問」；測試用假的 `claude`／`codex` 放 PATH。1～2 天。
六軸：少 ○、穩 ○、省 ○、快 －、懂 ＋（手感不變）、安 ○。

## 4. 反過來：讓它們用 aos

**最省的做法是 skill，不是 MCP**：寫一份 markdown 告訴 claude「用 Bash 跑 `aos-kernel ls`、`aos-agent say … --wait`、`aos-cli say`」，放進 `.claude/skills/`（codex 用 AGENTS.md）。零程式，它們本來就會跑指令。注意 claude 開了 `--safe-mode` 就**不載入 skill 與 MCP**，所以「准用 aos」的單子不能開 safe-mode（[cost-safety §4](cost-safety.md#4-危險動作怎麼擋)）。
MCP（`--mcp-config`）要另寫一支 aos-mcp 伺服器（proto2 有過一支 `aos-mcp`，可參考但照「舊 proto 是遺產」謹慎採用），好處是參數有型別、權限可以逐個工具開關。codex 0.156 **沒有**當 MCP 伺服器的指令，但能**用** MCP 伺服器（`codex mcp add`）。

**調度者的活能不能變成 aos 的 agent 團隊做**：拆開看——
- 派隊（寫任務書、放單子、等回音、叫審查）：**能**，就是 [uses §7](uses.md#7-把工作流的每一步變成一張單子)；接力手可以是一支小程式或一個 aos-agent。
- 判斷「審查意見哪些必修」、「方向對不對」：要聰明模型，可以是一張 claude 單子；方向性的仍然回使用者（鐵律 5）。
- ff-merge、push、刪分支：**不交出去**。鐵律 2 說不可逆與對外的動作要使用者授權，而且 agent 寄來的不算；這些留在人或頂層手上。
六軸：少 ＋、穩 ○、省 ＋、快 ○、懂 ＋、安 －（它拿到 K 就能放任何單子）。
