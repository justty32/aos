# 回答配對 04：Argon 原文（審 03 v1）

← [reply-match-1114](../reply-match-1114.md)

> 11-14 ok-pilot 在 /tmp 跑 agy（Gemini 4 Argon High，--mode plan），提示貼 01、02、03 v1 全文，不給工具。第一次它想叫工具被擋、沒有輸出，第二次加「不要用工具」後得到下文。原文未改。採納與否見 [05](05-採納表.md)。

以下分 **(A) 審查** 與 **(B) 提案** 兩段回答。

---

# (A) 審查：03 計劃的錯誤、漏洞、競態與事實出入

## 一、特別點名項目審查

### 1. §2「先看 queue 再看 history」真的沒有競態嗎？

**結論：有競態，而且因為 03 把「找不到」直接當成終態 `LetterDropped`（立即報錯退出，不再輪詢），任何瞬間空窗都會變成致命誤報。**

* **(A1) Queue 內部搬移（`new/ → cur/`）與目錄掃描順序的競態**
  * **嚴重程度**：**會卡住（誤報 `LetterDropped` 直接中斷）**
  * **依據**：01 §1（`idle.py:147-172` 先 `take-all` 把信從 `new/` 搬進 `cur/`，跑 `before_queue` hook，寫入 history 後才 `done`）、03 §2 第 1 步。
  * **問題**：03 只寫「信名還在 queue 的 `new/` 或 `cur/`」，沒規定掃描順序。在檔案系統裡，檢查兩個目錄必然有先後：
    * 若實作成**先掃 `cur/` 再掃 `new/`**：讀方掃 `cur/`（不在）➔ 寫方執行 `take-all` 把信從 `new/` 搬到 `cur/`，正在跑前幾封信或 `before_queue` hook（尚未寫入 history）➔ 讀方掃 `new/`（已搬走，不在）➔ 讀方掃 `history.jsonl` 與 `history_removed.jsonl`（都還沒寫入）➔ 落入第 5 步，**當場誤報 `LetterDropped`**。
    * 就算規定**先掃 `new/` 再掃 `cur/`**，若寫方正好把信從 `new/` 搬到 `cur/`、寫入 history 並 `done`，讀方接下來讀 history 雖然看得到，但若同時碰上 history 改寫（見 A2），一樣會掉進空窗。

* **(A2) History 改寫／折疊（`history.jsonl → history_removed.jsonl`）的空窗與第 4 步漏看 `aos.letter`**
  * **嚴重程度**：**會卡住（誤報 `LetterDropped`）**
  * **依據**：01 §1（`cli_hook.py:77` summarize 呼叫 `replace_history`）、02 §1（`do_task/_entry:119-231` 折疊 user 列、`self_history/_entry:109-158`）、03 §2 第 3～5 步。
  * **問題**：
    1. **只查 `answer_to` 沒查 `letter`**：若一輪中間（例如在 tool 迴圈跑 `do_task` 折疊、或觸發 `replace_history` summarize）把這輪剛收到的 user 列移進了 `history_removed.jsonl`，而**最終回答還沒算出來**。此時讀方在第 2、3 步讀 `history.jsonl` 找不到 user 列，到了第 4 步去 `history_removed.jsonl` **卻只找 `message.aos.answer_to` 而不找 `message.aos.letter`**！結果第 1～4 步全空，直接進第 5 步誤報 `LetterDropped`，但 agent 其實正在算回答。
    2. **寫檔交錯**：當 `replace_history` 或 `history rm/set` 執行時，若「改寫 `history.jsonl`」與「附加 `history_removed.jsonl`」之間被讀方插入，讀方會兩邊都沒讀到，直接誤判 `LetterDropped`。
    3. **封存覆蓋範圍未核實**：02／03 只確認了 `aos_agent/history.py:207` 與 `cli_hook.py:86` 會寫入 `history_removed.jsonl`，**沒有核實 `self_history` 與 `do_task` 折疊時是否也會寫入同一個 `history_removed.jsonl`**。若沒有，列一被折疊就徹底消失。

