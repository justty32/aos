compact 改進第 4 刀施工紀錄：agent-fsm 的 `/compact` 加壓縮前、壓縮後兩個 hook 點 `before_compact`／`after_compact`（攔、改指示、交摘要、改摘要、補回都開），規矩寫在範本的 `compact.py`，範本預設不掛；假腦全套與真模型四次小呼叫都驗過補回的字進了對話。

← [2026-11-21](README.md)｜規劃稿 [compact-改進規劃-1121](compact-改進規劃-1121/README.md)（草稿照 [03](compact-改進規劃-1121/03-壓完補回走hook.md)、刀序照 [04](compact-改進規劃-1121/04-施工刀序.md)）｜使用者已答 [07](compact-改進規劃-1121/07-使用者已答.md)｜hook 新格式 [施工紀錄](hook-新格式施工-1121/README.md)｜eca 那邊 [eca-reasoning-effort-1121](eca-reasoning-effort-1121.md)｜進度 `compact-improve`｜線 `top-1121-compact4`

## 使用者原話（逐字）

- 11-20 晚：「壓完後補回這塊，我們可以用hook實現，之後可以實現大家各自的compact方式」
- 11-21 三題：「可以派。三題：1.照叫。2.都開。3.我還在審。」——第 2 題「都開」＝調指示、補回、換掉整個壓縮都開；第 3 題當時在等 hook 宣告格式，今天已定案並施工完（[審格式第 1～8 則](hook-points-格式-使用者審-1121.md)、[引擎第四層](aos-hook-簡化-1121/07-使用者已答.md)）。
- 第 1 刀交件後：「compact這塊，反正各agent有需要的，可以自訂自己的compact程式和流程」
- hook 引擎第四層：「發事件的程式自己決定 <- 沒錯，我們提供的hook fire本身會參與這個過程……如果有人不想用我們的aos-hook fire，那就弄他自己的。」——所以攔、改、補的規矩由 agent-fsm 自己的 `compact.py` 做，引擎（`aos.hook_run`）只負責叫 handler。

## 結論

1. **活樹不用重裝就能起**：格程式只用 lib 裡今天中午（97d4abc16）就有的 `aos.hook_run.run／names` 與 `agent_hooks.open(...).load()`，`py/` 只動了說明字（`self_hook` 給腦看的說明、`aos-agent hook --help`、`agentlib/hooks.py` 檔頭、`docs/06-hook.md`）與一支一致性測試；這些字要等下次 `install.py` 才換進 `lib/`，不影響跑。ann 動態連結 `templates/agent-fsm/` 的格，存檔即生效；沒掛 hook 時 `/compact` 的行為跟以前一模一樣（只多讀一次 hookeds 清單）。
2. **兩個點**（宣告在 `templates/agent-fsm/hooks.json`）：
   - `before_compact`：夠摺時（不到 4 則的 `compact not needed` 不發）、清舊工具輸出與加要求之前，idle 與做到一半的 brain 兩條路都發。能**攔**（退 10）、**改給腦的指示**（`instructions`）、**不清工具輸出**（`clear: false`）、**直接交摘要**（`summary`：不叫腦、不清，當場摺）、先交**補回**（`restore`，當 `after_compact` 的起始值）。
   - `after_compact`：摘要好了、history 改寫之前（wait；hook 交摘要時在 idle／brain）。能**改摘要**（`summary`）、**交補回**（`restore`）：非空就在摘要那則後面接一則 user `[aos] restored after compact: …`，在 `compact done` 之前，不多叫一次腦。
3. **測試**：新 `templates/tests/agent-fsm/test_compact_hooks.py` 11 支（攔、改指示＋不清、交摘要、改摘要＋補回位置＋task 模式找得到摘要、輪中補回、輪中交摘要、輪中攔下、壞掉的 handler 四種、太短不發、stack 抄本關掉）；全套逐夾比基準見「測試」。暫存樹假腦一輪三段都對；真模型 sol 四次小呼叫：補回那則寫的「secret word is PAPAYA-9」，壓完問它答 `PAPAYA-9`。

## 兩個點的 input／output

每份事件照引擎都有 `event`、`hook`、`stack`。

