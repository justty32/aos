# round4 實作筆記（偏離規劃、做到哪、坑）

← [round4.md](round4.md)｜一段一個步驟，追加；不改 round4.md。

## 步驟 1：評分細項（opus 實作者，2026-10-25）——程式做完，測試 1～4、7 還沒寫

做了：`data/dims.json`（照 § 1.4 原樣）、`data/lint_switches.json`（`contrast_order`／`reveal`／`ooc_mark`）、`data/hints.json`（`hints`＋`options` 兩組）、`styles.json.types.傲嬌` 加 `deny`／`yield`／`cover`／`reveal`／`ooc`、`cast.json` 柚葉精簡卡；`brief.py`（`brief.detail`、`brief.hints_fixed`、`rules.switches`、`rules.contrast`）；lint（`OocMark`、`dims.反差／洩底／語域`）；`grader/system.v2.txt`＋`system.txt` 捷徑（v1 改名 `system.v1.txt`）；假評審四行（`GALTXT_FAKE_GRADE` 可換回覆）；`judge.py` 四行解析（`scores`、`tier2`＝承接）；`pick.py` 照表加權 total＋`一致`；`write.py` 讀 `hints.json`、`hints_fixed`；假寫手 `GALTXT_FAKE_JITTER=1`。

偏離／解讀：
- 精簡卡的稱呼表（`calls_lead`／`called_by_lead`）**整張留著**，不是只留 rank 2——lint 擋越階要靠比本場高的那幾階；多一個 `short: "柚葉"`，給 lint 判「旁白有提到她」用。`catchphrase` 改成五個口癖串起來；markers 去掉「笨蛋」。
- `rules.contrast` 也帶 `cover`（§ 7.1 說四個表；lint 不用 cover，寫手工具會用）。
- `GALTXT_FAKE_JITTER` 的「第 n 份」用寫手小格的編號（`$AOS_STACK` 上一層 `runs/NNN`），不往題目塞 n（不想讓真腦看到）。同一個 root stack 跑多題時編號會往上加，仍然字面不同，公式驗得到。
- 假腦傲嬌 fill 第三份（留白）是 `KeywordMissing`＝total 0（不是 § 1.4 估的 3.0），`反差` 0（「也沒有」不是否認標記）。三份實得 ≈ 3.69／3.69／0。
- `pick.py` 對舊 `judge.json`（沒有 `scores`）把 `tier2` 當承接，其他兩項 null。
- 踩到的坑：pick 迴圈變數叫 `name` 蓋掉了題名 → 題目永遠搬不到 done、loop 一直重跑同一題（`test_route` 抓到）。已改名。

## 步驟 2：收窄題目與迴圈骨架——程式大半做完，round3 測試還沒改

做了：`plan/examples/cls-ribbon／poster／lights.json`（scene、`detail`）、`Q16-fixed.json`；`set.json`（scope、measure、writers 只剩 writer）、`budget.json`；`common.py` 加 `scope_check`、`gather`（照 score.json 裡有的維度彙總，不寫死名）、`run_cost`、`stage_of`、`brain`、`run_question(env=)`；`rate.py` 重寫（scope 守門、dims 照表、`determinism` 從 `verify.json.measure`、`cost`、`tags`、`grader/ratings.json` 的 `role:grader`＋`分辨力`）；`verify.py` 重寫（measure 題在 `epochs/NNN/measure/`、`by_question`、`measure.一致／dims_std`、`brain`、根 `ratings.json`、§ 2.3 那行 stdout）；`git rm human/samples.json`；新檔 `grader/ratings.json`、根 `ratings.json`（只有 source）。

偏離／解讀：
- `budget.json` 用 § 7.4 的數（`max_calls 250`、`max_tokens 650000`），不是 § 1.2 的 180／500000（§ 7.4 較後、較細）。
- `train/loop.json` `max` 用 17（不是 § 7.1 的 16）：4 個 epoch＝5 次 verify＋4×3 格＝17；既有測試斷言 `max == 4 × max_epochs + 1`。
- `brain.nodes` 在 rollup 出來前由 verify 自己收：set.json 的寫手＋`grader`＋`tools/lint`（`common.brain`）；步驟 4 改讀 rollup。
- 人評樣本挑法沿用 round3（§ 8.1 配對是步驟 7），只把 disagree 改成「反差 vs 像柚葉」、分組加題名（現在只剩一個寫手一個風格）。
- `verify` 的 delta／`action:route`／route 回滾整段照舊（步驟 5 才換成 diff／weigh／changed.json）。
- 根 `_metainfo`、`grader/_metainfo` 還沒加 `$ref` 行（打算步驟 4 一起加）；fsm.json 裡 brief／write／pick 的 `_metainfo.reads` 還沒補 `data:dims.json`、`data:hints.json`、`data:lint_switches.json`。

## 交接（30% 換手，停在步驟 2 中間）

現況：`test_topdown_galtxt_a.py` 28 個裡 5 個紅，都是**規劃預期要改的 round3 斷言**：
- `test_fake_skill_table`、`test_fill_q16`：dims 字面從 `{語域, 語意, 護欄}` 換成 profile 維度 → 改關係斷言（例：fill 第 3 份 `護欄 0`、`像柚葉 null`；scene 三份 `語域 0.5`、`反差 1.0`）。
- `test_rate`：餵了文靜的 score.json → 現在 scope 守門 StateBad。改成只餵傲嬌，另外寫測試 4（scope 改文靜 → StateBad）。
- `test_optimize`：set.json writers 只剩 writer，「傲嬌: writer → writer-sol」不會出現——測試在拷貝上把 `set.json.writers` 改回兩個再測（優化器步驟 6 才重寫）。
- `test_train_whole`：題目換了、route 不會變，`e1 > e0` 不成立 → 改關係（≥）、M7 changed 集合加根 `ratings.json`、`grader/ratings.json`、去掉 `data/route.json`／`writer-sol/ratings.json`；`max_epochs` 1 時 loop 序列不變。

還沒做：步驟 1 的測試 1～4、7（新 `Round4T`，每個要證明能變紅一次）；步驟 2 的 round3 測試改寫；整個步驟 3（`writer/tools/beat`、`voice`、`data/templates.json`（照 § 7.2 只放 `ribbon`，poster、lights 都不放）、`writer/compose.py`、`writer/stage.json`、`_entry` 改 python 分流、`brain.py` 只列 `stage.tools`＋假腦 semi 先叫 beat、`system.txt` 兩句、`_metainfo` 的 `steps`／`brain` `$ref`；測試 5、6、8）。

坑（給下一手）：
- § 7.1 說 `templates.json.by_detail` 有 ribbon、lights，§ 7.2 說 lights 是 held-out、templates 不放它的專屬句——兩處矛盾，我傾向 § 7.2。那 lights 在 program 階也會記難例，步驟 6 的 `distill` 要跳過驗證集的 detail，不然 held-out 被蒸進模板。
- 測試 5 說 program 階「`stack/writer/runs/` 不存在」，但 § 2.1 又說 `write.py` 一字不改（`fresh_cell` 一定會開 `runs/NNN`）。我的解讀：小格照開，裡面沒有 `history.jsonl`／`usage.jsonl`／`trace.jsonl`、`counter_calls` 0。
- `compose.py` 寫 `writer/hard.jsonl` 是寫在**樹裡**：測試一律在 `tree_copy` 上跑 program 階，不然會弄髒真的 G。
- Q16 正解隔離（`test_fill_q16` 掃整個 stack）：`templates.json` 不能放正解原句。
- 這個環境的 Bash 會擋「`cd` 後接多段 && 指令／heredoc 裡寫多個檔」這類組合；`cd X && python3 - <<EOF` 單段可以，寫檔改用 Write 工具。

## 步驟 2 收尾（opus 實作者，2026-10-25）——round3 測試改關係斷言、全綠

改的測試（`proto8/tests/test_topdown_galtxt_a.py`；程式行為一行沒動）：
- `test_fill_q16`：第 3 份（留白）改驗「dims 的 key＝`dims.json` 傲嬌 profile＋護欄」、`護欄 0`、`total 0`、評審量的維度與 fill 沒有的 `洩底` 都 `null`；前兩份 `洩底 null`、`total`＝加權手算（新 helper `yuzu_total`、`YUZU` 從 `data/dims.json` 讀，不寫死權重）。
- `test_fake_skill_table`：每份 key 照 profile、`護欄 1.0`／`語域 0.5`（NgMark）／`反差 1.0`、scene 每維都有值、`total`＝加權；writer-sol／`GALTXT_FAKE_WEAK` 兩段沒動。
- `test_rate`：只餵傲嬌（writer、writer-sol 各一格，驗證題故意放文靜＝rate 不收）；dims 用 profile 維度；新驗 `determinism null`（沒 verify.json）、`cost`（手放一個寫手小格：2 次 assistant、1000 token、500 ms）、`tags`、檔頂 `scope`、`grader/ratings.json role:grader` 的 `分辨力`（手算）與 `counter_samples`；`none`（2 份）改用第二個 stack 驗；原本混文靜的情形改成第三個 stack 驗 `StateBad`、評級 bytes 不變。
- `test_optimize`：只在拷貝上把 `set.json.writers` 改回 `["writer", "writer-sol"]`，其餘斷言不動（優化器步驟 6 才重寫）。
- `test_train_whole`：`e1 ≥ e0`＋`delta` 對得上；兩次 verify 的 `by_question`＝set.json 驗證題、`measure.question`、`brain.nodes`；writer `val` 照門檻對 `score_avg`、dims key 照 profile、`scope`；根 `ratings.json` 的 `score_avg`／`determinism`／`brain`＝最後一次 verify；樣本全在 scope（傲嬌、教室），而且訓練＋驗證四題每題都有一筆（取代「四個（寫手, 風格）格」）；M7 變動集合＝`{writer/ratings.json, grader/ratings.json, ratings.json, human/samples.json}`（route 沒換＝`data/route.json`、`train/optimize/ratings.json`、`writer-sol/ratings.json` 不動）。
- 新 `Round4T.test_scope_guard`（§ 10 測試 4）：對照組過；`scope.style` 改文靜 → `StateBad` 一行、writer／grader 評級 bytes 不變。

變紅過一次：暫時讓 `common.scope_check` 直接 return、`pick.py` 權重全當 1 → `test_fill_q16`、`test_fake_skill_table`、`test_rate`、`test_scope_guard` 四個紅；還原後綠。`test_optimize`／`test_train_whole` 改之前就是紅的（原斷言）。

順手補完：根 `_metainfo`、`grader/_metainfo` 加 `"ratings": {"$ref": "ratings.json"}`；`fsm.json` brief 的 reads 加 `data:lint_switches.json`、write 加 `data:hints.json`、pick 加 `data:dims.json`（各格只補自己真的讀的那張）。

結果：`test_topdown_galtxt_a.py` 29 個綠；`proto8/tests` 全套 544 個 OK（skip 2）。步驟 1 的測試 1～3、7 還沒寫（只補了 4）。

## 步驟 3：寫手三階（節點生命週期）＋步驟 1 欠的測試 1、2、3、7（實作者，2026-10-25）

做了：
- `writer/tools/beat/`、`writer/tools/voice/`（各 `_entry`＋`tool.json`＋`_metainfo`；`kind program`、`deterministic true`、`fs_needs ["tool_json"]`——`test_metainfo_consistent` 要 program 沒 fs_needs 的資料夾只有 `_entry`／`_metainfo`）。
  - beat：stdin `{deny, yield, cover}` → 一行「`<deny>。不過……<yield>，<cover>。`」（不含說話者；各段尾標點先拿掉）。槽缺＝**那一槽**換通用句（不是整句換），缺幾槽 stderr 幾行 `beat: SlotMissing <槽>（用通用句）`、退 0。
  - voice：stdin `{text, who?, calls?, tics?, ending?}`：`{calls}` 換稱呼 → 口癖一個都沒有就句首補 `tics[0]，` → 有 `ending` 插在最後「。」前 → 給 `who` 回「`who：「…」`」。text 缺＝通用句「哼，真是的。」＋stderr 一行、退 0。
