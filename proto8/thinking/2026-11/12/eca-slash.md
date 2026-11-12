# eca 的 slash 指令（11-12 公司 WSL）：實測 claude／codex 的 /clear、/compact、/status、/usage、/exit，修成 aos 跟上 CLI（畫面 hook 跟 id、/clear 連 history 清；say／chat 也認；codex 有畫面）

← [11-12 日索引](README.md)｜試驗場搭法 [playground](playground.md)

## 使用者原話（逐字）

- 「你自己幫我試。我這邊說一下claude code cli一些我常用的slash指令：/compact, /exit, /clear, /usage, /status。然後codex cli也一樣。」
- 「弄好後能修就修」
- 「連 aos 那邊的歷史也要一起清，eca就是要同步，eca就是會變成以他為主，aos體系要盡量跟上。codex要做畫面。然後aos-say/listen我希望也能支援這些」
- 「chat也要」

## 結論

- **修前**：畫面裡 `/status`、`/usage`、`/compact`、`/exit` 都沒事；**`/clear` 會接錯對話**——claude 換新 session id，hook 只在 `session.txt` 空著時寫，aos 照記舊 id；畫面開著時經 aos 問的是清之後那段（答 NONE），畫面一關再問就接回清之前那段（答出暗號 PLUM-7），清之後講的那幾輪接不上。say 送 slash 指令：claude 的 `/clear` 沒效（id 不記）、`/status`／`/exit` 回「isn't available」，codex 全部被當成一般題目丟給模型。codex 身在試驗場被拿掉畫面。
- **修後**（三個 commit，見文末）：畫面 hook 看到 id 換了就改記，claude `/clear` 連 aos history 一起清；`aos-agent say`／`listen`／`chat` 送這五個指令都有對應效果；codex 身有畫面（範本本來就有，只是試驗場腳本刪了它；再加一條：codex 取標題的旁支 thread 不記）。
- 臨時樹 `/tmp/slash-1112/pg`（照 playground 搭法、工作區新路徑，claude 跳信任提示，在 aos 開的畫面裡選 Yes 一次）；eca_bob（haiku、範本預設花費上限）、eca_cody（gpt-6-luna、workspace-write）。沒加任何全繞過權限旗標。

## 每個指令（實測，claude 2.1.322、codex 0.167.1／0.167.2）

| 指令 | claude 畫面 | codex 畫面 | 非互動（`claude -p`／`codex exec`） | 修後經 aos say／chat |
|---|---|---|---|---|
| `/status` | 顯示設定面板（版本、session id、cwd、登入方式、組織、帳號、模型、MCP）；不觸發 hook、檔都不變 | 顯示模型、目錄、權限、帳號、session、context、週額度 | claude：「isn't available」；codex：當題目答 | aos 自己答：kind、model、對話 id、畫面開關、history 幾則、transcript 路徑 |
| `/usage` | 顯示本 session 花費與額度百分比；不觸發 hook | 選單（看用量、重置） | claude 認得、印額度（不花錢）；codex 當題目 | claude 另起一次 `claude -p --no-session-persistence` 原樣回；codex 回一句沒有 |
| `/compact` | 同一個 session id、同一個檔多一行 compact_boundary；沒有 UserPromptSubmit／Stop；之後經 aos 問暗號照答（摘要保住） | 同一個 thread、沒有 notify | claude 認得（同 id、result 空）；codex 當題目 | claude 照一般 `--resume` 交給它；codex 刪 session.txt、下一句開新 thread 帶 aos 紀錄 |
| `/clear` | 新 session id（新檔）；**修前 aos 不知道**（見結論）；修後 SessionStart(source clear) 改記新 id、history 清空（原文搬 `history_removed.jsonl`），畫面開著、關掉後再問都答 NONE | 新 thread（下一輪才建檔）；修後下一輪 notify 帶新 id、改記；history 不清 | claude 回新 session id（舊的照樣能 resume），aos 原本不記；codex 當題目（答「我清不了」） | history 搬走、刪 session.txt、下一句開新對話；畫面開著不代打、回一句 |
| `/exit` | CLI 結束、tmux 跟著沒了（socket 檔留著、`alive()` 照判沒開）；`ctl ls` 照 running；下一句走非互動、接同一段 | 同左 | claude：「isn't available」；codex 當題目 | 畫面開著（沒人接著）就關；沒開回一句 |

