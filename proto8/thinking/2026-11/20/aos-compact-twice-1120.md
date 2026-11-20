# 線 aos-compact-twice-1120：連續兩封 /compact 今天在 agent-fsm 與 eca 各會怎樣（只查現況，沒改程式）

頂層派、線隊長寫。程式、測試、文件一行沒動；只交這份紀錄。

## 00 使用者原話（逐字）

- 「compact這塊，如果在等回答途中，是先來了普通訊息，後面才接著compact，那就算兩封信。就是說，兩次連續compact應該要擋掉，這是單獨用於compact的特性。」
- 頂層用選項框問「這是一條新規則…跟『同一封信過兩次 hook』是兩件事。對嗎？」他選：「對，兩件事都要」
- 問「『連續』怎麼算？」（選項：中間要有腦的回合／中間要有別的信／只管同一批排著的／先不定）他用自由填寫回答：「應該說，第二封compact照樣收，只是那個工具看到上次是compact，那這次就不做。」
- 問「被擋掉的那封 /compact 要怎麼處理？範圍要包含哪種身體？」他選：「安靜丟掉，兩種身體都做」（選項說明：不回信、不報錯，只記一行 log；fsm 和 eca 都加這條）。
- 之後（11-20，本線開工後）：「原來你說的是hook這塊的bug，好，那沒事了。」
- 頂層用選項框問「連續第二次 compact 不做這條還要嗎？」他選「先只查現況」（選項說明：只做實跑——今天連續兩封 /compact 各會怎樣，不改程式，看到結果再定）。

所以本線縮成：查現況＋實跑，不改程式、不代選、不推薦。

## 01 兩種身體怎麼認 /compact、誰實際做 compact

行號照 HEAD `7327f47bc`（這幾個檔工作樹裡沒有別線的改動；`midturn.py` 例外，見下）。

### agent-fsm（`templates/agent-fsm/`；起手範本 `templates/start-api/agents/ann/` 是一模一樣的抄本）

- **認**：`compact.py:28-32` `is_compact`——去頭尾空白後第一個字是 `/compact`，後面的字當「額外指示」。
- **收信那格**：`idle.py:150-214` `take()`。`/compact` 信在 `idle.py:169-175` 先被挑出來、**不過 before_queue／after_queue**（設計如此，`hook_points.json:6`、測試 `test_compact.py` 的 `test_compact_bypasses_both_queue_hooks`）；同一批的普通信先照常進對話，`/compact` 在最後合成**一次**請求（`idle.py:196-213`）。
- **門檻**：`compact.py:9` `MIN_ROWS = 4`。能摺的不到 4 則＝這封記成 dropped `failed`、`mailbox_warning.txt` 寫 `letter X not compacted: only N messages to fold`、對話不動（`idle.py:205-209`）。
- **做的那個「工具」**：不是一支工具，是 `compact.py` 這組函數由三格接力——`idle.py` 叫 `compact.ask`（`compact.py:73-81`，在對話尾加一則 `[aos] compact: …` 請求、`compact.json` 記 `phase: asked`）→ `brain.py:160`/`:240` 這次問腦不給工具 → `wait.py:620-629` 收到回答叫 `compact.fold`（`compact.py:183-238`：摘要之前的全換成一則 `[aos] summary: …`＋一則 `compact done …`（`aos.compact: true`），原文搬到 `history_removed.jsonl`，`compact.json` 記 `phase: done`）。
- **答到一半來的 /compact**：`brain.py:134-158`，要工具結果都到齊、而且能摺的 ≥4 則才認領。
- **自動的**：`context_wrap` hook（`templates/agent-fsm/hooks.json` 的 `context_wrap`，handler `py/tools/agent/context_wrap`）滿 35% 時寄一封只有 `/compact` 的信，走的是同一條收信路。

### eca（`py/aos/apps/eca/`，aos-eca-turn）

- **認**：`slash.py:75-78` `is_compact`（`/compact` 或 `/compact 指示`）；`slash.py:81-95` 任何 slash 信一定自己一批。
- **收信**：`turn.py:54-70`——`/compact` **照常過 before_queue**（`turn.py:64`），自己一批；`turn.py:77-79` 認出是 slash 就交給 `slash_turn`。
  等回答時來的 slash 信：`midturn.py`（工作樹裡有線 `aos-hook-drift-1120` 沒交的改動，本線沒看沒碰）；照 `1bcde0265` 的紀錄，HEAD 上它在 `midturn.py:41` 過一次 hook、留在 cur/、下一輪 `turn.py:64` 再過一次——那是另一件事，不在本線。
