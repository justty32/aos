直接叫 API 的 agent（agent-fsm，ann 這類）也認 `/clear` 了：不叫模型，history 全部搬進 history_removed.jsonl、只留這一問一答，下一封信從乾淨的對話開始（線 top-1121-apiclear）。

# API agent 也認 /clear（11-21）

## 使用者原話

使用者問：「ann有支援/clear這個指令嗎」。頂層查到只有 eca 認、直接叫 API 的那種不認，說可以做；使用者答：「做」。

## 先確認的事

- **頂層的說法屬實（/clear 這一條）**：直接叫 API 的 agent 全部跑 `templates/agent-fsm` 的四格（start-api 的 ann、`agent-python` 用 `std.fsm()` 編出來的也是這四格）；改之前 `idle.py` 只認 `/compact`，`templates/docs/02-agent-fsm.md` 也寫著「`/clear` 不在這個功能裡，仍是普通文字」。沒有等效機制（`aos-agent history rm` 可以手動刪，但要人下指令、不是寄一封信）。
- **頂層說法有一處不對**：`/compact` 在 API 這邊**早就有**（11-20 起，`compact.py`；`context_wrap` 自動寄的也是它），不是只有 eca 認。

## 做了什麼

- `templates/agent-fsm/compact.py`：加 `is_clear()`、`clear()`；`replace()`（摺與清工具輸出共用的「寫暫存、history 沒變才改名、原文接進 history_removed.jsonl」）多收讀不懂的行（記 `raw`）。
- `templates/agent-fsm/idle.py`：收信時認 `/clear`，檔頭與 `--help` 補說明。
- 測試 `templates/tests/agent-fsm/test_slash_clear.py`（8 條）。
- 文件：`templates/docs/02-agent-fsm.md` 新一節「寄 /clear：清空對話重來」、拿掉「`/clear` 仍是普通文字」那句；`templates/agent-fsm/README.md` 一段（`start-api/agents/ann/README.md` 開頭是它的原樣，照 `test_start` 一起改）；知識庫 `aos/me/compact.md` 新一節 `# clear: start the conversation over`、`aos/me.md` 指過去、`aos/definition.md` 的 `compact.py` 那句補一句。

## 怎麼驗

- 乾淨複本（`git archive HEAD` 疊這幾檔、`install.py`）：`templates/tests/agent-fsm` 26 支全過（含新的 8 條）；`test_start`、`test_daily`（2 略過、2 預期失敗照舊）、`kits/test_kits`、`py/tests` 的 `test_hook_points_match`、`test_context_wrap`、`test_knowledge_paths` 過。
- 在複本上照 start-api 抄一棵樹、假腦跑一次：hello、again 各答一次（history 8 則）→ `say /clear`，`listen` 拿到 `[aos] slash: /clear: 8 messages moved to history_removed.jsonl; the next message starts a new conversation`，history 剩 2 則、removed 8 則 → 再問一句照答，history 6 則。關樹後行程都收掉。
- 沒叫真模型：`/clear` 本身不碰模型，「之後的信從乾淨的對話開始」看送出的請求就驗得到（測試直接比對寄給假腦的 messages）。

## 替使用者定的

1. **放哪**：寫在 agent-fsm 的格裡（`compact.py`＋`idle.py`），不動 `py/`。改 history 那段跟 `/compact` 的摺共用 `compact.replace()`（有「被別人動過就重做、三次」）；沒共用 eca 的 `cli_hook.clear_history`（它綁 eca 的小格、刪 `.history_sum`、沒有被動過的檢查），也沒共用 `aos-agent history` 的 `rewrite`（那是命令列內部的、帶 `--keep` 與互動確認）。回答的前綴用 lib 既有的 `aos_flags.aos_note("slash", …)`，跟 eca 同一支。結果：**活樹不用重裝**，這批 commit 一進 repo，活樹的 ann 下一次收信就認（ann 的格是動態連結 `$AOS_HOME/templates/agent-fsm/`，家機的 `AOS_HOME` 就是 repo 的 proto8）。
2. **記不記這一問一答**：記，跟 eca 一樣——history 換成 user `/clear`＋assistant `[aos] slash: /clear: N messages moved …`（帶 `aos.answer_to` 與 `aos.clear: true`）。理由：`listen` 照信名配回答、聊天頁才看得到回應；代價是之後模型會看到這兩則（它就知道前面被清過，知識庫也寫了這樣看）。
3. **回答的字**：照 eca，只差 eca 說「a new claude conversation」，這邊沒有 CLI 名字，說「a new conversation」。
4. **一定自己一批**（同 eca）：前面有一般信或 `/compact` 就先處理它們，`/clear` 跟後面的留在 `cur/`；輪到它時只做它，後面的信下一次 idle 再收。輪中來的 `/clear` 等這一輪答完（不像 `/compact` 會在輪中做）。
5. **hook**：不跑 `before_queue`／`after_queue`，跟 API 這邊的 `/compact` 一樣（eca 那邊 slash 會過 `before_queue`，這裡選跟同一隻身體的 `/compact` 對齊）。
6. **lock**：不另外拿鎖。agent-fsm 同時只有一格在跑，`/clear` 在 idle 做；外面同時用 `aos-agent history` 改的話，靠「沒變才改名、三次」擋，跟摺一樣。
7. **不動的東西**：`goal.json`（active 的話回答完 idle 照常接 goal 提醒）、todo、`handoff.md`、`compact.json`。做到一半的 `do_task` 開頭標記會被一起搬走（之後 end 報 `MarkerMissing`，同 compact）。壓縮進行中 idle 不收信，`/clear` 等壓完。
8. **沒寫進文件的小邊緣**：`/clear` 之前讀數已過門檻、`context_wrap` 還沒寄的話，下一拍可能寄一封 `/compact`，會得到 `compact not needed`（history 只剩 2 則），無害。

## 沒做的四個（API 這邊要做的話大概動什麼）

- **`/compact`**：已經有了，不用做。
- **`/status`**：在 `idle.py` 收信那段加一支，跟 `/clear` 一樣不叫腦、回一則 `[aos] slash: …`；內容從 stack 拼（`llm.json` 的模型、history 幾則、goal、compact.json 的 phase、冷卻），可參考 eca 的 `slash_status` 與工具 `self_state`。
- **`/usage`**：API 這邊沒有 CLI 可問額度，要看 llm kernel 有沒有給額度的介面（kernel 回 `BudgetMissing` 時才帶視窗資訊）；做的話是 idle 去讀 kernel 的額度／`observed.jsonl` 的 token 用量拼一則回答，需要先定「usage 指的是哪個數」。
- **`/exit`**：eca 的 `/exit` 是關畫面，API 這邊沒有畫面；最接近的是「讓這隻停下」，idle 收到時照 `self_ctl stop` 或 `aos-agent ctl stop` 的路走，要先定是停下（stop）還是睡（sleep）。