- `data/templates.json`：`generic`＋`by_detail.ribbon`；**poster、lights 都不放**（照 § 7.2，同前手傾向）。偏離：槽除了 § 7.1 的 deny／yield／cover／open／close／reveal，多 `lead`、`lead2`（主角兩句；scene 要兩人對話）。字句自擬、不含 Q16 正解。
- `writer/compose.py`：不是逐字從 `brain.py.compose()` 搬，而是照 templates 重寫（brain.py 的 compose() 留給 agent／semi 階的假腦）。順序 beat → voice → lint；候選照 hint 在 `hints.json`（hints 或 options 任一組）的位置挑，同 hint 同輸出。fill 挑含 `must` 第 1／2 組詞的 deny／yield。scene 六行：open、lead、女角（beat→voice）、reveal、lead2、close。
  - 難例：brief 有 `detail` 而 `by_detail` 沒有 → `TemplateMissing`；**另加** `LintFailed`（專屬句沒過 lint 先退回 generic 再試，還沒過才記；答案照交）。沒 `detail` 的題（Q16）只用 generic、不算難例。去重鍵＝(question, why)，`flock` 住再查再寫（三份草稿同時跑也只一行）。
  - **lights（held-out）在 program 階也會記 TemplateMissing**——步驟 6 的 distill 要跳過 `set.json.verify` 題的 detail，不然 held-out 被蒸進模板（前手坑的再確認，實跑看到了）。
- `writer/stage.json`：`stage agent`、`tools ["lint"]`、`history []`、`since_epoch`／`why` null、`tools_share 0.17`（6 環節裡只有「自檢」有工具）、`decisions_left` 其餘五個。
- `writer/_entry` 改成 python（sh 讀不了 JSON）：`GALTXT_STAGE` 有設蓋過 `stage.json`；program → `python3 compose.py`，否則 `aos-loop loop.json`；stage 不是三值之一或 stage.json 壞 → `writer: StateBad`、退 1。
- `writer/brain.py`：有 `stage.json` 只列 `stage.tools`；**沒有＝全部**（writer-sol 的 brain.py 是捷徑過來的，它沒 stage.json，行為不變）。假腦：semi 且看得到 beat → 先叫 beat 一次（三槽取 `must` 第一個詞），再 lint，再交稿；beat 回的句子**不拿來用**（只示範腦叫工具；草稿跟 agent 階一樣）。
- `system.txt` 加兩句（beat 組節拍、voice 補口癖句尾稱呼；writer-sol 共用這份，句子是「有…工具時」所以無害）。
- `writer/_metainfo`：`steps`、`"brain": {"$ref": "stage.json"}`、`children`（beat、voice、lint 捷徑）、reads 加 `data:templates.json`／`data:hints.json`、writes 加 `cell:beat/`、`cell:voice/`、`tree:writer/hard.jsonl`。`kind` 留 `agent`（目前階）。`grad`／`rollup` 的 `$ref` 沒加（檔還不存在，步驟 4／5）。

測試 5 的解讀（同前手）：program 階 `write.py` 照開小格 `runs/NNN/`，小格裡沒有 `history.jsonl`／`usage.jsonl`／`trace.jsonl`（→ counter_calls 0）；compose 經 aos-exec 叫工具，所以有空的 `stack/beat|voice|lint/` 資料夾。

順手修的 bug（步驟 1）：`GALTXT_FAKE_JITTER` 原本在第 n 份句尾前加 n 個「…」——「一致」量的是二元組**集合**，n ≥ 2 多出來的「……」本來就有，三份集合相同、一致仍 1.0（測試 7 一寫就紅）。改成「…」＋第 n 個天干。

新測試（`Round4T`，§ 10 編號）：`test_dims_table`（1）、`test_lint_contrast`（2）、`test_judge_four_lines`（3；另驗 ReplyBad 時沒有 out）、`test_writer_stages`（5；多跑一組 semi＋`["lint"]` 證明 tools 過濾、`GALTXT_STAGE=program` 蓋過、`GALTXT_STAGE=nope` → StateBad）、`test_tool_contract`（6）、`test_determinism`（7）、`test_hard_cases`（8；另驗 ribbon 用了專屬句且不記、真樹沒有 hard.jsonl）。`Round3T.test_tree` 加 `writer/stage.json`（stage 三值之一、tools ⊆ `writer/tools/`）、`compose.py`、`_metainfo.brain`。

變紅過一次（暫改 → 紅 → 還原 → 綠，腳本一次跑完）：dims.json 反差 `by` 改 `tools/nolint` → 1 紅；lint 反差不看順序 → 2 紅；judge 不檢「承接」→ 3 紅；brain.py 不照 `stage.tools` 過濾、`_entry` 不認 program、假腦 semi 不叫 beat → 5 各紅；beat 三槽順序對調、voice 不補口癖 → 6 各紅；compose 用小格編號當 idx → 7 紅；hard.jsonl 不去重 → 8 紅；stage.json tools 多一個不存在的 → test_tree 紅。

環境：這個 worktree 沒建 impls，`proto8/impls/*/bin/` 從主 repo 拷來（gitignore 的，不進 commit）。

結果：`test_topdown_galtxt_a.py` 36 個綠；`proto8/tests` 全套 560 個 OK（skip 2）。

下一步（步驟 4）：`meta/rollup/`、各子樹初始旁檔與 `$ref`（writer 的 `grad`／`rollup`，beat／voice 的 `grad`／`rollup`）、rate／verify 叫 `rollup_up`；測試 12、17、20、21。README 的樹、code map 還沒補 beat／voice／compose／templates（步驟 8 一起）。

## 步驟 4：rollup（實作者，2026-10-25）

做了：
- `meta/rollup/`（`_entry` python 標準庫＋`_metainfo` 照 § 9：`kind program`、`role dev`、`grow_level 3`、`fs_needs [mount]`、`callers 3`）。`rollup [--up] [--dry-run] [--json] <子樹>`；寫 `rollup.json`：`kind`／`role`、自己那格評級的 `val`／`score_avg`／`determinism`／`dims`、`stage`、`cost`（`per_run`；根那格有 `brain`＝`per_question`；`declared`；dev 標 `excluded_from_cost`）、`grad_total`（＋`grad_foreign`）、`children`、`brain`（`nodes`／`counter_on_brain`／`counter_program`）、`rolled_at`。錯 `RootMissing`／`MetainfoBad`／`RefBad`／`FlagUnknown`／`ArgumentsBad` 退 1、一份都不寫（`--up` 先驗每一層的 `_metainfo`＋`$ref`，再由下往上算、最後才落檔）。
- 初始旁檔（只有 `source`）：根 `rollup.json`；`writer/{grad,rollup}.json`；`grader/{grad,human,rollup}.json`＋`grader/stage.json`；`writer/tools/beat|voice/{grad,rollup}.json`；`tools/lint/{grad,rollup}.json`；`train/optimize/rollup.json`。`_metainfo` 的 `$ref` 行照 § 3.2（根 `rollup`；writer 補 `grad`／`rollup`；grader 補 `brain`／`grad`／`human_ratings`／`rollup`；beat／voice／lint `grad`／`rollup`；optimize `rollup`）。其餘子樹不加（「rollup 跑過才加」）。
- `common.rollup_up(sub)`（`rollup --up`，stdout 照印）、`common.rollup_view(sub)`（`--dry-run --json`）；`rate.py` 寫完每個寫手評級 → `rollup_up(<寫手>)`、寫完 grader → `rollup_up("grader")`；`verify.py` 的 `brain.nodes` 改讀根 rollup（`rollup_view(".")`，不寫檔），寫完根 `ratings.json` → `rollup_up(".")`。`common.stage_of` 刪掉（規則搬進 rollup）。
- metatable（只做 rollup 要的最小部分）：資料夾列解一層 `$ref` 多 `ratings`（`{格: val}`）、`stage` 欄；彙總多 `counter_on_brain`／`counter_program`＋md 一行；`suggest.py` 本來是候選、但有旁檔的列改標 `N-4（原 X）`、動作「不縮」。
- 順手：`train/fsm.json` verify／rate 格的 `writes`、`train/_metainfo` 的 `writes` 補根 `ratings.json`、grader 評級、`rollup.json`；`meta/_metainfo` summary 加 rollup。

偏離／解讀：
- **直接子樹從資料夾找，不從 `_metainfo.children`**（大半 `_metainfo` 沒有 `children`；writer 那份是描述字串）。往下：沒 `_metainfo` 的資料夾一律穿過去、名字接成 `tools/lint`；往上（`--up`／找樹根）只穿過叫 `tools` 的容器（不然 galtxt-a 會往上穿 `topdown/`）。捷徑（含懸空的）列 `{"kind": "捷徑", "to"}`、不進去。
- **固化階的退路規則用 `kind` 不用 `resource`**（§ 3.3 寫「`resource` 含 llm＝agent」）：`train/` 是 `kind program` 但 resource 有 llm（它叫寫手），照 § 3.3 會被算成 agent。改成：有 `stage.json` 照它；`kind agent`＝agent；`kind data`（或沒 kind）＝不算節點；其餘＝program。
- **`brain.nodes` 是整棵樹的函數子樹**，不只「每題會叫到的」：現在根的 nodes＝writer、writer-sol（凍結，仍是 agent）、grader、tools/lint、idle、train（dev）＋攤平的 `writer/tools/beat|voice`；`counter_on_brain` 3（writer、writer-sol、grader）——§ 2.3 範例的 3 是 writer、grader、weigh，步驟 5 加 weigh 後會是 4。要不要把凍結的 writer-sol 拿掉，留給隊長／fable 判（拿掉要在 `_metainfo` 加個標記，這步沒做）。
- **epoch 0 的 verify 看不到 `writer/tools/*`**：verify 在 rate 之前，那時 writer 還沒有跑過的 rollup.json（只有 source＝當作沒有），根只看得到 writer 自己的 stage；rate 跑過 `--up writer` 之後 epoch 1 才攤平到孫子。照「只看直接子樹的 rollup」的規則就是這樣，沒補。
- `rollup.json` 只有 `source`（沒 `rolled_at`）＝當作沒跑過、退讀旁檔。`--up` 路上每層一律重寫（`rolled_at` 秒級；內容沒變時 bytes 可能一樣）；不在路上的子樹不碰。
- 評級格：`ratings.json.scope.style` 的 `style:<風格>`，沒有就唯一一格（grader 的 `role:grader` 沒 `val`＝不列）。
- `DeclaredOff` 只比 `per_run.llm_tokens` vs `_metainfo.llm_tokens.val`（根的 per_question 不比）。
- `grader/stage.json` 不是只有 source：給了 `stage agent`、`tools []`、`decisions_left`（承接／像柚葉／文筆／理由標籤）、`history []`——`brain` 的 `$ref` 指它，空的會讓 stage 退回 kind 判，等價但不直觀。
- N-4 照 § 9「加欄」的意思做成「改判準欄＋動作」（候選列留著、標不縮），沒另開一欄；md 表頭不變（SuggestT 照舊綠）。metatable 其餘（`role` 欄、`table-round4.md`）留步驟 8。

