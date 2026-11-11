# 02 do_task：改成 save／load——start 留紀錄點、end 附總結把那段 history 換成總結（11-11，線 K 施工）

← [fork-and-do-task](README.md)｜前一版 [do-task-rename](../do-task-rename.md)

裁定照 [README](README.md)：「do_task改成save/load模式」「do_task有兩個子指令，一個是開始，一個是結束。結束的時候要附上總結」「eca 不給 do_task」「拿掉這個能力」（開一次性小幫手）。

## 施工結果

- **工具** `lib/agent/do_task/` 整個改寫（舊的開小幫手程式全拿掉）：stdin `{"op": "start"|"end"|"status", …}`。
  - `start {task?}`：叫我的那則 assistant＝紀錄點，記進工具小格 `tasks.json`（用 call id 認，不記行號）；任務裡再 start＝巢狀。
  - `end {summary}`（必給）：收最裡面那段。紀錄點那則與它後面連著的 tool 結果之後、到叫 end 的那則之前，自己的訊息換成一則 user `[aos] summary: lines A-B, N messages. Task "…" ended: 總結`；別人給的 user 訊息（信、`[aos] goal:` 提醒）不摺，照原順序接在總結後面。叫 end 那則與它的結果照常由 act 接在後面。
  - `status {}`：列開著的任務（外到內）、紀錄點現在第幾行。
- **怎麼改 history**：全走 `aos-agent history`（跟 self_history 同一套：`ctl who` 認人、`history ls --json` 讀、`summarize` 換、原文進 `history_removed.jsonl`）。有要留的訊息時先 `history set` 把它們挪到段尾，再 `summarize` 前面空出來的那一整段——所以總結那則的「N messages」＝真的摺掉的則數。沒新增改 history 的程式，也沒動 aos-agent。
- **只給 fsm**：只看 history 的形狀——最後一則 assistant 帶 `tool_calls`、後面只有 tool、有一個 call 還沒結果＝叫我的這一個。找不到＝`BodyUnsupported`（eca 的工具來回在 CLI 裡，history 沒有這種行；手動 aos-tools call 也一樣）。不看定義、不猜身體。
- **錯誤代號**（這支自己的）：`TaskMissing`（沒開始就 end）、`MarkerMissing`（紀錄點那則已不在 history）、`DepthExceeded`（巢狀超過 5 層；沿用舊名）、`BodyUnsupported`、`StateBad`（tasks.json 壞）；其餘照 self_history 接下層（C-52 例外 ⑥ 照用）。
- **假腦** `lib/base/llm_fake` 加 `when`：劇本項帶 `"when": "字"`＝最後一則含那個字就回它、比按順序的先看（摺完 assistant 則數會倒退，按順序的劇本會重播）。沒帶 when 的劇本行為不變。
- **知識節點**搬到 `aos/me/do_task.json`（`aos/me.json#/do_task`；它改的是自己的 history，跟 self_history 同一區），舊 `aos/agents/do_task.json` 刪掉。
- **舊東西清掉**：`AOS_DO_TASK_FROM`／`AOS_DO_TASK_DEPTH`（cli_session 的 MCP_ENV、defs 的 refs、沙箱例子、world 節點、aos-agent README）；舊測試 `test_do_task_own_def.py` 刪；`do_task/tests/test_observed_children.py` 裡測 `observed_children` 模組的兩格搬到 `lib/tests/test_observed_children.py`、看舊 do_task 程式碼的兩格刪；`test_batch3`、`measure/test_fake_agent` 原本借舊 do_task 生子驗子帳，改用 `subagent`（add／ask／rm）；沙箱例子 `do-task-boxed` 改指 subagent、改名 `subagent-boxed`（沒重測）；review_round 認「生子的工具」拿掉 do_task；NORMS／CONCEPTS 在「11-11 改名 do_task」那些註後面接 11-11 再註，C-42 續多一段附裁定的再註。

## history 摺疊前後（真 daemon＋假腦實跑，`test_do_task_fold`）

叫 end 那一刻（act 還沒接 end 的結果）：