| 點 | input（共通三欄以外） | output（退 0 印 JSON 物件，這些鍵換掉事件裡的） | 退 10 |
|---|---|---|---|
| `before_compact` | `letters`（/compact 信名）、`asked`（/compact 後面的字，沒有＝""）、`instructions`（要求會帶的額外指示，起始＝`asked`）、`mid_turn`、`foldable`（會摺幾則）、`clear`（true）、`summary`（null）、`restore`（null） | `instructions`（字串，""＝不給）、`clear`（布林）、`summary`（非空字串）、`restore`（字串或 null） | 攔下 |
| `after_compact` | `letters`、`summary`（去頭尾空白）、`by`（`brain` 或交摘要的 hook 名）、`mid_turn`、`cleared`（清掉幾則工具輸出）、`restore`（`before_compact` 交的，沒有＝null） | `summary`（非空字串）、`restore`（字串或 null） | 不攔（當 0） |

最短的 handler（補回 todo 清單，掛 `aos-agent hook add --event after_compact ./restore_todo`）：

```python
#!/usr/bin/env python3
# restore_todo - after_compact hook: add the todo list back right after the summary
import json, os, sys
ev = json.load(sys.stdin)
path = os.path.join(ev["stack"], "tools/todo/todo.json")     # the todo tool's own cell in the agent's stack
if os.path.exists(path):
    print(json.dumps({"restore": (ev["restore"] or "") + "\nYour todo list: " + open(path, encoding="utf-8").read()}))
```

換掉整個壓縮（不用模型，例：只留 handoff.md 最後一段）就是 `before_compact` 印 `{"summary": "..."}`；不准壓就退 10、stdout 寫理由。

## 跟 eca 那邊對不上的地方

eca-claude 的同名兩點（[eca-reasoning-effort-1121](eca-reasoning-effort-1121.md)「compact hook 點」）是 Claude Code 自己的壓縮，aos 只接它給的時刻；agent-fsm 是 body 自己壓，照規劃稿自己的流程設計。點名、`asked`、`instructions`、`restore`、`summary` 同名同義的盡量對齊，對不上的：

| 項 | agent-fsm | eca-claude | 為什麼 |
|---|---|---|---|
| `restore` 在哪交 | 兩點都收：`before_compact` 交的當 `after_compact` 的起始值，`after_compact` 可再改 | 只有 `before_compact`（`after_compact` 只告知） | eca 實測 Claude Code 的 SessionStart 比 PostCompact 早跑，補回得在壓之前交；agent-fsm 兩點都收，**同一支只在 `before_compact` 交 `restore` 的 handler 兩邊都能用** |
| `instructions` 的起始值 | `asked`（/compact 後面的字）；body 自己那段要求（`[aos] compact: …`）不給改 | compact_hook 給 CLI 的那段「要留什麼」清單；使用者打的 `asked` 拿不掉 | 兩邊「aos 這側加給模型的額外指示」意思一樣，起始值不同 |
| `summary` | `before_compact` 可交（換掉整個壓縮）、`after_compact` 可改 | `before_compact` 沒有；`after_compact` 只讀 | Claude Code 的摘要改不了 |
| `clear`、`letters`、`mid_turn`、`foldable`、`by`、`cleared` | 有 | 沒有 | Claude Code 給不出來 |
| `trigger`（manual／auto） | 沒有 | 有 | agent-fsm 收到的一律是一封 `/compact` 信，人寄的和 `context_wrap` 寄的分不出來 |
| 多個 handler | 照名字一個一個跑，**後一個看得到前一個改的** | `aos-hook fire` 每個拿同一份事件，依名字順序後蓋前 | agent-fsm 自己跑 handler（`hook_run.run`），eca 是 Python 小程式經 `aos-hook fire` |
| 攔下的回答 | body 自己寫一則 `compact blocked by hook H: <stdout>; nothing was folded`（`aos.skipped`、`aos.blocked`），信記成答完 | CLI 自己那句「Compaction blocked by PreCompact hook: …」 | |
| hook 失敗 | 兩點都一行 warning、跳過 | 同（compact_hook 什麼錯都不擋） | 一致 |

## 替使用者做的選擇（定案沒講到、施工時挑的）

