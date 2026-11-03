# round4 補充：自我優化模式——節點掛上優化工具包、自己改自己（fable，2026-10-25）

← [round4.md](round4.md)（§ 5.3 動作表、§ 5.4 回滾、§ 6 蒸餾、§ 11 步驟 6 由本檔改寫）｜已做 [round4-impl-notes.md](round4-impl-notes.md)（步驟 1～3）｜工具契約 [lib/README](../../../lib/README.md)、P-41｜並行補充 [round4-data.md](round4-data.md)（資料拆格；本檔只引用它的 `templates.distilled.json`）｜先例 [self-improve 10-24](../../../thinking/2026-10-24-self-improve.md)（改進者＝另一個函數；「函數自己改自己」當時列為選項、沒做）

使用者 10-25（逐字）：「理想情況是，如果那格是agent節點，那麼在我們進行優化時，就是額外給他相關工具包，跟他說請優化一些東西，並給予一些先前的執行結果，然後他就會自動去做。 其實就算不是agent節點也可以」

一句話：**優化器不親自改節點**。它挑一棵子樹、寫一句任務、附先前結果，把節點叫起來（agent 節點＝同一個 loop 多掛一包工具、換一份優化模式的 system prompt；純程式節點＝臨時配一個腦當殼），讓節點在**整棵樹的拷貝**上自己改；改完由純程式查白名單與錨、搬回原樹，收不收照 § 5.4（verify → weigh → 回滾）。只寫規劃、不改程式；round4-data.md 不存在、略過。

---

## 1. 工具包 `optkit/`（放 `galtxt-a/optkit/`，任何節點都能掛）

一支工具＝一個資料夾 `optkit/<名>/{_entry, tool.json, _metainfo}`（lib 契約：stdin JSON、stdout 結果、錯＝stderr＋stdout 各一行 `名: 代號 原因` 退 1）。共用模組 `optkit/optkit_common.py`（同 lib/agent 的 agent_tool.py 做法：讀 `OPTKIT_*` 環境、白名單、路徑解析）。全部純程式、標準庫；**沒有 bash**（self-improve 決定 3）。

| 工具 | 輸入 → 輸出 | 寫哪 |
|---|---|---|
| `opt_describe` | `{}` → 自己的對外描述（`_metainfo` 解一層 `$ref`：ratings、stage、grad、rollup）＋ `hard.jsonl` 未處理筆數＋ `steps` 與 `decisions_left` | 只讀 |
| `opt_history` | `{"max_runs": 6}` → 先前執行結果：最近幾次小格的 `score.json`（每份 total、dims、lint 違規代號、評審 `reason`）、`grad.json.steps` 最近 3 筆、`opt_log.jsonl` 自己上次改了什麼 | 只讀（從 `OPTKIT_RUNS`＝訓練 stack 的 `epochs/*/runs`、`verify` 小格讀） |
| `opt_read` | `{"path"}` → 檔內容（上限同 lib/read）；路徑從**拷貝樹根**算 | 只讀；**拒讀** `data/bench/`、`train/`、`proto8/tests`（PathDenied） |
| `opt_edit` | `{"path", "edits[{old_text,new_text}]"}` → 換了幾處（同 lib/edit 語意） | 只准白名單（§ 1.1），違規 `WriteDenied` |
| `opt_write` | `{"path", "content"}` → bytes；只准**新檔**或白名單檔 | 同上 |
| `opt_extract` | `{"name", "description", "parameters", "code", "summary"}` → 在自己的 `tools/<name>/` 建 `tool.json`、`_entry`（+x，先 `py_compile`）、`_metainfo` 骨架（`kind program`、`deterministic true`、`author: "<子樹>@selfopt epoch N"`），並把 name 加進自己的 `stage.json.tools` | 自己的 `tools/<新名>/`、`stage.json#/tools`；同名已存在 `ToolExists` |
| `opt_try` | `{"question": "cls-ribbon.json", "drafts": 1}` → 在拷貝上跑根一題（`aos-exec --ws 暫存 <拷貝根>`），回 `answer.txt`、lint 的 `dims`／違規、評審分（`judge: false` 時 judge.py 照 `GALTXT_JUDGE=off` 寫空 judge.json、省腦） | 只寫暫存小格 |
| `opt_test` | `{}` → `proto8/tests/test_topdown_galtxt_a.py` 只跑跟自己有關的測試（`GALTXT_TREE=<拷貝根>`，測試檔讀這個環境變數決定 `G`；`OPTKIT_TESTS`＝子樹→測試名清單，人寫在 `optkit/tests.json`），回 `{counter_pass, counter_fail, failed: [名]}`，不回測試原始碼 | 只讀 |
| `opt_note` | `{"what", "why", "metainfo_suggest"?}` → 追加一行 `<子樹>/opt_log.jsonl {at, epoch, what, why, files, metainfo_suggest}` | 只寫這一檔 |