測試（`Round4T`；§ 10 編號）：
- `test_rollup`（12）：暫存三層樹（根 → mid（semi）→ `mid/tools/gc`、`mid/helper`；根 → uncle、notes（data））：中層 children 兩行、穿過 `tools/`；DeclaredOff 一行；根 nodes 有 `mid/tools/gc`、`mid/helper`、data 不算；孫子改評級＋stage 只重算根 → 根除 `rolled_at` 不變；`--up 孫子` → 三份變、叔叔不變；兩次除 `rolled_at` 全同；`--dry-run --json` 每層一行、不寫；懸空 `$ref` → `RefBad` 退 1、一份都不寫；`RootMissing`；純容器 → `MetainfoBad`；所有 `_metainfo` bytes 不變。（第一版只改孫子的評級，根的內容本來就不含孫子的 val、秒級 `rolled_at` 又同一秒 → 根 bytes 沒變、斷言錯；改成孫子也換 stage，根的 `nodes` 才會跟著變。）
- `test_rollup_portable`（20）：`cp -r writer/` 到別棵假根（捷徑懸空）＋手放 `context.tree galtxt-a` 的 grad → `--up` 退 0、stdout `foreign grad（context.tree galtxt-a）`、`children.writer.grad_total null`、`val`／`stage` 照列；在原樹裡不是 foreign。
- `test_m7`（17）：假腦訓練 `max_epochs 1`：所有 `_metainfo`、`fsm.json`、`loop.json`、`dims.json` bytes 不變；變的檔名 ⊆ {ratings, stage, grad, rollup, human}.json、`hard.jsonl`、`log.jsonl`、`templates.json`、`samples.json`、`route.json`、`policy.json`；根／writer／grader 的 `rollup.json` 有變、`writer/tools/beat`、`tools/lint`、`train/optimize` 的不變；根 rollup 的 brain＝根評級的 brain。§ 10 清單裡的 `weigh/rules.json` 步驟 5 才有，先不列。
- `test_metatable_sidecars`（21 的最小部分）：`--json` writer 列有 `ratings`、`stage`；idle 沒 stage；on_brain＋program＝資料夾函數節點數；md 有 on_brain 行；`--suggest` 小表沒旁檔＝`B-3`、放了 `rollup.json`＝`N-4（原 B-3）`／不縮。
- `Round3T.test_train_whole` 改：`brain.nodes` 斷言改成「含 writer／grader／tools/lint／writer-sol 且 on_brain 對得上」、epoch 0 沒有 `writer/tools/beat`、epoch 1 有且＝根 rollup 的 nodes；M7 變動集合加 `rollup.json`、`writer/rollup.json`、`grader/rollup.json`。

變紅過一次（腳本暫改 → 跑 → 還原）：rollup 不讀子樹的 rollup.json → 12 紅；不判 `context.tree` → 20 紅；rate 不叫 `rollup_up` → 17 紅；verify 的 nodes 清空 → `test_train_whole`、17 紅；suggest 不標 N-4、metatable 不讀 stage → 21 紅。

結果：`test_topdown_galtxt_a.py` 40 個綠；`proto8/tests` 全套 571 OK（skip 2）。

下一步（步驟 5）：`common.diff`、`train/weigh/`（建的時候補五個 `$ref`＋初始旁檔）、verify 寫 `grad.json`（`context.tree` 用樹根資料夾名，rollup 靠它判 foreign）、`rollup --up <被改那棵>`；M7 測試的凍結清單加 `weigh/rules.json`。


## 步驟 3b：設定拆成有 id 的格（照 round4-data.md；實作者，2026-10-25）

順序：fable 排在步驟 4 之前，實際在步驟 4（rollup）**之後**做。衝突只有一處：rollup／metatable 不看格層（round4-data § 6），所以 4 不用回頭改；data/ 的新子資料夾是 `kind data`、rollup 不算節點，`test_rollup`／`test_m7` 照綠。

做了（3b-α 資料與 brief）：
- `cells.py`（根下伴隨檔，標準庫）：`resolve(id) → (檔, pointer, 值)`、`load_ref`（解一層 `$ref`）、`expand("…*[旗標]")`、`kids`、`marker`、`must_groups`、`count_cells`、`ids`、**`touched(舊, 新, 前綴)`**；命令列 `cells.py get <id>｜ls [前綴]｜diff 舊.json 新.json 前綴`。id 規則照 § 2.1；別名 `tpl.`＝`templates.json`、`tpld.`＝`templates.distilled.json`；找不到 `data/<1>/<2>` 就退成 `data/<1>.json`（`styles.ng_marks`、`lint_switches.contrast_order` 這種 id 不用改檔也有）。
- 新格檔：`data/cast/yuzu.json`（31 格）、`data/style/tsun.json`（35）、`data/place/classroom.json`（2）、`data/scene/closeup.json`（15）；`templates.json` 改成一句一格（39，`uses` 指設定格）；新 `templates.distilled.json`（0 格，distill 唯一寫的檔）。`cast.json`／`places.json`／`styles.json` 裡那一項換成 `{"$ref"}`。四個新資料夾各一份 `_metainfo`（`kind data`、`fs_needs [git_tracked, isolation]`）。
- `bench/Q16.json`：`setting`、`speaker_note`、place／cast／季節／時間／基調／稱謂階拿掉，改 `scene: "scene.closeup"`＋`blank_note`；`points` → `point.a～c {text, dims}`；`guard.must` → `{"01": {"any": […]}, "02": …}`。`cls-*.json` 只剩 `mode, scene, detail, min/max_lines, drafts`。
- `brief.py`：解 `$ref`、把格渲染回舊卡的形狀；場景格補題目缺的欄；`event` 渲染「`<occasion>：<before><短名><say>，<do>`」；挖空題 `setting`＝`scene.setting`＋「氛圍：」＋`mood.*`；`speaker_note`＝說話者 `trait`＋`bio`＋`scene.backstory`＋`bench.blank_note`。錯多 `SceneMissing`、`DetailMissing`。
- 等價（改前改後用 scratchpad 腳本比）：Q01、晴子 scene 的 `brief.json`／`rules.json` bytes 一字不變；scene-yuzuha、cls 三題的 `brief.json` bytes 一字不變（event 一字不差）；Q16 的 `brief.json` 只有 `speaker_note` 變了（規劃本來就要從格渲染）；柚葉那幾題的 `rules.json` 只多 `contrast.cells`／`contrast.card`／`scene`／`cells_used`，`contrast.reveal` 集合相同（順序變：她的小動作在前）。

做了（3b-β 消費者）：
- `tools/lint`：輸出多 `hits {反差, 洩底, 語域}`（沒 `contrast.cells`＝全 `[]`）；分數一行沒動。
- `pick.py`：每份草稿照抄 `hits`；`guard_hit` 用 `cells.must_groups`。`train/common.gather` 多 `cell_hits`（過護欄的草稿、同份同格算一次）→ `rate.py` 寫進 `ratings.json.style:<風格>.cell_hits`。
- `judge.py`＋`grader/system.v3.txt`（`system.txt` 捷徑改指 v3；v2 留著當歷史，同 v1）：「像柚葉」那行只留評分尺度，人物描述改由 judge 從 `dims.json` 評審維度的 `cells` 渲染一行「人物設定：宮澤柚葉（傲嬌）——…」進題目。
- `dims.json` 每維多 `cells`（§ 2.2 的；語域多 `style.tsun.ooc.*`——OocMark 扣的是語域）。
- `writer/compose.py`：槽候選是格、`pick()` 記下格 id；`{prop}` 從 `rules.json` 的 `scene`＋題目 `detail` 解（by_detail.ribbon 的「彩帶」改成 `{prop}`）；口癖從 `rules.contrast.card` 的 `tic.*`（不再切字串；沒有才退回切）；`templates.distilled.json` 接在同槽人寫的後面；`hard.jsonl` 行多 `cells`（TemplateMissing＝缺的那格 `scene.closeup.detail.<detail>`；LintFailed＝這次用到的模板格）、`cells_hit`、`tpl`。
- `beat`／`voice` 的 `DEFAULT`／`DEFAULT_TICS`／`GENERIC` 註明「退路，不是資料」；契約沒變。
- `_metainfo`：`data/_metainfo` 的 `children` 加新檔、`counter_cells 122`、`writes` 加 `templates.distilled.json`、`fs_needs` 加 `shared_write`；`fsm.json` brief 的 reads 加四個格檔、judge 的 reads 加 `dims.json`／`cast/yuzu.json`；`writer/_metainfo` reads 加 distilled、yuzu、closeup。README 樹加 `cells.py` 一行、data 那行補格檔。

偏離／解讀：
- **`cells_used`、`scene`、`contrast.cells`／`card` 放 `rules.json`、不放 `brief.json`**（§ 7 風險 (b) 擇一）：`brief.json` 給腦看，格 id 不進去＝零多餘 token，晴子／cls 的 `brief.json` bytes 也就能一字不變。compose 讀工作區的 `rules.json`（write.py 本來就放進去給 lint）。
- **`contrast.cells` 分類別的表**（`{deny|yield|cover|reveal|ooc|markers|calls: {字面: id}, ng_marks: id}`），不是 § 3 寫的一張平的「字面 → id」：「哼」同時是 `tic.01` 與 `deny.03`、「真是的」同時是 `tic.04` 與 `cover.01`，平表會撞。
- **3b-3 的「`hits.反差 == [deny.03, yield.01]`」解讀成「決定分數的那兩格」**：位置最前的否認（同位置照表序）＋它之後照表序第一個讓步（就是 lint 的 `any()` 停下來那個）。照「所有出現的字面」算會多 `deny.02`（才沒有含「才沒」）、`yield.02`。洩底與語域則是全部命中的。
- **粒度比 § 2.2 粗的地方**（§ 4 停止條件三問全否就不拆）：`place.fact` 只拆兩句、句子不拆（沒人單獨量它；§ 4 也預測拆了沒用）；`scene.state` 兩句（不是三格），字面就是舊 `places.教室.details` 的後兩句，brief 才能一字不變；Q16 的 setting 主句是一格 `scene.closeup.setting`（散文、沒人單獨命中），氛圍拆 `mood.01～03`。
- **沒拆的**：`hints.json`、`lint_switches.json`（§ 2.2 說改格、§ 4 說 `hint.*` 拆了沒用——照 § 4，較後較細；switch 不拆也有 id：`lint_switches.contrast_order` 解得到）；`forbidden`、`address`、`samples`、`route`、Q01、晴子／佐伯／河鹿堂（同規劃）。
- `cast.yuzu.type` 留 `"傲嬌"`（styles.json 的 key），不是 § 2.2 的 `"style.tsun"`：ratings 的 `style:傲嬌`、route、dims profiles 都用這個字。Q16 的 `speaker` 也留顯示名（lint 的 `rules.speaker` 用它），另加 `speaker_cell: "cast.yuzu"`。
- 新增兩種格：`cast.yuzu.bio.01～02`（文藝社、逞強是保護色——從 system.v2「像柚葉」那行收回來的第三份卡）、`scene.closeup.occasion`／`backstory.01`（event、speaker_note 渲染要的）。`style.tsun.habits` 去掉跟 `tic` 重複的「哼」「真是的」，留「所以說啊」「…算了」陣列（沒人讀）；`narration` 留一句。
- 格檔的 `source` 在檔內 `_metainfo`（§ 2.1）——`test_tree_shape` 原本要頂層 `source`，改成兩處擇一。
- `brief`／`pick`／`judge`／`compose` 都 `import cells`：每支都設 `sys.dont_write_bytecode`——不然樹裡長 `__pycache__/`，`test_tree_shape` 要每個資料夾有 `_metainfo` 會紅（踩到過一次；那份 `__pycache__` 已搬去 scratchpad，沒刪 repo 裡的東西）。

**給步驟 5 的介面**（`grad.json` 的 `diff.cells`／`changed_cells` 這步沒做）：
- `changed_cells`：`cells.touched(舊實體, 新實體, 前綴)` 列出兩版之間新增／刪掉／值變了的格 id；distill 追加 → `touched(舊 distilled, 新 distilled, "tpld")`；switch 翻 → `["lint_switches.contrast_order"]`（root 檔 id 直接解得到）。命令列 `python3 -B cells.py diff 舊.json 新.json tpld`。
- `diff.cells {"+", "-"}`：比前後兩次 `ratings.json.style:<風格>.cell_hits` 的 key 集合（已在 rate 寫）。
- `hard.jsonl` 的 `resolved_cells`：distill 那步用 `touched` 的結果填。