- **做的那個「工具」**：`slash.py:240-347` `slash_turn`，照身體與畫面分五條：
  - claude、沒畫面（最常見）：`slash.py:283-300`——`Handoff.ask` 把 `/compact` 原樣用 `claude -p --resume` 交給 claude（**真的叫一次 CLI**），再從 transcript 找最後一則 `isCompactSummary`（`agentlib/cli_hook.py:111-131`），`replace_history(..., keep_tail=True)`（`cli_hook.py:50-103`）把 history 換成「`[aos] summary:` 一則＋這封 `/compact`」，再接 claude 的回答。
  - 畫面開著（claude／pi／codex）：`slash.py:276-282` → `on_screen`（`slash.py:185-222`）照人打字一樣打進畫面，等畫面 hook 改 history（claude 的 SessionStart compact：`cli_hook.py:282-283`）。
  - pi、沒畫面：`slash.py:316-317` → `pi_compact`（`slash.py:225-237`），另起一次 `pi --mode rpc` 送 compact。
  - codex、沒畫面：`slash.py:318-321`，codex exec 不會壓，只 `drop_session`（下一封開新 thread、帶 aos 的紀錄過去）。
  - claude 還沒對話：`slash.py:284-285` 回一句「nothing to compact」。
- eca 沒有像 fsm `compact.json` 那樣的「上次 compact 做完」紀錄；也沒有「能摺幾則」的門檻。

## 02 實跑

- 樹：`git archive HEAD`（`7327f47bc`）抄到 `~/.aos/scratch/aos-compact-twice-1120/base/`、複本裡 `install.py`；腳本先 unset 全部 `AOS_*`。
- 一台真的 aos-daemon＋一台問腦總機（`kernel_llm`），**假腦**：fsm 的端點是 scratch 裡的 `endpoint.py`（compact 請求回 `SUMMARY-n`，其他回 `answer to: …`，每次記一行）；eca 用 `py/tests/apps/eca/fake_claude` 外面包一層（`/compact` 時照真 claude 的樣子往 transcript 補一行 `isCompactSummary`，內容 `CLAUDE-SUMMARY-n`）。`HOME`、`CLAUDE_CONFIG_DIR` 都指到 scratch。
- 定義：`templates/agent-fsm`、`templates/eca-claude` 各抄一份，`hooks.json` 換成只有一支計數用的 before_queue hook（不改內容、不擋），其他 on_clock hook（含 context_wrap）拿掉，結果才穩。
- 每個情境一隻新 agent，`aos-agent say` 一封等它處理完再寄下一封；最後對最後那封 `/compact` 跑 `aos-agent listen --letter … --timeout-s 3`。
- 腳本 `~/.aos/scratch/aos-compact-twice-1120/run_twice.py`（`run.sh base run1` 起），輸出原樣在 `run1.txt`，跑完兩台 daemon 都用 `aos-daemon-ctl -d … shutdown` 收（退 0）。

輸出（原樣）：

