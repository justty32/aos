# 回答配對 02：fable 設計稿（原文）

← [reply-match-1114](../reply-match-1114.md)

> 11-14 ok-pilot 派 fable（Claude 子 agent，唯讀）。只給事實（01 備料與 sol-7／sol-8 的 answer.md），沒有給 ok-pilot 的傾向。fable 讀 01 與部分原始碼時被權限擋下（它自己在缺口段寫明），所以 file:line 都轉引自 sol 備料；關鍵幾處 ok-pilot 已回原始碼核對過，見 [03](03-計劃.md)。下面是原文，未改。

# 設計：agent 的回答對到是回哪封信

## 先講缺口

- **`01-備料.md` 沒讀到**，所以「別線定案、前置依賴」沒併進這份設計，請先對過再採納。
- 同樣沒讀到：`AGENTS.md`、`user.md`、`aos-teams.md` 與 06、07，以及 proto8 原始碼。Read 和 Grep 在這些路徑都被權限擋下，我沒有改用 shell 繞過。
- 讀到的只有三份：sol-7 和 sol-8 的 `answer.md`，以及知識庫入口 `_description.json`。
- 下面的 file:line 全部轉引自 sol-7／sol-8，**我沒有回原始碼核對**。路徑都在 `/home/lorkhan/repo/aos/proto8/` 下。
- 第 5 節換樹清單只列檔案，換樹步驟的硬規則（06 那份）沒讀到。

## 現況

- 信名在收信那一刻是知道的，但沒人存下來。
  - fsm 寫 user 列時只留 `role`、`content`（`templates/agent-fsm/idle.py:164`）。
  - eca 的信名只活在 Handoff 物件裡（`cmd/aos-eca/aos_eca/handoff.py:13`）。
- `ask` 丟掉 `sender.put` 回的信名，只靠「回答數變多」來等（`cmd/aos-agent/aos_agent/ask.py:46`、`listen.py:51`、`:64`）。
- 所以兩個人同時問，會拿到彼此的回答；help 自己也這樣寫（`ask.py:12`）。

## 1. 多記什麼、記在哪、誰寫、何時寫

推薦兩處一起記：history 列內加一個 `aos` 鍵當永久紀錄，stack 裡加一個小檔 `letters.json` 當工作狀態。

**history 列內**

- 信的 user 列：`{"role":"user","content":…,"aos":{"letter":"<信名>"}}`。
- 最終回答列（沒有 `tool_calls` 的 assistant，同 `py/aos_ws.py:139` 的判定）：加 `"aos":{"answer_to":["<信名>",…]}`。
- goal 提醒列、summary 列不加。沒有信可回的回答（例如只被 goal 提醒觸發）也不加。
- 鍵名不叫 `in_reply_to`、`reply_to`，避開 mailbox 那組名字。
- aos 自己的東西全收在 `aos` 這一個鍵下，送端點時只要剝一個鍵。

**`<stack>/letters.json`**（小檔，寫暫存檔再改名）

- `pending`：已交給腦、還沒被最終回答蓋到的信名。
- `dropped`：最近 N 筆（例 200）`{"letter","reason","at"}`；`reason` 是 `bad`、`blocked`、`failed`、`lost`。

**誰寫、何時寫（fsm）**

- idle 收一封好信（`idle.py:157`–`:170`）：先附加帶 `aos.letter` 的 user 列，再把信名加進 `pending`，最後才 `done`。
- idle 丟壞信或被 hook 擋的信（`idle.py:153`–`:160`）：先記進 `dropped`，再 `done`。
- wait 收到沒有 `tool_calls` 的回覆（`wait.py:505`）：讀 `pending`，寫進 `aos.answer_to`，附加這一列，然後清空 `pending`。

**為什麼要 `pending` 檔，不從 history 現算**

- 一輪中間，agent 可以把自己剛收的 user 列折掉或刪掉。
- self_history 的鎖只從最近一則 assistant 起算（`lib/agent/self_history/_entry:109`–`:158`），保護不到更早的信列。
- do_task 折疊也會動到 user 列（`lib/agent/do_task/_entry:119`–`:231`）。

**寫入順序的用意**