* **(A3) 第 5 步把「四處都找不到」當成 `LetterDropped`，並附上 `mailbox_warning.txt` 張冠李戴**
  * **嚴重程度**：**會配錯錯誤訊息／會卡住**
  * **依據**：01 §1（「`mailbox_warning.txt`：只留最後一封被丟的信名」）、03 §2 第 5 步。
  * **問題**：01 明載 `mailbox_warning.txt` 只留最後一封被丟的信。若信是因為「user 列在回答前被刪」（03 §2 第 5 步自己寫的ケース）或兩封壞信先後被丟，直接把 `mailbox_warning.txt` 那一行附上去，會把**別人（上一封壞信）的錯誤訊息**安在這封信頭上。

* **(A4) eca 中途信（`midturn.py`／ok-wake stream-json）的收信與 `done` 順序未核實**
  * **嚴重程度**：**會卡住（可能誤報 `LetterDropped`）**
  * **依據**：01 §1（`turn.py:41-84`、`midturn.py`、`Handoff.extra`）、02 §3（點名 `midturn.py:14`）、03 §3（「`midturn.py` 只呼叫 `extra()`，不用改」）。
  * **問題**：03 §2 的無競態前提是「寫的一方一定先附加 history 再 `done`」。開頭那批信在 `Handoff.handed()` 確實先寫 history 再對 `good` 逐封 `done`；但**中途信**走 `midturn.py` 與 ok-wake 的 stream-json 時，是誰、在何時把信從 queue `done` 掉的？如果 `midturn.py` 先從 queue 取走（`done`）才呼叫 `extra()` 寫入 history，中間就有空窗讓 `answer_for` 誤判成 `LetterDropped`。03 沒核對 `midturn.py:14` 就斷言不用改，太武斷。

---

### 2. fsm 用「上一則最終回答之後的 user 列」現算 `answer_to`，在 tool 迴圈、goal 提醒、`self_history` 改寫時對不對？

**結論：不對。這三個場景組合起來，既會「漏記信名（導致誤報 `LetterDropped`）」，也會「把上一輪的信算進這一輪（導致配錯回答）」。**

* **(A5) Tool 迴圈中途失敗／中斷後，下一輪（含 goal 提醒）會把上一輪的死信掃進來**
  * **嚴重程度**：**會配錯**
  * **依據**：01 §1（`idle.py:239-245` goal 提醒、ok-fsm T22 `[aos] goal: paused`）、01 §2（`aos_ws.is_answer`＝assistant 且無 `tool_calls`；`test_cooldown.py`、`test_selfheal.py`）、03 §1。
  * **問題**：在單純成功的 tool 迴圈（`user(L1) → assistant(tool_calls) → tool → assistant(最終回答)`）裡，往回掃到上一則最終回答確實能找到 `L1`。**但是**，如果上一輪在 tool 迴圈中途因為端點失敗進入 cooldown／selfheal、deadline 逾時（ok-fsm T21）、或被中斷退回 `idle`，**沒有產生無 `tool_calls` 的最終回答**：
    1. 下一輪進來一封新信 `L2` 並回答 `A2`：`wait.py` 往回找「上一則最終回答」時，會**穿過上一輪未完成的 `assistant(tool_calls)` 與 `tool` 列**，把上一輪死掉的 `L1` 一併收進 `A2` 的 `answer_to: [L1, L2]`。等 `L1` 的人會拿到回給 `L2` 的答案！
    2. 更糟的是：若下一輪沒有新信，而是觸發了 **goal 提醒**（`idle.goal_turn()` 寫入無信名的 `[aos] goal: ...` user 列），當 goal 輪產生最終回答時，往回掃會掃到上一輪卡死的 `L1`，**把原本不該有 `answer_to` 的 goal 回答標成 `answer_to: [L1]`**！