測試（`Round4T`，§ 5 編號）：`test_cells_resolve`（3b-1）、`test_cells_equivalent`（3b-2；用 `git archive 970b8e2c` 取 3b 前的整棵樹，對同題跑 brief 比 bytes／集合、整條假腦跑 Q01／scene／Q16／cls-ribbon 比每份 total；拿不到那版就 skip）、`test_lint_hits`（3b-3）、`test_event_render`（3b-4）、`test_rubric_render`（3b-5）、`test_template_cells`（3b-6；另驗 `{prop}`：拷貝裡把 ribbon 的道具改「紙鶴串」→ 答案裡有；distilled 追加 poster 的否認句 → 不再記難例、答案用到它）、`test_cell_hits_rate`（3b-7）、`test_cells_metainfo`（3b-8；多加一格 metatable 行數不變）。既有測試改：`test_tree_shape`（source 兩處擇一）、`test_hard_cases`（`cells`）、`test_m7`（允許變的檔加 `templates.distilled.json`；人寫的格檔 `data/cast|place|scene|style/`、`templates.json` bytes 不變）。

變紅過一次（scratchpad 腳本：暫改 → 跑該測試 → 還原）：`load_entity` 不認資料夾 → 3b-1 紅；habits 用「，」接 → 3b-2 紅；反差 hits 列全部否認 → 3b-3 紅；event 不渲染 before → 3b-4 紅；judge 不加人物設定 → 3b-5 紅；`{prop}` 寫死「彩帶」→ 3b-6 紅；沒過護欄的草稿也算 cell_hits → 3b-7 紅（第一版改的「同份同格不去重」沒變紅——測試資料裡同份沒有重複的格，換這個）；`counter_cells` 差一 → 3b-8 紅；TemplateMissing 的 `cells` 給空 → `test_hard_cases` 紅。

結果：`test_topdown_galtxt_a.py` 48 個綠；`proto8/tests` 全套 579 OK（skip 2）。

### 給隊長寫 thinking 的結論（拆到什麼粒度、誰在用）

- **量**：5 個新格檔（`cast/yuzu.json`、`style/tsun.json`、`place/classroom.json`、`scene/closeup.json`、`templates.distilled.json`）＋`templates.json` 改成格，加 4 份資料夾 `_metainfo`、1 支 `cells.py`。格數 122：設定 83（柚葉 31、傲嬌 35、教室 2、場景 15）＋模板 39（distilled 0）；Q16 另有 `point` 3、`guard.must` 2。每檔 2～39 格，都在 § 4 的「20～40、超過 80 懷疑拆過頭」以內；設定檔都 ≤ 3 KB；最大的是 `templates.json` 6.1 KB（`uses` 與 `by` 撐大的，離 B-3 的 8 KB 不遠——再多一個 detail 的專屬句就該照 § 2.3 (a)／(d) 長成 `templates/`），其餘沒有檔要長成資料夾。
- **已有消費者單獨引用的格**（假腦跑柚葉四題、agent＋program 各一次實數）：lint `hits` 命中 25 個 id——`tic` 5／5、`gesture` 5／5、`calls_lead.r2` 2／2、`deny` 3／5、`yield` 5／7、`reveal` 4／6、`styles.ng_marks`（假腦的 NG 標記，12 次）；`hard.cells` 指到 `detail.poster`、`detail.lights`；模板 `uses` 指到 `fact.02`、`state.01～02`、`prop.ribbon`、`cover` 三格、`gesture`／`tic`／`deny`／`yield`／`reveal` 多格；評審 rubric 渲染 `trait` 3、`bio` 2；`dims.cells` 涵蓋 `order.01`、`ooc.*`。`hard.tpl` 指到 39 句模板裡的 8 句（poster／lights 走 generic 用到的那些）。
- **拆了暫時沒人單獨用的**（只被 brief 整張渲染）：`ending` 4、`style.tsun.ng` 3、`cast.yuzu.ng` 3（brief 渲染 never）、`calls_lead`／`called_by_lead` 非本階的 9 格（lint 只當 bad 清單整張用）、`mood` 3、`backstory` 1、`occasion`、`setting`、`intent`、`fact.01`、`prop.poster／lights`（等 distill 寫 poster 句才會被 `uses`）、`ooc.*`（定義了、這輪假腦沒觸發）。
- **對照 fable § 4 的預測**：「預測有用」那欄全中——`tic.*`（lint markers、voice tics、模板 uses 三處同一源，口癖字面真源只剩一處）、`gesture.*[reveal]`（洩底 hits 直接是它）、`deny／yield／cover`、`scene.detail.*`（題目開關＋難例缺格）、`tpl.*`、`dims.*.cells`、`Q16.point.*.dims`（已標、還沒程式讀）。「預測沒用」的照做沒拆（forbidden、address、hints、晴子卡…）；`place.fact` 拆了但只拆兩句，實測只有模板 `uses` 指到一句，跟預測（沒人量）一致。**預測外**：`styles.ng_marks` 整張是一格、卻是 hits 次數第二多的 id（假腦愛用 NG 標記）——之後若要知道「是哪個 NG 字」可能值得拆；`cover` 沒有 lint 消費者（lint 不量遮掩），只有模板 `uses`；`ending`／`ng` 完全沒人單獨讀，步驟 9 真腦後若仍 0 次，依 § 4 併回陣列。
- 還沒長出來的引用面：`grad.cells`／`changed_cells`（步驟 5）、distill 的 `resolved_cells`（步驟 6）、`meta/cells/` 的 `where`（步驟 8）。

下一步（步驟 5）：同上一節；`grad.json` 多 `diff.cells`（比兩次 `cell_hits`）與 `steps[].changed_cells`（用 `cells.touched`）。


## 步驟 5：梯度與判斷器（實作者，2026-10-25）

做了：
- `train/common.py`：`diff(before, after)`（§ 4.1：巢狀物件攤平成 `a.b`；數值＝差、三位小數、差 0 不出現；字串／布林／null↔數＝`[舊,新]`；陣列當集合＝`{"+","-"}`；兩邊同＝`{}`）；`snapshot(verify.json, stage.json, 那棵的用量)`＝before／after 的形狀（`val`、`total_avg`、`determinism`、`dims`、`bench {guard_hit, bigram_overlap}`、`tags`、`cells`、`cost {llm_tokens, llm_calls}`、有 stage.json 才有 `stage`／`tools`）；`val_of`（從 verify.py 搬來）、`epoch_cells`、`cell_prefix`／`cells_touched`（data 底下的格檔 → `cells.touched`）；`params_save(st, n, change, files, created)`（步驟 6 與 selfopt accept 用：拷快照＋寫 `changed.json`）、`rollback(params, change)`；`called(sets)`／`is_called`、`brain(usage, questions, sets)` 多一個參數。
- `train/weigh/`（agent-dan 範本，抄 grader）：`_entry`（python；`stage.json` 分流 agent＝`aos-loop`、rules＝直接照表；`GALTXT_WEIGH_STAGE` 覆寫；agent 回答解不開＝改用 rules 的答案、stderr `weigh: ReplyBad`；每答一題追加 `log.jsonl`）、`rules.py`、`rules.json`、`brain.py`（假腦＝`rules.py`；真腦 system＝`system.txt`＋`rules.json` 全文）、`act.py`、`fsm.json`、`loop.json`、`system.txt`、`.env`（luna-low）、`idle → ../../idle`、`stage.json`（agent）、`ratings.json`／`human.json`／`grad.json`／`rollup.json`（初始只有 source）、`_metainfo`（`kind agent`、`role dev`、`llm_calls 1／2`、`llm_tokens 1500／5000`、`steps` 三個、五個 `$ref`）。手跑兩階：同題同答案、agent 階有 history、rules 階沒有。
- `train/verify.py` 重寫比較那段（§ 5.4）：開跑先 `rollup --up train/weigh`；有 `epochs/NNN/params/changed.json` 就先 `rollup --up <被改那棵>`（brain.nodes 才是這次實際跑的階）→ 算分 → before（上一個 epoch 的 verify.json＋params 快照裡的 `<子樹>/stage.json`＋那棵在上一個 epoch 驗證小格的 `run_cost`）／after → `diff` → `changed_cells`（changed.json 的 `cells`，沒給＝照 `files` 用 `cells.touched` 算）→ 判斷器小格 `epochs/NNN/weigh/`（題目 `{A, B: {}, before, after, params {min_gain, min_loss}, epoch, subtree, action, target}`）→ 選 B＝`common.rollback`；不論結果都寫 `<子樹>/grad.json`（`scope`、`context {tree, verify, S}`、`steps`（同 epoch 覆蓋）、`sum`（只算收下的步、數值鍵 × share、`cells_touched`）、三個計數）、分給工具、`optimize/ratings.json` 的 `action:<動作>`（多 `counter_accepted`／`counter_rolled_back`、`dims.收下`）、`weigh/ratings.json` 的 `judge:accept`、`stage.json.history`、`rollup --up <子樹>` 與分到梯度的工具。verify.json 多 `tags`、`cell_hits`、`step`。stdout 那行尾巴多 `weigh A（理由）writer/extract`。選 B＝stderr `train: Regressed epoch N 回滾 writer/extract beat（weigh: 拒A：…）`、退 10；收工後重叫照 verify.json 退 10、不重判。沒有 changed.json、只有舊 `params/optimize.json`（round3 選路）＝舊規則照舊（`action:route`、delta < 0 回滾 route.json），步驟 6 重寫優化器後可以刪。
- `meta/rollup/_entry`：自己那格評級的 `brain.excluded` 裡的名字搬去 `brain.excluded`、不算進 `nodes` 與兩個計數（只有根那格有，verify 寫）。
- `train/fsm.json` verify 格、`train/_metainfo` 的 summary／reads／writes 補上。

**隊長裁定（brain 只算會被叫到的）怎麼做**：`common.called(sets)`＝set.json 的 `writers` ∪ `data/route.json` 的 `default`＋`by_style` 值 ∪ `grader`、`train/weigh`；`is_called` 再收它們底下的「子樹/孫」（`writer/tools/beat`…）與根的 `tools/*`。其餘進 `brain.excluded {名: 階}`：**`writer-sol`（凍結、route 沒選它＝不算；哪天 route 選到它就自動算回來）**、`idle`（每個 agent 的 fsm 都叫它，但它是殼的一部分不是「節點」，照裁定清單不列）、`train`、`train/optimize`（訓練迴圈本身，不是每題會叫的）、`optkit`（6a 正在長的，同理）。根評級的 `brain` 與根 `rollup.json` 的 `brain` 同一套（rollup 讀評級裡的 excluded 名單），metatable 仍是整棵樹結構（除錯用，不過濾）。現在假腦數字：`on_brain` writer、grader、train/weigh＝3；殼拿掉後 → 2（測試 14 驗）。