```
1 user       Go.
2 assistant  -> do_task({"op": "start", "task": "Find the time"})
3 tool       Task started (depth 1) "Find the time". From here on, what you do is folded when you end it: ...
4 assistant  -> peek_now_time({})
5 tool       2026-11-11T06:55:05Z
6 assistant  -> peek_now_time({})
7 tool       2026-11-11T06:55:06Z
8 assistant  -> do_task({"op": "end", "summary": "It is today."})
```

答完之後：

```
1 user       Go.
2 assistant  -> do_task({"op": "start", "task": "Find the time"})
3 tool       Task started (depth 1) "Find the time". ...
4 user       [aos] summary: lines 4-7, 4 messages. Task "Find the time" ended: It is today.
5 assistant  -> do_task({"op": "end", "summary": "It is today."})
6 tool       Task ended (depth 1) "Find the time".
             4 messages of yours (lines 4-7) are now one summary at line 4; the originals are in .../procs/fold/history_removed.jsonl.
7 assistant  Done.
```

`history_removed.jsonl` 四行（`op: summarize`，line 4～7 原文）。任務中等信那條：腦在任務裡答「Waiting for bob.」停下 → 信「From bob: the answer is 42.」進來 → end；結果第 4 行總結（`line 4, 1 message`）、第 5 行那封信原樣、end 的結果多一行 `1 message from others during the task is kept after the summary.`。

## 代定（每條可翻案）

1. op 名 `start`／`end`／`status`；`task` 選填（一句話，進總結那行）、`summary` 必給。
2. 紀錄點＝叫 start 的那則 assistant 與它的 tool 結果，都留著；用 call id 找（中間有人改 history、行號變了也找得到）。
3. 摺的範圍到「叫 end 的那則」之前為止（那則與結果是這一步，self_history 也鎖它）。同一則裡先 start 後 end＝沒東西可摺、照樣關掉。
4. 留下的＝role user 且不以 `[aos] summary:` 開頭（信、goal 提醒、`[aos] new_mail` 通知）；自己摺過的總結、assistant、tool、讀不懂的行都摺。巢狀時裡面那段留下的信，外面那段也照留。
5. 留下的挪到總結後面（先 `history set` 挪、再 `summarize` 一次）；被 set 蓋掉的那幾則也在 removed 檔（op 是 `set`）。
6. 巢狀最多 5 層（`DepthExceeded`），end 一律收最裡面那段、不給 id。
7. 狀態在工具小格 `tasks.json`（寫才建）；act 斷了重跑同一個 call：start 不再開一次、end 照印上次結果；摺完還沒記上就斷了＝認得出那則總結就只關不再摺。
8. 紀錄點那則不在了（被 self_history 刪／摺）＝`MarkerMissing`、這段任務關掉、不摺（不關的話之後每次 end 都報錯，卡死）。
9. 只看 history 形狀判 fsm（`BodyUnsupported`），不讀定義。
10. 要 daemon（`aos-agent ctl who`），同 self_history／goal。
11. 總結那則 role `user`（同 self_history summarize 預設），內文 `Task "X" ended: 總結`；end 的結果不再印一次總結。
12. 不給 self_history 的 `keep`／`no_keep`：原文一律進預設的 `history_removed.jsonl`。
13. metainfo：`interrupt: unsafe`（摺到一半被殺會留半套，見沒驗到 3）、`timeout_ms` 120000（最多三次以上 aos-agent、每次 60 秒上限）。
14. goal：do_task 的 start／end 照現在的規則算「有進展」（goal 以外的工具）。這樣才對：摺完之後任務裡做事的那些 tool call 不見了，留下的 goal 提醒後面只剩 end 那則；不算的話做了事也被當沒進展。
15. todo：清單在 `tools/todo/`，end 不碰。
16. history summarize（人或 self_history）摺到紀錄點那則＝代定 8；只摺任務裡面的幾行＝沒影響（那則總結之後照摺）。

## 待裁（可直接貼進選項框）

