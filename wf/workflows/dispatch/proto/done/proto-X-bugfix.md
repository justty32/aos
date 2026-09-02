# 任務：修 bug——試用 L1／L2 找到的 25 條 `bug`，repro 當回歸

> 交接書是唯一契約。發現在 [trial/findings-L1.csv](../../trial/findings-L1.csv)、[findings-L2.csv](../../trial/findings-L2.csv)（`kind=bug`），每條有 `trial/repro/<id>.sh`（現在全部 FAIL）。摘要在 [trial/README](../../trial/README.md)。

## 唯一目標

**25 條 `bug` 全部修到對應 repro 通過**，且 ctest 全綠、不改變其他行為。只修 bug；`awkward`／`spec-gap`／`cannot` 不碰（改進隊在做）。

## 團隊（你是 Opus 隊長）

codex ×4（`codex exec -m gpt-5.6-sol -C /home/lorkhan/repo/simple_tools/aos --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`；任務書寫「最終回覆即成品，另寫到 -o」）。**按小專案切線、不按 bug 切**：每條 codex 拿一組落在同一批檔的 bug（例如 loop／exec 那組：Ctrl-C 孤兒、every 裸 `aos` 的 PATH、投遞不喚醒；agent 那組：say 訊息被吃、init 建到祖先世界、`say --help` 當訊息、log 被竄改；tool／llm 那組…）。共用 working tree，**同檔的線循序**。隊長寫任務書、審 diff、跑 ctest＋全部 repro、commit；不親自寫實作。**在 main 做。**

## 工作

1. 先跑 `for f in wf/workflows/dispatch/trial/repro/*.sh; do bash $f; done` 建立基線（哪些 FAIL）；用主 repo 的 `build/bin/aos`（先重建）。
2. 把 25 條按檔案分組，寫進 `reports/X.md` 的分組表，再派線。
3. 每修一組：對應 repro 轉 PASS、ctest 全綠、其他 repro 不退化；把 repro 的核心斷言**搬進該小專案的 ctest**（不 sleep、不連外），repro 腳本留著。
4. 修法原則：最小、不改協定；**要改 PROTOCOL 或行為語意**（例如 every 該存絕對路徑還是 loop 注入 PATH）就在 `reports/X.md` 列選項＋建議、先選最簡單的做、標「隊長裁決」。
5. code map、README 同步；commit 可分組。

## 硬性限制

- 可改 `core/*`、`.gitignore`、code-map、`trial/repro/`（只可加註「已修於 <hash>」，不可改斷言）。**禁區**：`app/`、`reference/`、`docs/`、其餘 `wf/`、`ideas/`。
- `git add` 只加明確路徑、絕不 `-A`；不 push；不 load／unload LM Studio；不開 GUI；不用 wf-lint；DeepSeek key 只從環境變數。
- 改進隊 Y 同時在 worktree 改 `core/agent`（state／inbox／chat／contacts 進 prompt）——你在 `core/agent` 的修改**盡量小、局部**，方便它 rebase。

## 驗收（就這 3 條）

1. 25 支 `bug` repro 全部 PASS（`reports/X.md` 附逐條 PASS 輸出）；其餘 repro 不從 PASS 變 FAIL。
2. ctest 全綠，新增回歸案例數 ≥ 15。
3. `reports/X.md` 有分組表、每條 bug 的修法一句話、行為語意改動（若有）的選項表。

## 回報

最後一則訊息＝摘要（≤ 25 行）＋STATUS。

## 隊長裁決

（隊長追加）