* **(A6) Tool 迴圈中 `do_task` 折疊、summarize 或 `self_history` 改寫本輪 user 列，導致最終回答漏寫 `answer_to`**
  * **嚴重程度**：**會卡住（明明已回答，卻誤報 `LetterDropped`）**
  * **依據**：02 §1（`lib/agent/self_history/_entry:109-158` 鎖只從最近一則 assistant 起算；`lib/agent/do_task/_entry:119-231` 折疊會動 user 列）、01 §1（`cli_hook.py:77` summarize）、03 §1。
  * **問題**：03 認為「腦在同一輪刪掉自己剛收的 user 列少見；真發生了，讀方會報找不到，不會配錯」。這與 01／02 的原始碼事實不合：
    1. 一旦進入 tool 迴圈，history 尾端已經有一則 `assistant(tool_calls)` 列，此時 `self_history` 的鎖（只鎖最後一則 assistant 之後）**已經保護不到本輪開頭那則 user 信列**。
    2. 更常見的是 agent 在 tool 迴圈裡呼叫 **`do_task`**（完成子任務時折疊歷史，見 `test_do_task_fold.py`）或觸發 **summarize**，把本輪開頭的 user 列折疊／替換成無 `aos.letter` 的列。
    3. 等 tool 迴圈結束、`wait.py` 寫入最終回答時，往回掃 history 已經看不到 `aos.letter`，於是**最終回答列完全不寫 `aos.answer_to`**。
    4. 接著讀方的 `ask` 去查：queue 沒有、`history.jsonl` 沒有、`history_removed.jsonl` 裡只有被折疊的 user 列（無 `answer_to`），直接掉進第 5 步**報 `LetterDropped`（信被丟了）**——但其實 agent 已經順利答完了！

* **(A7) 上一輪的「最終回答列」被 `self_history` 或 `do_task` 刪除／折疊，導致已答完的舊信被重複配給新回答**
  * **嚴重程度**：**會配錯**
  * **依據**：03 §1（往回掃到上一則最終回答為止）。
  * **問題**：若第 1 輪的信 `L1` 已經答完（產生最終回答 `A1`），在第 2 輪 tool 迴圈中 agent 用 `self_history` 或 `do_task` 整理歷史時刪掉或折疊了 `A1`（而 `L1` 的 user 列仍在），等第 2 輪（甚至只是個 goal 提醒輪）結束寫入最終回答 `A2` 時，往回掃因為看不見 `A1`，會一路掃到第 1 輪的 `L1`，把 `L1` 放進 `A2.aos.answer_to`。若此時有人查 `L1`（因為 `history.jsonl` 排在第 2 步，比第 4 步的 `history_removed.jsonl` 優先！），**會直接拿到第 2 輪的 `A2`，而不是封存檔裡真正的 `A1`**！

---

### 3. §4 剝 `aos` 鍵與 `stale_request`

* **(A8) 送端點組 `messages` 的路徑不只 `brain.py:191`，且寫入 assistant 列時未防端點髒鍵**
  * **嚴重程度**：**小事～會卡住（若漏剝鍵導致端點 400 拒收，或 `stale_request` 無窮重建）**
  * **依據**：01 §1（明確列出三處：`cell_common.py:17-30`、`brain.py:191`、`lib/base/llm_http/_entry:60-90`，以及 `wait.py:493-505`）、03 §4。
  * **問題**：
    1. 01 指出送端點的路徑包含 `cell_common.py:17-30` 與 `brain.py:191`，03 §4 卻只寫在 `brain.py:191` 與 `wait.stale_request` 呼叫 `for_endpoint(m)`。若 `cell_common.py:17-30` 本身就是讀取／準備 history 給 request 的共用函式，應直接在共用源頭剝鍵，並確認 `for_endpoint(m)` 回傳的是拷貝（`{k: v for k, v in m.items() if k != "aos"}`），不可原地 `pop` 改動記憶體中的 history 列。
    2. 03 §1 記得在寫 user 列時覆蓋信 body 原有的 `aos` 鍵，但忘了 `wait.py:493-505` 是「把端點回的 `message` 整個附加到 history，不挑鍵」。若這是一則 `tool_calls` 的 assistant 列，或無信可回的最終回答列，也應先確保剝除端點回傳物件上可能夾帶的 `aos` 鍵。

---