1. **do_task 從哪包掛、eca 範本怎麼不掛？** ① 留在 gadgets 包，eca 範本 tools.json 寫 `"do_task": null` 關掉（推薦：改一格就好）② 新開一包（例 `task.json`）只有 agent-fsm 範本疊 ③ agent-fsm 範本 tools.json 直接登記、不進任何包。
2. **任務期間別人給的訊息放哪？** ① 挪到總結後面、照原順序（推薦，現況）② 留在原位置，總結切成好幾段 ③ 一起摺進總結。
3. **總結文字重複一份要不要省？** 現在 end 的 arguments 裡一份、總結那則一份。① 照留兩份（推薦：總結那則自己讀得懂）② 總結那則只留「Task X ended (summary in the next call)」。
4. **巢狀上限？** ① 5 層（推薦，現況）② 不設 ③ 不准巢狀（任務裡再 start＝錯）。
5. **do_task 算不算 goal 的進展？** ① 算（推薦，現況，理由見代定 14）② 不算（跟叫 goal 一樣排除）。

## 測試

- `lib/agent/do_task/tests/test_do_task.py` 15 格（假 aos-agent，history 那半是真的 `aos_agent.history`）：開始摺回紀錄點＋總結、原文留檔；status（不建小格）；沒開始就結束；總結必給、多給鍵；同一個 start 重跑；同一個 end 重跑；摺完沒記上不再摺；巢狀；上限；期間的信與 goal 提醒留下、自己的舊總結照摺；重起後紀錄點還在；紀錄點不見；沒東西可摺；eca 形狀；下層錯照接——全綠。
- `templates/tests/agent-fsm/test_do_task_fold.py` 4 格（真 aos-daemon＋真 aos-llm-kernel＋假腦劇本，約 10 秒）：摺疊、巢狀（裡面那段的總結也摺進外面那段）、任務中停下等信（信沒被摺）、`ctl stop`／`ctl start` 之後 status 看得到任務、end 照摺——全綠。
- 跟著改的：`test_batch3` 1、`measure/test_fake_agent` 1（think 數 5→7、token 35→49：父多了 subagent 三步）、`defs` 15、`review_round/test_suggestions` 3、`lib/tests` 34（含搬來的 observed_children 2）、`lib/agent/tests` 21——全綠。順跑沒動到的：self_history 6、aos-agent `test_history` 10、templates `test_goal` 9、`test_integration` 1、llm-kernel `test_ledger` 4、aos-llm `test_full` 6（後兩支用 llm_fake）——全綠。
- `knowledge_check` 的 `test_factory_tree` 紅：3 個是 do_task 的（`aos/packs.json#/gadgets` 與 `aos/agents/_index.json` 還指舊節點——這兩檔歸隊長改），4 個是 fork 那邊還沒掛上的節點。

## 沒驗到

1. 真腦（會不會照著 start／end 用、總結寫得夠不夠）。
2. eca 體真的叫到：只在單元測試餵 eca 形狀的 history；真 claude／codex 經 aos-mcp 叫沒跑（範本還掛著，見待裁 1）。
3. 摺到一半被殺（`history set` 挪完、`summarize` 前）：留下的那幾則會重複一次；end 那則在 act 裡被殺、重跑的情況只在單元測試模擬。
4. 沙箱例子 `subagent-boxed` 沒重測（舊的 do-task-boxed 11-06 測過）。
5. `brain.py --history task` 模式：總結之後的 user 訊息會變成「這題的開頭」，沒試。

## 要重建什麼

- 舊 stack 的 `tools/do_task/`（舊小幫手的 `children/<子名>/state`、`observed/<子名>/` 帳）新版不讀，留著無害；要清手刪。表上還留著的 `t-…` 小幫手（`keep: true` 或失敗留下的）也要手動 `aos-agent ctl rm --purge`。
- 登記檔或覆蓋層寫了 `env.AOS_DO_TASK_FROM`、`ctl add --envs AOS_DO_TASK_DEPTH=…` 的：沒作用了，刪掉就好。
- tooldef 快取（例 `~/.cache/aos-mcp-aos/tools.json`）要重刷才看得到新參數。
- 試驗場的劇本假腦 `fake-demo-today` 叫 `do_task {"goal", "model"}`＝現在會 `ArgumentsBad op is required`，劇本要改（句子寫在回報）。
- 新檔 `tools/do_task/tasks.json`：新的，不用重建。

