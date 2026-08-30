# 任務：補兩個已裁決的缺口——step 走 lmstudio 也取槽；使用者是 agent、住 `~`

> 交接書是唯一契約。兩件都是使用者已裁決、前隊留下的缺口：排程 [reports/V.md](reports/V.md)「真實缺口」段；通訊錄 [ideas/tools/contacts.md](../../ideas/tools/contacts.md) 末段「使用者也是 agent」。

## 唯一目標

1. `aos agent step` 走 **lmstudio** 那條（直接呼叫 `aos::llm::complete()`）在打端點前取該 CPU 的槽，行為與 `aos llm` 子命令一致（priority 來自 `engine.json.priority`，沒有＝0；`aos agent init --priority N` 寫進去）。
2. **使用者＝agent，住 `~`**：`aos say` 的訊息帶 `from`（＝執行 say 的人所在世界的資料夾；不在任何世界時＝`~`）；`aos say --to ~ …` 投到 `~/.aos/`（沒有就建最小版面：`say/`、`log.md`）；在 `~` 下 `aos listen` 能讀到寄來的信；通訊錄 `aos contact ls` 天然顯示一格 `~`。

## 團隊（你是 Opus 隊長）

codex ×2–3（`codex exec -m gpt-5.6-sol -C /home/lorkhan/repo/simple_tools/aos --dangerously-bypass-approvals-and-sandbox -o <out.md> - < <task.md>`；任務書寫「最終回覆即成品，另寫到 -o」）；一位做 1、一位做 2、一位測試＋README＋code map。**在 main working tree 做**（L1／L2 在 worktree、docs 線只碰 docs/）。隊長寫任務書、審 diff、跑 ctest、commit；不親自寫實作。

## 硬性限制

- 可改：`core/agent/`、`core/tool/`（contacts 那一格）、`core/llm/`（只在必要時）、code-map。**禁區**：`core/exec`、`core/wire`、`core/loop`、`core/tick`、`reference/`、`app/`、`docs/`、其餘 `wf/`。
- `git add` 只加明確路徑；不 push；不 load／unload LM Studio；不開 GUI；不用 wf-lint；**不要真的在使用者的 `~/.aos/` 留東西**——測試用 `HOME` 指向暫存目錄。
- 最小原型、邊緣跳過、小裁決記「隊長裁決」。

## 驗收（就這 4 條）

1. build＋ctest 全綠。
2. `AOS_HOME=<tmp>`、`cpus.json` 設 `lmstudio: {max_inflight: 1, wait_ms: 100}`，兩隻 agent 同回合 step → 一隻成功、一隻 exit 75／status `waiting-llm`（假端點或真 LM Studio 皆可）。
3. `HOME=<tmp>`：在世界 W 裡 `aos say "hi"` → `say/*.md` 含 `from: <W 的絕對路徑>`；`aos say --to ~ "回報完成"` → `<tmp>/.aos/say/` 有檔且 `from` 是 W；`cd <tmp> && aos listen --once` 印出那句。
4. `aos contact ls` 第一列是 `~`。

## 回報

`reports/W.md`＋最後一則訊息摘要（≤ 20 行）＋STATUS。

## 隊長裁決

（隊長追加）