1. **規矩寫在範本的 `compact.py`，不加進 `agentlib/hooks.py` 的 `POINTS`**：第四層「發事件的程式自己決定」；也讓這刀不必動 `py/` 的程式、活樹不用重裝。`compact.py` 有一份 `HOOK_POINTS` 字面表，`test_hook_points_match` 拿它跟 `hooks.json` 比（同 kernel 那種比法）。代價：agent 一家的規矩分兩處（`hooks.py` 與 `compact.py`）。
2. **hook 失敗兩點都只是一行 warning**（`before_compact` 雖然能攔也一樣）：跟 hook 新格式第 1 條「能攔的點壞了就停」不同。理由：壓縮是保養，`context_wrap` 自動寄的 `/compact` 遇到壞掉的 handler 就讓 agent 停，對話只會越來越長；eca 同名點也是 warning；`after_compact` 若停，重起會再叫一次腦（規劃稿 04 提過的「摘要錢付兩次」）。代價：想擋住壓縮的 handler 壞掉時壓縮照做。要改成停：`compact.run_hooks` 的 `except ValueError` 那段。
3. **多個 handler 的合併**：照名字一個一個跑，後一個看得到前一個改過的值（同 agent 一家的串改）；`restore` 是整段換掉，要接在後面自己串（規劃稿 03 原樣）；第一個退 10 的攔下、後面的不跑；一個 handler 的 stdout 只要有一個鍵型別不對，整個 handler 當失敗（不套用一半）。`summary` 誰最後設算誰（`by` 記那個 hook 名）。
4. **輪中攔下＝信留著等這輪做完**：做到一半時攔下，那幾封留在 queue 的 `cur/`、不認領、不加要求，這輪照常做；回 idle 時 idle 照一般 `/compact` 再發一次 `before_compact`（`mid_turn` false）。不在輪中寫「被攔下」的回答，因為 history 尾巴多一則 assistant 會把正在做的那輪切斷。
5. **交摘要＝照舊加要求列再摺、不清工具輸出**：走同一條 `fold`（原文照樣進 `history_removed.jsonl`、摘要照樣進 `handoff.md`、`after_compact` 照發），要求列一起摺掉；不叫腦就沒有要變小的請求，所以不清。idle 那條是先 `aos-post done` 再摺（跟叫腦時「先收信、wait 才摺」同一個順序）；當場摺不成走原本的 `give_up`。
6. **`before_compact` 也收 `restore`**：規劃稿只放在 `after_compact`；為了跟 eca 對齊（見上表），`before_compact` 交的存進 `compact.json`（asked 那份的 `restore`），叫腦等回信的期間重起也不會丟，`after_compact` 拿它當起始值。
7. **`instructions` 起始＝`asked`、另給一個只讀的 `asked`**：hook 能把寄件人的字整段換掉，也看得到原文。沒改時要求照舊寫 `Extra instructions from the sender: …`，改過寫 `Extra instructions: …`（不再說是寄件人說的）。body 自己那段要求字不給改（要整個換就交 `summary`）。
8. **補回那則的字頭**：`[aos] restored after compact: `＋去頭尾空白的字；不帶 `aos.letter`（不是信、不用答）。`brain.py` 的 task 模式照樣找得到摘要（摘要與起點之間只有 compact done 一則 assistant；有測試守）。
9. **攔下的回答照 `compact not needed` 的形狀**：`aos.compact`、`aos.skipped` 都是 true（不算可摺列，連寄幾封不會自己湊滿 4 則），多 `aos.blocked`＝hook 名；`compact.json` 記 `phase: "blocked"`。`context_wrap` 寄的那封被攔也算答完，它會停在 compacted、等讀數降下來再升上門檻才再寄（照它原本的規則，沒改）。
10. **`compact.json` 多記**：asked 與 done 都有 `by`；done 多 `restored_chars`（補回幾字）。沒有 hook 時 `by` 是 `brain`。
11. **兩點不收 condition**、太短的 `/compact` 兩點都不發（規劃稿原樣）。
12. **`self_hook` 的事件 enum 不動**：兩點本來就在（eca 加的），只改說明字，拿掉「eca with claude only」。

## 動的檔