- 任何時刻，一封信名至少在一處：queue、`pending`、`dropped`、或 history 的 `answer_to`。
- 讀的人因此不會把「正在搬」誤判成「不見了」。

## 2. ask／listen／chat／subagent 怎麼配對

共用一個函式，建議放 `py/aos_ws.py`，例 `answer_for(stack, name)`。它照順序查：

1. history 裡第一則 `aos.answer_to` 含這個信名的最終回答 → 回它的文字。
2. `letters.json` 的 `dropped` 有它 → 報錯 `LetterDropped`，帶 `reason`。
3. 信名還在 queue 的 `new`／`cur`，或在 `pending` → 繼續等。
4. 都不在 → 再查一次第 1 步（防交錯）。還是沒有，就查 `history_removed.jsonl` 裡 `message.aos.answer_to` 含它的那筆。
   - 封存會留整個 message 物件（`cmd/aos-agent/aos_agent/history.py:207`、`lib/agent/cli_hook.py:86`）。
   - 找到就印，stderr 加一句「這則回答已被移出 history」。
   - 找不到報新錯碼 `AnswerRemoved`。

**各指令**

- `ask`（`ask.py:32`–`:46`）：留住 `sender.put` 回的信名（`sender.py:43`、`aos_ws.py:94`），用它等。刪掉 `before` 計數和 `handed_unanswered`（`listen.py:51`）。stdout 仍只印回答。
- `chat`（`chat.py:56`）：同 `ask`，每句用自己的信名。
- `listen`：新增 `--letter NAME`，`say` 本來就會印信名（`say.py:47`–`:53`）。
  - 不給名字時維持「最新那封」的意思：取 queue 最新信名（`listen.py:32`）；queue 空就取 `pending` 最後一個；都沒有就印最後一則回答。
  - `--last`／`--follow` 走 `exchanges()`（`aos_ws.py:153`），不動。
- subagent 的 op ask（`lib/agent/subagent/_entry:228`）：現在是先 `say` 再 `listen`，中間有空窗，也沒傳信名。改成直接呼叫 `aos-agent ask`。op listen 加可選的 `letter` 參數。

**三種出事的情況**

- 等不到：照舊報 `AnswerMissing`，訊息帶信名和它在哪（還在 queue／已交給腦），呼叫者之後可以用 `listen --letter` 再等。
- 信被丟：立刻報 `LetterDropped`，不用等到逾時。
- history 被改過：
  - 回答列還在：照常配到，不管它的 user 列有沒有被刪或 summarize。
  - 回答列被 rm 或 summarize 掉：走封存檔；封存被關掉或改路徑時報 `AnswerRemoved`。
  - 回答列被 `set` 改寫時 agent 自己拿掉了 `aos` 鍵：同樣報 `AnswerRemoved`。知識庫要寫一句「`set` 時保留 `aos` 鍵」。

**一則回答回好幾封**：每個問的人都拿到同一則全文。這是對的，不拆。

## 3. eca 做不做

做。`ask`／`chat` 也會打到 eca（`sender.py:43`），不做的話問題原樣留著。全部在 aos-eca-turn 自己的行程裡完成，不需要 tool hook。

- 收信：`Handoff.handed` 附加 user 列時帶 `aos.letter`（`handoff.py:22`）；中途信同樣（`handoff.py:36`、`midturn.py:14`）。信名寫進 `pending` 後才 `done`。
- 回答：`turn.py:84` 寫 assistant 列時，把這輪的 `good` 加上中途信的名字（`handoff.py:31`、`:45`）寫進 `aos.answer_to`，然後清 `pending`。socket 模式把幾個 CLI 回合併成一則回答的情況（`lib/agent/cli_ask.py:63`–`:81`）也一樣，一列蓋全部信名。
- slash 回答列（`slash.py:275`、`:287`）：`answer_to` 填那封 slash 信。
- 壞信、被擋的信（`turn.py:50`、`hook.py:24`）：記 `dropped`。
- 交出去後失敗（`CliFailed`／`ReplyMissing`，`handoff.py:57`、`:62`）：現在只記丟了幾封。改成把信名記進 `dropped`，`reason` 是 `failed`。
- 行程在交信後、回答前被殺：下一輪開頭看到 `pending` 有殘留，移進 `dropped`，`reason` 是 `lost`。
- 交信前 `SessionBad`：信還在 `cur`，不用處理。
- reseed 只印 `[role] content`（`reseed.py:39`），不受影響。
- `.history_sum` 是整檔雜湊（`history.py:37`），在附加後才算，不受影響。