**M7**：節點**不能改自己的 `_metainfo` 本體**（宣告只有作者改）；想改宣告（新 `children`、`steps` 變了）寫 `opt_note.metainfo_suggest`，人看了再改。`opt_extract` 建的是**新**工具的 `_metainfo`（作者＝這次的腦，標 `author`），不違 M7。旁檔（`stage.json.tools`、`opt_log.jsonl`、`hard.jsonl`）照 round4 § 3.2 誰寫誰管：`stage.json.history` 仍只有 verify 寫。

### 1.1 權限邊界（程式查，不靠腦自律）

白名單＝**原樹**（不是拷貝）每棵子樹 `_metainfo.opt_writes`（作者宣告、相對子樹根）∩ 不在 `optkit/deny.json` 裡：

- `writer/_metainfo.opt_writes`: `["system.txt", "stage.json#/tools", "tools/*/", "compose.py", "../data/templates.distilled.json#append"]`（`#append`＝只准追加條目：既有鍵值 bytes 不變，程式比；人寫的 `templates.json` 進 deny，照 round4-data.md § 2.2）。
- `writer/tools/voice/_metainfo.opt_writes`: `["_entry", "tool.json#/description", "tool.json#/parameters/properties#append"]`（`required` 與既有 properties 不變＝介面不變）；`beat` 同。
- `optkit/deny.json`（人寫；永遠拒，優先於 opt_writes）：所有 `_metainfo`、`_entry`（**除了** `opt_extract` 新建的與 opt_writes 點名的工具自己的）、`fsm.json`、`loop.json`、`brain.py`、`act.py`、`data/dims.json`、`data/lint_switches.json`、`data/templates.json`、`data/bench/**`、`data/cast.json`、`data/styles.json`、`tools/lint/**`、`grader/**`、`train/**`、`optkit/**`、`plan/**`、`meta/**`、`human/**`、`ratings.json`、`grad.json`、`rollup.json`、`human.json`、`proto8/tests/**`。
- `#/指標` 寫法＝只准改 JSON 的那個位置（opt_edit 對 JSON 檔改完要 `json.loads` 得過、其他位置 bytes 不變）。

### 1.2 沙箱

1. 驅動程式 `optkit/run`（純程式，§ 3）把**整棵 galtxt-a 拷到** `stack:epochs/NNN/selfopt/<子樹>/tree/`（`cp -a`，捷徑照捷徑；排除 `.git`、`plan/`、`meta/`）——相對捷徑（`tools/lint → ../../tools/lint`）與 `compose.py` 的 `../data` 才都接得上；拷貝一次 ≈ 1 MB、< 1 s。
2. 節點在拷貝裡跑（cwd＝拷貝裡的子樹）；optkit 工具的 `OPTKIT_TREE`＝拷貝根、`OPTKIT_SUBTREE`＝子樹相對路徑、`OPTKIT_ALLOW`＝驅動程式**從原樹算好**的白名單 JSON（拷貝裡改 `_metainfo` 加寬白名單沒用）。
3. 做完 `optkit/accept`（純程式）：`diff -r` 原樹 vs 拷貝 → 每個變動檔過白名單（任一違規＝整筆拒、stderr `optkit: WriteDenied <檔>`、什麼都不搬）→ 錨檔 bytes 檢查（§ 5）→ 在拷貝上跑 `opt_test`（假腦、0 token；紅＝拒）→ 只搬白名單內變動檔回原樹、寫 `params/changed.json {"subtree", "action": "selfopt", "files", "from": "<拷貝>", "task"}`（§ 5.4 的通用回滾清單，回滾＝從 `params/` 拷回、新建的工具資料夾整個刪）。品質由**下一個 verify → weigh** 判（跟 extract／stage 同一條路）；accept 不跑驗證題（不重複付 token）。