### 4. §5 新讀舊寫時的寬容退路

**結論：03 §5 推薦的「做法一（history 裡找不到任何帶 `aos.letter` 的列時，退回現在的『最新那則』）」有三個嚴重破洞，在實際環境一定會配錯或卡死。**

* **(A9) 已升級的新 agent 在「空 history／剛開機／summarize 或 compact 後」會誤觸發退路**
  * **嚴重程度**：**會配錯**
  * **依據**：01 §1（`cli_hook.py:77` summarize 列無信名）、03 §4（`cli_hook.py:174` Codex compact 重建的列沒有 `aos`）、03 §5。
  * **問題**：一隻**已經升級**的 agent，在下列時刻整份 `history.jsonl` 裡都「沒有任何帶 `aos.letter` 的列」：
    1. 新建或剛清空 history 的 agent，第一封信還在 queue 裡或只有 goal 提醒列時；
    2. 剛跑完 summarize（`replace_history`）或 Codex compact，舊列全部被替換成無 `aos` 鍵的摘要列時。
    此時新 `ask` 一查發現「history 裡沒有任何 `aos.letter`」，就會誤判這隻 agent「還沒升級」，直接退回舊版「拿最新那則」，導致多人同時問時互相拿錯，且在 stderr 亂印未升級警告。

* **(A10) 半新半舊的 agent（history 曾有過一筆 `aos.letter`，但當前身體還是舊版）退路完全失效**
  * **嚴重程度**：**會卡住（每問必報 `LetterDropped`）**
  * **依據**：03 §4（`fork_copy` 照抄母體的 `aos` 鍵）、03 §5（`cmd/aos-eca` 進 main 即生效，fsm 範本要等換樹）。
  * **問題**：只要某隻 fsm 的 history 裡曾經有過任何一列帶 `aos.letter`（例如 fork 自已升級的 agent，或曾切過已生效的 eca），「找不到任何帶 `aos.letter` 的列」就永遠為假。當它用還沒換樹的舊 fsm 身體收信時，信從 queue `done` 了卻沒寫 `aos.letter`，`answer_for` 走第 1～5 步，**每一封信都會當場報 `LetterDropped`**。

* **(A11) 刪掉 `before` 計數與 `handed_unanswered()` 後，「退回最新那則」會直接拿到發信前的舊回答**
  * **嚴重程度**：**會配錯（100% 拿錯）**
  * **依據**：01 §2（`listen.py:32-89` 靠記下回答數與 `handed_unanswered()`）、03 §2（「拿掉 `before` 計數」）、03 §5。
  * **問題**：對上舊身體時，信一被收進 history 就會立刻從 queue `done` 掉（此時模型才剛要開始算，**根本還沒回答**）。但 `answer_for` 發現信已不在 queue、且 history 沒有 `aos.letter`，若直接觸發退路「回傳最新那則（`answers()[-1]`）」，因為已經拿掉了 `before` 回答數比對與 `handed_unanswered()` 檢查，**它不會等待新回答，而是立刻把 history 裡上一輪的舊回答當成這次的回答印出來**！

---

## 二、其他在 eca、讀取端、測試與文件的漏洞

* **(A12) eca 交信後 `CliFailed`／`ReplyMissing` 不記失敗，讓呼叫者白白卡死到逾時**
  * **嚴重程度**：**會卡住**
  * **依據**：02 §3（`handoff.py:57, 62`）、03 §2。
  * **問題**：當 eca 發生 `CliFailed` 或 `ReplyMissing` 時，信已經從 queue `done` 掉，且 `aos-eca-turn` 行程已經退出，**這封信永遠不會再有回答了**。03 為了省掉 `letters.json`，讓這封信永遠停在 `handed`（因為 user 列留在 history 裡），迫使 `ask` 和 `subagent` 白白卡死乾等整個 timeout 才報 `AnswerMissing`。而且那則沒有回答的 user 列永遠留在 history，見下條 (A13)。

