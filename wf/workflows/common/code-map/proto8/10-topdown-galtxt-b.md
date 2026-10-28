← [入口](../proto8.md)｜涵蓋：`proto8/topdown/galtxt-b`（10-25 乙隊：由上而下拆、galgame 台詞生成）

### `proto8/topdown/galtxt-b/`

樹與每格一句在 [galtxt-b/README](../../../../../proto8/topdown/galtxt-b/README.md)；拆法與理由在 `plan/round*.md`；結論在 [thinking 10-25 top-down「乙隊」](../../../../../proto8/thinking/2026-10-25-top-down.md)。每個資料夾都有 `_metainfo`（JSON）。

- 頂層 `_entry`（`exec aos-loop loop.json`）、`loop.json`、`fsm.json`（一圈六格 idle→brief→draft→check→judge→deliver，每格不是自己的回合就退 0）。
- `idle/_entry`（sh）；`brief/_entry`（python：認領場景、由 `tables/*.json` 的結構化格子〔一格一事實、id `<表>/<路徑>`；`events.json` 事件節拍〕組 `brief.json`＋`cells_used`）；`draft/_entry`（黏合：叫 `tools/director` 出 beat 表、`tools/plan_lint` 驗、再叫 `tools/writer` 寫稿）；`check/_entry`（叫 `tools/lint`→`check.json`）；`judge/_entry`（叫 `tools/critic`、合成 `score.json`；`benchmarks/q01.json`、`q08.json`）；`deliver/_entry`（寫 `out/<題名>/`、彙整 `measure.json`、清 stack）。
- agent／腦函數：`draft/tools/writer/`（agent-dan 形：`brain.py`、`act.py`、`fsm.json`、`loop.json`、`idle/`、`system.txt`、`.env`、`tools/lint` 捷徑）；`judge/tools/critic/`（round3 收攏成第 4 級：`_entry` 是 JSON 單子→`ask.py`；評分的尺，刻意凍結）；`draft/tools/director/`（round6 走完 agent→script→pure：`run.py` 叫 `tools/plan_template` 查 `plans.json`〔2×2 場景表＋default〕，表外降級照產、難例寫小格 `hard_cases.jsonl`；舊版留 `versions/v0_agent/`、`v1_script/`）；writer 抽出的 `tools/trim/`（純程式：旁白上限、感嘆號、口癖次數）；writer `act.py` 照可選的 `act_rules.json` 交稿前必叫工具、補漏參（訓練場 apply 寫，repo 樹沒有）。
- `lib/selfopt/`（自我優化工具包：read_self、read_runs、edit_self、extract_tool、run_self_test、note、claude_code〔`claude -p` 限節點資料夾〕；`guard.py` 擋越界與凍結節點；`host/` 給非 agent 節點臨時配腦）。
- 純函數：`lib/lint/`（稿子的 Tier 0／1 檢核，違規帶 `cell`；`check/tools/lint`、`writer/tools/lint` 是指它的相對捷徑）、`draft/tools/plan_lint/`（beat 表文法）；各有 `_tooldef.json`。
- `train/`（訓練迴圈，round4～5）：`set/`（固定場景：梅雨傍晚河鹿堂、主角＋宮澤柚葉〔傲嬌〕、進新書日；只動「誰先開口」×「第二組必提詞」兩個開關＝4 題）、`score/`（收一輪成果成 `rounds/<輪>.json`、結構化分數與多樣性）、`pick/`（主動學習挑 ≤6 筆送人評；`subtree_score` 按貢獻＋`λ_gain` 挑子樹）、`init/`（建訓練場 `tree/` 複本與 `tree_v0`／`critic_v0`）、`record/`（收難例、結構化 diff 梯度＋`gradient_share`、判斷器帳、`rollup.py` 子樹彙總）、`apply/`（白名單動作 teach／freeze_order／patch_act）、`optimize/`（一步提 2 條候選）、`arbiter/`（判斷器：單發腦函數，≥8 次固化成 `priority_rules.json`）、`score/drift.py`（漂移兩條線）。
- `human/`：`samples.json`（給頂層網頁的人評樣本）、`questions.json`（網頁要問的 tag／維度）、`import/`（把 `ratings.json` 併進 `produced_by` 資料夾 `_metainfo.ratings.human`、算 `calibration.json`）、`README.md`（契約）。
- `examples/`（q01、q08 場景 JSON）、`demo.sh`（假腦三段）。
- `plan/`（不是樹的一部分）：`metainfo_table.py`（`_metainfo` 收成表、`--measure` 並實測）、`aos-fold`（反向收攏原型：agent／link／layer／pack／verify）、`mcp/aos_mcp.py`（支線：把 _tooldef.json 資料夾攤成 MCP tools 的 stdio 原型）、`round*.md`、`optimize.md`、`mcp.md`、`lessons.md`、`runs/`（真腦實跑留存）。
- 測試：`proto8/tests/test_topdown_galtxt_b.py`（端到端假腦、lint／plan_lint 每條規則會紅、`_metainfo` 形狀、真腦案例連不上 skip）、`test_topdown_galtxt_b_fold.py`（aos-fold 五個子命令）、`test_topdown_galtxt_b_train.py`（train／human 假腦案例）、`test_topdown_galtxt_b_lifecycle.py`（節點生命週期：director 三階、難例、trim、關閉開關）、`test_topdown_galtxt_b_round6.py`（teach、梯度、判斷器、漂移、rollup、結構化場景）、`test_topdown_galtxt_b_selfopt.py`（自我優化工具包與越界防護，假腦／假 claude）。