```
=== fsm fsm_a: q1 | q2 | /compact | /compact
  say 'q1'                   -> letter 000000000001.01795153074031325715.1834206.2080427: answered (answer to: q1) 
  say 'q2'                   -> letter 000000000002.01795153079538577734.1834737.2080977: answered (answer to: q2) 
  say '/compact'             -> letter 000000000003.01795153086866994500.1835235.2081710: answered (compact done: 5 messages replaced by the summary above; the originals ) 
  say '/compact'             -> letter 000000000004.01795153091241915475.1835912.2082148: dropped (failed) 
  history:
    user      '[aos] summary: lines 1-5, 5 messages. SUMMARY-1 of 6 message' 
    assistant 'compact done: 5 messages replaced by the summary above; the ' {"answer_to": ["000000000003.01795153086866994500.1835235.2081710"], "compact": true}
  mailbox_warning.txt: letter 000000000004.01795153091241915475.1835912.2082148 not compacted: only 2 messages to fold
  compact.json: {"phase": "done", "letters": ["000000000003.01795153086866994500.1835235.2081710"], "done_at": "2026-11-20T05:38:09.395Z", "replaced": 5, "kept": 0, "summary_chars": 23}
  letters.json: {"pending": [], "dropped": [{"letter": "000000000004.01795153091241915475.1835912.2082148", "reason": "failed", "at": "2026-11-20T05:38:11+00:00"}]}
  before_queue saw: ['q1', 'q2']
  brain requests so far (all fsm agents): 3, compact asks: 1
  listen --letter 000000000004.01795153091241915475.1835912.2082148 (last /compact): exit 1, stdout '', stderr 'aos-agent: error: LetterDropped 000000000004.01795153091241915475.1835912.2082148 will not be answered: fsm_a dropped it (failed: the agent failed after it was handed over); say it again for a new ans'

=== fsm fsm_b: q1 | q2 | /compact | plain letter | /compact
  say 'q1'                   -> letter 000000000001.01795153093870531848.1836306.2082412: answered (answer to: q1) 
  say 'q2'                   -> letter 000000000002.01795153097439538278.1836850.2082768: answered (answer to: q2) 
  say '/compact'             -> letter 000000000003.01795153100561120643.1837476.2083081: answered (compact done: 5 messages replaced by the summary above; the originals ) 
  say 'plain letter'         -> letter 000000000004.01795153104419069117.1838241.2083466: answered (answer to: plain letter) 
  say '/compact'             -> letter 000000000005.01795153108258680624.1838903.2083850: answered (compact done: 5 messages replaced by the summary above; the originals ) 
  history:
    user      '[aos] summary: lines 1-5, 5 messages. SUMMARY-3 of 6 message' 
    assistant 'compact done: 5 messages replaced by the summary above; the ' {"answer_to": ["000000000005.01795153108258680624.1838903.2083850"], "compact": true}
  mailbox_warning.txt: (none)
  compact.json: {"phase": "done", "letters": ["000000000005.01795153108258680624.1838903.2083850"], "done_at": "2026-11-20T05:38:29.941Z", "replaced": 5, "kept": 0, "summary_chars": 23}
  letters.json: {"pending": [], "dropped": []}
  before_queue saw: ['q1', 'q2', 'plain letter']
  brain requests so far (all fsm agents): 8, compact asks: 3
  listen --letter 000000000005.01795153108258680624.1838903.2083850 (last /compact): exit 0, stdout 'compact done: 5 messages replaced by the summary above; the originals are in history_removed.jsonl', stderr ''

=== eca eca_a: hello | /compact | /compact
  say 'hello'                -> letter 000000000001.01795153112356435302.1839458.2084260: answered (FAKE: hello) 
  say '/compact'             -> letter 000000000002.01795153114372399898.1839819.2084462: answered (FAKE: /compact) 
  say '/compact'             -> letter 000000000003.01795153116266161401.1840167.2084651: answered (FAKE: /compact) 
  history:
    user      '[aos] summary: lines 1-3, 3 messages. CLAUDE-SUMMARY-2'     
    user      '/compact'                                                   {"letter": "000000000003.01795153116266161401.1840167.2084651"}
    assistant 'FAKE: /compact'                                             {"answer_to": ["000000000003.01795153116266161401.1840167.2084651"]}
  mailbox_warning.txt: (none)
  compact.json: (none)
  letters.json: {"pending": [], "dropped": []}
  before_queue saw: ['hello', '/compact', '/compact']
  claude calls so far (all eca agents): ['hello', '/compact', '/compact']
  listen --letter 000000000003.01795153116266161401.1840167.2084651 (last /compact): exit 0, stdout 'FAKE: /compact', stderr ''

=== eca eca_b: hello | /compact | plain letter | /compact
  say 'hello'                -> letter 000000000001.01795153119615449105.1840618.2084986: answered (FAKE: hello) 
  say '/compact'             -> letter 000000000002.01795153121652362403.1840787.2085190: answered (FAKE: /compact) 
  say 'plain letter'         -> letter 000000000003.01795153123597331244.1840919.2085384: answered (FAKE: plain letter) 
  say '/compact'             -> letter 000000000004.01795153125696496206.1841063.2085594: answered (FAKE: /compact) 
  history:
    user      '[aos] summary: lines 1-5, 5 messages. CLAUDE-SUMMARY-2'     
    user      '/compact'                                                   {"letter": "000000000004.01795153125696496206.1841063.2085594"}
    assistant 'FAKE: /compact'                                             {"answer_to": ["000000000004.01795153125696496206.1841063.2085594"]}
  mailbox_warning.txt: (none)
  compact.json: (none)
  letters.json: {"pending": [], "dropped": []}
  before_queue saw: ['hello', '/compact', 'plain letter', '/compact']
  claude calls so far (all eca agents): ['hello', '/compact', '/compact', 'hello', '/compact', 'plain letter', '/compact']
  listen --letter 000000000004.01795153125696496206.1841063.2085594 (last /compact): exit 0, stdout 'FAKE: /compact', stderr ''
```

