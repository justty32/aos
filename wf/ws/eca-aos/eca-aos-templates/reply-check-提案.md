agent-fsm 收尾時「有 REQUEST 還沒回就提醒一次」的狀態機設計提案（11-24，範本位子；只設計、沒改 .py，格程式明早搬進 py/aos/apps/agent_fsm/、歸核心程式位子）。

# reply-check 提案：收尾前看有沒有沒回的 REQUEST

← [筆記](notes.md)｜起因：guanyu/ops 來信第 ④ 條（progress `ops-feedback-1124`），使用者 11-24「那四條也照推薦做」

## 現象

ops-patrol（agent-fsm、gpt sol）11-23 做完工作沒寄回信，要上層 `say` 提醒才寄；排隊中的那則 `say` 又讓它多寄一封重複的確認。system 文字 11-24 已補一句「寄出回信是最後一步，給最後答案之前先確認每個接下的 request 都有它唯一的一封回信」（`templates/agent-fsm/system.txt` 第 10 段）。這份是另一半：不靠腦記得，由狀態機在收尾時看一次。

## 做法：照 goal 提醒的樣子放在 idle 格

`idle.py` 已經有一個一模一樣形狀的機制：沒信、history 最後一則是沒有 `tool_calls` 的 assistant（＝腦給了最後答案）時，`goal_turn()` 丟一則 user 提醒、退 0 回 think。reply-check 排在同一個位置、在 goal 之前：

1. **什麼時候看**：這一拍沒收到信，且 history 最後一則是沒有 `tool_calls` 的 assistant。其他時候不讀 history（跟 goal 一樣先看便宜的條件），所以平常每拍不多花。
2. **看哪一段**：從 history 尾巴往回讀（上限照 goal 的 paused 檢查，262144 bytes），讀到上一次 compact 的 summary 為止。
3. **接了哪些 REQUEST**：`mailbox_read` 工具結果裡的每封信（輸出的 `letter: <名>` 與 `status: REQUEST` 兩行；`all: true` 的一次多封）。
4. **回了哪些**：assistant 的 `tool_calls` 裡 `mailbox_send`，arguments 有 `in_reply_to` 的，收集那個信名（結果是錯誤的不算，看配對的 tool 結果開頭不是錯誤行）。
5. **沒回的**＝3 減 4。不空、而且這幾封都還沒被提醒過，就接一則 user：
   `[aos] reply check: you took request <信名> ("<title>") and sent no answer with in_reply_to set to it. Answer it once with mailbox_send (DONE, BLOCKED, NEEDS-USER or FAILED), or say in your answer why not.`
   退 0 去 think。
6. **只一次**：提醒過的信名就寫在那則提醒裡；第 2 步往回讀時看到提醒裡有這個信名，就不再提。腦答完還是沒寄（例如它判斷不該回），就讓它停，不纏。

## 為什麼不會再造成重複寄

- 只看 `in_reply_to`，不看標題、內容；寄過一封帶 `in_reply_to` 的就算回了，不再提醒。
- 提醒走 history，不走 queue（同 goal），不會排在其他信後面晚到，也不觸發 before_queue／after_queue hook。ops 那次的重複，是因為 `say` 進了 queue，等腦寄完才被讀到。

## 便宜嗎

- 沒有最後答案的拍（大多數拍）：一個條件判斷，不讀檔。
- 有最後答案時：讀 history 尾巴一次（goal 的 paused 檢查已經在做同樣的讀），算兩個集合。
- 不叫腦、不叫工具；最多多問腦一輪（提醒那一則）。

## 要誰定

- 動 `.py`：明早 templates 三分把格程式搬到 `py/aos/apps/agent_fsm/`，歸核心程式位子，由 eca-aos 派。
- 開不開關：建議預設開、可在 `interfaces.json`（或 `loop.json` 的 idle 參數）關掉；名字、位置照核心程式位子的慣例。
- 測試：`tests/agent-fsm/` 學 goal 的那幾支，用假 history 驗「沒回→提醒一次」「回了→不提醒」「提醒過→不再提醒」「compact summary 之前的不算」。