表的「修後」欄是第一輪（上午）的；下午使用者裁 Q1～Q3 後又改了三處：codex 畫面 /clear 也清 history、畫面開著時 say 送的 /clear／/compact 直接打進畫面、claude /compact 後 history 換成它的摘要（見下面「使用者裁定」）。

旁證：hook 只在一般一輪送出（UserPromptSubmit）與講完（Stop）時叫，slash 指令兩個都不觸發；claude 另有 SessionStart（source startup／resume／clear／compact）。codex 的 notify 每輪一次，**但畫面替對話取標題時另開一條旁支 thread 也叫 notify**（`input-messages` 是「Generate a concise, single-line task title…」、`last-assistant-message` 是 `{"title": …}`，沒有 rollout 檔），有時比真的那則先到——不濾掉的話第一輪會記錯 thread id、turns.jsonl 多一行標題 JSON。

## 改了什麼

1. **畫面 hook 跟上**（`lib/agent/cli_session.py`）：多註冊 SessionStart；`follow_session`＝id 跟 session.txt 不同就 `mark_session` 改記（原本只在空著時寫）；SessionStart source startup 照舊不記（新對話第一輪才記，保住 ask 的 reseed）；source clear＝`clear_history`：history 原文照 `aos-agent history rm` 的規矩每則一行 `{"removed_at", "op": "clear", "line", "message"|"raw"}` 接到 `history_removed.jsonl`、history 換成空檔、刪 `.history_sum`（不然下一輪當成 history 被改過、又丟掉新對話）；工具形（stack＝小格）不動 history。codex notify 的 thread 沒 rollout 檔＝旁支、整則不記。
2. **say／listen／chat**（`cmd/aos-eca/bin/aos-eca-turn` ⑭）：一批只有一封、內容去頭尾空白剛好是五個之一＝aos 這層做，照一般一輪記 history（user 那封＋一則 `[aos] slash: …`；`py/aos_flags.py` 的 NOTE_KINDS 加 `slash`）、收信、after_queue 照跑；listen、chat 不用改（同一條路）。
3. **codex 畫面**：程式不用改（`start()` 本來就有 codex 那條、範本有 `screen/`）；試驗場刷新腳本拿掉刪 screen 的兩行（[playground](playground.md)），範本說明補一段。

測試：`lib/agent/tests/test_cli_hook_follow.py` 10 支、`cmd/aos-eca/tests/test_slash.py` 10 支（假 CLI）；實跑見上表與下面第二輪。

## 代定（我選的，可翻）

- S1 只有「一封信剛好是指令」才當指令；多封一批或後面帶字＝一般題目（`/clear\n\nhello` 照原樣交給 CLI）。
- S2 `/clear` 之後 history 留這一問一答（listen 要拿得到回答），下一句的新對話開場會帶這兩則（`--- record: 2 messages ---`）。
- ~~S3 畫面開著時 say 送 `/clear`、`/compact` 不代打~~（作廢：使用者 Q2「幫我貼進去」）
- ~~S4 `/compact` 不動 aos history~~（作廢：使用者 Q3「要動，希望能同步」）。codex 的 `/compact`（非互動）照舊＝丟掉 thread、下一句帶 aos 紀錄開新的（上限 `reseed_bytes`），新 thread 的上下文就是 aos 的紀錄，history 不另外改。
- S5 `/exit` 經 say＝關畫面（CLI 結束的意思）；不停掉這隻（停用 `ctl stop`）。有人接在畫面上＝不關。
- S6 `/usage` 經 say 另起一次 `claude -p`，不碰這隻的對話；codex 沒有非互動的對應，回一句。
- S7 clear 的原文檔沿用 `history_removed.jsonl`（同 history rm），op 叫 `clear`；compact 的叫 `compact`。

## 使用者裁定（11-12 下午）與第二輪施工

原話（逐字）：「1.要。2.幫我貼進去。3.要動，希望能同步。4.不用」

