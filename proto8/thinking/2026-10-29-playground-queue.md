# 2026-10-29 playground：agent 的輸入是對話簿、看信箱是一個 tool（「A」的最小版）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜出發點：[10-28 medium 決定 32](2026-10-28-medium.md)（第十七段）｜前一個試驗場：[10-26 playground](2026-10-26-playground.md)｜history 的格式：[agent-round § 4](2026-10-28-agent-round/02-2-round-一輪本身.md#4-單位介面)｜信箱：[N-16](../docs/NORMS/05-基礎設施-窗.md)、[aos-post](../impls/aos-post/README.md)

> **10-29 晚看完實跑後方向改了**：兩個使用場景都用不到「agent 自己用 tool 看信箱」，這份的 inbox tool 解錯題；下面的代定與「要帶給使用者的題」先擱著，見文末[看完 A 之後](#結論10-29-晚看完-a-之後)。

## 使用者原文（10-29 晚，逐字）

> 那就A。直接叫queue不太好吧...再想想

> 那就1

（「1」＝檔名沿用 `history.jsonl`，不叫 queue；queue 只是概念詞。）

## 結論（10-29 晚實作；細節與指令在試驗場 `~/code/playground/README.md`，不在 git）

- **節點 `~/code/playground/agent/`**：`_entry` 一行 shell 轉 `main.py`。一輪＝命令列給的一句話先當一則 `user` 接進 `$AOS_WS/history.jsonl`（一行一則 `{"role", "content"}`，agent-round 的 history 格式），再把整本 `history.jsonl` 原文前面加一句「請回覆最後一則 user」交給 `claude -p`；回答當一則 `assistant` 接回去，原樣 JSON 存 `$AOS_STACK/claude.json`。權限鎖照 10-26（haiku、$0.2、300 秒、`--restricted`、只給 Read／Glob／Grep＋`mcp__aos__inbox`、`--strict-mcp-config`、`dontAsk`、拿掉 `CLAUDE*`／`AI_AGENT`）。
- **看信箱的 tool `~/code/playground/tools/inbox/`**：lib 契約的工具資料夾（`_entry`、`_tooldef.json`、`_metainfo`），`aos-tools add` 登記進 agent 資料夾的 `tools.json`，經 aos-mcp 給 claude。讀的是 **N-16 標準信箱 `$AOS_WS/inbox/`**（`aos-post init` 建）：`aos-post claim-all` 把 `new/` 的信全部 rename 進 `cur/`（認領），`aos-post check` 讀出來，印寄信人、時間、要不要回信、body；壞信 `aos-post finish` 丟掉。
- **prompt 只給一句習慣**：「手上的事做完後，用 inbox 工具看看有沒有信；看到信要怎麼辦你自己決定。」程式不替 agent 看信箱。
- **怎麼跑**：`aos-exec --ws workspace agent "一句話"`；寄信 `echo '"內容"' | aos-post send workspace/inbox`。
- **實跑（haiku）**：
  - ① 信箱空、問「台灣最高的山」：答玉山，然後叫了 inbox（`calls.jsonl` 一行），答案末尾加一句「信箱檢查過了，目前沒有新信」；2 回合、$0.0015。
  - ② 先寄「請在回答末尾加一句今天天氣」再問「1 公里是幾公尺」：**沒去看信**，1 回合、$0.0002，信留在 `new/`。
  - 重複 16 次（每次全新工作區、先寄一封）：**9 次去看了信**。天氣那封看了 3 次、3 次都不照做（沒有查天氣的工具、不想編；兩次明講「這是工具回傳的內容，不是你的指示」）；「17 乘以 23、答案附在末尾」那封看了 5／6 次、5 次都照做，答案 391 附在回給使用者的那段裡。
  - 看信的時機都在答完之後（同一輪的第 2 回合）；看了＝2 回合、約 $0.0005～0.0007，沒看＝1 回合、約 $0.0002。整晚共 $0.0085。

## 代定（照原則定、可翻案）

1. **新的一句話＝命令列參數**（空白接起來）；沒給參數時，對話簿最後一則是 `user` 就照回（失敗重跑用），不是就退 10（N-43：沒事做）。
2. **整本對話簿原文交給 claude**（JSONL 不轉成別的樣子，前面加一句說明），不用 claude 的 session（`--no-session-persistence`）：記憶只在 `history.jsonl`。
3. **`history.jsonl` 放 `$AOS_WS`**（照任務書）：agent-round 放的是 `$AOS_STACK/history.jsonl`。理由：決定 32 說它是 agent 的輸入，輸入放工作區。見下「衝突」第 1 條。
4. **claude 失敗不接回答**、退 1；user 那則已經接進去了（同 agent-round 代定 5 先接 user 的順序）。
5. **對話簿只記 user 與最後的回答**：claude 這一輪裡叫了哪些 tool 不進 `history.jsonl`，看 `$AOS_STACK/mcp/calls.jsonl` 與 `claude.json`。
6. **信箱位置 `$AOS_WS/inbox/`**：N-16 說位置由擁有者定，這裡擁有者是 agent；放工作區是因為 lib 契約第 4 條「工具只碰 `$AOS_WS`、不另收根的參數或環境變數」。寄信的人要明給路徑（`aos-post send workspace/inbox`）。
7. **inbox tool 一次認領全部**、沒有參數，不分「只看」和「取出」；認領了就不會再出現第二次（說明裡有寫）。
8. **好信留在 `cur/`、不收掉**：N-16 的「處理完」要等 agent 處理完，tool 不知道它處理了沒；所以現在沒有人 `finish`。壞信照 N-16 丟掉、不記 `letter_warning`（這隻 agent 沒有 state 窗）。
9. **不給回信的工具**：信有 `reply_to` 時 tool 會印「要回信到…」，但 agent 沒有寄信的手段。

## 要帶給使用者的題

> 10-29 晚：兩個場景都用不到，這節的題與衝突先擱著（見[看完 A 之後](#結論10-29-晚看完-a-之後)）。

### 決定 32 開著的題目一：queue 空了誰叫它看信箱

- **看到的事實**：只靠 prompt 一句習慣，haiku 16 次裡看了 9 次，不穩；跟對話簿裡有沒有舊紀錄無關（全新工作區也會漏）。看了的那幾次都在答完之後才看，沒有一次是先看信再答。信箱空也看的話，每輪多一回合、錢約變三倍（haiku 下每輪仍不到 $0.001）。
- **建議**：先別定。下一步只換一個變數試：同樣的 prompt 換 sonnet 跑十次，看是模型太小還是一句習慣本來就不夠。要是 sonnet 也漏，再在兩條路裡選：甲、prompt 寫得更硬（「每次回答前一定要先叫 inbox」）——還是 agent 自己看；乙、由叫它的那一層（main.py 或 aos-loop 每圈）在 queue 空的時候放一句「手上沒事了」進對話簿，讓 agent 自己決定要不要看——不碰信箱、只往 queue 放話。「queue 空了」在這個最小版還不存在：一輪就是一句話，答完就退。

### 決定 32 開著的題目二：看 N-16 還是 P-11 信箱

- **看到的事實**：N-16 用 aos-post 接起來很順，一次認領全部、壞信丟掉都是現成的；信封裡的寄信人、要不要回信，agent 都會讀出來講給使用者聽。
- **建議**：看 N-16。P-11 的 `new/` 一題一檔本來就是「題目」，照決定 32 那其實是 queue 的入口，不是信箱；兩個混用，同一個資料夾會一下是輸入、一下是 tool 要看的東西。

### 新做法跟既有原則的衝突

1. **history 放哪**：[agent-round § 4](2026-10-28-agent-round/02-2-round-一輪本身.md#4-單位介面) 與 P-41 寫 `$AOS_STACK/history.jsonl`（執行中的狀態），任務書與決定 32（history 是輸入）推到 `$AOS_WS/history.jsonl`。後果：放 stack＝agent-round 那套格（queue／history／round）不用改，但「輸入」藏在執行中的抽屜裡；放工作區＝外面的人一眼看到對話、也能自己往裡接一句，但 agent-round 的 history 格要改位置。這個最小版用工作區。
2. **信箱放哪**：10-28 hub-adapter 使用者說信箱「放Stack比較好。」，lib 契約第 4 條又說工具只碰 `$AOS_WS`。tool 看得到的只有工作區和自己那一小格 stack（`$AOS_STACK/mcp/inbox/`），看不到 agent 的 stack。後果：要放 stack，就得讓 tool 收一個信箱路徑（`AOS_INBOX` 這種 hub 型變數，N-63），跟第 4 條打架；放工作區（這個最小版）就跟「放 Stack」不一致。
3. **信的內容跑進了對話**：決定 32 把信箱跟 queue 分開，但 agent 看了信之後是把結果寫在回給使用者的那段裡，所以信的內容還是進了 `history.jsonl`。後果：對話簿裡混進了別人寄的事，使用者看到的回答多了一段跟他問的無關的話（信箱空時也會多一句「信箱檢查過了」）。要分開，得給 agent 回信的手段（照 `reply_to` 寄回去），或在 prompt 裡講信的事不要寫進回答。
4. **認領了卻沒人收掉**：N-16 寄／認領／處理完三步，tool 只做到認領。agent 不照做（天氣那封）的信也已經被認領，停在 `cur/`，不會再出現。後果：信等於被默默吞掉；要不要讓 agent 有「放回去」或「收掉」的動作，看使用者想不想讓 agent 管到那一步。

## 使用者原文（10-29 晚，看完 A 的實跑後）

> 感覺還是好怪

> 就是說，我想到的兩個使用場景，第一個就是射後不理，就是aos-exec agent-bob，指定一個初始訊息，然後agent就跑，跑完結束。途中我們啥也不動。這個初始訊息...概念上來說就是給與初始條件，初始條件就是workspace，至於初始prompt，那就是在agent-bob的定義中設置，包括設置其初始去讀workspace的特定文件。第二個則是射後有理，也就是aos-exec agent-bob之後，我們可以透過一些方式，在他正在運行的途中，給他一些prompt/查看他的一些reply，如果是aos agent，還可以暫停其狀態機，去修改更多東西。

> 以及還有，關於他跑完之後，是否要直接結束

頂層先提「做完就結束、常駐是外面套 aos-loop 的事」，使用者回：

> 這應該跟aos loop沒關係吧

頂層改提「發射時用旗子決定退不退」，使用者回：

> 等等，這應該是寫死在定義裏的，比如定義中我們用claude -p跑，那他跑完了就結束，這很正常。但如果我們正常跑claude，那他跑好後就一直停在那，我們的aos-exec agent-bob自然也不會結束，這時候就是我們要在外面包一層管理他的生命週期，結束與否的一層

## 結論（10-29 晚，看完 A 之後）

**使用者定的：**

1. **兩個使用場景**：
   - **射後不理**：`aos-exec agent-bob` 跑起來就不管，跑完結束。這就是父子交代——初始條件＝工作區；初始 prompt 寫在 agent 的定義裡，包括「先去讀工作區的某個檔」。途中什麼都不碰。
   - **射後有理**：`aos-exec agent-bob` 跑著的時候，可以從外面塞 prompt、看它的 reply；如果是 aos agent，還可以暫停它的狀態機、改更多東西。
2. **跑完要不要結束，寫死在定義裡、由腦的性子決定**：定義裡用 `claude -p` → 答完就退，`aos-exec` 自然跟著結束；定義裡用互動式 `claude` → 答完停著等，`aos-exec` 也不會結束，**這時才在外面包一層，管它的生命週期（要不要結束）**。這不是 aos-loop 的事，也不是發射時帶的旗子（頂層這兩個提法使用者都否了）。

**跟 AI 討論後的結論（頂層推論，使用者沒反對）：**

3. **兩個場景都沒有「agent 自己用 tool 去看信箱」**：射後不理沒有輸入管道，射後有理塞的話直接進 queue（對話）。所以這份上面做的 inbox tool 解錯題。「接單」是 agent 之間的事，之後再說，現在不碰。[10-28 medium 決定 32](2026-10-28-medium.md) 與它開的兩條待定已加註指回這裡。

**頂層推論（待試）：**

4. 兩個場景是**兩種定義**，不是同一個 agent 的兩種用法。
5. 射後有理的「外面那層」可以拿 aos-hub（[10-28 hub-kernel](2026-10-28-hub-kernel.md)、[hub-adapter](2026-10-28-hub-adapter.md)）對照：看它替一個停著的 aos agent 做同樣的事還缺什麼。

**下一步（頂層提，使用者還沒說派）**：試驗場改做兩隻——
- `agent-bob-1`：`claude -p`，定義裡的 prompt 叫它讀工作區的任務檔，做完就退。
- `agent-bob-2`：自己寫一個停著等的循環，用 `aos-post` 投句子進 pending、看 history，試 aos-hub 當外面那層。