（`brain requests`／`claude calls` 是整個 run 累計，同一隻端點／同一份 log 給所有 agent 共用。fsm_a 之後 fsm_b 的 `compact asks: 3`＝fsm_a 1 次＋fsm_b 2 次。）

### 讀出來的

**agent-fsm，連續兩封（fsm_a）**
- 第二封**今天就不做**：沒問腦（compact 請求只有 1 次）、對話不動。原因不是「認出上次是 compact」，是門檻——compact 完對話只剩「摘要＋compact done」2 則，`MIN_ROWS = 4` 不到。
- 但不安靜：這封記成 dropped `failed`、`mailbox_warning.txt` 一行；寄的人用 `aos-agent ask`／`listen` 拿到**錯誤** `LetterDropped`，原因字樣是「the agent failed after it was handed over」（跟實際原因對不上）。
- before_queue 兩封 `/compact` 都沒過（設計如此）。
- 照 `compact.py` 的算法，compact 完能摺的永遠是 2 則（留下來的未答信、尾巴的 user 都不算），所以「上一次 compact 之後什麼都沒新增」的第二封一定撞門檻——不管上次是收信時做的還是答到一半做的。
- 同一批排著兩封（例：`/compact`、`/compact 指示`）今天本來就合成一次請求、兩封一起被那則 `compact done` 答掉（既有測試 `test_entire_batch_is_taken_before_one_ask`）。

**agent-fsm，中間夾一封普通信（fsm_b）**：第二封照做——能摺的變 5 則（舊摘要、compact done、普通信、回答……），問腦一次，舊摘要被摺進新摘要（摘要的摘要）。

**eca，連續兩封（eca_a）**
- 第二封**今天照做**：兩封都過 before_queue（各一次），第二封又 `claude -p --resume … /compact` 叫一次 CLI，history 從「摘要1、/compact、回答」再換成「摘要2、/compact、回答」，那 3 則搬進 `history_removed.jsonl`。
- 沒報錯、沒壞東西，寄的人正常拿到回答。

**eca，中間夾一封普通信（eca_b）**：跟連續兩封一樣照做，只是第二次摺的多了普通信那一問一答。

## 03 連續做兩次的實際代價或害處

- **agent-fsm**：沒有多花問腦；害處只在「吵」——寄的人拿到 `LetterDropped` 錯誤（原因字樣寫錯成「the agent failed after it was handed over」）、`mailbox_warning.txt` 被覆寫成這一行（蓋掉前一則警告）。對話、摘要、`handoff.md` 都不動。
- **eca（claude，沒畫面）**：多叫一次 claude。真的 claude 時是一次真的模型呼叫，在剛壓完的對話上再寫一份摘要（摘要的摘要，可能越壓越短、丟細節）；`history_removed.jsonl` 多 3 則。假腦跑看不出花多少、也看不出真 claude 遇到「剛壓過」會不會拒絕（本線沒叫真模型）。
  - 沒驗證的一點：如果真 claude 這次沒產生新的 `isCompactSummary`（例：它說太短不壓），`compact_summary` 會撿到 transcript 裡**上一次**的摘要（`cli_hook.py:111-131` 取最後一則），aos 就把 history 換成那份舊摘要；連續兩封時中間只有 `/compact` 那一問一答，所以實際只是那兩則被搬走。
- **eca 其他身體**（沒實跑）：codex 沒畫面＝只再 `drop_session` 一次，不花錢；pi 沒畫面＝再起一次 `pi --mode rpc` 壓（對話太短時 pi 會回原因、history 不動，`slash.py:229-231`）；畫面開著＝再打一次 `/compact` 進畫面，等畫面 hook 最多 120 秒（`slash.py:174`）。

