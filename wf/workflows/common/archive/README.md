# common/archive — 共享文檔封存索引

只准追加列。

| 檔名 | 封存日期 | 原因 |
|------|---------|------|
| [wait-user-2026-10-12/](wait-user-2026-10-12/README.md) | 2026-10-12 | 原 `wf/wait-user/`（WAIT_USER A 區 3～75 題分類檔＋digest）；使用者說舊帳清掉，全部結案 |
| `roadmap.md` | 2026-10-13 | 原 `wf/workflows/roadmap.md`（單檔工作流，沒有自己的資料夾所以放這裡）；現況停在 10-03 開 proto7，使用者 10-13 決定封存；open 進度改看 wf/SESSION-LOG.md |
| `code-map/inst.md`、`code-map/inst/` | 2026-11-03 | `core/inst` 逐檔 code map；程式已於 2026-08-30 刪除 |
| `code-map/tooljson.md` | 2026-11-03 | `core/tooljson` 逐檔 code map；程式已於 2026-08-30 刪除 |
| `code-map/llms.md` | 2026-11-03 | `core/llms` 逐檔 code map；程式已於 2026-08-30 刪除 |
| `code-map/proto5-lib.md`、`code-map/proto5-lib/` | 2026-11-04 | `proto5/lib` 逐模組 code map；`proto5/` 已於 2026-11-04 封存到 repo 根 `archive/`，使用者 11-04「從 code map 移掉」 |
| `code-map/proto7-2.md` | 2026-11-04 | `proto7-2/` 逐檔表位置；`proto7-2/` 已於 2026-11-04 封存到 repo 根 `archive/`，使用者 11-04「從 code map 移掉」 |
| `tick.md`、`routines.md`、`schedule.md` | 2026-11-05 | 原 `wf/workflows/` 單檔工作流（定期喚醒 flavor：心跳、常規事務、一次性行程）；靠甲代 `aos run`／`aos heartbeat`，清單是空的、十月起沒人跑，隨甲代封存（arch-refactor 方向題 7，使用者 11-05「七題都照推薦」）；要時在 proto8 用 daemon＋aos-tick 重做 |
| `wf-tick.md` | 2026-11-05 | 原 `.claude/commands/wf-tick.md`（`/wf-tick` slash 指令，tick 的薄殼）；同上一列一起封存，放這裡不放 `.claude/commands/` 底下以免仍被當指令載入 |
| `use-aos.md`、`add-subproject.md` | 2026-11-05 | 原 `wf/workflows/` 單檔工作流：教用甲代單一執行檔 `aos` 的子命令、在根 CMake 底下加 `core/`／`modules/` 小專案；甲代 11-05 整組封存到 repo 根 `archive/aos-v1/`（arch-refactor 方向題 1） |
| `code-map/build.md`、`code-map/tool.md`、`code-map/llm.md`、`code-map/agent.md`、`code-map/agent-lookup.md` | 2026-11-05 | 甲代（repo 根 `common/`／`app/`／`cmake/`、`core/tool`、`core/llm`、`core/agent`）逐檔 code map；11-05 夜架構大重構甲代整組封存（arch-refactor S4），code map 只留 proto8、逐檔表改由 `wf/tools/codemap_gen.py` 從檔頭生成 |
| `gotchas/02-core-loop投遞.md`、`gotchas/03-inst交接協定.md` | 2026-11-12 | 原 `common/gotchas/` 分檔，講甲代 `core/loop`、`core/inst`（`aos deliver`、`.runi`）；程式隨 `archive/aos-v1/` 封存、已不存在（03 自述「已作廢，留作歷史」），tidy 內容精簡「不存在的東西就刪掉」 |
| [spec/](spec/README.md)、[ideas/](ideas/README.md) | 2026-11-14 | 原 `wf/workflows/spec/`、`wf/workflows/ideas/` 兩個工作流整夾（入口 README 與各自的 `archive/`）；09-05 那代的舊規格與舊構想，已沒有現行內容，原位置只留一行轉址 README；現行規範在 proto8/docs/NORMS.md、CONVENTION.md，概念在 CONCEPTS.md（使用者 11-14 專區答「oldentry:archive」，reply cee70afc742361ba） |
| `team-model.md` | 2026-11-14 | 原 `wf/workflows/team-model.md` 改寫前全文（單檔工作流入口，沒有自己的封存夾所以放這裡；codex 隊員、terra、「隊長 commit、push」、每隊兩個 CLI 程序是舊隊形）；由改寫成只寫現行做法的同名檔取代（使用者 11-14 專區「q2:move」，kb-1114） |
| `dev-env.md` | 2026-11-14 | 原 `wf/workflows/dev-env.md` 改寫前全文（單檔工作流入口；只有「git 佈局」一節的 worktree 隔離、rebase、ff-merge 是舊做法，其餘照舊）；由改寫了那一節（只有一個 `main`、不開 worktree 分支，使用者 2026-11-03）的同名檔取代（同上） |