- **Q1 codex 畫面 `/clear` 也清 history**：判別法＝notify 帶來的 thread id 跟 `session.txt` 不同時，數那段 rollout 的 `task_complete`（講完幾輪，`cli_session.codex_turns`）：**只有 1（就是這一輪）＝剛開的 thread（/clear、/new）→ 清 history**；比 1 多＝`/resume` 到有內容的舊 thread → **只跟 id、history 不動**（代定 S8，不把那段對話併進 aos history）。清的時候 history 尾巴「最後一則 assistant 之後的 user」（aos 剛交出去、還沒答的那則）留著（S9）。實測：codex 畫面人打 `/clear` 後經 aos 問暗號＝NONE，history 只剩這一問一答；經 say 送 `/clear`（貼進去）同樣。
- **Q2 畫面開著時貼進去**：say／chat 送的 `/clear`、`/compact` 用 `tmux send-keys` 打進畫面（`cli_session.type_line`），回 `[aos] slash: …typed into the open screen…`；同步走畫面 hook。claude 那條**等 hook 改完 history 才記這一問一答**（上限 120 秒，S10；不等的話 hook 晚到會把這兩則一起搬走）；codex 沒有即時事件、不等。畫面正在跑一輪（busy.txt 在）＝這次不動、信留 `cur/`、下一輪再試（S11，選簡單的）。有人接在畫面上照貼。`/status`、`/usage` 照舊 aos 自己答，`/exit` 照舊關畫面（效果同打 `/exit`）。
- **Q3 `/compact` 同步**：claude 有 SessionStart source `compact`（實測會叫），transcript 裡有一則 `isCompactSummary` 的 user 訊息＝摘要；hook（畫面上打的）與 aos-eca-turn（say 送、非互動）都用 `cli_session.compact_history`：history 原文搬到 `history_removed.jsonl`（op compact），換成一則 user `[aos] summary: lines 1-N, N messages. 摘要`（同 `aos-agent history summarize` 的格式）；刪／重寫 `.history_sum`，自己改的不會觸發「history 被改過就丟掉對話」（測試驗過）。找不到摘要＝history 不動。**codex 拿不到摘要文字**：rollout 的 `compacted` 事件 `message` 是空字串，壓縮後的上下文是一串結構化的 `replacement_history`（含工具定義等），畫面上打的 `/compact` 也沒有 notify——所以 codex 的 `/compact` 只留 say 那則 `[aos] slash` 當標記、history 不動（列為 Q5）。實測：claude 非互動 `/compact` 後 history 14 則→摘要 1 則，再問暗號照答 KIWI-8；畫面開著經 say 送 `/compact`、`/clear` 都打進去、history 跟著換。
- **Q4 fsm 不做**。

### 第二輪代定

- S8 codex 換到有舊輪數的 thread（`/resume`）＝只跟 id、history 不動。
- S9 codex 判成新 thread 時，清掉的是「最後一則 assistant 之後的 user」以前的全部。
- S10 claude 畫面貼進去後最多等 120 秒（`SCREEN_WAIT`），等不到照回、多說一句請人看畫面。
- S11 畫面正在答題時 say 送的 `/clear`、`/compact` 這輪不動，下一輪再試。

### Q5（已裁、已做）

使用者原話（逐字）：「Codex 的 /compact改成「從那串結構化資料裡撈出對話文字，當成新的歷史」。我覺得可以做，去做吧」

- **怎麼撈**（`cli_session.codex_compact_rows`）：codex rollout 最後一個 `compacted` 事件的 `payload.replacement_history` 裡，`type` 是 `message`、`role` 是 user 或 assistant 的項，把各 part 的 `text` 接起來；實測 0.167 留下的是 developer 訊息、工具定義、使用者說過的話、一個 `compaction` 項（加密、沒有字），assistant 的話不留。
- **換法**：history 原文搬到 `history_removed.jsonl`（op compact），新 history＝一則 `[aos] summary: lines 1-N, N messages. codex compacted the conversation; it keeps the messages below (its own summary is not shown)`＋撈出來的話；最後一則 assistant 之後的 user（剛交出去的）留著。
- **兩條路**：say／chat 送的（畫面開著，貼進去）＝打之前記下壓過幾次，等 rollout 多一個 `compacted`（上限 120 秒）再換；畫面上人打的＝沒有事件，**下一輪 notify 時比對**：同一段 thread、rollout 的 `compacted` 次數比小格 `.compact_seen` 記的多＝壓過了、補做。`.compact_seen`（`{"thread", "compacted"}`）在畫面開起來時與每輪 notify 時更新；不在或記的是別段 thread＝只記基準、不回頭補。畫面沒開時 say 送 `/compact`＝照舊換新 thread 帶 aos 紀錄（codex exec 沒有 compact）。
- **不觸發「history 被改過」**：hook 換 history 時刪 `.history_sum`；aos-eca-turn 記下交出去前它在、答完不在＝這一輪中間是跟上 CLI 改的，不寫 `edited`（實跑抓到修前會寫 `edited`、下一輪丟掉對話，修後同一段 thread 照接）。
- **代定**：S12 只留 user／assistant 的文字；developer／system、工具定義、工具呼叫與結果、`compaction` 項略過。S13 codex 自己塞進 user 的區塊（`<environment_context>` 這種以 `<小寫標籤>` 開頭的）略過。S14 撈不到（沒有 `replacement_history`、裡面沒有對話）＝history 不動、回一句講明。S15 `.compact_seen` 沒有基準時不回頭補以前的壓縮。
- **實跑**（gpt-6-luna、畫面開著）：先講暗號 MANGO-6 再一句 pong（history 6 則）→ say 送 `/compact`：回「history replaced by the conversation codex kept (6 messages moved…)」，history 變 summary＋codex 留下的 user 話；再問暗號＝MANGO-6。接著在畫面上手打 `/compact`、再經 aos 問暗號：notify 時補做（history 9 則→7 則、`.compact_seen` 1→2），答 MANGO-6；關畫面再問照接同一段 thread、答 MANGO-6。