## 4. 對現有讀者的影響

**要改**

- `templates/agent-fsm/brain.py:191`：history 列原樣送端點，沒有白名單（`cell_common.py:17`–`:30`、`lib/base/llm_http/_entry:60`）。組 request 前要剝掉 `aos` 鍵。
  - 用「剝一個鍵」不用白名單，因為 assistant 列要保留供應商給的其他鍵（`templates/tests/agent-fsm/test_cells.py:111`）。
  - 剝鍵的函式放 `cell_common.py`，brain 和 wait 共用。
- `templates/agent-fsm/wait.py:301` 的 `stale_request`：它拿 history 最後一列整列去比 `request.messages[-1]`。最後一列現在帶 `aos`，request 那邊已剝掉，不改就會每次都判成過期、一直重建。**比之前先用同一個函式剝掉。**
- 寫入端：`idle.py`、`wait.py`；eca 的 `handoff.py`、`midturn.py`、`turn.py`、`slash.py`。
- 讀取端：`aos_ws.py`、`listen.py`、`ask.py`、`chat.py`、`subagent/_entry`。

**不用改**（都只看 `role`、`tool_calls`、`content` 這類欄位，多一個鍵沒事）

- `aos_ws` 的 `is_answer`／`answers`／`exchanges`、history 子指令的 `ls`／`rm`／`set`（`history.py:179`、`:298`、`:336`）。
- `act.py:104`–`:170`、`lib/agent/goal_state.py:130`–`:150`、`idle.goal_turn`（`idle.py:207`）。
- `self_history`、`do_task`（搬列時整個物件照搬）、`brain_notify`、`mail_notify`、`ctl/state.py:75`、`ctl/phase.py:206`。
- eca 的 `history_rows`、`reseed`、`batch`。

**要留意、實作時核對**

- `fork_copy`（`lib/agent/fork/fork_copy.py:64`–`:158`）照抄原始列，分身的 history 會帶母體的信名。信名本身不會撞，但分身不該帶走母體的 `letters.json`。
- Codex compact 重建的列只有 `role`、`content`（`cli_hook.py:174`），舊回答的 `aos` 鍵會消失。那些是已答完的舊輪，可接受。
- aos-view 不在可讀範圍，sol-8 也沒驗（`thinking/2026-11/14/view-1114/03-計劃.md:24`）。要另外確認它遇到多的鍵不會壞。

**要改的測試**（斷言整列相等的那些）

- fsm：
  - `test_hooks.py:111`、`:132`、`:144`、`:152`、`:334`
  - `test_clock_hook.py:183`、`test_goal.py:157`、`:201`
  - `test_cooldown.py:104`、`:138`、`test_selfheal.py:118`
  - `test_do_task_fold.py:168`、`:178`、`:194`
  - `test_cells.py:89`、`:92`、`:111`：加「history 有 `aos`、request 沒有」和「`stale_request` 不誤判」兩案。
- eca：`test_letter_name.py:82`、`:93`、`:102`、`:109`；`test_hooks.py:90`；`test_slash.py:140`；`test_switch.py:246`、`:267`、`:312`。
- aos-agent：`test_ask.py:126`（傳回答數 0 那條改成傳信名）；`:167`、`:175`、`:180` 的行為保留。
- 新增測試：
  - 兩人同時問，各拿各的。
  - 一批多封，拿到同一則。
  - 壞信和被擋的信報 `LetterDropped`。
  - 回答列被 rm 後走封存檔。
  - 逾時訊息帶信名。
  - eca 中途信、eca 交信後失敗。
  - subagent op ask。

**文件**

