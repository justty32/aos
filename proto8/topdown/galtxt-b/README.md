# galtxt-b — 由上而下拆資料夾樹：galgame 台詞生成（乙隊）

`galtxt-b - 工作區 new/<題名>.json 的場景（兩人、一地、一事、意圖）→ out/<題名>/answer.txt 一小段 galgame 台詞＋score.json＋measure.json`

← [proto8](../../README.md)｜題目與使用者原文：[thinking 2026-10-25 top-down](../../thinking/2026-10-25-top-down.md)｜拆法與理由：[plan/round1.md](plan/round1.md)、[plan/round2.md](plan/round2.md)、[plan/round3-collapse.md](plan/round3-collapse.md)（反向收攏）、[plan/round4.md](plan/round4.md)（評級、結構化分數、訓練迴圈、人評）｜素材（只讀）：`~/repo/ai_core/sub_projs/galtxt`｜範本：[demo/agent-dan](../../demo/README.md)｜測試：`proto8/tests/test_topdown_galtxt_b.py`、`test_topdown_galtxt_b_fold.py`（plan/aos-fold）、`test_topdown_galtxt_b_train.py`（第 4 輪）

**跑**（先建 impls，見 [wf/workflows/testing.md](../../../wf/workflows/testing.md)）：

```sh
sh proto8/topdown/galtxt-b/demo.sh            # 假腦：q01 一稿過、q08 打回重寫、q01 再跑一次走 writer 自檢；印 out/、measure.json 與 stack 樹
export AOS_BRAIN_URL=http://localhost:4000/v1 # 真腦（LiteLLM，只用 gpt 系列；模型名在各 agent 的 .env）
mkdir -p ws/new && cp proto8/topdown/galtxt-b/examples/q01_河鹿堂讓書.json ws/new/ && aos-exec --ws ws proto8/topdown/galtxt-b
python3 proto8/topdown/galtxt-b/plan/metainfo_table.py --measure ws/out/*/measure.json   # 宣告 vs 實測的表 → plan/metainfo_table.{json,md}
# 反向收攏原型（round3）：先 --dry-run 看會做什麼，再做；收完拿收攏前的複本對照（抹時間欄後逐檔比 out/ 與 .stack/）
python3 proto8/topdown/galtxt-b/plan/aos-fold --dry-run agent 某 agent 資料夾 --script ask.py   # 也有 link、layer、pack；用法見檔頭
python3 proto8/topdown/galtxt-b/plan/aos-fold verify 收攏前的樹 proto8/topdown/galtxt-b --ws 空資料夾 --question proto8/topdown/galtxt-b/examples/q08_河鹿堂進新書日.json --env GALTXT_FAKE_BAD_FIRST=1
```

**輸入**：`new/<題名>.json`（形狀見 `examples/`：summary、place、season、time、cast 兩人、relation_level、event、intent、must_mention、nice_to_mention、lines、max_redrafts、benchmark；選填 style＝評級的 key，沒寫＝女角卡 type 的第一個，如「文靜」「傲嬌」「害羞」）。女角卡有三張：森下晴子（文靜）、宮澤柚葉（傲嬌）、木下柚葉（害羞，停用）；10-25 使用者限縮到單一性格單一場景，訓練只用宮澤柚葉。
**輸出**：`out/<題名>/answer.txt`（台詞）、`score.json`（0～6：Tier 0 護欄＋Tier 1 語域＋Tier 2 語意；第 4 輪起是結構化分數：`val` good／ok／bad、`style`、`dims` 護欄／語域／語意各 0～1，語意可長成 `{"val", "承接", "含蓄", "角色味"}`）、`check.json`（每稿的違規）、`measure.json`（這題的實跑數字：總時間、各格時間、各 agent 問腦次數與 token、幾圈、幾稿、幾張表、自檢幾次）；題目搬到 `done/`。
**量測**：director、writer、critic 每問一次腦在自己的小格寫一行 `$AOS_STACK/<agent>/llm.jsonl`（`asked_at`、`model`、`elapsed_ms`、`counter_tokens_*`、API 原樣的 `usage`），deliver 彙整成 measure.json（director、critic 是單發腦函數、小格沒有 trace.jsonl，各自的 `elapsed_ms` 拿 llm.jsonl 的加總代替）；`_metainfo` 只放宣告，實測不回寫（M7）。
**測試開關**（假腦）：`GALTXT_FAKE_BAD_FIRST=1` 第 1 稿故意寫壞（打回重寫那條路）；`GALTXT_FAKE_LINT=1` writer 先叫 lint 再交稿（自檢那條路）；`GALTXT_FAKE_BAD_PLAN=n` director 前 n 張表故意缺 B0（n＝2 會停在 `draft: PlanBad` 等人，關掉再跑從 draft 接著做）。