## /goal（11-12 晚）

使用者原話（逐字）：「啊，eca還有一個slash command我很常用：/goal」「包括/goal clear」「反方向？aos goal工具本來就不會給eca用」

**實測**（claude 2.1.322、codex 0.167.2）：

| | claude | codex |
|---|---|---|
| 形式 | `/goal <condition>` 設、`/goal clear` 清（沒有目標時回「No goal set」）、只打 `/goal` 查看（沒有＝「No goal set. Usage: /goal <condition>」）；`clear` 是保留字，照 CLI 自己的判法 | 畫面：`/goal [<objective>\|clear\|edit\|pause\|resume]`，`/goal clear`＝「Goal cleared」，只打 `/goal` 顯示目標、狀態、用時 |
| 存哪 | 對話檔（transcript）裡的 attachment `goal_status`（condition、met、reason） | rollout 的 `thread_goal_updated`（objective、status）＋ `~/.codex/goals_1.sqlite` |
| 換 session／thread | 不換 | 不換 |
| 非互動 | `claude -p` 認：設了就照跑一輪直到判定 met（num_turns 1），但**目標只活在那一次 `claude -p`**，下一次 `-p` 查看＝No goal set | `codex exec` 不認（當題目，模型回「What goal should I track?」） |
| 畫面裡打 | `/goal 條件` 會跑一輪：UserPromptSubmit／Stop 都叫、turns 多一行；只打 `/goal`、`/goal clear` 不觸發 hook | `/goal 目標` 跑一輪、notify 一次；`/goal`、`/goal clear` 沒有 notify |

**做法**：aos 的 goal（`goal.json`，aos-eca-turn ⑬，`aos-agent goal -t <eca>` 設的那種「queue 空時丟 `[aos] goal:` 提醒」）跟 CLI 的 `/goal` 是兩回事，**不做同步**（使用者「aos goal工具本來就不會給eca用」：eca 的工具裡沒有 self goal；人用 `aos-agent goal` 設的照舊走 ⑬）。只做到「CLI 自己的 goal 經 aos 也用得起來、不被 aos 弄壞」：

- say／chat 送的信以 `/goal` 開頭（`/goal`、`/goal …`；`/goals …` 不算）＝slash 指令（只有它放寬，其他五個照舊要剛好）。畫面開著＝原樣打進畫面（busy 時下一輪再試），回 `[aos] slash: /goal: typed into the open screen…`；沒開＝claude 照一般 `--resume` 原樣交給它、回它的原話；codex＝回一句「codex 只有畫面上有 /goal，請開畫面」。
- `/status` 多一行「last goal the CLI recorded: 目標 (狀態)」。
- 畫面裡人自己打：session id、history、turns 都沒被弄亂（實測 claude 畫面 `/goal 條件` 跑一輪、turns 照記、busy 清掉、id 不變）。

**實跑**：haiku 不開畫面 `/goal reply with the single word ok`＝回「Goal acknowledged. ok」，`/status` 顯示「reply with the single word ok (met)」，`/goal clear`＝「No goal set」，`/goal`＝Usage。luna 畫面開著 `/goal reply with the single word ok` 打進去、codex 跑一輪（turns 多一行 ok、thread 不變），`/status` 顯示「(active)」，`/goal clear` 打進去＝「Goal cleared」，之後 `Reply only: pong` 照常進 history。

**代定**：S16 `/goal` 以開頭判（`/goal` 或 `/goal ` 後接任何字），其餘五個照舊要剛好。S17 codex 不開畫面時不代做 goal（exec 沒有），回一句。S18 `/status` 的 goal 只說「CLI 最後記下的」：清掉時兩邊都不另記一筆，所以清了之後還會顯示上一個（codex 也不更新成 complete）。

