# `knowledge/aos/status.md` 的中文映照版，給人看；正本是 `knowledge/` 那份

> 正本：`proto8/knowledge/aos/status.md`，跟到正本 commit `fe053b828`（正本這頁最後一次改動）。英文譯成繁體中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣；每個標題前一行的粗體 `#/…` 是那一節在正本裡的尋址，別頁寫的 `aos/status.md#/…` 對的就是它。改請改正本，再照 [README](../README.md) 的做法跟上這份。

---

**`#/Reading state`**

# 讀狀態

daemon 的表、agent 可能處在的 phase，以及每個 phase 對你代表什麼。

每個 daemon 都記一張表，每個 proc 一列：`name  phase  ws  queue N  [reason ...]`。顯示它的工具和指令：工具 `agents_ctl` 加 `{"op": "ls"}`（整張表；`subagent` `{"op": "ls"}` 只列你的）；給人用的是 `aos-agent ctl ls` 和 `aos-agent ctl state --target <name>`。

Phase：

| phase | 意思 | 該怎麼做 |
|---|---|---|
| `running` | 活著；回覆它 queue 裡的信 | 跟它說話（`say`／`ask`） |
| `stopped` | 沒在跑；stack 保留。要嘛是人停了它，要嘛是它當掉了：這時那一列有 `reason`，帶著弄死它的那行錯誤 | 讀 `reason`；修好原因（常常是工具或腦的設定不對），然後由人跑 `aos-agent ctl start --target <name>`。你寄的信會保留，不會被回覆 |
| `sleeping` | daemon 讓它睡了（daemon 正在關機，或 `sleep` 指令）；daemon 回來或收到 `wake` 時它會醒 | 等，或問人 |
| `stopping` | 正在做完目前這一輪再停 | 等 |
| `stuck` | 活著，但它沒有及時回應控制請求（stop、pause ...）：只有在那一列設了 `stuck_after_cycles`／`stuck_after_ms` 時才會（沒設或 0 = 永不 stuck）。`reason` 寫著 `control window has not been answered within N cycles`。通常是某一步很長，或身體卡住了。它一回應就變回 `running`。daemon 只是標記它，除非那一列有 `restart_on_stuck`：這時它會被重新啟動，試 3 次都沒回應就停掉 | 等；指令把它當成 `running`。如果一直 stuck，告訴人（他們可以 `sleep` 或 `rm` 它） |

一列不見了：那個 proc 做完了（結束碼 0）或被移除了（`rm`）。`rm` 保留它的 stack（只有帶 purge 的 `rm` 才刪掉）；用同一個 stack 再加回來，就會接上它。`ask` 之後，不見的列會顯示成 `InstanceMissing`。

`queue N`：它的 queue 裡有幾封信在等。`queue 0` 加上 phase `running` 表示閒著。

讀 `reason`：它是死掉的那個東西最後一行錯誤，常見的格式是 `program: error: Code reason`。例子：`agent-fsm: error: LlmKernelMissing AOS_LLM_KERNEL is not set` 表示這個 agent 連不到 llm kernel；必須由人來設定。代號見 `aos/errors.md`。

很久沒動靜：當一個 agent 在很長的一輪裡（eca 的 CLI 一輪，或 agent-fsm 在等它的腦），而且 10 分鐘都沒有任何變動，它的 stack 會有 `quiet.json`（`{"quiet": true, "what": "cli_turn" | "brain_reply", "since", "at", "quiet_s", "pid"}`）。它只是一個標記：不會殺掉任何東西，不會丟掉任何信，phase 仍是 `running`。這一輪又動起來或結束時，它就消失；如果它的 `pid` 不在了，這個檔就是過期的。很長的一輪不是當掉：除非定義設了，否則沒有時間限制。

暫停：人可以暫停和恢復 agent（`aos-agent ctl pause/resume`）。暫停的 agent 在 daemon 的表上仍顯示 `running`；它只是不走下一步。如果對子 agent 的 `ask` 卡住又沒有 `reason`，它可能是被暫停了；需要人來恢復它。
