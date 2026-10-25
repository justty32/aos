# galtxt-a 交棒（第一任隊長 opus → 下一任，2026-10-25）

← [README](README.md)｜規劃 [plan/](plan/)｜經驗 [plan/lessons.md](plan/lessons.md)

第一任隊長 context 到約 30%（使用者 10-25「差不多30%的時候就該換手了其實」），在 round4 實作步驟 2 收尾處交棒。

## 分工與規矩（照舊）

- 隊長 opus：派工、核驗、收線、commit；**規劃＝fable**（Agent 工具 `model: "fable"`），實作派 opus，雜活 sonnet。一件事一個新 agent；長工 agent 到 30% context 就停、寫 notes、回報。
- 腦只用 LiteLLM `http://localhost:4000/v1` 的 gpt 系列（預設 `chatgpt-gpt-6-luna-low`），不用 claude 當腦。
- 不要看 `proto8/topdown/galtxt-b/`（乙隊，同題獨立做，給使用者比較兩次 fable 的拆法）。
- 只動 `proto8/topdown/galtxt-a/`、`proto8/tests/test_topdown_galtxt_a.py`、thinking 那一節、code map 自己那一列。
- 使用者人在外面、**不要等人評**；人評網頁由頂層做，我們只交 `human/samples.json`（≤ 6 筆、同一性格同一場景）與 `human/questions.json`，匯入程式用假評級測。
- 命名 C-54：計數 `counter_*`、上限 `max_*`、時間點 `<事>_at`。
- 有人 rmtree 刪掉過整棵 galtxt-a：刪除只准刪 `~/code/try/` 或 `/tmp` 下自己建的，先 assert 不在 repo 裡。
- commit 訊息繁中、結尾附使用者原話「我想看看fable的潛力」與日期 10-25、Co-Authored-By 兩行；推送 `git fetch origin && git rebase origin/main && git push origin HEAD:main`（使用者已授權）。

## 已做（git log 看 galtxt-a 的幾個 commit）

1. fable round1 由上而下拆（plan/round1.md）→ 實作跑通、真腦 Q01＋場景各一次（plan/round1-measure.md）。
2. metatable 收表 → fable round2 只看表做優化盤點（plan/round2-optimize.md）＋收攏方案（round2-collapse.md）→ 實作收攏：資料夾 25 → 14、深度 4 → 2，meta/collapse 工具、metatable --suggest，假腦前後逐檔一樣（round2-result.md）。
3. fable round3（評級→選路＋訓練迴圈＋優化器自評＋人評）→ 實作步驟 1～6（train/、writer-sol/、ratings 旁檔＋`$ref`、human/ 假腦樣本）。
4. 使用者改方向（單一性格單一場景、整棵樹最終不靠 LLM、樹中有樹、按子樹貢獻、結構化梯度、判斷器樹、錨）→ fable round4（plan/round4.md，取代 round3 § 12 的 7～9）。
5. round4 § 11 步驟 1 做完、步驟 2 做完並收尾（細節與偏離見 plan/round4-impl-notes.md）。

## 未做（照 plan/round4.md § 11）

- 步驟 1 的測試 1～3、7 還沒寫（§ 10）；現在 test_topdown_galtxt_a.py 29 個綠、proto8 全套 544 OK（skip 2）。
- 步驟 3 寫手三階（tools/beat、tools/voice、compose.py、stage.json、templates.json）。
- 步驟 4 rollup；5 梯度 diff＋判斷器樹 train/weigh；6 優化器照樹走＋distill；7 人評匯入；8 metatable／README／code map；9 真腦 4 epoch → plan/round4-measure.md、真腦 human/samples.json 推上去後 SendMessage 通知頂層（main）。
- 收線：thinking `proto8/thinking/2026-10-25-top-down.md` 文末加「甲隊：galtxt（galtxt-a）」一節（乙隊那節在上面）：開頭記使用者原文（全部逐字，見下）、fable 最後的拆法（樹＋每層理由）、刻意不拆的、實跑結果、優化盤點結論、`_metainfo` 格式缺口、反向收攏、round4 的結論（plan/round4.md § 12 草稿＋實測）、錨與漂移、「這輪沒有人評」、對 fable 拆法的評估。code map：`wf/workflows/common/code-map/proto8.md` 末尾乙隊那列下面加甲隊一列，指到新分檔 `code-map/proto8/10-topdown-galtxt-a.md`。驗證：repo 根 `cmake --build --preset default && ctest --preset default`、`python3 -m unittest discover -s proto8/tests`、`wf/tools/wf-lint.sh` broken=0（10-25 時有一個舊的 `impls/README → dcap` 壞連結不是我們的）。
- 最後白話回報頂層：做了什麼、fable 怎麼拆（簡圖）、對 fable 的評價、優化盤點重點、收攏併了哪些縮了哪些、`_metainfo` 缺什麼、測試、commit hash。