## 11-11 稍後使用者裁定（do-2：任務期間別人送進來的訊息）

使用者自己寫的：「可選。預設清掉。」——翻掉上面待裁 2 的推薦 ①（挪到總結後面）與代定 4、5 的「別人的照留」。另一句：goal 那邊改成只看 history 判進展，「兩者不要耦合太深」——do_task 不通知 goal，這邊沒為 goal 加任何東西（代定 14 的「算進展」由 goal 那邊自己看 history 決定）。

- **預設**：end 時紀錄點之後、叫 end 之前的訊息**全部**摺進那則總結，連別人的 user 訊息（信、`[aos] goal:` 提醒、`[aos] new_mail` 通知）一起；原文照舊進 `history_removed.jsonl`（只有 `summarize` 一筆、沒有 `set`）。總結那則的「N messages」＝連別人的一起算。end 的結果多一行 `K of them came from others during the task (letters, reminders) and were folded too; end with "keep_others": true to keep such messages after the summary.`。
- **選項**：end 的 `keep_others`（boolean，預設 false）。true＝照舊：別人的不摺，先 `history set` 挪到總結後面、照原順序（就是上面施工結果那套），結果那行 `K messages from others during the task are kept after the summary.`。不是 boolean＝`ArgumentsBad keep_others must be boolean`（tool_io 照 tooldef 驗）；start 給它＝`ArgumentsBad op start does not take keep_others`。
- **結果行改字**：`N messages of yours (lines A-B) …` 改成 `N messages (lines A-B) …`（預設摺的不只自己的）。

代定（可翻案）：

1. **放 end、不放 start**：要不要留，看的是任務期間實際進來了什麼，只有 end 那一刻知道；總結也是 end 才寫，預設摺掉時腦該把信裡要的事實寫進總結（tooldef 與知識節點都這樣叮嚀）。放 start 等於事先猜會不會有信。
2. **名字 `keep_others`**：說的是「別人的訊息留下」；不叫 `keep`，因為 self_history 的 `keep`／`no_keep` 是「原文留不留檔」，同名會混。
3. **型別 boolean**，不給＝false；沒有「只留信、不留 goal 提醒」這種細分（KISS，要再說）。
4. 自己摺過的 `[aos] summary:` 照舊一律摺（不算別人的）；巢狀時裡面那段 `keep_others` 留下的信，外面那段的 end 沒給 `keep_others` 就一起摺。
5. 重跑同一個 end（act 斷了）：預設那條摺完只剩一則總結、`done_before` 照認；`keep_others` 那條同原本。

改的檔：`lib/agent/do_task/_entry`（參數、摺的範圍、結果行、HELP）、`_tooldef.json`（description、`keep_others` 參數）、`README.md`、`knowledge/aos/me/do_task.json`（_description、rules）、`tests/test_do_task.py`、`templates/tests/agent-fsm/test_do_task_fold.py`。

測試：`lib/agent/do_task/tests` 16 格全綠（原「期間的信留下」拆成「預設一起摺」與「keep_others 留下」兩格，`test_summary_required` 加 `keep_others` 型別與 start 不收）；`test_do_task_fold` 5 格全綠（任務中等信拆成兩格：預設信一起摺、原文在 removed 檔；`mail_keep` 劇本 `keep_others: true` 信留著；停掉再起來那格的「Go on.」現在也一起摺）；`templates/tests/agent-fsm` 整夾 94 格全綠；`knowledge_check` tests 17 格、出廠庫 0 錯誤（44 提醒，`do_task.json` 兩格超 1024 位元組是原本就有的）。

要重建什麼：持久格式沒變（`tasks.json` 不動）；tooldef 快取要重刷才看得到 `keep_others`。

沒驗到：真腦會不會把信裡的事實寫進總結（預設摺掉後只剩總結那句）。
