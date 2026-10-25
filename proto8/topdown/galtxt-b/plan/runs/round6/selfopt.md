# round6 自我優化：工具包＋三次示範（真腦，10-25）

← [round6 §1b](../../round6.md)｜程式 [lib/selfopt/](../../../lib/selfopt/_metainfo)｜留檔 [selfopt/](selfopt/)（各 session 的 report.json、對話 history.jsonl、`runs.*.json` 每次一列、`changes_1.*.json` 梯度、重跑腳本 `demo.py`（gpt 兩次）與 `cc.py`（claude_code），路徑寫死成這個 worktree 的 scratchpad）｜測試 `proto8/tests/test_topdown_galtxt_b_selfopt.py`（假腦、假 claude，14 個）

使用者 10-25：「理想情況是，如果那格是agent節點，那麼在我們進行優化時，就是額外給他相關工具包，跟他說請優化一些東西，並給予一些先前的執行結果，然後他就會自動去做。 其實就算不是agent節點也可以」；後補：「在這套工具包尚未成熟前，可以先由claude code代勞，或是乾脆工具就是呼叫claude code cli」。

## 工具包（`lib/selfopt/`；放 lib 是因為任何節點都能掛，不屬於某一格）

| 工具 | 做什麼 | 示範裡用到 |
|---|---|---|
| read_self | 讀自己：_metainfo、哪些檔可改、system.txt、規則表、難例（含上層記的，例 plan_template 的難例在 director）、剩餘預算 | gpt writer、plan、plan2 |
| read_runs | 讀先前每次跑：分數、違規、token、這個節點的用量與叫工具順序、ArgumentsBad 次數 | gpt writer、plan、plan2 |
| edit_self | 改白名單檔（system.txt、*.json）：照字面替換、`set`（JSON 指標）或整份；寫前存 `versions/selfopt_<session>/` | gpt writer（成）、plan（TextMissing）、plan2（set，成） |
| extract_tool | 抽純程式工具（規則表殼 `rules_shell.py`）＋system.txt 加一句＋lifecycle 記一筆 | 沒用到（只測試） |
| run_self_test | 用改過的自己跑整棵樹一題，分數由凍結的量尺（check、judge）打 | gpt writer（真腦 1 次） |
| note | 寫回 `lifecycle.history` 一筆 | gpt writer；plan、plan2 預算用完沒叫，host 收工補記 |
| claude_code | 主要工具：整件交給 `claude -p`（cwd＝節點複本、只給 Read/Glob/Grep/Edit/Write、acceptEdits），事後比對整棵 tree，越界還原 | writer（sonnet） |

邊界全由程式擋（`guard.py`）：寫入只限 `tree/<node>/`（解開捷徑後）；凍結＝lib/lint、lib/selfopt、judge、check、human、train、`_metainfo` 標 frozen 的、tests；白名單外（`_metainfo`、`*.py`、fsm／loop、.env、hard_cases、versions/）拒寫；三種都記 `attempted_violation`。預算：`max_calls`、`max_tokens`（host 問腦前檢查，用完就不再問、直接收工）、claude 的 `max_usd`／`--max-turns`／`--max-budget-usd`。
掛法：`lib/selfopt/host/`（agent-dan 形）。agent 節點（writer）＝system 是 host 的「優化模式」說明＋它自己的 system.txt、模型照它的 .env；非 agent 節點（選 plan_template：表驅動、有現成難例；trim 6 次 0 改字，沒東西可優化）＝同一個 host 臨時配腦。不碰 writer 的 act.py／brain.py。

## 怎麼量

訓練場（scratchpad，`train/init` 的 tree 複本）。改前＝第 1 輪：round6 measure 的 trim_after 6 次真腦＋teach/round1 舊車票 1 次，**匯入、不重跑**（樹相同）。改後＝第 2 輪，`train/score`＋`train/record` 算梯度。舊車票題的難例用假腦跑一次得到（director 是純程式，0 token）。

## 數字

| | 動作 | 第一題 總分 | 根 token／次 | writer token（問腦次數） | 違規 | 優化本身花費 |
|---|---|---|---|---|---|---|
| 改前（第 1 輪，3 次） | — | 5、5、5 | 20174 | 16.5k（3：lint、trim、交稿） | 0/3 | — |
| **gpt 自我優化 writer** | system.txt 7、8 條：明寫 brief_path、lint 沒違規就直接交、**拿掉 trim** | **4、5**（平均 4.5） | 19933、13804（平均 16869，−16%） | 16.4k（lint、lint）、10.2k（lint） | **1/2**（narration_max，旁白 5 行） | 29770（4 次問腦）＋自測 19933 |
| **Claude Code 優化 writer** | 新增 `act_rules.json`：trim 改成交稿後程式一律跑（freeze_order）、lint 漏 brief_path 程式補（patch_act）；system.txt 7、8 條 | **5**（1 次） | **13631（−32%）** | 10.1k（2：lint、交稿；trim 由程式跑，0 改字） | 0/1 | $0.104（sonnet，8 輪，24 秒） |