偏離／解讀：
- **after 用 verify 那次量的、不用被改子樹的 `ratings.json`**：迴圈順序是 verify → train → rate → optimize（改）→ verify，verify 那時寫手的 `ratings.json` 還是改之前 rate 寫的，「改之後的評級」要等下一個 rate。所以 before／after 都取「那個 epoch 的驗證題＋measure 題」實測（verify.json），`cost` 取被改那棵在驗證小格的每次用量（`run_cost`，量不到的子樹——`.`、`tools/lint`——退回每題用量）。`diff.cells` 同理比兩次 verify.json 的 `cell_hits` key（跟 ratings 的 `cell_hits` 同一個 `gather` 算的、同形），不是比 ratings 的。
- **`stage.json.history` 每個 epoch 都寫**（set.json 的寫手＋被改那棵；§ 5.4 只說被改那棵，但 § 10 測試 15 要 writer 四筆 `agent, semi, semi, program`＝每個 epoch 一筆）；值是那棵自己的 `llm_tokens`／`llm_calls`（不是每題的）、`determinism`／`val`／`total_avg` 是整次 verify 的。回滾後寫在拷回來那份上，記的是**這次實際跑的**階（`stage semi`、`accepted false`）。
- **rules.json 加兩列 `cost.llm_calls`**（`reject_if` 評級掉的 `unless` 改成兩條任一：token 歸零或 calls 歸零；`prefer` 多「腦呼叫省三成」）：假腦沒有 token，`cost.llm_tokens` 永遠 0→0，只看 token 的話假腦殼拿掉那步判不出 A。真腦兩條同向。
- 規則語法：§ 4.4 的 `{"key", lt/ge/le/gt, relative, drops/rises, to_zero, only_if_before_lt, contains_any, and, unless}` 全照做，另加 `label`（理由標籤，真腦也照它回）；`"-min_loss"`／`"min_gain"` 從題目的 `params` 取；`tags.+` 取 `diff["tags"]["+"]`；`to_zero`／`relative`／`only_if_before_lt` 看題目裡的 before／after 快照。B 不一定是空：兩份都過 reject、比 prefer 順位，同順位或都沒有＝`tie`（B）。
- 判斷器的「下一步分掉」：`judge:accept.counter_contradicted`＝上一個 epoch 的 step 被收下、這個 epoch `delta < 0`（這個 epoch 本身也有新改動，只是粗記）。`counter_confirmed`／`agreement` 留給步驟 7 的 human/import。
- 判斷器 `loop.json` `max 40`（不是 grader 的 6）：一題要 idle→think→act 三格，6 只夠兩題；verify 一次只給一題，但單元測試一次餵 8 題。
- `log.jsonl` 由判斷器自己的 `_entry` 寫（它的紀錄、在它的資料夾），verify 不寫；`weigh/ratings.json` 由 verify 寫（成果由下層驗證寫，同 § 5.1）。
- 分給工具：只分給 `<子樹>/tools/` 底下**不是捷徑**的（`writer/tools/lint` 是 `../../tools/lint` 的捷徑，那是別棵——`tools/lint/grad.json` 不動，測試 14 驗）。extract＝`target` 那個工具整筆（share 1）；stage→program＝`stage.tools` 裡自己的工具按這次驗證小格被叫的次數分（有 history 數 tool_calls，program 階數「那次有沒有 `stack/<工具>/`」），和為 1（最後一個補差）。工具那份只留 `epoch/action/target/diff/changed_cells/weigh/accepted`＋`assigned_from/step_epoch/assigned_share`（不重抄 before／after）。
- `rollback` 的 `created` 只准刪路徑裡有 `tools` 這段的（selfopt 新建工具資料夾），其餘 `StateBad`；`files` 有快照＝拷回、沒快照（本來不存在）＝刪；路徑出樹（`..`、絕對、realpath 出 ROOT）＝`StateBad`。
- `confidence`：照 § 4.1 寫的「`|Δtotal_avg| < 0.3` 標 low」（字面照做；那句的本意是「腦量的維度雜訊大」，純程式維度不受它影響）。
- verify 被殺在「寫完旁檔、還沒寫 verify.json」之間重跑：grad steps 與 history 同 epoch 覆蓋（冪等），`action:*`／`judge:accept` 計數會多算一次（沒處理）。

**給步驟 6 的介面**：
- `params/changed.json`＝`{source, action, subtree, target?, files, created, cells?, at, …}`（from／to／task 隨意加，verify 不讀）。`source`：外部動作寫 `"optimize"`、selfopt 寫 `"selfopt"`（grad step 照抄 `source`）；`files` 相對樹根、快照放 `params/<同路徑>`；`created`＝新建的資料夾（回滾整個刪）；`cells` 給了就照用（distill 知道自己加了哪幾格；switch 寫 `["lint_switches.contrast_order"]`），沒給 verify 照 files 算（只算 `data/*.json` 的格檔）。用 `common.params_save(st, n, change, files, created)` 寫，n＝`epoch.txt`。一步一份；舊的 `params/optimize.json`＋`route.json` 有 changed.json 時 verify 不看。
- **假腦下判斷器的結果**（測試 14 實跑）：epoch 0 不加 `GALTXT_FAKE_JITTER` 的話假腦 agent 的 `determinism` 已經 1.0，extract 那步 diff 只有 `cost.llm_calls +1`（semi 的假腦多叫一次 beat）→ 沒有 prefer 成立 → **tie＝B＝回滾、退 10**。測試 14／16 在 epoch 0 設 `GALTXT_FAKE_JITTER=1` 才有「確定性升 → A」。步驟 6 的整條假腦訓練（測試 15、so-10）要嘛 epoch 0 也開抖動，要嘛假腦 semi 真的用 beat 的輸出（現在 beat 回的句子不拿來用，草稿跟 agent 一樣）。殼拿掉那步（semi → program）假腦實得 `cost.llm_calls −3`、`total_avg +0.507`、`val ok → good` → A（評級升）。
- 優化器挑子樹讀根 `rollup.json.brain.nodes`：現在已過濾成會被叫到的（writer-sol 不在），`excluded` 另列。

測試（新 `Round4GradT`，§ 10 編號）：
- `test_diff`（10）：數值差、`[舊,新]`（含 null↔數）、集合 `{+,-}`（含 `cells`）、沒變的鍵不出現、兩邊同＝`{}`、浮點三位內同＝沒變；`snapshot` 形狀、量得到的那棵用它的 cost；`cell_prefix`。
- `test_weigh`（11）：八題（護欄掉 B；token 歸零 −0.2 A；評級掉但殼拿掉、−0.2 A；−0.4 B；確定性 +0.2 token +1.5k A；全零 B；評級掉沒拿掉腦 B；Q16 錨掉 B）在 agent、rules 兩階答案一樣；`log.jsonl` 16 行、`by` 分兩階；agent 階有 history、rules 階沒有；`_metainfo` bytes 不變；`GALTXT_WEIGH_STAGE=nope` → `weigh: StateBad`。
- `test_grad_assign`（14）：epoch 0（抖動）→ epoch 1 extract beat → A（確定性升）、writer 與 beat 的 grad 同一筆（`assigned_from`、share 1）、voice 沒有、history `[(0,agent),(1,semi)]`、`action:extract`、`judge:accept`、`log.jsonl` 1 行、writer rollup 的 `children.tools/beat.grad_total`；epoch 2 stage program → beat、voice 都分到、和為 1；verify.json 的 brain：writer semi → program、`counter_on_brain` 少 1；`grader/*`、`tools/lint/*` bytes 不變。
- `test_rollback`（16）：rules.json 加「確定性升也拒」→ 退 10、stderr `Regressed epoch 1 回滾 writer/extract beat（weigh: 拒A：確定性升也拒）`、stage.json 拷回（history 外一字不差）、history 記 semi／accepted false、`created` 的 `writer/tools/close/` 刪掉、grad `accepted false`／`rolled_back`／`counter_rolled_back 1`、sum 不含被拒的、beat 那份也 false、`action:extract.counter_rolled_back 1`、epoch.txt 不動；收工後重叫退 10 不重判；changed.json 路徑出樹 → `StateBad` 退 1。
- 既有測試改：`test_train_whole`（brain 斷言改成 writer／grader／tools/lint／train/weigh 在、writer-sol 不在而在 `excluded`；M7 變動集合加 `train/rollup.json`、`train/weigh/rollup.json`、`writer/stage.json`，history 兩筆）、`test_m7`（凍結清單加 `train/weigh/rules.json`；根 rollup 的 brain＝根評級的 brain 多比 `excluded`）、`test_metatable_sidecars`（未訓練的真樹 rollup.json 沒有 brain，原本拿預設 3 比 metatable——改成驗 writer、writer-sol、grader、train/weigh 都在 metatable 的 on_brain 裡、≥ 4；metatable 不過濾）。

變紅過一次（scratchpad 腳本：暫改 → 跑該測試 → 還原）：diff 的 `+`／`-` 對調 → 10 紅；rules.py 不看 `unless` → 11 紅；extract 不分給工具 → 14 紅；verify 開頭不先 `rollup --up <被改那棵>` → 14 紅（brain 還是 semi）；rollback 不刪 created → 16 紅；verify 不回滾 → 16 紅；`common.brain` 不過濾 → `test_train_whole` 紅；rollup 不讀 excluded → `test_m7` 紅。**沒變紅的**：tool_calls 不數 history 的 tool_calls（program 階本來就只數 stack 資料夾、兩個工具各一次＝平分，跟退回平分一樣）——測試沒覆蓋「次數不等」的分攤，semi 階分攤才看得出來，這圈沒有那種動作。

**平行施工注意**：同一個 worktree 裡有另一位（步驟 6a，optkit）同時在改——`judge.py`、`writer/brain.py`、`writer/fsm.json`、`optkit/`、`writer/tools/opt_*`、`writer/system.opt.txt` 不是我動的。跑的時候紅的都是那邊施工中造成的（中途一度還有 `test_tree_shape`：`optkit/` 還沒 `_metainfo`，後來補了）：`Round3T.test_tree`（writer 與 writer-sol 的 `fsm.json` act 逾時不同：900000 vs 60000）、`SuggestT.test_after_tree_lists_nothing`（`optkit/accept`、`optkit/run` 被列成 B-2 候選）。我的測試在那些檔之外都綠。`optkit` 會出現在根 brain 的 `excluded`（program，不算）；若 `optkit/shell/` 長成 `kind agent`，metatable 的 on_brain 會再多一（我那條斷言是 ≥ 4，不會因此紅）。

結果：`test_topdown_galtxt_a.py` 52 個，我這步的全綠（新 4 個＋改的 3 個）；紅的 2 個（`Round3T.test_tree`、`SuggestT.test_after_tree_lists_nothing`）是 6a 施工中；`proto8/tests` 全套 625 個，4 紅、skip 2——4 紅全是 6a 那邊的（上面兩個＋`test_topdown_galtxt_a_optkit` 的 `test_cheat_and_break`、`test_shell_voice`）。

下一步（步驟 6）：照 round4-selfopt.md（6a optkit／6b 優化器照樹走＋selfopt）；外部動作與 accept 都用 `common.params_save` 寫 changed.json；整條假腦訓練要先解決「假腦 extract 那步判不出 A」（見上）。

## 步驟 6a：optkit 自我優化工具包＋claude code 代勞（實作者，2026-10-25）

照 [round4-selfopt.md](round4-selfopt.md) § 1～§ 6 的 6a；隊長加一支 `optkit/claude/`（使用者 10-25「在這套工具包尚未成熟前，可以先由claude code代勞，或是乾脆工具就是呼叫claude code cli」）。6b（`train/optimize` 照樹走＋`selfopt` 動作＋fallback）沒做。