* **(A13) `listen` 不帶 `--letter` 時的退路規則會拿錯舊回答或永遠卡死**
  * **嚴重程度**：**會配錯／會卡住**
  * **依據**：03 §2（「不給信名時照舊取 queue 裡最新那封。queue 是空的，就取 history 最後一封帶 `aos.letter` 的 user 列，再用 `answer_for` 等它」）。
  * **問題**：
    1. **拿錯舊回答**：若第 1 輪信 `L1` 答完了（`A1`），第 2 輪是無信名的 goal 提醒並產生了新回答 `A2`（此時 queue 為空），使用者跑 `aos-agent listen` 想看最新回答，程式卻去找「最後一封帶 `aos.letter` 的 user 列 `L1`」，印出上一輪的 `A1`！
    2. **永遠卡死**：若 history 最後一封帶 `aos.letter` 的 user 列剛好是上一輪 `CliFailed` 沒回答的死信，之後 queue 為空時跑 `aos-agent listen`，每次都會抓到這封死信並卡在 `handed` 直到逾時。
    3. **未定義行為**：若 queue 為空且 history 裡沒有任何帶 `aos.letter` 的列（如新 agent），03 沒寫 `listen` 該怎麼辦。

* **(A14) eca 的 `slash.py` 回答與 `turn.py:84` 的 `hand.good` 是否重疊**
  * **嚴重程度**：**小事～會配錯**
  * **依據**：03 §1、§3（`turn.py:84` 與 `slash.py:275, 287`）。
  * **問題**：若 slash 指令走 `slash.py:275, 287` 自己寫了一列 assistant 回答，需確認該輪是否還會走到 `turn.py:84`，或同一批信混有 slash 與一般信時，`slash.py` 的 `answer_to` 只該填那封 slash 信名，而 `turn.py:84` 的 `answer_to` 應扣除已由 slash 單獨回答過的信名。

* **(A15) 測試與文件修改清單遺漏**
  * **嚴重程度**：**小事（會破測試或漏更文件）**
  * **依據**：對照 01 §2 與 02 §4。
  * **問題**：
    * 測試漏列：02 §4 查出的 `test_do_task_fold.py:168, 178, 194`、`test_slash.py:140`、`test_ask.py:126, 167, 175, 180` 在 01 §2 清單裡沒有，03 §4 只寫「見 01 §2 那份清單」因而漏掉。
    * 文件漏列：01 §2 列出的 `docs/NORMS/附錄4-持久檔.json#/rows/24`（`history.jsonl` 欄位規範）、`docs/CONVENTION/02-題目stack停錯腦/01-P-11～P-14.md:5`、知識庫 `cli/history.json`，在 03 §4 漏列。

---

# (B) 提案：修正方案、方向選擇與 02／03 都沒想到的做法

## 一、03 第 6 節「方向問題」的選擇與理由

1. **記在哪：選 (a) history 列的 `aos` 鍵**。
   * **理由**：讓每列 history 自帶因果關係（哪列是哪封信、哪則回答回哪幾封信），除錯、`history ls --json`、封存查找都一目了然。送端點前統一在 `cell_common.py` 剝除 `aos` 鍵非常單純。
2. **要不要 `pending／dropped` 小檔（`letters.json`）：選 (a) 不要獨立狀態檔，但不能用 03 那種有破洞的現算法**（改用下方「二、02 和 03 都沒想到的做法」）。
   * **理由**：02 的 `letters.json` 需要額外維護狀態同步、crash 殘留清理、200 筆上限截斷、`fork_copy` 排除與持久檔規範，確實太重；但 03 直接拿掉後留下的破洞，可以用既有的 `request`／`history.jsonl`／`history_removed.jsonl` 無縫補齊，完全不必新增 `letters.json`。
3. **回答被移出 history 之後：選 (a) 去 `history_removed.jsonl` 找**（且必須同時支援找 `aos.answer_to` 與 `aos.letter`）。
   * **理由**：agent 常在任務完成後跑 summarize 或 `do_task` 折疊，若回答剛產出就被折疊，去封存檔找回能避免呼叫端誤以為沒回答。