plan_template（非 agent，目標「消化 hard_cases：主角|舊車票」）：

| session | 叫了 | 結果 | 花費 |
|---|---|---|---|
| plan | read_self、read_runs、edit_self（edits）、read_self | **TextMissing**：腦看到的是 read_self 解析過的 JSON，猜錯原檔縮排；預算（1.5 萬）用完、沒改成 | 19202 |
| plan2（edit_self 加了 `set` 之後） | read_self、read_runs、edit_self（`set /plans/主角|舊車票`） | 補一列 9 拍（抄「主角|梅花章」那列、B6 加舊車票）；預算 6000 第 2 次問腦就超、沒叫 note（host 補記） | 13289 |

驗證（0 token：director 是純程式，假腦跑整棵樹就驗得到表）：舊車票題 `degraded` 空、用的是 `plans.json#/plans/主角|舊車票`、plan_lint 過。梯度（`changes_1.gpt.json`）：plan_template `rollup.counter_rows` 4→5、`counter_degraded` 1→0，根 `ratings.傲嬌.counter_degraded` 1→0。分數沒測（舊車票題真腦要 2.5 萬，預算不夠）。

**越界**：三次真腦都沒有嘗試越界（attempted_violations 0；claude 的 permission_denials 0）。假腦／假 claude 的測試裡，越界、凍結、白名單三種都被擋住（claude 那邊是事後還原）。

**花費**：gpt（luna-low）共 **109,629**：writer session 49,703（含自測）＋plan 19,202＋plan2 13,289＋驗證 13,804＋13,631。超出份額 10 萬約 1 萬，原因是 plan 第一次失敗重跑、以及新加的 claude_code 示範要一次驗證。Claude Code $0.105（含一次 0.0006 的旗標探測）。

## 自我優化 vs 外部優化器（train/optimize＋arbiter）

- **gpt 自我優化會拆掉自己的保險。** 它照證據「trim 6/6 沒改字」把 trim 拿掉，自測就回來一條旁白超量（4 分），它在 note 裡自己寫了「未驗證分數持平」，可是改動還是留著。trim 沒改到字，是因為 lint 在前面先擋住了。它真正的作用是保險，這從平均數看不出來。外部優化器（apply 的 freeze_order）不會這樣改，因為規則是「留著當保險、只省來回」。
- **Claude Code 用了同樣的證據，結果比 gpt 自己改要好。** 它在樹裡找到了 act.py 已經支援的 `act_rules.json`（另一位實作者剛做的 freeze_order／patch_act），所以 trim 留著由程式跑，brief_path 也由程式補。token −32%、分數 5、違規 0。它做的其實就是外部優化器會提的那兩步，而且它是自己讀程式碼發現的。代價是要錢，也要信任它不越界。它的權限只給改檔、不給 Bash，事後再比對整棵樹還原越界；bwrap 沙箱這次沒綁上，因為 claude 要帳號設定、node、網路一起綁。
- **在 luna-low 上，工具介面比 prompt 重要。** plan 第一次失敗，是因為 edit_self 只能照字面改 JSON。加了 `set` 之後，第二次只問兩次腦就改成了。多輪對話每次都重送整段（每次 4～9k），所以 gpt 的 session 很貴：自我優化本身的花費（1.3～3 萬）跟跑一次樹（2 萬）同一個量級。
- **風險**：一是改壞自己（上面的 trim）。二是作弊：改量尺、改測試、改題目。這次由程式擋住，而且 critic、lint、judge、check 在 FROZEN 裡；外部打分一律用凍結的樹跑。三是自測拿到的是單次樣本，雜訊 σ 約 0.5。四是 note 的理由可能寫得好聽，但跟數字不符（gpt 這次倒是誠實寫了未驗證）。

## 建議

1. 預設**以 claude_code 為主**（工具包成熟前），gpt host 留著對照、也拿來做 plan_template 這種小而明確的表修補。不管哪一種，**改完一律由外部再跑 ≥ 2 次**，分數掉或違規回來就退回 `versions/selfopt_<session>/`。這一步還沒寫成程式，現在要手動。
2. 加一條「不准拿掉保險」：工具或步驟的貢獻要看關掉它時違規會不會回來（round5 §3a 的 ablation），不能只看它改了幾個字。拿掉某個工具之前，必須先有 ablation 的數字。
3. read_self 要縮：writer 的總覽一次就 6k 字，多輪對話時每輪都重送。
4. 還沒做：host 把結果寫進 changes（現在由 scratchpad 的 demo.py 寫 `changes/1.json`）；`run_self_test` 一次跑多次取平均；claude_code 綁 bwrap；extract_tool 的 agent 版；凍結清單改從 `_metainfo.frozen` 收集（現在一部分寫死在 guard.FROZEN）。