---

## 2. 怎麼掛到節點上

| 節點 | 怎麼進優化模式 | 腦看到什麼 |
|---|---|---|
| agent 節點（`writer` 在 `agent`／`semi` 階） | 同一個 loop：`GALTXT_OPT=1 aos-exec --ws 小格/ws <拷貝>/writer`，題目 `ws/new/task.json`（§ 3 的任務物件）。`writer/tools/` **永久**放捷徑 `opt_* → ../../optkit/opt_*`；平時 `brain.py` 只列 `stage.tools`，optkit 不在裡面＝看不到（既有機制）；`GALTXT_OPT=1` 時 `brain.py` 把 `optkit/` 底下全部加進 ALLOWED、system 換讀 `system.opt.txt`（兩句：你在優化自己、規矩 § 1.1、做完純文字說改了什麼）。`act.py` 一字不改（工具名只認 `tools/` 底下有 `tool.json` 的）。`_entry` 不改（分流照 stage；`program` 階的 writer 走下一列）。 |
| 純程式節點（`writer/tools/voice`、`tools/lint`、`program` 階的 writer、compose 的模板） | `optkit/shell/`：agent-dan 範本一隻（`_entry`、`fsm.json`、`brain.py`、`act.py`、`system.txt`、`.env` luna-low、`tools/` 捷徑＝optkit 全部），`OPTKIT_TARGET`＝拷貝裡的那棵；`aos-exec --ws 小格/ws optkit/shell`，題目同上。殼不屬於任何子樹、用完即丟，節點的 `_metainfo` 不變。 |

兩條路的 `task.json` 同形、回答同形（純文字報告＋ `opt_log.jsonl`）。假腦照固定劇本叫工具（§ 4）；真腦 `.env` 同寫手。

---

## 3. 外部優化器（`train/optimize`）的角色

變成「**派工＋驗收**」，不再親手改節點：

1. 挑子樹：照 § 5.2（根 rollup：還在 agent／semi、最吃腦、最不確定的先；平手看最差維度 `moved_by`）。
2. 寫任務句（純程式從模板組，`policy.json.task_templates`）：`「請優化 <子樹>：目標 <why：determinism|token|dims.<最差維度>>；現況 <opt_describe 摘要>；先前結果附在 history；規矩：只改白名單、介面不變、改完跑 opt_test。」`＋ `history`（＝`opt_history` 的輸出，inline 進 `task.json`，腦不用再叫一次）＋ `budget {max_calls: 12, max_tokens: 80000}`。
3. 叫 `optkit/run <子樹> --task task.json`（§ 1.2 的 1～2；預算到頂＝殺掉 loop、`BudgetSpent`、什麼都不搬）。
4. `optkit/accept`（§ 1.2 的 3）→ 搬回＋`changed.json`；下一個 verify → diff → weigh → 收或回滾（§ 5.4 不變）；`grad.json.steps[].action = "selfopt"`，`by` 記 `writer@selfopt` 或 `shell@selfopt`。
5. `optimize/ratings.json` 多 `action:selfopt` 格（同 `action:extract` 形）；**連兩步 selfopt 被拒或回滾＝那棵退回外部動作**（下表），印 `optimize: SelfoptFallback <子樹>`。

§ 5.3 動作表怎麼分：