## 04 若要加規則，看到的邊緣狀況（只列，不選）

1. 「上次是 compact」怎麼判：fsm 有 `compact.json`（`phase: done`）可以接著用；eca 今天沒有對應的紀錄，要另記（例：compact 做完那刻 history 的雜湊）。eca compact 完的 history 長「摘要、這封 /compact、回答」，fsm 長「摘要、compact done（＋留下的未答信）」，兩邊不一樣。
2. fsm 今天其實已經不做第二次（門檻擋），加規則實際只改「怎麼丟」：安靜 vs. 今天的 dropped failed＋警告＋寄的人收到錯誤。
3. 「不回信、不報錯」跟 `aos-agent ask` 的衝突：信收掉但 `letters.json` 什麼都不記＝`ask`／`listen` 等到逾時才說「left the queue but has no record」，沒給逾時就一直等；記成 dropped＝寄的人拿到 `LetterDropped` 錯誤。兩種都不是「什麼都沒發生」。
4. compact 失敗之後再來一封（fsm：`phase: failed`；eca：找不到摘要、畫面 120 秒沒動、pi 說太短）算不算「上次是 compact」。
5. 重起 agent 之後（fsm 的 `compact.json`、history 都還在）。
6. CLI 自己做的 compact（claude 畫面自動壓、codex 自己壓，靠畫面 hook 改 history）算不算上一次。
7. 手動與自動混著來：context_wrap 寄的也是一封 `/compact` 信，走同一條路；context_wrap 自己本來就「讀數沒降回門檻下不會再寄」。
8. hook 把 `/compact` 改成別的字（或把別的字改成 `/compact`）：只有 eca 會發生（fsm 的 `/compact` 不過 hook）；eca 是過完 hook 才認 slash（`turn.py:64` 在 `:77` 之前）。
9. 「照樣過 before_queue」：eca 今天每封 `/compact` 都過；fsm 的 `/compact` 一封都不過（設計），所以這句只在 eca 有意義。
10. 第二封帶不同的指示（`/compact` 之後馬上 `/compact 重點放在 X`）算不算連續。
11. 中間只多了 goal 提醒、mail_notify 的 `[aos] new_mail` 這類 aos 自己塞的訊息、或 `aos-agent history` 從外面改過，算不算「有新東西」。
12. 等回答途中來的 `/compact`：fsm 走 `brain.py:134-158`（要能摺 ≥4 則才認領）；eca 留在 cur/ 下一輪（另一條線在改的那段）。
13. eca 不同身體、畫面開關不同，「做完」的時間點不同（畫面路要等 hook），判法要對五條路各自成立。

## 05 對不上處

- 任務書原本要「第二封照樣過 before_queue」兩種身體都驗；fsm 的 `/compact` 依設計本來就不過 before_queue（第一封也不過），這句只在 eca 成立。
- fsm 的「連續第二封」今天已經不做（被 4 則門檻擋），跟頂層原先假設「今天會做兩次」不同；eca 今天確實做兩次。

## 06 替使用者做的選擇

- 實跑時把定義的 on_clock hook（含 context_wrap、mail_notify、timer）拿掉、只留一支計數 before_queue hook，讓結果只反映 `/compact` 本身。
- 假 claude 在 `/compact` 時補一行 `isCompactSummary`（照真 claude 11-12 實測的形狀），否則 aos 這邊永遠「找不到摘要、history 不動」，看不出第二次壓的是什麼。
- 只跑 claude 沒畫面那條 eca；畫面路、codex、pi 沒跑（要 tmux 或對應 CLI），只照程式讀。

## 07 收尾

- repo：沒改任何程式、測試、文件；本線開工到收到縮小範圍時還沒動 repo 檔，沒有要還原的檔、沒有 patch、沒 claim 過程式檔。
- 暫存：`~/.aos/scratch/aos-compact-twice-1120/`（`base/` 複本、`run1/` 實跑樹、`run1.txt` 輸出、`run_twice.py`、`run.sh`、`setup.sh`、`suite.sh`、`check.sh`、`look*.sh`；`suite-base.txt`＋`logs-base/` 是開工時跑的相關夾基準，範圍縮小後沒用到）。TMPDIR `/tmp/aos-compact-twice-1120-*`。
- 行程：實跑的兩台 daemon 已 shutdown（退 0）。
