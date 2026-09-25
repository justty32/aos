# 2026-09-25 lib 拆檔審查（b1087729..871bd5ce）

拆了什麼：main 上 20 個 commit，把 `proto5/lib/` 下 19 支母模組拆成母模組＋子模組（共 145 支 .py；原任務書寫 24 支，astra 逐 commit 數是 19 支＋1 個文件 commit），另把 `lib/README.md`（677 行）拆成入口＋ `lib/docs/` 八份（directives／exec／daemon／kernel／agent／team／company／tests）。號稱純結構搬移、零行為變更。

審查：codex CLI 叫 gpt-6-astra，唯讀沙箱，328 秒、78k tokens。完整輸出見 [review-astra.md](review-astra.md)（末尾附原 prompt）。

astra 結論摘要：
- **必修：0 條。** 19 支母模組與全部 145 支模組逐支 import 都過；外部用到的名字、既有 `patch(...)` 目標、函式本體／預設參數、模組層級副作用順序都沒漏；各家族內沒有載入時會炸的循環（跨家族反向引用都在函式內延遲 import）。
- `Post` 的 MRO 實測 `Post → _PostJobs → _PostWatch → object`，mixin 用到的 self 屬性都由 `Post.__init__` 建、互相呼叫的方法都由 `Post` 提供。`aos_market_score`／`aos_company_config` 重複的 `LIB` 值與母模組相等；`aos_directives_edit_persona` 重複 `sys.path.insert` 只多一筆同路徑、不改解析順序。`aos_team_verify` 的 CHECKS 六條字串全解析得到。
- docs：七家族 6＋11＋6＋13＋44＋54＋11＝145 支全對得上、13 個舊 `##` 錨點都有 `<a id>`。
- **建議：4 條**（不影響行為）：(1) 母模組再匯出不會轉接子模組 globals，日後若要 patch `check_result`／`JOB_TIMEOUT`／`update_section`／`load` 得 patch 子模組（目前 repo 沒人這樣 patch，我用 grep 再確認過一次）；(2) `aos_directives_edit_persona.py:11` 與母模組重複的 `sys.path.insert` 可去重；(3) `docs/agent.md:69` 寫「九個子命令」，實際 parser 是 19 個（我用 `_parser()` 數過）；(4) `docs/daemon.md:16` 段落寫「五支」，實際六支（漏 `aos_daemon_ticks`；頁首與家族表已是六支）。

我這邊的驗證：必修 0 條，無可驗；建議 (1)(3)(4) 已驗證成立（見上括號）。astra 的沙箱沒有可寫暫存目錄、跑不了測試（2621 errors 全是這原因），所以我在主 repo 補跑一次 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5/lib python3 -m unittest discover -s proto5/lib/test`：2874 條、216 秒、**1 failure**——`test_agent_fix_r5.FixR5Tests.test_short_old_error`，原因是我把 TMPDIR 指到很長的 scratch 路徑、status 一行截斷了路徑，不是拆檔問題；改用預設暫存目錄單跑該條就 OK。等於全綠。

沒動 `proto5/lib/` 任何檔，沒 commit、沒 push。
