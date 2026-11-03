← [入口](../proto8.md)｜涵蓋：`proto8/topdown/`（10-25 由上而下拆的總覽）、`proto8/topdown/galtxt-a`（甲隊）；乙隊 galtxt-b 在 [10-topdown-galtxt-b](10-topdown-galtxt-b.md)

### `proto8/topdown/`

同一題（galgame 台詞生成）兩隊獨立各做一棵樹，給使用者比較兩次 fable 的拆法（使用者 10-25「我想看看fable的潛力」）；本層只有兩個子資料夾，沒有自己的檔。結論在 [thinking 10-25 top-down](../../../../../proto8/thinking/2026-10-25-top-down.md)。

- `galtxt-a/`＝甲隊（下面）；`galtxt-b/`＝乙隊（見上面連結）。兩棵互不引用、各自有 README／HANDOFF／`plan/`。

### `proto8/topdown/galtxt-a/`

樹與評分在 [galtxt-a/README](../../../../../proto8/topdown/galtxt-a/README.md)；交棒與裁定在 [HANDOFF](../../../../../proto8/topdown/galtxt-a/HANDOFF.md)；拆法與理由在 `plan/round1～4*.md`（`lessons.md` 經驗）。每個資料夾有 `_metainfo`（JSON）。

- 頂層 `_entry`（`exec aos-loop loop.json`）、`loop.json`、`fsm.json`（idle→brief→write→check→judge→pick；五格是內嵌單子 `X.py`，cwd＝galtxt-a 根）。
- 五格：`brief.py`（認領題目，`data/`→`brief.json`＋`rules.json`）、`write.py`（黏合：開小格叫 `writer/`、收 `drafts/N.txt`）、`check.py`（叫 `tools/lint`→`checks.json`）、`judge.py`（過護欄的逐份叫 `grader/`）、`pick.py`（合分挑一份、寫 `out/`；挖空模式的正解只有它讀）；`cells.py`＝`data/` 結構化格的解析器（id＝JSON key 路徑），brief／pick／judge／`writer/compose.py` 共用。
- `idle/`（有題退 0、沒題退 10；寫手、評審、`train/weigh` 的 idle 都是指它的捷徑）。
- agent：`writer/`（agent-dan 形：`brain.py`、`act.py`、`compose.py`、`system.txt`、`fsm.json`、`loop.json`；`fsm.opt.json`／`loop.opt.json`／`system.opt.txt` 是自我優化時用；`stage.json` 固化階、`grad.json`／`rollup.json`／`ratings.json`／`human.json` 是梯度、子樹彙總、人評旁檔；`tools/beat`、`tools/voice` 是抽出的純程式工具，`tools/lint` 與 `tools/opt_*` 是捷徑；`tools.json`＝腦看得到哪些工具的 aos-tools 註冊檔〔10-29 起：`brain.py` 經 `aos-tools ls --json` 組 tools、再照 `stage.json` 篩，`act.py` 經 `aos-tools call` 叫；相對路徑 `tools/<名>`〕）；`writer-sol/`（寫手變體：程式與 prompt 全是捷徑，只有 `.env` 換模型，另有自己的 `ratings.json`、`human.json`、`tools.json`）；`grader/`（評審：沒有工具，回「分數：N」「理由：…」；`system.v1～v3.txt`，`system.txt`→v3，同樣有 `grad.json` 等旁檔）。
- `tools/lint/`（純程式：Tier 0 護欄＋Tier 1 語域；`check.py` 與寫手兩處叫）。
- `data/`（手抄自 corpus 的固化表，每張帶 source：`cast.json`、`places.json`、`samples.json`、`address.json`、`forbidden.json`、`styles.json`、`dims.json`、`hints.json`、`route.json`、`lint_switches.json`；`bench/` 挖空題含正解；柚葉×文化祭收攤教室拆成有 id 的格：`cast/`、`style/`、`place/`、`scene/`、`templates.json`＋`templates.distilled.json`，122 格）。
- `train/`（訓練迴圈，自成小 agent 形：`train.py` 跑訓練題、`rate.py` 收評級並挑人評樣本、`verify.py` 驗證題＋前後 diff＋叫 `weigh/` 判收或回滾＋寫 `grad.json`；`set.json` 題組、`budget.json`、`common.py`；`weigh/`＝判斷器第三棵樹〔agent-dan 範本，`rules.json`／`rules.py` 為假腦〕；`optimize/`＝優化器，挑子樹與動作、改動留 `params/changed.json`）。
- `optkit/`（自我優化工具包：九支 `opt_*`〔describe、history、read、edit、write、extract、try、test、note〕；`shell/` 純程式節點臨時配腦〔自己的 `tools.json` 登記九支 `opt_*`〕、`opt_extract` 抽新工具時順手登記進那棵的 `tools.json`〔白名單 `tools.json#/tools#append`〕、`run` 派工＋預算、`accept` 白名單＋錨 sha256＋`opt_test` 才搬回、`claude` 呼叫 claude code CLI〔沙箱拷貝、限輪數與花費、記 `usage.jsonl`〕；`budget.json`、`deny.json`、`tests.json`、`fake_opt.py`、`optkit_common.py`）。
- `human/`（`questions.json` 給頂層網頁、`import/` 把 `ratings.json` 併回並算校準）；`ratings.json`、`rollup.json` 是根的旁檔。
- `meta/`（這棵樹自己的工具：`metatable/` 收 `_metainfo` 成表並 `--suggest`、`collapse/` 收攏〔inline／unwrap／table／dedupe〕、`rollup/` 子樹彙總；`table-round*.md`、`suggest-round1.md` 每輪的表）。
- `plan/`（不是樹的一部分：`round1～4*.md` 規劃與結果、`round1-measure.md` 實測、`lessons.md`、`side-mcp.md`、`examples/` 題目範例）。
- 測試：`proto8/tests/test_topdown_galtxt_a.py`（端到端假腦、metatable／collapse／suggest、round3 路由與訓練、round4 結構化格、梯度與判斷器、優化器、人評匯入）、`test_topdown_galtxt_a_optkit.py`（樹契約與自我優化工具包，假腦／假 claude）。