做了：
- `optkit/`（`kind program`、`role dev`）：九支 `opt_describe／opt_history／opt_read／opt_edit／opt_write／opt_extract／opt_try／opt_test／opt_note`（各 `_entry`＋`tool.json`＋`_metainfo`，契約同 lib：stdin JSON、錯＝stderr＋stdout 各一行退 1）；共用 `optkit_common.py`（環境、路徑解析、白名單、diff、錨）；`deny.json`（always／unless_named／read_deny／anchors／ignore）、`tests.json`、`budget.json`；`fake_opt.py`（優化模式的假腦劇本：writer 抽 close、voice 加 idx、`GALTXT_FAKE_OPT=cheat|break` 壞劇本）；`shell/`（純程式節點的臨時腦）；`run/`、`accept/`；`claude/`（`_entry`＋`cli.json`）。
- writer：`tools/opt_* → ../../optkit/opt_*` 九個捷徑；`system.opt.txt`；`brain.py` 最小改動（`GALTXT_OPT=1`＝`ALLOWED` 多 `opt_*`、system 讀 `system.opt.txt`、沒真腦時 import `fake_opt`；平常一字不變）；`_entry` 在 `GALTXT_OPT=1` 時跑 `loop.opt.json`（新：`max 40`、`exec fsm.opt.json`；新 `fsm.opt.json`＝`fsm.json` 但 act 逾時 900 s——opt_try／opt_test 跑一題要幾十秒，平常的 60 s 不夠；`fsm.json` 本身不動，writer-sol 要跟它 bytes 一樣）。
- `_metainfo.opt_writes`：writer `["system.txt", "stage.json#/tools", "tools/*/", "compose.py", "../data/templates.distilled.json#append"]`；beat、voice `["_entry", "tool.json#/description", "tool.json#/parameters/properties#append"]`（照 § 1.1）。
- `judge.py`：`GALTXT_JUDGE=off`＝寫空 judge.json、退 0（評審的維度 null）。

偏離／解讀：
- **optkit 在拷貝裡是指回原樹的捷徑**（§ 1.2 說整棵 `cp -a`）：工具永遠跑原樹那份，拷貝裡的程式（opt_try 跑起來的）改不到 optkit；`writer/tools/opt_*` 的相對捷徑照樣接得上。拷貝也不拷 `plan`／`meta`；`<小格>/tree/proto8/lib` 指回真的 lib（同測試的 tree_copy）。小格在 `<stack>/selfopt/<子樹 / 換 _>/NNN/`（`--cell` 可指定），拷貝根＝`<小格>/tree/proto8/topdown/galtxt-a`。
- **路徑一律從拷貝樹根算**（§ 1 表；§ 4 示範寫 `opt_read _entry` 是相對子樹——照表，劇本寫 `writer/tools/voice/_entry`）。`opt_writes` 寫在 `_metainfo` 裡是相對子樹，`allow_entries` 正規化成相對樹根。
- **白名單語法的細節**：`資料夾/*/`＝**只准新建**子資料夾（原樹已有的 `tools/voice/` 不算，不然 writer 的 `tools/*/` 會繞過 voice 自己的 `tool.json#/…` 限制）；新建資料夾裡什麼都准（新工具自己的 `_entry`／`_metainfo` 是腦寫的，M7 不違）。`#/指標`／`#append` 比的是**解析後的 JSON**（不是 bytes：opt_extract 改 stage.json 會換排版）。`unless_named` 只有 `**/_entry`。另外 `<子樹>/opt_log.jsonl` 永遠准、只准追加；不准刪檔、不准新增或改捷徑（accept 查）。
- **held-out**：run 從原樹 `set.json.verify` 的題目讀 `detail`（現在＝`lights`），經 `OPTKIT_HELDOUT` 給工具、記進 run.json；`templates.distilled.json` 的 `by_detail` 新增這些＝`HeldOut` 拒。opt_try 能跑的題只有 `set.json` 的 train＋measure（拷到 `<小格>/questions/`），驗證題不在。
- **opt_test 跑新檔 `test_topdown_galtxt_a_optkit.TreeContractT`**（§ 1 說跑 `test_topdown_galtxt_a.py`、測試檔讀 `GALTXT_TREE`）：那個檔這輪歸步驟 5 的實作者，我不改；`TreeContractT` 讀 `GALTXT_TREE`（沒設＝自己拷一份真樹），四個：writer/tools 每支工具契約（compile、空 stdin 有一行、壞 stdin ArgumentsBad）、beat／voice 既有行為（測試 6 那幾條）、stage.json 合法、program 階跑 cls-ribbon 得出 ≥ 5 行。`tests.json`：`writer`＝全部、`writer/tools`＝前兩個。之後要把 `test_topdown_galtxt_a.py` 的相關測試也點進來，得先讓那檔讀 `GALTXT_TREE`。
- **accept 的 changed.json 跟步驟 5 的 `common.params_save` 同形**（`{source: "selfopt", action: "selfopt", subtree, by, files, created, cells?, from, task, test, at}`、快照在 `<params>/<相對樹根路徑>`；`--params` 預設 `<小格>/params`，6b 給 `epochs/NNN/params`）；測試裡用 `common.rollback` 吃這份、原樹整棵 bytes 回到原樣。accept 沒呼叫 `params_save`（optkit 不 import train）。
- **還沒做**：§ 5.3 的 `AnchorSuspicious`（`bigram_overlap` 一步升 > 0.3——要 verify 的數，6b 在 verify／weigh 那邊加）；§ 5.7 震盪（opt_log 已帶每檔 sha256，`same_as` 判斷留 6b 派工時做）；§ 5.8 只做了「改動內容新出現 bench 字樣＝stdout 警告」。
- **預算**：node／shell 數 `<小格>/stack/history.jsonl` 的 assistant 則數與 `usage.jsonl` 的 `total_tokens`、牆鐘，每 0.1 s 看一次、到頂 `killpg` TERM→KILL；跑完再對一次（假腦太快、輪詢沒抓到也算 BudgetSpent）。task.json 的 budget 只能壓低。claude 那條用 `--max-turns`、`--max-budget-usd`（budget.json 的 `claude`）＋`max_elapsed_ms` 逾時。
- 殼的 `brain.py`／`act.py` 是寫手那兩支的捷徑（沒 stage.json＝tools/ 全看得到、`GALTXT_OPT=1` 讀 `system.opt.txt`），沒另寫一份。`run`／`accept` 的 `_metainfo` `callers 2`（optimize＋人／測試；`callers 1` 會被 metatable 列成 B-2 候選）。
- 踩到的坑：run 起子行程沒給 `stdin=DEVNULL`，被叫到純程式節點（voice 的 `_entry` 讀 stdin）時卡到逾時——補了（run、opt_try、opt_test）。

**claude code CLI**（`optkit/claude/`，`run … --by claude`）：這個環境叫得起來（claude 2.1.310，訂閱登入）。旗標：`-p --output-format json --model sonnet --tools Read,Edit,Write,Glob,Grep --permission-mode acceptEdits --permission-prompts none --strict-mcp-config --setting-sources project --no-session-persistence --add-dir <拷貝根> --settings '{"permissions":{"deny":["Read(/<拷貝根>/data/bench/**)","Read(/<拷貝根>/train/**)"]}}' --max-turns 30 --max-budget-usd 1.0`；cwd＝拷貝裡的子樹；`--max-turns` 在 help 裡沒列但收（試過）；`--bare` 不能用（只認 API key，訂閱登入會失敗）。prompt＝任務＋白名單逐條＋禁區＋先前結果（task.json 的 history）。花費每次一行進 `optkit/usage.jsonl`（`cost_usd`、四種 token 與合計、`num_turns`、`duration_ms`、`elapsed_ms`、`subtype`、`timed_out`、`flags`），原始輸出在 `<小格>/stack/claude/claude.json`。**實跑一次**（scratchpad 的樹拷貝、任務＝voice 加選填 idx 輪替口癖）：5 輪、27,684 token（cache read 21k）、0.035 美元、14 s；改了 `_entry` 三行＋`tool.json` 加 idx、不帶 idx 行為不變；accept 白名單／錨／opt_test 全過、收了 2 檔。

測試（新檔 `proto8/tests/test_topdown_galtxt_a_optkit.py`，17 個）：TreeContractT 4 個（上面）；OptkitT：`test_contract`（so-1）、`test_whitelist`（so-2；加寬是在拷貝的 writer/_metainfo 加 `../brief.py`——dims.json 本來就被 deny 擋，驗不出「從原樹算」）、`test_append_pointer`（so-3；`generic.deny[0]` 在人寫的 templates.json、已整檔 deny，改驗「distilled 已追加的 poster 再改＝拒」）、`test_agent_selfopt`（so-4）、`test_tools_visible_only_in_opt`（so-4 下半：本機假 OpenAI 端點抓請求——平常 tools＝stage.tools、system＝system.txt；優化模式多九支 opt_*、system＝system.opt.txt）、`test_shell_voice`（so-5）、`test_accept_moves`（so-6＋so-12 M7＋`common.rollback` 相容）、`test_cheat_and_break`（so-7；cheat 的「工具擋下」與「程式直接改 dims.json 被 accept 抓」兩層都驗；break 另驗 `--no-test` 會收＝是測試擋的）、`test_budget`（so-9）、`test_run_errors`、`test_claude_edit`／`test_claude_cheat`／`test_claude_timeout`（cc-1～3，PATH 上放假 `claude`：記 argv／cwd／prompt、照 `FAKE_CLAUDE` 改檔／改尺／睡 60 s）。so-8（回滾經 verify）、so-10、so-11 要 6b；so-13（真腦）沒寫。

變紅過一次（scratchpad `optkit_redproof.py`：暫改 → 跑該測試 → 還原；共用檔（voice、beat、stage.json、compose.py）改在拷貝、用 `GALTXT_TREE` 指過去，沒碰真樹）：die 不印 stdout → so-1；read_deny 不查 → so-2；`appended` 恆真 → so-3；brain 不加 opt_* → so-4；system 不換 → 看得到那個；auto 一律走 node → so-5；搬檔不保留權限位 → so-6；accept 不跑 opt_test → so-7；task 的 budget 不壓低 → so-9（第一版只關輪詢沒變紅：跑完那次對帳也會抓——改成這個）；SubtreeBad 不認 train → run_errors；claude 不記 usage → cc-1；accept 不擋違規 → cc-2；claude 不設逾時 → cc-3；voice 用 `tics[-1]`、beat 的 ArgumentsBad 改名（第一版只換第一個出現的、是註解，沒變紅）、stage.tools 多 `nope`、compose 開頭 `raise` → TreeContractT 四個。

結果：`test_topdown_galtxt_a_optkit.py` 17 綠；`test_topdown_galtxt_a.py` 全綠（前一節記的 `Round3T.test_tree`、`SuggestT.test_after_tree_lists_nothing` 兩紅是我施工中的 fsm.json 逾時與 callers 1，已改掉）；`proto8/tests` 全套 625 OK（skip 2）。

下一步（6b）：`train/optimize` 照 § 3 派工（`policy.json.task_templates` 組任務句、`opt_history` 的輸出 inline 進 task.json、`run --runs <stack>/epochs --epoch N` → `accept --params epochs/NNN/params`）、`grad.json.steps[].by` 抄 changed.json 的 `by`、fallback 表（連兩次被拒或回滾 → `SelfoptFallback`）、§ 5.3／§ 5.7 兩條；要不要讓 6b 預設走 `--by claude` 由隊長定（腦只用 gpt 的例外）。

## 步驟 6b：優化器照樹走＋selfopt 派工＋fallback（實作者，2026-10-25）

照 round4 § 5.2～5.4、§ 6 與 round4-selfopt.md § 3；隊長裁定：假腦確定性用乾淨做法、預設走 gpt（`--by claude` 或 `policy.selfopt.by` 可改）、評審留 agent、weigh 規則表人寫（§ 13 推薦方案）。