| 動作 | 誰做 | 理由 |
|---|---|---|
| `extract <工具>` | **節點自己**（`opt_extract`；工具程式由腦寫） | 使用者 7：「agent 會把一些功能或環節做成工具」——本來就該是節點自己抽。人寫好的 beat／voice 留著當 fallback（selfopt 兩次失敗才開） |
| `distill` | **節點自己**（agent 階讀 `hard.jsonl` → `opt_try` 示範 → `opt_write ../data/templates.distilled.json#append`） | 老師本來就是寫手自己的 agent 階；held-out 的 detail 由 `#append` 檢查拒絕（`set.json.verify` 的 detail 進 deny） |
| 改 `system.txt`、改自己的 `compose.py`、改工具 `_entry` | 節點自己 | 外部優化器沒有這些動作（改程式要腦） |
| `stage program`、`switch`、`hints` | **外部**（不變） | 一個 key 的翻轉、0 token；交給腦只會多花錢 |

---

## 4. 示範（各一次；題目、預期改動、怎麼量、假腦劇本）

| | agent 節點：`writer`（semi 階） | 純程式節點：`writer/tools/voice` |
|---|---|---|
| 任務 | 「收尾旁白還是腦在想（`decisions_left` 含收尾旁白）；請把它做成工具 `close`，介面 stdin `{hint}` → 一行旁白，候選從 `data/templates.json.generic.close` 拿；然後 opt_test」 | 「同題三份口癖都是『哼』（`opt_history`：`多樣性` 0.31、三份句首相同）；請讓口癖照 `idx` 輪替（加選填參數 `idx`，既有呼叫不帶它時行為不變）；然後 opt_test」 |
| 預期改動 | 新 `writer/tools/close/{_entry,tool.json,_metainfo}`；`stage.json.tools` 多 `close`；`opt_log.jsonl` 一行；`system.txt` 可能多一句「有 close 工具時收尾交給它」 | `voice/_entry` 改口癖那三行＋ `tool.json.parameters.properties.idx`；`opt_log.jsonl` 一行 |
| 怎麼量 | 下一個 verify：`determinism` 升（收尾那段固定）、`tools_share` 0.5 → `stage program` 成為候選；`dims.文筆`／`承接` 掉 ≤ `min_loss`；Q16 錨不動（fill 沒旁白） | 同題三份（`Q16-fixed`）`dims.一致` 仍 1.0（同 idx 同輸出）、scene 題 `多樣性` ↑、`語域` 不掉；測試 6（工具契約）綠 |
| 假腦劇本（`GALTXT_OPT=1` 時 `fake()`／殼的 `fake()` 照序） | `opt_describe` → `opt_history` → `opt_extract`（name close、code 是假腦內建的 12 行查表程式）→ `opt_test` → `opt_note` → 交稿「抽了 close」 | `opt_describe` → `opt_read _entry` → `opt_edit`（old_text＝「口癖一個都沒出現」那段、new_text 內建）→ `opt_edit tool.json`（加 idx）→ `opt_test` → `opt_note` → 交稿 |
| 真腦估 | 7 次腦 × ≈ 5k（history 重送）≈ 35k | 6 次 × ≈ 4k ≈ 25k |

假腦也要演**壞劇本**（測試用，`GALTXT_FAKE_OPT=cheat|break`）：`cheat`＝`opt_edit ../data/dims.json`（→ WriteDenied）與 `opt_write proto8/tests/...`（→ PathDenied）；`break`＝把 `voice/_entry` 改成語法錯（→ `opt_test` 紅 → accept 拒、原樹 bytes 不變）。

---

## 5. 防作弊與改壞自己（全部純程式、在 `accept` 與工具入口）

