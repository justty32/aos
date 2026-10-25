← [入口](../proto8.md)｜涵蓋：`proto8/topdown/galtxt-b`（10-25 乙隊：由上而下拆、galgame 台詞生成）

### `proto8/topdown/galtxt-b/`

樹與每格一句在 [galtxt-b/README](../../../../../proto8/topdown/galtxt-b/README.md)；拆法與理由在 `plan/round*.md`；結論在 [thinking 10-25 top-down「乙隊」](../../../../../proto8/thinking/2026-10-25-top-down.md)。每個資料夾都有 `_metainfo`（JSON）。

- 頂層 `_entry`（`exec aos-loop loop.json`）、`loop.json`、`fsm.json`（一圈六格 idle→brief→draft→check→judge→deliver，每格不是自己的回合就退 0）。
- `idle/_entry`（sh）；`brief/_entry`（python：認領場景、查 `tables/*.json` 編 `brief.json`）；`draft/_entry`（黏合：叫 `tools/director` 出 beat 表、`tools/plan_lint` 驗、再叫 `tools/writer` 寫稿）；`check/_entry`（叫 `tools/lint`→`check.json`）；`judge/_entry`（叫 `tools/critic`、合成 `score.json`；`benchmarks/q01.json`、`q08.json`）；`deliver/_entry`（寫 `out/<題名>/`、彙整 `measure.json`、清 stack）。
- agent／腦函數：`draft/tools/writer/`（agent-dan 形：`brain.py`、`act.py`、`fsm.json`、`loop.json`、`idle/`、`system.txt`、`.env`、`tools/lint` 捷徑）；`draft/tools/director/`、`judge/tools/critic/`（round3 收攏成第 4 級：`_entry` 是 JSON 單子→`ask.py`）。
- 純函數：`lib/lint/`（稿子的 Tier 0／1 檢核，`check/tools/lint`、`writer/tools/lint` 是指它的相對捷徑）、`draft/tools/plan_lint/`（beat 表文法）；各有 `tool.json`。
- `train/`（訓練迴圈，round4～5）：`set/`（固定場景：梅雨傍晚河鹿堂、主角＋宮澤柚葉〔傲嬌〕、進新書日；只動「誰先開口」×「第二組必提詞」兩個開關＝4 題）、`score/`（收一輪成果成 `rounds/<輪>.json`、結構化分數與多樣性）、`pick/`（主動學習挑 ≤6 筆送人評）。
- `human/`：`samples.json`（給頂層網頁的人評樣本）、`questions.json`（網頁要問的 tag／維度）、`import/`（把 `ratings.json` 併進 `produced_by` 資料夾 `_metainfo.ratings.human`、算 `calibration.json`）、`README.md`（契約）。
- `examples/`（q01、q08 場景 JSON）、`demo.sh`（假腦三段）。
- `plan/`（不是樹的一部分）：`metainfo_table.py`（`_metainfo` 收成表、`--measure` 並實測）、`aos-fold`（反向收攏原型：agent／link／layer／pack／verify）、`mcp/aos_mcp.py`（支線：把 tool.json 資料夾攤成 MCP tools 的 stdio 原型）、`round*.md`、`optimize.md`、`mcp.md`、`lessons.md`、`runs/`（真腦實跑留存）。
- 測試：`proto8/tests/test_topdown_galtxt_b.py`（端到端假腦、lint／plan_lint 每條規則會紅、`_metainfo` 形狀、真腦案例連不上 skip）、`test_topdown_galtxt_b_fold.py`（aos-fold 五個子命令）、`test_topdown_galtxt_b_train.py`（train／human 假腦案例）。