4. **subagent 的 op ask：選 (a) 改成直接呼叫 `aos-agent ask`**。
   * **理由**：消除原本 `say` 與 `listen` 兩步之間的空窗，也不必重複實作配對與錯誤處理邏輯。
5. **新讀舊寫：選 (b) 讀寫同一個 commit（必選），並搭配修正後的 (a)「憑發信前快照 `(before_rows, before_answers)` 動態偵測舊身體」**。
   * **理由**：(a) 與 (b) 根本不互斥。程式碼放在同一個 commit 合入是基本衛生；而因為活樹的 `cmd/`、`py/` 進 main 就生效、fsm 範本要等換樹（中間必有時間差），讀的一方仍需寬容退路，但不能用 03 那個「整份 history 沒 `aos.letter`」的錯誤條件（見下方創見三）。

---

## 二、02 和 03 都沒想到的三個做法（核心補丁）

為什麼 02 覺得非加 `letters.json` 不可，而 03 拿掉 `letters.json` 後卻到處破洞？因為兩份設計都沒注意到 aos 現有架構裡已經有三個現成機制可以直接利用：

### 創見 1：fsm 把本輪收到的信名放進既有的 `request`（或掃描時排除已結案信名＋加上輪次邊界），不開 `letters.json` 也不怕刪改與跨輪污染

* **怎麼做**：
  1. **利用 fsm 既有的 `request`（或 `idle → brain → wait` 傳遞）**：
     在 fsm 裡，`idle.take()` 收信時本來就握有這批好信的清單（跟 eca 的 `Handoff.good` 一樣）。当 `brain.py` 建立 `request` 時，除了把剝掉 `aos` 鍵的 `messages` 放進請求外，在本地 `request` 檔（或 `wait.py` 讀得到的欄位，送 HTTP 時不送出）帶上這輪未答的信名清單；或者：
  2. **若維持在 `wait.py` 掃 history，必須加兩條鐵律**：
     * **鐵律一（排除已結案信名）**：往回掃收集 `aos.letter` 時，不只要看最後一則最終回答之後，還要**扣除已經出現在任何 `aos.answer_to` 或 `aos.failed_letters`（含 `history_removed.jsonl` 內）的信名**。這樣就算上一輪的最終回答列被 `self_history` 刪掉，已答過的信也絕不會復活！
     * **鐵律二（往回掃描不可無視 `history_removed.jsonl` 與失敗邊界）**：若本輪開頭的 user 列在 tool 迴圈中被 `do_task`／`self_history`／summarize 移入了 `history_removed.jsonl`，其被移除的時間點在本輪開始之後，仍屬於本輪待回的信；反之，若上一輪因錯誤中止，見下方「創見 2」寫入失敗標記後，掃描遇到失敗標記即停止，絕不跨輪把上一輪的死信掃進這一輪（或掃進 goal 提醒輪）。
     * **更簡單的做法（推薦）**：直接在 `self_history` 的鎖規則（`lib/agent/self_history/_entry:109-158`）與 `do_task` 折疊規則補上一條：**「尚未被任何 `aos.answer_to` 涵蓋的未答 `aos.letter` user 列視同未完成輪次，鎖定不准在產生最終回答前刪除／折疊」**（或折疊進 `history_removed.jsonl` 時在替代列保留未答的 `aos.pending_letters`）。一舉兩得，既保護了當輪上下文，又讓 `wait.py` 掃描 100% 穩定！

### 創見 2：把「丟信／失敗」寫進既有的 `history_removed.jsonl`（與 history 失敗標記），廢除「找不到就猜是 `LetterDropped`」

03 最大的競態根源，就是把「四處都找不到」當成 `LetterDropped`。在多行程系統中，**「找不到」只代表「可能正在搬移中（繼續等）」，只有讀到「明確的拒絕／失敗紀錄」才可以立即報錯退出**！