**樹**（每格一句；每個資料夾都有 `_metainfo`；→＝相對捷徑）：

```
galtxt-b/                 agent：aos-loop → fsm.json 一圈六格 idle→brief→draft→check→judge→deliver；每格「不是我的回合就退 0 什麼都不做」，靠 stack 裡的檔決定誰做事
  lib/                    這支程式自己的函式庫：被兩處以上叫的純函數（stdin 一份 JSON → stdout 一行 JSON，照 proto8/lib 的契約）
    lint/                 純函數：稿子的確定性檢核（Tier 0 格式、護欄關鍵詞、禁語、地點；Tier 1 稱謂階、感嘆號、口頭禪、句長、旁白數）→ violations
  idle/                   純程式：cur/ 或 new/ 還有場景就 0，沒有就 10
  brief/                  純程式：認領場景、查 tables/ 編成稿紙 $AOS_STACK/brief.json（固化階梯 1～3 級）
    tables/               資料：人物卡、稱謂階、地點卡、禁語、開場收尾、samples（別題的前後文當語料錨）、beats（beat 文法）
  draft/                  黏合，兩步：沒 plan.json 先叫 director 出 beat 表、plan_lint 驗（最多 2 次）；再叫 writer 照表寫一稿 → draft.json
    tools/director/       單發腦函數（第 4 級：_entry 是 JSON 單子 → ask.py）：問腦一次出 beat 表 JSON；被打回就同一小格接著聊
    tools/plan_lint/      純函數：beat 表的文法校驗（B0 B1 B2 B3+ (B4) B5 (B6) B7、蓋章前要拿書、必提詞有拍認領、拍數）→ violations（只有 draft 叫，round3 從 lib/ 搬回）
    tools/writer/         agent（照 agent-dan，loop→fsm idle→think→act）：問腦寫稿；同一小格再叫＝接著上一稿聊
      tools/lint          → ../../../../lib/lint（腦交稿前自檢，最多兩次）
  check/                  黏合：叫 tools/lint 拿 violations，算 pass／final，寫 check.json
    tools/lint            → ../../lib/lint
  judge/                  黏合：定稿後把稿子＋benchmarks/ 正解交給 critic，合成 score.json（0～6）
    benchmarks/           資料：corpus/評測 的抄本（正解只給 judge）
    tools/critic/         單發腦函數（第 4 級：_entry 是 JSON 單子 → ask.py）：問腦一次打語意分
  deliver/                純程式：寫 out/<題名>/（含 measure.json 彙整實跑數字）、題目 cur/→done/、清 stack
  examples/               範例場景 JSON（q01、q08）
  human/                  人評契約（samples.json 給人勾的 ≤ 6 筆、questions.json 網頁問什麼、ratings.json 網頁寫回）＋ import/（純程式：併進 _metainfo.ratings.human、寫校正表）；見 human/README.md
  train/                  訓練迴圈：set/（傲嬌 × 一個固定場景，兩個開關＝4 題）、init、score（含 drift）、record（含 rollup.py）、optimize、arbiter（判斷器）、apply、pick；見下方「生命週期與訓練迴圈」
  plan/                   規劃與盤點（不是這棵樹的一部分）：round1～3 的 md、metainfo_table.py（_metainfo 收表工具）、aos-fold（反向收攏原型）、
                          metainfo_table.{json,md}（宣告＋最近一輪真腦實跑數字）、runs/round2／round3/<題名>/（真腦 Q01、Q08 的 answer／score／measure）、
                          runs/round3/{tree_before,tree_after,verify}.txt（收攏前後的樹與假腦對照）、
                          runs/round4/（noise.md 同題重跑的雜訊、round0/ 六題基準、rounds/0.json）
```