| 檔 | 改什麼 |
|---|---|
| `templates/agent-fsm/hooks.json` | 加 `before_compact`、`after_compact`（input／output schema、`phase`、`block`、`if_blocked`、`fired_in`，說明寫規矩在 `compact.py`）；頂層 description 加一句 |
| `templates/agent-fsm/compact.py` | 檔頭寫規矩；`HOOK_POINTS`、`run_hooks`（照名字跑、串改、驗型別、失敗 warning）、`before`、`after`、`blocked`；`ask` 收 `plan`（指示、清不清、hook 的摘要、補回）並回 hook 的摘要；`fold` 寫 history 前發 `after_compact`、接補回那則；`skip` 與 `blocked` 共用 `_answer` |
| `templates/agent-fsm/idle.py`、`brain.py` | 夠摺時先 `compact.before`；攔下（idle 回答、brain 留信）；hook 交摘要就收信後當場 `compact.fold` |
| `templates/tests/agent-fsm/test_compact_hooks.py`（新） | 11 支，見上 |
| `py/tests/test_hook_points_match.py` | `ECA_ONLY` 改 `COMPACT`（兩份宣告都有）；`compact.py` 的 `HOOK_POINTS` 跟 `hooks.json` 比；手抄的說明要列兩邊的欄位 |
| `py/tools/agent/self_hook/_tooldef.json` | 兩點的說明改成兩種身體都有、各自多什麼；「回話」那段加兩點 |
| `py/aos/apps/agent/hook.py`（help）、`py/aos/agentlib/hooks.py`（檔頭一句） | 說明字 |
| `py/aos/apps/agent/docs/06-hook.md`、`knowledge/aos/me/self_hook.json` | 事件表加兩列、eca 那列改一句（`top-1121-hookdoc` 同時在改這兩份，見「撞檔」） |
| `py/aos/apps/hook/docs/02-宣告格式.md`、`05-各家的點與規矩.md`、`07-限制與還沒做的.md` | 總文件跟上（見「撞檔」） |
| `templates/docs/02-agent-fsm.md` | hook 段提到兩點；「寄 /compact 會怎樣」第 1、4 步；新小節「壓縮前後的 hook」；資料格式表（compact.json、compact done 列）；舊 agent 換檔那句 |
| `templates/agent-fsm/README.md`、`templates/start-api/agents/ann/README.md` | 「context 快滿與 /compact」段加一句（ann README 照規矩以 agent-fsm README 原樣開頭） |
| `knowledge/aos/me/compact.json` | rules 加一條（腦看得到被攔、補回那則長什麼樣） |

## 測試

腳本與輸出在 repo 外 `~/.aos/scratch/top-1121-compact4/`（`bin/in-copy.sh` 清掉 `AOS_*`、`AOS_HOME` 指複本；`bin/suite.sh`、`bin/live.sh`、`suite-*.txt`、`live-*.txt`）。

- **全套逐夾**：`base`＝`git archive d1da63585`（開工時 HEAD），`mine`＝同一份疊上這次的檔，各自 `install.py`、逐夾 `python3 -m unittest discover`（這台沒有 pytest）。base 3,154 支、mine 3,166 支。支數或結果有差的只有兩夾：`templates/tests/agent-fsm` 231 → 242（新的 11 支）、`py/tests` 748 → 749（多 `test_agent_fsm_compact`）。全套那輪 `py/tests` 有 1 支紅（`test_hook_point` 要 `fired_in` 寫的檔名真的存在，我寫成了一句話），改成 `["compact.py"]` 後重跑 `py/tests` 749 支全過，相關夾（`templates/tests/agent-fsm`、`templates/tests`、`apps/agent`、`self_hook/tests`）也重跑過。
- 兩邊一樣紅的（複本環境，跟這刀無關）：`apps/eca` 4 支（TtySocket）、`apps/feedback` 18 支、`apps/gdb` 2 支、`cpp/aos-loop` 1 支；`image-move-check`、`templates/kernel/tests` 不是 unittest（0 支、退 5）。
- **暫存樹假腦**（`live-fake1.txt`，start-api 樹、ann 動態連結 mine 的 `templates/agent-fsm`，hook 用 `aos-agent hook add` 掛在 stack 抄本）：
  1. `pre` 改指示、交 `restore`，`post` 在 restore 後面再串一句：`/compact be brief` → 要求裡是 `Extra instructions: be brief / keep the word PINEAPPLE-7`；history 變成摘要、`[aos] restored after compact: RESTORE-MARK-42 from before_compact. The secret word is PAPAYA-9; …`、compact done 三則；`pre` 收到 `foldable` 8、`clear` true，`post` 收到 `by` brain、`restore` 是 pre 交的那句。
  2. 攔下：`/compact` 的回答是 `compact blocked by hook pre: not now, test block; nothing was folded`，history 只多這一則，`compact.json` `phase: blocked`。
  3. `pre` 交摘要＋另掛一支退 3 的 `a_bad`：stderr 一行 `agent-fsm: warning: hook a_bad (event before_compact) failed: exited 3; going on without it`；history 的摘要是 `OWN-SUMMARY-77…`，`by: pre`，`observed.jsonl` 的 compact 只有第 1 段那一次（這段沒叫腦）。