- 知識庫：`body.json#/system_history`、`me.json#/stack`、`cli/eca.json#/turn`、`me/self_history.json#/rules`，以及 ask／listen／say 的頁。
- `docs/NORMS/附錄4-持久檔.json` 加 `letters.json` 一列。
- P-41、P-42 的「回答就是最新那則 assistant」那句（`docs/CONVENTION/02-題目stack停錯腦/02-P-42.md:3`）。
- `cmd/aos-agent/README.md:50`；`ask.py:12` 的限制說明刪掉。

## 5. 換樹要帶的檔

- `templates/agent-fsm/`：`idle.py`、`wait.py`、`brain.py`、`cell_common.py`。
- `cmd/aos-eca/aos_eca/`：`turn.py`、`handoff.py`、`midturn.py`、`slash.py`，加上放 `letters.json` 讀寫的那支（建議 `history.py` 或 `common.py`）。
- `cmd/aos-agent/aos_agent/`：`listen.py`、`ask.py`、`chat.py`。
- `py/aos_ws.py`。
- `lib/agent/subagent/_entry` 和它的工具說明檔。
- 知識庫上面那幾頁。

注意事項：

- **寫的一方和讀的一方必須同一次換。** 新 `ask` 對上舊身體會誤報 `AnswerRemoved`。
- 現有 agent 的 stack 裡若有自己那份 cell 複本，要一起換或重起。
- 舊 history 不用搬遷，舊列沒有 `aos` 鍵就是配不到而已。
- 換的當下正在等的 `ask` 會失敗，要挑沒人在問的時候換。

## 考慮過但不推薦

- **獨立帳本檔，連回答全文都記。** 完全不碰 history 和端點那條路，也不怕改寫。但回答存兩份、檔案只長不短、要另做清理，而且 history 列本身還是看不出誰是信。
- **用 history 行號指回答。** rm／summarize／set 一動，行號就錯。
- **用信的內文比對。** `before_queue` hook 會改內文（`idle.py:157`），兩封同文的信也分不開。
- **一封信一輪，不成批。** 改掉現有的批次行為，變慢，eca 中途信也做不到。
- **請模型自己在回答裡寫回哪封。** 不可靠，還污染提示。
- **借 mailbox 的 `in_reply_to`。** 那是另一條通道，欄位也不准改；人從 CLI 問的時候沒有 mailbox 可收。

## 要使用者或部長決定的

1. **記在哪。**
   - (a) history 列內 `aos` 鍵加小檔 `letters.json`。
   - (b) 全部放獨立帳本檔，history 不動。
   - 推薦 (a)。代價是 `brain.py` 和 `stale_request` 要改。
2. **鍵的形狀。**
   - (a) 收在單一 `aos` 物件下。
   - (b) 頂層直接放 `letter`／`answer_to`。
   - 推薦 (a)，剝鍵規則只有一條，以後要加東西也不用再動端點那條路。
3. **user 列要不要也記 `aos.letter`。**
   - (a) 記。
   - (b) 只記回答列。
   - 推薦 (a)。配對本身靠 `pending` 就夠，但記了才看得出哪列是信、哪列是 goal 提醒或 summary。
4. **回答列被移出 history 之後。**
   - (a) 去 `history_removed.jsonl` 找，找到照印並提醒。
   - (b) 直接報 `AnswerRemoved`。
   - 推薦 (a)。
5. **eca 交信後失敗的信。**
   - (a) 記名字，`ask` 立刻報錯。
   - (b) 維持只記數量，`ask` 等到逾時。
   - 推薦 (a)。
6. **`listen` 不給信名時。**
   - (a) 維持「最新那封」。
   - (b) 一律要給 `--letter`。
   - 推薦 (a)，人手動用比較順。
7. **`ask` 的輸出。**
   - (a) stdout 只印回答，信名只在逾時或出錯時出現在訊息裡。
   - (b) 另加 `--json`，印 `{letter, answer, answer_to}`。
   - 推薦先做 (a)，(b) 等有人要再加。
8. **subagent op ask。**
   - (a) 改成直接呼叫 `aos-agent ask`。
   - (b) 保留 `say` 加 `listen --letter` 兩步。
   - 推薦 (a)，少一個空窗。當初為什麼沒用 `ask`，我不知道，請確認沒有別的原因。