一題的 stack 樹（＝呼叫樹，P-38）：頂層 `.stack/` 放 `brief.json`、`plan.json`、`draft.json`、`check.json`、`score.json`；小格 `director/`、`writer/`（裡面還有 `lint/`）、`critic/` 各有自己的 `ws/`、`history.jsonl`、`current.txt`、`llm.jsonl`，writer 是 agent 所以另有 `state.txt`、`trace.jsonl`；`lint/`、`plan_lint/` 是純函數的空小格。

## 生命週期與訓練迴圈（round6）

節點走 `agent → tools → script → pure`（`_metainfo.lifecycle`；director 已 pure、writer 是 tools＋trim 抽出）。訓練迴圈只改**訓練場的複本**（`$AOS_WS/tree/`），repo 的樹不被寫（P-15）。各格都是 `aos-exec --ws <訓練場> train/<格>`，`$AOS_STACK/round.json` 給輪數 `{"round": n}`；腦照呼叫者的 `AOS_BRAIN_URL`（沒給＝假腦）。一輪的順序：

| 步 | 格 | 做什麼 | 問腦 |
|---|---|---|---|
| 0 | `train/init` | 複製 tree/、set/；另存漂移錨點 tree_v0/、critic_v0/、v0_drafts/ 與判斷器複本 arbiter/（都只第一次） | 否 |
| 1 | （跑）| 每題一個工作區 `runs/<n>/<題>/<次>/`：`aos-exec --ws 它 <訓練場>/tree`，寫 `run.json {"code"}` | 台詞樹 |
| 2 | `train/score` | → `rounds/<n>.json`（每次一列、每題、每風格、合計、delta）＋`drift` 三條線（[drift.md](plan/runs/round6/drift.md)） | critic_v0 2 稿＋基準 |
| 3 | `train/record` | 難例收進 tree/、評級、量測（agent token、工具呼叫／漏參）、子樹彙總 `rollup`（[rollup.txt](plan/runs/round6/rollup.txt)）、上一步的梯度與 gain、判斷器的帳 | 否 |
| 4 | `train/optimize` | 提 2 條白名單候選（程式從 `_metainfo` 推，或 `proposals/<n>.json`）＋預期梯度 → 判斷器 `arbiter/` 挑 → `changes/<n>.json` | 判斷器 1 次 |
| 5 | `train/apply` | 照 `changes/<n>.json` 改 tree/：`teach`（難例→表）、`freeze_order`（交稿前必叫的工具）、`patch_act`（漏參自動補） | teach 才問 |
| 6 | 回到 1（n+1） | record 在 n+1 算 changes/<n> 的實測梯度、判斷器這一判的對錯 | |

另：`train/pick`（人評樣本、挑子樹的 pick_rule＋λ_gain）。子樹彙總也能單獨印：`python3 train/record/rollup.py <樹根>`（不寫）。示範與數字：[measure.md](plan/runs/round6/measure.md)（director 換階、抽 trim）、[teach.md](plan/runs/round6/teach.md)（難例→teach→梯度）、[arbiter.md](plan/runs/round6/arbiter.md)（一步兩條→判斷器→apply→驗證）、[drift.md](plan/runs/round6/drift.md)。
