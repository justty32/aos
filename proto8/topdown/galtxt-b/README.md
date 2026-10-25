# galtxt-b — 由上而下拆資料夾樹：galgame 台詞生成（乙隊）

`galtxt-b - 工作區 new/<題名>.json 的場景（兩人、一地、一事、意圖）→ out/<題名>/answer.txt 一小段 galgame 台詞＋score.json＋measure.json`

← [proto8](../../README.md)｜題目與使用者原文：[thinking 2026-10-25 top-down](../../thinking/2026-10-25-top-down.md)｜拆法與理由：[plan/round1.md](plan/round1.md)、[plan/round2.md](plan/round2.md)、[plan/round3-collapse.md](plan/round3-collapse.md)（反向收攏）｜素材（只讀）：`~/repo/ai_core/sub_projs/galtxt`｜範本：[demo/agent-dan](../../demo/README.md)｜測試：`proto8/tests/test_topdown_galtxt_b.py`、`test_topdown_galtxt_b_fold.py`（plan/aos-fold）

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

**輸入**：`new/<題名>.json`（形狀見 `examples/`：summary、place、season、time、cast 兩人、relation_level、event、intent、must_mention、nice_to_mention、lines、max_redrafts、benchmark）。
**輸出**：`out/<題名>/answer.txt`（台詞）、`score.json`（0～6：Tier 0 護欄＋Tier 1 語域＋Tier 2 語意）、`check.json`（每稿的違規）、`measure.json`（這題的實跑數字：總時間、各格時間、各 agent 問腦次數與 token、幾圈、幾稿、幾張表、自檢幾次）；題目搬到 `done/`。
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
  plan/                   規劃與盤點（不是這棵樹的一部分）：round1～3 的 md、metainfo_table.py（_metainfo 收表工具）、aos-fold（反向收攏原型）、
                          metainfo_table.{json,md}（宣告＋最近一輪真腦實跑數字）、runs/round2／round3/<題名>/（真腦 Q01、Q08 的 answer／score／measure）、
                          runs/round3/{tree_before,tree_after,verify}.txt（收攏前後的樹與假腦對照）
```

一題的 stack 樹（＝呼叫樹，P-38）：頂層 `.stack/` 放 `brief.json`、`plan.json`、`draft.json`、`check.json`、`score.json`；小格 `director/`、`writer/`（裡面還有 `lint/`）、`critic/` 各有自己的 `ws/`、`history.jsonl`、`current.txt`、`llm.jsonl`，writer 是 agent 所以另有 `state.txt`、`trace.jsonl`；`lint/`、`plan_lint/` 是純函數的空小格。