做了：
- `train/optimize/_entry` 重寫（第三輪的選路＋`min_gap` 自調整個拿掉：寫手只剩一個、route 沒得選；verify 讀舊 `params/optimize.json` 的分支還在）。讀根 `rollup.json`（沒 rollup 過＝`rollup --dry-run` 現算）的 `brain.nodes`＋`children.*.cost`；候選＝還在 agent／semi 的或 `policy.actions` 有列的，順位 (還靠腦, token, 腦呼叫, 1 − determinism)；每棵照 `policy.actions` 找第一個成立的：`stage program`（tools_share ≥ `min_share_program` 0.5，外部）→ `selfopt distill`（`common.hard_open` 非空）→ `selfopt extract`（agent／semi、還有 decisions_left）→ `extract`（外部、人寫的 beat／voice，只在 fallback）；都不成立＝印「<子樹>（…）這圈沒動作」換下一棵。selfopt：任務句照 `policy.task_templates`、`opt_history` 的輸出 inline、budget＝`policy.selfopt.budget` 與訓練預算剩下的取小（剩 0＝不派工）→ `optkit/run --cell epochs/NNN/selfopt/<子樹>/NNN --runs <stack>/epochs --epoch N` → `optkit/accept --params epochs/NNN/params`；收了就在 changed.json 補 `goal`、`target`（新工具 `tools/<名>` 或 `data/templates.distilled.json`），抽了工具而還在 agent＝外部把 stage 翻成 semi（`stage_flip`，stage.json 一起進回滾清單）。同一個 epoch 已有 changed.json 或 selfopt 紀錄＝不重做。`--dry-run` 只印。
- 自己的旁檔 `train/optimize/selfopt.json`（`_metainfo` 加 `$ref`）：每次 selfopt 一筆 `{epoch, subtree, goal, by, cell, accepted, code, reason, files, created, target, counter_calls, tokens, elapsed_ms, cost_usd, usage?}`＋`sum`。token／次數／秒從 `run.json`；**$ 只有 claude 那條有**（`optkit/usage.jsonl` 這次新增的行，原行附在 `usage`）；gpt 那條 LiteLLM 不回錢＝null。
- `policy.json` 換成動作表：`actions`（writer 四個；grader、train/weigh 空＝這圈沒動作，§ 13 推薦方案）、`tools.writer`（lint 自檢、beat 反差節拍＋遮掩句、voice 口癖句尾的 `covers`，beat／voice 標 `fallback`）、`min_share_program`、`selfopt {by, max_fail_streak 2, budget}`、`task_templates {extract, distill}`。
- `train/common.py`：`tools_share(sub)`（`_metainfo.steps` 裡被工具 covers 的比例；covers 先看工具自己的 `_metainfo.covers`——selfopt 抽的——再看 policy 表）、`heldout_details`、`covered_details`、`hard_rows`、`hard_open`（TemplateMissing、模板還沒有、不是 held-out 的 detail；照模板檔程式查，不信 resolved 標記）、`hard_resolve`。
- `train/verify.py`：before／after 多 `hard.uncovered`（同一份 hard.jsonl，模板用 params 快照 vs 現在各算一次）；收下而動了 templates.distilled.json＝`hard_resolve`（`resolved_epoch`、`resolved_cells`）；grad step 多 `by`（changed.json 的，外部動作＝`optimize`）、`goal`；selfopt 抽了新工具跟 extract 一樣整筆分給它；selfopt 那步 `bench.bigram_overlap` 一步升 > 0.3＝`AnchorSuspicious` 直接 B（selfopt § 5.3，不問判斷器、stderr 一行）；每個 epoch 寫 history 時重算 `tools_share`／`decisions_left`；**每題腦用量只算驗證＋measure 小格**（原本 `usage_of(epochs/NNN)`，selfopt 小格在同一層，會把派工的 6～8 次腦算進「每題」）。
- `train/weigh/rules.json` 加一列 prefer `{"key": "hard.uncovered", "le": -1, "label": "難例接住了"}`（人寫的表、訓練前改；source 註明）。
- `optkit`：`opt_extract` 收選填 `covers`（要在那棵 `_metainfo.steps` 裡，寫進新 `_metainfo.covers`）；`opt_try` 收選填 `stage`（`GALTXT_STAGE`：distill 拿自己的 agent 階當老師）；`fake_opt.py` 劇本改成看任務 `goal`＋原樹：extract＝原樹還沒有的第一支（close → open，共用一段查表程式，佔位 `{heroine}`／`{place}` 會填）；distill＝opt_describe → opt_read hard.jsonl → opt_try 第一個非 held-out 難例（stage agent）→ opt_write 全部未處理 detail（含 lights → 工具回 HeldOut）→ opt_write 拿掉 held-out 再寫 → opt_test → opt_note。假老師的句子內建（同 6a 的 CLOSE_CODE）。
- 假腦（`writer/brain.py`）見下「隊長裁定」；`system.txt` 加一句「有 open／close 工具時交給它」。
- `set.json` 的 `measure` 換成新題 `plan/examples/cls-ribbon-fixed.json`（見偏離）；`train/_metainfo`、`plan/examples/_metainfo` 補敘述。

**隊長裁定（步驟 5 的坑：假腦 agent 確定性 1.0）選了「agent 階預設帶抽樣差」**：腦自己決定、本來就照 hint 挑的環節（整場的開場／收尾旁白、挖空句的口氣）改照「第幾次抽」挑（`$AOS_STACK` 上一層 runs/NNN，第 n 次＝`KEYS[(n−1) mod 3]`）。平常每份的 hint 剛好就是第 n 個角度，**字面一字不差**（3b-2 的跨版本逐份比對、round3 的逐份斷言都沒動）；只有 hints_fixed 的 measure 題三份會不同——像真腦同輸入每次抽樣不同。`GALTXT_FAKE_JITTER=0` 關、`=1` 再疊舊的句尾記號。理由：(1) 確定性是固化的主訊號（§ 5.5「固化方向的梯度比分數準」），假腦 agent 恆 1.0 就測不到固化在幹嘛；(2)「semi 用 beat 的輸出」單獨不夠——beat 是確定性的、假腦本來也是，換誰寫都還是 1.0，判斷器照樣 tie＝B。所以「看得到 open／close 就叫它、用它回的那行」只是讓工具**接手**那個環節（那段從此不隨抽樣變），確定性才升；beat 的輸出仍沒拿來用（它接手的環節假腦本來就不抽樣）。整條訓練沒有設任何環境變數。實測（假腦，cls-ribbon-fixed）：agent 0.663 → 抽 close 0.78 → 抽 open 1.0 → program 1.0。

偏離／解讀：
- **measure 換成整場題** `cls-ribbon-fixed`（§ 4.2 是 Q16-fixed）：挖空題只有一行，量不到開場／收尾旁白——selfopt 示範抽的 close／open（selfopt § 4、§ 6 的預期序列）在 Q16-fixed 上確定性一點都不會動，判斷器只能 tie＝B。ribbon 是訓練題（確定性不是泛化指標，用訓練題量沒問題）；真腦花費不變（還是一題 3 份）。Q16-fixed 留著（測試 7 用）。optkit/run 拷給 opt_try 的題跟著變（so-4 的斷言改了）。
- **§ 7.3 的四步要 4 個 epoch**：verify 在 `n ≥ max_epochs` 收工，`max_epochs 3` 只有三步優化（selfopt close → selfopt open → stage program），poster 的難例要 program 階的訓練題才會出現（epoch 3 train），distill 在 epoch 3 的 optimize、epoch 4 的 verify 判。所以整條測試用 `max_epochs 4`（`budget.json` 本來就是 4），前四筆 history＝§ 10 測試 15 的 agent, semi, semi, program，第五筆 program＋distill。三個 epoch 版的 stdout＝下面摘要的前三步。
- **distill 的梯度**：驗證題只有 Q16 與 held-out 的 lights，蒸 poster 在分數上看不到（假腦實測 diff 只剩 0）→ 判斷器 tie＝B。加了 `hard.uncovered`（verify 程式查「hard.jsonl 的 detail 模板接不接得住」，不信節點自己標的）＋ rules 一列。真腦的 distill 也一樣看不到——要看分數得把 poster 放進驗證題（那就不是訓練題了）；這圈只證明「接住了」。
- **難例的 resolved 標記由 verify 寫**（§ 6 寫 distill 那步標；selfopt 的 deny.json `ignore` 本來就不搬 hard.jsonl、節點也標不了）：收下後才標，回滾就不標。
- **selfopt 抽了工具，stage 由優化器翻**：opt_extract 只准改 `stage.json#/tools`（6a 白名單），stage 是外部動作；accept 收了、還在 agent＝optimize 補翻成 semi，同一步、同一份回滾清單。
- **fallback 的「失敗」**＝accept 沒收（WriteDenied／TestFailed／BudgetSpent／RunFailed／NothingChanged）或收了被 verify 回滾；verify 還沒判的不算（streak 斷在那）。fallback 時 distill 沒有外部版（舊 `train/distill.py` 照 selfopt § 6 不寫）＝跳過。
- **優化器挑子樹的順位**沒照 § 4.3 的「鑽下一層」排序鍵（`grad_total` 與 `cost_to_extract`）：fallback 的候選工具照 policy 表順序（beat 先）。§ 5.7 震盪（`same_as`）沒做——opt_log 有每檔 sha256，留給下一步。
- `switch`／`hints` 兩個外部動作沒做（根與 lint 都不是 agent／semi，照順位永遠輪不到；要做就在 `policy.actions` 加列）。
- 假腦 semi 在 close＋open 之後確定性就 1.0（假腦只在那兩個環節抽樣），殼拿掉那步的判斷靠「評級升／腦呼叫歸零」——真腦 semi 階預期 < 1。
- optimize 印的 epoch 是 params 那個（＝下一個 verify 判它的 epoch），不是剛跑完的那個。

測試（新 `Round4OptT`＋optkit 檔一個；§ 10 / selfopt 編號）：
- `test_optimize_tree`（13）：手寫根 rollup → `--dry-run` 挑 writer、selfopt extract、什麼都不寫；tools_share 0.67 → stage program；program＋hard（poster、lights）→ grader 先印「這圈沒動作」、writer selfopt distill（只 poster）；只剩 held-out → writer 也沒動作、「這圈沒有可做的動作」；真改 → changed.json＋快照、stage.json program／since_epoch；同 epoch 不重做；FlagUnknown。
- `test_distill`（9）：program 階 verify → 手放 poster 難例 → optimize（by shell）→ distilled 只有 poster（deny／yield／cover／open…，`teacher writer@agent`）、假老師先試 lights 被 HeldOut、opt_try 是 cls-poster＋stage agent；changed.json 含 distilled、`by shell@selfopt`；verify → A（難例接住了）、`hard.uncovered −1`、poster 行 `resolved_epoch 1`＋`resolved_cells`＝changed_cells、lights 不標；再跑 poster 不記難例、答案用到蒸餾句。
- `test_train_selfopt`（15＋so-10）：`max_epochs 4` 整條（上面那段的形狀）＋so-12（既有 `_metainfo`、fsm、dims、rules、templates.json bytes 不變）。
- `test_selfopt_rollback`（so-8）：rules 加一列全拒 → optimize 收了 close、stage 翻 semi → verify 退 10「回滾 writer/selfopt close」、close 資料夾與 opt_log.jsonl 沒了、stage.json 回原樣、grad 最後一步 selfopt／false／`writer@selfopt`、`action:selfopt.counter_rolled_back 1`。
- `test_selfopt_fallback`（so-11）：cheat 兩次（WriteDenied、沒 changed.json）→ 第三次 `SelfoptFallback`、外部 `extract tools/beat`、stage semi＋beat。
- `test_budget_selfopt`（18）：訓練預算只剩 2 次腦 → task budget 壓成 2、run BudgetSpent、樹只有 selfopt.json 變、下一個 verify BudgetSpent 退 2；剩 0＝不派工。
- `test_optimize_by_claude`（cc-4，optkit 檔；假 claude 新 mode `system`）：`--by claude` → 收了 system.txt、selfopt.json 記 by claude、180 token、$0.0123、usage 原行；policy 的 `selfopt.by` 也生效。
- 改的：`test_determinism`（7：agent 預設 < 1、JITTER=0 是 1.0、JITTER=1 更低）、`test_grad_assign`／`test_rollback`（14、16：epoch 0 不再設 JITTER=1；epoch 1 設 `STEADY`＝JITTER=0——這兩個驗分配／回滾機制，人寫的 beat 不接手假腦會抽樣的環節，寫在測試檔註解）、`test_train_whole`／`test_m7`（epoch 0 的 selfopt 抽了 close：writer semi、變動集合多 close 三檔＋旁檔、opt_log、selfopt.json）、so-4 的題目清單、`Round3T.test_optimize` 刪掉（選路優化器沒了，單元換成 13）。

