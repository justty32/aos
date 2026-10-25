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