## 隊長對 fable 的觀察（寫 thinking 評估用）

- 拆得好：round1 切在「要不要腦」與資料形狀變化處；刻意不拆都有理由；`fs_needs` 這個自加 key 直接成了收攏判準；只看表那步誠實留下錯判再對照實測。
- 要人修的：round1 逾時算錯（外層 900 s < 三次寫手上限，違 P-36）、換題沒清舊草稿（第二題吃到第一題的草稿）、上限欄混了兩種意思；規劃檔都偏大（58～74 KB）；round4 自相矛盾一處（lights 既放模板又當 held-out，見 notes）。
- 收攏預測（round1 § 7）跟實際收攏結果大致吻合（猜 11 → 約 6，實際 25 → 14 含容器）。

## 使用者原文（10-25，逐字，給 thinking 用）

見 thinking 檔頂部「使用者原文」（頂層已逐條補上）；甲隊直接收到的另外幾句：
「差不多30%的時候就該換手了其實」「我人在外面，不方便評」「然後整棵樹的_metainfo收攏成一張表，不是一件好事，我想要的是一棵樹中有很多棵樹，嵌套再嵌套，這樣樹可以重複利用」「並且在進行改進時，_metainfo就是很好的依據。改進的時候可以只改進特定子樹。也就是根據各子樹的貢獻去做優化」「限縮角色設定，限縮故事背景。盡可能控制各種變量，然後我預期子樹會很深層...，因爲最終目標是讓整棵樹都不依靠LLM」

## 第二任隊長（opus，2026-10-25 接手）進度

- 步驟 3 寫手三階做完（commit 8343085e）；§ 10 測試 1、2、3、5、6、7、8 補齊。
- 頂層轉來使用者兩段新補（逐字，寫進 thinking 甲隊那節）：
  - 「場景條件，背景故事，人物設定，都可以用結構化來表示，也就是json，拆的愈散，後續愈方便。」→ fable 補充規劃 [plan/round4-data.md](plan/round4-data.md)（步驟 3b：資料拆成有 id 的格）。
  - 「理想情況是，如果那格是agent節點，那麼在我們進行優化時，就是額外給他相關工具包，跟他說請優化一些東西，並給予一些先前的執行結果，然後他就會自動去做。 其實就算不是agent節點也可以」→ fable 補充規劃 [plan/round4-selfopt.md](plan/round4-selfopt.md)（optkit 工具包、自我優化；步驟 6 改成 6a／6b；至少一個 agent 節點、一個純程式節點各自優化一次）。
  - 「在這套工具包尚未成熟前，可以先由claude code代勞，或是乾脆工具就是呼叫claude code cli」→ 6a 的 optkit 加一支主工具＝呼叫 `claude -p`（參考 proto8/ai_tools 的 aos-ai、proto8/demo/agent-fay、thinking 10-24 cli-tools／aos-ai），在 selfopt 的沙箱拷貝裡、cwd 設在節點、限輪數／時間，改完由 accept 白名單＋測試＋verify 判；這是「腦只用 gpt」的例外（只當優化工具，台詞樹的腦照舊 gpt）；token／花費記進優化器的旁檔。至少實跑一次，記：改了什麼、分數前後、有沒有越界。
- 順序：4 rollup → 3b 資料拆格（fable 建議放 4 之前；rollup 不碰資料格，先做無妨）→ 5 梯度＋判斷器 → 6a optkit → 6b 優化器＋自優化 → 7 人評匯入 → 8 收尾 → 9 真腦（含真腦 human/samples.json ≤ 6 筆、新 id，推上後回報頂層）。
- 已做：4 rollup（970b8e2c）、3b 資料拆格 5 檔 122 格（73d85912）、5 梯度＋weigh、6a optkit＋claude CLI 工具（1549138a）。6b 進行中。
- 隊長裁定：brain.nodes 只算實際會被叫到的節點（writer-sol 不算）；changed.json 兩種來源共用 `{source, action, subtree, files, created, cells}`；自優化預設走 gpt，`--by claude` 可改走 claude code（真腦步驟至少跑一次）。
- round4 § 13 待使用者裁定的，照 fable 推薦先做（頂層代定可翻案），列在 thinking 甲隊那節。