變紅過一次（scratchpad `6b/red.py`：暫改 → 跑 → 還原、bytes 驗回原樣）：stage program 條件恆假 → 13 紅；verify 不放 `hard` → 9 紅（tie＝B 退 10）；假腦不用工具輸出 → 15 紅（epoch 1 就回滾）；rollback 不刪 created → so-8 紅；streak 恆 0 → so-11 紅；task budget 不壓 → 18 紅；cost_usd 不記 → cc-4 紅；say() 照 hint → 7 紅。

結果：`test_topdown_galtxt_a.py`＋`test_topdown_galtxt_a_optkit.py` 74 個綠；`proto8/tests` 全套 631 OK（skip 2）。

整條假腦（`max_epochs 4`）stdout 摘要（每步：挑誰 → 做什麼 → 下一個 verify 的判斷）：
- epoch 0 verify：score 3.602、determinism 0.663、on_brain 3。optimize（params epoch 1）：writer（agent，tools_share 0.17）→ selfopt extract，by node（6 次腦、0.8 s）→ 抽 close、accept 收 5 檔、stage → semi。
- epoch 1 verify：determinism 0.78（+0.117）、score 持平 → **weigh A（確定性升）**；梯度整筆給 tools/close。optimize：writer（semi，0.33）→ selfopt extract → 抽 open。
- epoch 2 verify：determinism 1.0（+0.22）→ **A（確定性升）**。optimize：writer（semi，tools_share 0.5）→ **stage program（外部）**。
- epoch 3 verify：score 4.109（+0.507、ok → good）、腦呼叫 −3.33、on_brain 3 → 2 → **A（評級升）**；close／open 各分 0.5。〔max_epochs 3 到這裡收工〕optimize：grader、train/weigh「這圈沒動作」→ writer（program）→ selfopt distill（by shell，8 次腦）→ 試蒸 lights 被 HeldOut、poster 收 → templates.distilled.json＋5 格。
- epoch 4 verify：分數不動、`hard.uncovered −1` → **A（難例接住了）**；hard.jsonl 的 poster 標 resolved_epoch 4、lights 仍未處理（held-out）。

下一步（步驟 7 人評／8 收尾／9 真腦）：真腦第 9 步用 `optimize --by claude`（或 policy `selfopt.by: claude`）至少跑一次 selfopt；gpt 那條的 $ 要另找（LiteLLM 的 spend 或照價目算）。§ 5.7 震盪、§ 4.3 候選工具排序鍵、`switch`／`hints` 動作沒做。README／code map 的 optimize 一節還是舊的選路描述（步驟 8 一起改）。

## 步驟 7：人評——配對挑樣本、匯入、優化器讀 untrusted（實作者，2026-10-25）

做了：
- `human/questions.json` 換成 § 8.2（tags 九個含「像套公式」、dims `反差／像柚葉／文筆`、`pair`）；source 註明 pair 的 A／B 方向。
- `train/rate.py` 的人評樣本整段重寫（§ 8.1）：槽＝pair-stage ×（set.json 的驗證題 Q16、cls-lights）×（agent、program）＋disagree 1＋hard 1，合計 ≤ 6；**追加不覆蓋**（已在 samples.json 的一字不動、只補空著的槽；檔壞＝不碰；沒新東西＝不寫檔）。pair 半邊＝最早一個寫手是那一階的驗證 epoch、pick 挑中那份；階從 `writer/stage.json.history` 來（驗證＝那次實際跑的階；訓練題＝上一個 epoch 判完留下的階，回滾算進去）。disagree＝各 epoch 驗證小格＋這個 epoch 訓練題、過護欄、`|反差 − 像柚葉| ≥ 0.33` 最大（場景題 ≤ 8 行）。hard＝這個 epoch 訓練題裡 `hard.jsonl` 有 TemplateMissing、沒 resolved、不是 held-out 的那題的挑中份。同題同字面不重複（不同題同字面照收：lights 與 poster 的 program 產出字面一樣——模板沒管小動作，正是要人看的）。
- 樣本欄位（網頁契約＝round3 § 16.1＋頂層網頁 scratchpad `rating/index.html` 實際讀的）：`id`、`team`、`round`、`question`、`scene{cast, place, event, style, intent, context(只有 fill), epoch, stage, pair_id}`、`lines`、`produced_by`、`auto_scores{val, total, tier1, tier2, dims, reason}`、`brain`、`why_picked`、`picked_at_epoch`。id＝`a4-<題>-<階>-e<epoch>-<份>`（例 `a4-q16-agent-e0-1`），不跟第三輪 `a-q01-writer-*` 撞。
- `human/import/`（`_entry`＋`_metainfo`，kind program、callers 0、人手叫）：ratings.json → `writer/human.json style:傲嬌`（多數決平手取較差、< 3 筆 none、tags 計數、dims 平均、comments、`by_stage`）；人評 dims 照 `dims.json` 的 `by` 分給量它的那棵：`grader/human.json dim:像柚葉／dim:文筆`、`tools/lint/human.json dim:反差`（`agreement`＝1 − 平均|人−自動|、`bias`＝平均(自動−人)、`counter_ratings`）；`train/weigh/ratings.json judge:accept` 只補 `counter_human_pairs／counter_confirmed／agreement／human_rated_at`（verify 的計數不動）、明細寫 `train/weigh/human.json`；`human/calibration.json`（cells 並排＋判讀、dims、judge、`untrusted`、notes：「模板太死」「評審太鬆」「判斷器反著選」）。SampleUnknown 每筆一行跳過退 0；RatingsBad 退 1 不寫；同 id 多筆取 rated_at 最晚；時間戳取人評最晚那筆（重跑一字不變）。
- `tools/lint/human.json`（新旁檔）＋`tools/lint/_metainfo` 加 `human_ratings $ref`。
- `train/common.py`：`untrusted()`、`drop_dims(obj, names)`。`train/optimize/_entry`：讀 untrusted → stdout 一行「人評說不可信的維度 …：這圈不當依據」（--dry-run 也印）、inline 給節點的先前結果拿掉那幾維（`dims.<名>` 與 dims 物件裡的鍵）、task.json 多 `untrusted`＋任務句一句。`_metainfo`（train、optimize、human）補 reads／children。

偏離／解讀：
- **「第一個 epoch 後 4 筆」照表改成 3 筆**：§ 8.1 標題說 4、表是 2＋2＋1＋1＝6——epoch 1 的 rate 只有 agent 階產出（Q16、lights 的 agent 半邊＋disagree），program 半邊與難例要寫手到 program 之後（整條 4 epoch 是 epoch 4 的 rate）才有。若 epoch 1 先塞第 4 筆，cap 6 會把 hard 擠掉。照表（較細）。真腦若寫手沒走到 program，pair 只有半邊（照樣交，pair_id 在）。
- **網頁沒有配對題**：頂層網頁一筆一張卡、只存 `{id, overall, tags, dims, comment, rated_at, team, round}`，`questions.json` 的 `pair` 它不讀（多的 key 忽略）；`why_picked` 的新值 `pair-stage`／`hard` 網頁的 WHY 表沒有，會顯示「挑這筆是因為：pair-stage」。import 的人評配對答案＝評分裡有 `pair`（A＝program 好、B＝agent 好、差不多）就照它，沒有就比兩筆 overall。**頂層若要並排顯示**：用 `scene.pair_id` 分組、`scene.stage` 標前後，WHY 表加兩條。`round` 填 4（第四輪；epoch 在 `scene.epoch`），第三輪的 `round` 是 epoch 編號——語意換了。
- **判斷器配對對哪一步**：一對跨好幾步（agent epoch 0 → program epoch 3），對 log.jsonl 裡 epoch＝program 那筆 scene.epoch 的那一步（殼拿掉那步）；判斷器選 A 時人說 A 或差不多都算對（規則就是「分沒掉就收」），選 B 只有人說 B 算對。
- **語域沒有人評**：§ 8.3 表列了 `tools/lint dim:語域`，但 § 8.2 的 dims 只有三個；import 照「人評有問、樣本 auto 也有」的交集算，語域不出現（要量就在 questions.dims 加它）。
- **「不拿那維度當依據」只做到優化器給節點的那一層**：優化器挑子樹本來就不看 dims（看 brain／token／determinism）；判斷器（weigh）的 diff 仍含那維——§ 8.3 寫的是「優化器」，判斷器的表只有人改，這圈不動。
- `test_rate`／`test_scope_guard`／`test_cell_hits_rate` 先放 `samples.json = []` 的寫法還成立（單元的假 score.json 沒有 drafts 檔＝挑不到、不寫）。

測試（§ 10 編號）：
- 新 `Round4HumanT.test_human_import`（19）：6 筆樣本、5 筆人評＋1 筆舊 id → stderr 只有 `SampleUnknown a-q01-writer-1`；writer `val` bad（ok／bad 平手取較差）、`by_stage` agent／program 兩格、tags 計數；`dim:像柚葉` agreement／bias 手算（4 筆）、`dim:文筆` 1 筆、`dim:反差` 在 lint 不在 grader、沒有 `dim:語域`；`judge:accept` verify 的計數不動、人評 1 對 0 確認（人說 B、判斷器 epoch 3 選 A）；calibration `untrusted` 只有像柚葉、「評審太鬆」、「模板太死」；重跑六個輸出 bytes 不變；加 `pair: 差不多` → 確認 1；三種壞 ratings → RatingsBad 退 1、一行、輸出不動。
- 新 `Round4HumanT.test_optimize_untrusted`（19 之二）：verify epoch 0 → 手放 calibration → `--dry-run` 印那行；真跑 → selfopt 的 task.json `untrusted ["像柚葉"]`、任務句、history 有反差沒像柚葉（不放 calibration 時 history 有 3 處像柚葉，scratchpad 驗過，不是空斷言）；`drop_dims` 單元。
- 改的：`Round3T.test_train_whole`（max_epochs 1：id `a4-`、scene 多三欄、pair-stage 兩個 agent 半邊 epoch 0＋disagree）、`Round4OptT.test_train_selfopt`（6 筆的順序與槽：前 3 筆 `picked_at_epoch 1`、後 3 筆 4；hard 那筆是 cls-poster、字面＝hard.jsonl 那行的 output）。

變紅過一次（scratchpad `s7/red.py`：暫改 → 跑 → 還原、bytes 驗回原樣）：多數決平手取較好 → 19 紅；不看 log 的 choice（恆確認）→ 19 紅；optimize 不拿掉不可信維度 → 19 之二紅；rate 覆蓋舊樣本 → 15 紅；rate 不挑 program 半邊 → 15 紅；id 用舊前綴 `a-` → test_train_whole 紅。

結果：`test_topdown_galtxt_a.py`＋`_optkit` 77 個綠；`proto8/tests` 全套 633 OK（skip 2）。真樹沒有 `human/samples.json`、`calibration.json`（測試都在 tree_copy）。

假腦整條（max_epochs 4）挑出的 6 筆：`a4-q16-agent-e0-1`（pair）、`a4-cls-lights-agent-e0-1`（pair）、`a4-q16-agent-e0-2`（disagree：反差 1.0 vs 像柚葉 0.667）、`a4-q16-program-e3-1`、`a4-cls-lights-program-e3-1`、`a4-cls-poster-program-e4-1`（hard）。

下一步：步驟 8 收尾（README 的 human/ 與 import、code map 加 `human/import/`、`tools/lint/human.json`——鐵律 3）；步驟 9 真腦跑完 `human/samples.json` 換真腦 6 筆交頂層（網頁原始檔在 scratchpad `rating/`，換樣本用新 id；頂層 WHY 表加 pair-stage／hard、要不要做配對並排頂層決定）。