1. **改動白名單**（§ 1.1）：變動檔逐一比；白名單從原樹讀。
2. **尺與測試 bytes 不變**：`data/dims.json`、`lint_switches.json`、`tools/lint/**`、`grader/**`、`train/weigh/rules.json`、`train/**`、`data/bench/**`、所有 `_metainfo`／`fsm.json`／既有 `_entry`：拷貝 vs 原樹 `sha256` 相同，否則拒。`proto8/tests` 不在拷貝裡、工具路徑解析出不了拷貝根（realpath，捷徑解開後仍須在內）＝碰不到。
3. **錨只能掉不能升**：accept 後下一個 verify 的 `weigh.rules.reject_if` 已有「護欄掉、Q16 `guard_hit` 變沒中＝回滾」（§ 5.6）；selfopt 那步再加一條硬規則：`bigram_overlap` 升超過 +0.3（一步內）＝可疑（模板背到正解）→ 不接受、stderr `AnchorSuspicious`——正解在 `data/bench/` 節點讀不到，但腦可能從 corpus 記憶背出來。
4. **介面不變**：`tool.json.parameters.required` 與既有 properties bytes 不變；`opt_extract` 的新工具 `py_compile` 過、對空 stdin 退 0 或 1 都要印一行（契約規則 3）。
5. **回滾**：`changed.json` 通用清單（§ 5.4）；新建資料夾記 `created: [...]`，回滾時 rmtree（只准刪 `changed.json` 列出的、且在原樹子樹的 `tools/` 底下——程式 assert）。
6. **預算**：`optkit/run` 數 `history.jsonl` 的 assistant 則數與 `usage.jsonl` token；到頂殺 loop（P-36：先 TERM 再 KILL）、不搬。
7. **震盪**：`opt_log.jsonl` 帶 `files` 的 sha256；同子樹連兩次 selfopt 改回上一次的內容＝`same_as`、第三次不派（§ 3 的 fallback）。
8. **節點跑起來偷看**：`opt_try` 跑的是拷貝裡的程式，程式本身能讀任何絕對路徑（self-improve 挖過的邊緣）；這圈只擋工具層，不上 bwrap——寫進 § 7 風險，實跑看腦有沒有這麼做（`opt_log` 與 diff 裡出現 `bench` 字樣就印警告）。

---

## 6. 插進 § 11 哪一步、測試、預算

**改寫步驟 6**（原「優化器照樹走＋distill」）為兩半：6a `optkit/`（八支工具＋`shell/`＋`run`／`accept`＋`deny.json`／`tests.json`、writer 的捷徑與 `system.opt.txt`、`brain.py` 的 `GALTXT_OPT`、`judge.py` 的 `GALTXT_JUDGE=off`、測試檔讀 `GALTXT_TREE`、各子樹 `_metainfo.opt_writes`）；6b 優化器照樹走（§ 5.2 不變）＋ `selfopt` 動作＋ fallback 表；`distill` 不再另寫 `train/distill.py`。步驟 4（rollup）、5（diff／weigh）先做完，6 才有 `opt_describe` 可讀的東西。整條假腦 `max_epochs 3` 的預期序列改成：epoch 0 `selfopt writer`（抽 close）→ 1 `selfopt writer`（抽 open 或蒸餾 poster）→ 2 `stage program`（外部）。

測試（`Round4T`，全假腦，編號 so-）：