* **怎麼做（完全不需新建 `letters.json`）**：
  1. **壞信、被 `before_queue` hook 擋掉的信（fsm `idle.py` 與 eca `turn.py`／`hook.py`）**：
     在 `done` 之前，直接往既有的 **`history_removed.jsonl`** append 一行封存紀錄：
     `{"removed_at": ..., "reason": "bad_letter" | "blocked_by_hook", "detail": "<錯誤原因>", "message": {"role": "user", "aos": {"letter": "<信名>", "dropped": true}}}`。
     * 好處：先寫進 `history_removed.jsonl` 再從 queue `done`，讀方任何時刻都找得到它，而且**每封被丟的信都有自己專屬的 `reason` 與 `detail`**，不會像 `mailbox_warning.txt` 那樣張冠李戴！
  2. **eca 交信後 `CliFailed`／`ReplyMissing`（`handoff.py:57-62`）或 fsm 放棄當輪**：
     當 user 列已經寫進 `history.jsonl`，但隨後 CLI 失敗退出、不再產生回答時，在異常處理中直接往 `history_removed.jsonl`（或在 `history.jsonl` 尾端／該 user 列）寫入一筆明確的 `{"reason": "turn_failed", "aos": {"failed_letters": hand.good, "detail": ...}}`。
     * 好處：
       1. `ask`／`listen` 一讀到 `failed_letters` 含自己的信名，**0 秒立即報錯 `LetterDropped`（或 `TurnFailed`）返回**，不用像 03 那樣傻等到 timeout！
       2. 下一輪 fsm 或 `listen` 看到這批信名已在 `failed_letters` 中，就知道那一輪已經死掉結案，**不會把死信併入下一輪的 `answer_to`，`listen` 也不會卡死在死信上**！

### 創見 3：利用發信前快照 `(before_rows, before_answers)` 與 `say` 信名的單調序號，精準識別「新讀舊寫」

01 §2 第 5 點給了一個被 02 和 03 都忽略的關鍵事實：
> **`say` 的 stdout 就是信名：`<12 位序號>.<20 位 ns>.<pid>.<start ticks>`（`send.cpp:43-79`）。**

而且 `ask` 在寄信前（或 `listen` 開始時）本來就可以記下當時的 **`before_rows = len(history)`** 與 **`before_answers = len(answers())`**！

* **怎麼用它完美解決 §5「新讀舊寫」**：
  當 `ask` 寄出信 `sig` 後，只要 `sig` 已經離開了 queue（`new/` 與 `cur/` 都沒有它），且沒在 `history_removed.jsonl` 被標為 dropped，代表**寫方已經把這封信寫進 `history.jsonl` 並 `done` 掉了**。
  此時讀方檢查 `history[before_rows:]`（從發信那一刻起新增的 history 列）：
  1. 若裡面有 `aos.letter == sig`：確定是**新版身體**，走精準 `aos.answer_to` 配對。
  2. 若 `sig` 已離開 queue，且 `history[before_rows:]` 裡出現了一般 `role == "user"` 列（非 `[aos]` 系統列）卻**沒有 `aos` 鍵**：
     這就 100% 證明**「剛剛收下我這封信的身體是還沒換樹的舊版」**！
     此時立刻切換為舊版等待邏輯：**等待 `not handed_unanswered()` 且 `len(answers()) > before_answers`**，拿到後印出 `answers()[-1]` 並在 stderr 提醒一句「agent 身體尚未升級，本次使用舊版配對」。
  * **為什麼這招無懈可擊**：
    * 全新 agent、剛 summarize 完的 agent（整份 history 沒有 `aos.letter`），只要身體是新版，信進 history 時就會帶 `aos.letter`，**絕不會誤退回舊邏輯**；
    * 半新半舊的 agent（以前有 `aos.letter`，現在跑舊身體），因為看的是 `history[before_rows:]` 新增的列有沒有 `aos` 鍵，**也能正常退回舊邏輯，不會報 `LetterDropped`**；
    * 退回舊邏輯時有 `before_answers` 與 `handed_unanswered()` 把關，**絕不會拿到發信前的舊回答**！

---

## 三、對 03 計劃的具體修正清單（可直接替換進 03）