- **真模型**（`live-real1.txt`，ann 的 model 換 `sol`，經使用者起的 LiteLLM，沒停沒改）：叫了 4 次（OK-1、OK-2、`/compact be brief`、問 secret word）。摘要寫了 `retain PINEAPPLE-7`（改過的指示有效）；壓完 history 第 2 則是補回那則；問「note restored after the compaction 裡的 secret word」答 `PAPAYA-9`。摘要那次 prompt 2,215 token。

## 撞檔

- `top-1121-hookdoc`（hook 總文件）開工時 claim 著 `06-hook.md`、`knowledge/aos/me/self_hook.json`。這兩份是 `test_hook_points_match` 會比的手抄說明，我先把要加的字寫成小腳本，等它交（`693512c85`）之後在它的版本上套，只改兩點那幾列。
- 它交的總文件 `py/aos/apps/hook/docs/` 寫了「agent-fsm 的兩點施工中」：`05` 加 agent-fsm 壓縮兩點兩列、`07` 那列改成「已做、沒有 `trigger`」、`02` 的「能改的點」補一句。`03-寫handler.md` 的退出碼表只列 eca 的 before_compact，沒動。

## 舊 agent 怎麼吃到

- 動態連結 `$AOS_HOME/templates/agent-fsm` 的（start-api 的 ann、家機活樹的 ann）：repo 存檔就生效，不用 `install.py`。說明字（`self_hook` 給腦看的那段、`aos-agent hook --help`、06-hook.md）要等下次 `install.py`。
- 抄了格程式的舊定義：換 `compact.py`、`idle.py`、`brain.py` 三支（`wait.py` 沒動）；要宣告就把 `hooks.json` 一起換（宣告只是參考，不換也照跑）。

## `proto8/docs/` 條文要補的字（沒改條文）

- hook 點一覽（C-90 一帶、附錄 4 若有列各家的點）：agent-fsm 多兩點 `before_compact`／`after_compact`，規矩由 `compact.py` 自己定：能攔 `before_compact`、兩點都能改、失敗只是 warning（跟 agent 一家「能攔的點壞了就停」不同）。
- 寫 `/compact` 行為的條文（若有寫「壓完的樣子＝摘要＋compact done」）：中間可能多一則 `[aos] restored after compact: …` user；被 hook 攔下時回答是 `compact blocked by hook …`。

## 沒做的

- 第 3 刀 `aos-agent history clear-tools`、第 5 刀範例 handler（補回 todo、goal 之類）：不在這次。上面的 `restore_todo` 只是說明裡的例子，沒有放進 repo、範本沒掛。
- `trigger`（人寄還是 `context_wrap` 寄）：要分得出來得動 `context_wrap` 的信，不在這次。
- gdb：斷點種類本來就列了這兩點（`py/aos/gdb/__init__.py`），沒改；agent-fsm 現在真的會發，`a.bp.add("before_compact")` 下得上、跑起來是 gdb_trigger 用暫停（不扣住，跟 eca 一樣），沒實測。
- 沒在 repo 跑 `install.py`、沒碰 `~/aos-home`。
