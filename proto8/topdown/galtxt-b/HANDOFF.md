# galtxt-b 隊長交棒（10-25，opus 隊長 → 新隊長）

← [README](README.md)｜任務書（原隊長的）：scratchpad 的 `team_b.md`（內容摘要在下）｜使用者原文：[thinking 10-25 top-down「乙隊」](../../thinking/2026-10-25-top-down.md)｜實作者交接：[plan/handoff-B.md](plan/handoff-B.md)｜經驗：[plan/lessons.md](plan/lessons.md)

使用者 10-25「注意context有沒有滿，可能的話抓個大斷落重開隊伍」「差不多30%的時候就該換手了其實」——原隊長 context 到約 30%，在 B 段中途交棒。

## 任務書要點（原隊長收到的）

- 隊長＝opus：派工、核驗、收線、commit；規劃＝fable（Agent model "fable"，每輪拆法存 `plan/round*.md`）；實作誰都可；腦只用 LiteLLM `http://localhost:4000/v1` 的 gpt 系列（luna-low），不准 claude 當腦。
- **不要看 `proto8/topdown/galtxt-a/`**（甲隊，同題獨立做），派出去的每個 agent 也要交代。只動 `galtxt-b/`、自己的測試檔 `proto8/tests/test_topdown_galtxt_b*.py`、thinking 那一節、code map 那一份（`wf/workflows/common/code-map/proto8/10-topdown-galtxt-b.md`）。
- 交付：原型能跑＋README＋測試（假腦能過、真腦另記）；`_metainfo` 優化盤點；thinking 文末「乙隊」一節只寫結論（題目、fable 最後拆法、刻意不拆、實跑、優化盤點、`_metainfo` 缺口、對 fable 的評估）；驗證＝repo 根 `cmake --build --preset default && ctest --preset default` 全綠、`python3 -m unittest discover -s proto8/tests` 全過、`wf/tools/wf-lint.sh` broken=0（現有唯一 broken 是 `proto8/impls/README.md → ../../../dcap`，worktree 路徑造成，非本隊）；commit 繁中、結尾附「我想看看fable的潛力」與 Co-Authored-By／Claude-Session 兩行；`git fetch origin && git rebase origin/main && git push origin HEAD:main`（已授權）。
- 最後白話回報：做出了什麼、fable 怎麼拆（簡圖）、評價、優化盤點重點、收攏併／縮了哪些、`_metainfo` 缺什麼、測試結果、commit hash。

## 已做（都已 push；最後一個 commit 見 git log）

| 輪 | 誰 | 結果 |
|---|---|---|
| round1 | fable（拆＋自建骨架＋真腦一題） | 一圈六格 idle→brief→draft→check→judge→deliver |
| round2 | fable 規劃、opus 實作 | director（beat 表）→plan_lint→writer（自檢 lint）；`_metainfo` 收表 `plan/metainfo_table.py`；真腦 Q01 6、Q08 4 |
| round3 | fable（只看表的 `optimize.md`＋`round3-collapse.md`）、opus 實作 | director、critic 縮成單發腦函數；plan_lint 搬回；`plan/aos-fold` 原型 |
| 支線 | opus | `plan/mcp.md`＋`plan/mcp/aos_mcp.py`（MCP 原型，跑過） |
| round4 A | fable 規劃、opus 實作 | 限縮到單一性格單一場景（宮澤柚葉傲嬌、梅雨傍晚河鹿堂進新書日、2 開關 4 題）；結構化分數；`train/score`、`train/pick`；**人評樣本已交頂層**（`human/samples.json` 6 筆，網頁 https://claude.ai/artifact/ENDqGGkxBpydhsh6YcxGT9 ）——**場景與樣本已凍結，不可再改** |
| round5／6 | fable | 子樹對外描述五區、按貢獻挑子樹、固化；節點生命週期、難例、結構化梯度、判斷器樹、錨 |
| B 段前半 | opus | director 走完 agent→script→pure（`versions/` 留前版）、writer 抽 `trim`、五區宣告部分、五個關閉開關 |

## 未做（下一步）

1. **派新的實作者**（一件事一個新 agent）照 `plan/handoff-B.md` 的「未做」1～6 繼續（round6 §7 的順序）。真腦預算 B 段 ≤ 60 萬 token，已花約 4～6 萬（全套測試的 `test_q01_real`）。**這輪沒有人評**（使用者在外面），只用自動評分＋外部錨；人評之後由頂層轉 `human/ratings.json`。
2. 實作者回來後核驗：跑假腦 demo 與測試、看真腦數字合不合理。
3. **寫 thinking「乙隊」一節的結論**（現在只有使用者原文＋中途結論）：要補的題目見下節。
4. code map 跟著補新檔；驗證三件；commit＋push；白話回報給頂層。

## thinking 結論要答的題（頂層轉來、使用者要的）

- 子樹對外描述怎麼從下層彙總（誰算、何時更新）、重複利用時怎麼帶、跟六級／收攏怎麼接。
- 貢獻怎麼量、準不準、跟反向傳播像／不像。
- 哪些子樹已固化（0 token）、哪些還靠腦與為什麼、固化前後分數、下一步最該固化哪棵。
- 節點換階判準；接不住的輸入（照 ML：降級照產＋難例＋下輪補）。
- 梯度＝`_metainfo` 同形 diff；非數值怎麼比（判斷器樹）；判斷器／優化器／台詞樹三樹關係圖。
- 塔：第 N 層的成果是什麼、成本怎麼乘、雜訊；自我參照會壞在哪（round4 §4e 已有推論）。
- 錨：森林接到哪些錨、哪些沒有、有沒有看到漂移。
- 評分結構怎麼長、誰決定細化；人評多少才夠、怎麼挑（round4 §6d）；標明「這輪沒有人評」。
- 對 fable 的評估（見中途結論與 lessons）。

## 坑

- worktree 隔離會擋 `cd X && …`、heredoc、`$變數` 當參數等複合指令；寫腳本到 scratchpad 再 `sh 腳本`／`python3 腳本`。
- impls 要先建（`wf/workflows/testing.md` proto8 段）；main 上有新 commit 改了 C++ 時 rebase 後要重建。
- main 途中改過命名：計數 `counter_*`、時間點 `<事件>_at`、上限 `max_*`；`_metainfo` 通用 key 照 10-24 原樣。
- 長工 agent 的 context 到約 30% 就要它寫交接、換新的。