**codex 的「Replace goal?」**（使用者原話：「codex的/goal，如果連續跑兩次，第二次他會問你說是否要replace。幫我處理，要自動說選yes」）：實拍 codex 0.167.2，已有 goal（還在 Pursuing）時再 `/goal 新目標`，畫面中間跳選單——標題「Replace goal?」、「New objective: …」、「› 1. Replace current goal  Set the new objective and start it now」「2. Cancel  Keep the current goal」「enter select · esc back」，預設停在 1、Enter 選它（實按過）。aos 經 say／chat 打 `/goal 文字` 進 codex 畫面後最多等 5 秒，畫面最後 30 行有「Replace goal?」而且有「› 1. Replace current goal」與「2. Cancel」＝按 Enter，回的那則加一句「codex asked "Replace goal?" and aos chose "1. Replace current goal" (yes) for you」；有標題但長得不一樣（例如游標在 Cancel）＝不按、回一句請人到畫面上處理；沒跳＝照舊。人自己在畫面上打的不代按。claude 的 `/goal` 沒實測到類似確認（`claude -p` 的目標不跨次、畫面上沒試連設兩次），沒動。實跑 luna：連送兩次（one、two），第二次自動 replace，`/status` 顯示「keep answering with the single word two… (active)」，再送 `/goal clear` 清掉。測試 `cmd/aos-eca/tests/test_goal_replace.py` 4 支（用實拍畫面當樣本）。代定 S19：只認這一個選單、游標要在 1 才按；等 5 秒。

**題**（使用者回家可接著看）：
- G1 畫面上 goal 讓 CLI 自己連跑好幾輪時，只有第一輪的回答回到 aos 的 history（經 say 送的那則），之後幾輪只在 turns.jsonl；busy.txt 在第一個 Stop 就清掉，接著經 aos 送的話可能在 CLI 還在跑時就貼進去（CLI 會排隊）。Replace 實測時 codex 確實連跑（Pursuing goal、每輪回 one／two），後幾輪只在 turns.jsonl。要不要把畫面上非 aos 送出的那幾輪也接進 history？
  - **11-12 裁定**：使用者「codex目標這塊不用管，就是這樣」——維持現況、不做。
- G2 `/status` 想正確顯示「現在有沒有 goal」：claude 要另外讀不到清掉的紀錄；codex 可讀 `goals_1.sqlite`（沒試）。
  - **11-12 裁定（頂層比照 G1 解讀）**：同屬 goal 這塊，跟著使用者「codex目標這塊不用管，就是這樣」一併不做。

## 沒試到

- 人真的 `aos-agent open` 接進畫面（要終端機）：改用 `--detach`＋`tmux send-keys`，同一個 tmux。
- claude 畫面的 `/resume` 換到別段：程式照 follow_session 會跟，沒實跑。
- 使用者直接在工作區自己開 `codex`／`claude`（不經 aos）：那是另一個 thread／session，aos 不知道、也不受影響（aos 只認 session.txt 那段）；沒另外實跑。

## commit

- `e1eeec7ea` 畫面 hook 跟上（①）
- `cc945235c` say／listen／chat 支援（②）
- `f9ca77a15` codex 畫面說明與本篇（③）
- `95db04e50` 第二輪（Q1～Q3）
- `b06c17c1b` Q5
- `e49929811` /goal
- Replace goal 自動選 yes 見 SESSION-LOG 那行

## 11-12 晚：/goal、/compact 交給 claude 失敗時照一般一輪（收信、brain_failed、冷卻）

- 決定（使用者點頭修、會改行為）：沒畫面時交給 `claude -p` 的 `/goal …`、`/compact` 整段照一般一輪——交出去那刻 user 接進 history、信收掉、`after_queue` 照跑；交出去後 `CliFailed`／`ReplyMissing`＝這封掉了、fire `brain_failed`、記冷卻；成功＝冷卻歸零。
- 原因：之前沒傳 `handed`，claude 失敗時信留 `cur/` 每輪重試、不記冷卻也不 fire `brain_failed`，跟一般一輪不一致。
- 做法：`aos_eca/handoff.py` 的 `Handoff`（一般一輪與這兩條共用）。`/compact` 成功後換摘要用 `replace_history(…, keep_tail=True)`，交出去那刻接進的 `/compact` 留在摘要後面，結果跟之前一樣（摘要＋/compact＋回答，搬走的還是舊那幾則）。