- so-1 工具契約：optkit 八支各有三檔、`tool.json` 形狀、空 stdin 不炸、錯誤行 stderr＋stdout。
- so-2 白名單：`opt_edit data/dims.json` → `WriteDenied`；`opt_edit writer/system.txt` → 成功；`opt_write writer/tools/new/_entry` → 成功；`opt_read data/bench/Q16.json` → `PathDenied`；`../` 與捷徑出拷貝 → `PathBad`；拷貝裡把 `writer/_metainfo.opt_writes` 加寬 → 仍 `WriteDenied`（白名單從原樹算）。
- so-3 `#append`／`#/指標`：templates.distilled.json 追加 `by_detail.poster` 過、改 `generic.deny[0]` 拒、追加 held-out `lights` 拒；`stage.json#/tools` 改 `tools` 過、改 `stage` 拒。
- so-4 agent 示範：`writer` semi 階、`GALTXT_OPT=1` 跑拷貝 → history 的 tool_call 序列＝劇本、`tools/close/` 三檔在、`stage.json.tools` 含 close、`opt_log.jsonl` 一行；**原樹 bytes 不變**（accept 前）。平時（沒 `GALTXT_OPT`）history 裡沒有 `opt_*`、`tools` 陣列不含 optkit。
- so-5 程式示範：`optkit/shell` 對 `voice` → `_entry` 變、`tool.json.properties.idx` 在、`required` 不變；之後 `voice` stdin 不帶 idx 的輸出跟改前一樣（測試 6 照跑）。
- so-6 accept 搬回：so-4 之後 `accept` → 原樹多 `writer/tools/close/`、`changed.json.files`／`created` 對、尺檔 sha256 全同；`--dry-run` 不搬。
- so-7 作弊與改壞：`GALTXT_FAKE_OPT=cheat` → accept 拒、stderr `WriteDenied`、原樹不變；`break` → `opt_test` 紅 → 拒。
- so-8 回滾：接 so-6，`weigh/rules.json` 暫改成全拒 → verify 退 10、`tools/close/` 被刪、`stage.json.tools` 拷回、`grad.json.steps[-1].action == "selfopt"`、`accepted false`。
- so-9 預算：`budget.max_calls 2` → `BudgetSpent`、不搬。
- so-10 整條訓練（取代 § 10 測試 15 的序列）：`max_epochs 3` → `optimize/ratings.json` 有 `action:selfopt`、`action:stage`；根 `rollup.brain.nodes.writer == "program"`。
- so-11 fallback：so-7 連兩次 → 第三次 optimize 印 `SelfoptFallback`、動作變 `extract beat`（人寫的工具）。
- so-12 M7：訓練前後所有 `_metainfo`（新建的 `tools/close/_metainfo` 除外，它有 `author`）、`dims.json`、`rules.json`、測試檔 bytes 一樣。
- so-13 真腦（連不上 skip）：writer selfopt 一次跑通、`opt_log.jsonl` 有一行、accept 過或拒都要有一行可讀的理由；不斷言改了什麼。

預算：真腦一次 selfopt ≈ 25～40k token、6～8 次腦、≈ 60 s（§ 4）；4 epoch 裡 2 次 selfopt ≈ +70k，`budget.json.max_tokens` 650k 夠（§ 7.4 的 535k＋70k）。`optkit` 自己的上限 `{max_calls: 12, max_tokens: 80000, max_elapsed_ms: 300000}` 在 `optkit/budget.json`。

---

## 7. 預測（之後實測對照，寫進 `round4-measure.md` 一節「selfopt vs 外部」）

- **效果**：自我優化贏在「能改程式與 prompt」——外部優化器只會翻 key，抽工具得靠人先寫好；腦看得到自己的 history 與 `hard.jsonl`，抽出來的工具更貼它實際的寫法。預測 agent 示範一次成功率 ≈ 60%（真腦寫出能 `py_compile` 且契約對的工具），程式示範 ≈ 80%（改幾行）。外部優化器 0 token、100% 可預測、但動作表只有四種。
- **風險**：(a) 改壞自己——腦改 `_entry` 沒試跑就交（self-improve v002 的再現）；靠 `opt_test` 擋，但測試覆蓋不到的壞法會漏到 verify 才被回滾（多付一個 epoch）。(b) 作弊——白名單擋得住改尺改測試；擋不住「把 Q16 正解背進模板」（§ 5.3 只能事後聞出來）與「程式跑起來讀絕對路徑」。(c) 成本——每步多 25～40k，是外部動作的 ∞ 倍（它是 0）；半固化期本來就貴，selfopt 要限制在「外部做不到的動作」。(d) 自己評自己——節點讀的 `opt_history` 是評審腦給的分，尺本身沒固化，self-opt 等於對著腦的偏好優化；錨（§ 5.6）是唯一的外部訊號。結論先寫一半：**自我優化負責「改內容」、外部優化器負責「翻開關與驗收」、判斷器與錨負責「收不收」**——三者分工，不互相取代；實測看 (a)(b) 各發生幾次。