1. **修正 §1（寫入端規則）**：
   * **user 列**：寫入時覆蓋原有的 `aos` 鍵為 `{"letter": sig}`。核對 `midturn.py:14` 與 ok-wake 的 `extra()`，確保中途信也是**先寫入 history（帶 `aos.letter`）再從 queue `done`**。
   * **最終回答列**：
     * 先剝除端點回傳物件可能自帶的 `aos` 鍵。
     * **eca**：`slash.py` 寫回答時 `answer_to = [slash_sig]`；`turn.py:84` 寫回答時 `answer_to` 為 `hand.good` 扣除已由 slash 單獨回答過的信名。
     * **fsm**：由 `request` 記錄本輪收到的信名，或往回掃描時排除已結案信名（已出現在 `answer_to` 或 `failed_letters` 者）並在 `self_history`／`do_task` 保護未答的 `aos.letter`（或於折疊時保留 `pending_letters`）。
   * **丟信與失敗紀錄**：
     * 壞信、被 hook 擋掉的信：先在 `history_removed.jsonl` 寫入 `dropped` 紀錄（含 `letter`、`reason`、`detail`），再從 queue `done`。
     * eca `CliFailed`／`ReplyMissing`（及 fsm 輪中放棄）：在 `history_removed.jsonl` 寫入 `failed_letters` 紀錄。

2. **修正 §2（讀取端 `answer_for` 與 `listen`）**：
   * **Queue 掃描順序**：固定**先掃 `new/` 再掃 `cur/`**（順著信件搬移方向的上游到下游）。
   * **`answer_for(stack, name)` 判斷順序**：
     1. 在 `new/` 或 `cur/` ➔ `waiting`。
     2. 在 `history.jsonl` 找到 `aos.answer_to` 含 `name` ➔ `answered`（回傳文字）。
     3. 在 `history_removed.jsonl` 找到：
        * `message.aos.answer_to` 含 `name`（取最後一筆）➔ `answered`（stderr 提示已移出 history）；
        * `dropped` 或 `failed_letters` 含 `name` ➔ **立即報 `LetterDropped`**（附該筆紀錄自己的 `reason` 與 `detail`，不用 `mailbox_warning.txt`）。
     4. 在 `history.jsonl` 或 `history_removed.jsonl` 找到 `aos.letter == name` ➔ `handed`（繼續等）。
     5. 以上皆無 ➔ 若 `history[before_rows:]` 出現無 `aos` 鍵的一般 user 列，切入舊身體相容等待（等 `not handed_unanswered()` 且 `len(answers()) > before_answers`）；否則再做一次雙重檢查（防搬移交錯），仍無則保持等待至 timeout 報 `AnswerMissing`。
   * **`listen` 不給 `--letter` 時**：
     * 若 queue（`new/`＋`cur/`）非空：取 queue 最後一封信名，用 `answer_for` 等它。
     * 若 queue 為空：看 history 最後一則最終回答之後，有沒有**尚未結案**（不在 `answer_to` 也不在 `failed_letters`）且帶 `aos.letter` 的 user 列？
       * 有 ➔ 用 `answer_for` 等那封信；
       * 沒有（但 `handed_unanswered()` 為真，例如正在跑無信名的 goal 提醒輪）➔ 等新回答產生後印出 `answers()[-1]`；
       * 都沒有（處於閒置且已答完）➔ 直接印出 `answers()[-1]`（維持原本「印最後一則回答」的直覺行為）。

3. **修正 §4（剝鍵、封存與測試／文件清單）**：
   * `for_endpoint(m)` 放在 `cell_common.py`，回傳新 dict（`{k: v for k, v in m.items() if k != "aos"}`），並在 `cell_common.py:17-30`、`brain.py:191`、`wait.stale_request` 統一使用。
   * 確認 `self_history` 與 `do_task` 折疊移除列時，一律寫入 `history_removed.jsonl`。
   * 把 02 §4 的 `test_do_task_fold.py`、`test_slash.py`、`test_ask.py` 以及 01 §2 的 `docs/NORMS/附錄4-持久檔.json#/rows/24`、`01-P-11～P-14.md`、`cli/history.json` 補回 §4 清單。
