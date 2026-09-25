← [邊緣狀況 83 條：主編採納決定（2026-09-05）](../edge-decisions.md)（分檔 3/3）｜[上一份](02-逐條.md)

# 原型 FINDINGS（proto/FINDINGS.md）採納決定

## 主編裁（跨檔）

- **P1** 閒著／停法：同 X1，已做。
- **P2** 投遞裡 `prompt`／`result` 相對路徑基準＝投的人（`from`）那塊地的根；落點禁止指進任何 `.aos/`。同 X3；09 也明寫。
- **P3** 投遞 id 去重＝接力棒檔頭 `recent_ids`（05 已定，1000 筆先進先出）；**不另設** `.aos/inbox/.seen.json`。LLM 世界另靠 `.aos/requests/<id>.json` 去重。
- **P4** LLM 世界是**特殊 run**：daemon 對它起的是 `aos llm serve <地>` 不是 `aos run`；它跟 exec 搶同一把 `.aos/lock`；不用接力棒與三種步。登記表每筆多 `runner` 欄（`"run"`／`"llm-serve"`，預設 `run`）。`aos llm serve` 預設 `--every 200 --until never`。
- **P5** `.aos/stopped.json` 三個寫者、一個檔：exec 判串失敗時寫（`reason: failed`，`series`／`step` 填、細代碼放 `detail`）；run 開跑先刪、停時必寫（含 SIGTERM）、寫時把 exec 那份的 `detail` 帶進去；`--kill` 後 daemon 代寫 `killed`。schema 加可選 `detail`（字串）。
- **P6** `--until` 多一個值 `never`：閒著也不停、只等投遞或控制信，伺服器型的地用；`aos llm serve` 預設用它。
- **P7** 控制收件匣：處理過的信搬到 `.aos/control/done/`；run 開跑前把既有的控制信全搬到 `done/` 並印一行；`aos stop` 查不到有人在跑（登記表無 running 且 `.aos/lock` 無活 pid）就不投信、印「沒人在跑」。
- **P8** `.aos/lock` 內容 `{"pid":N,"pid_start":"…"}`；拿不到鎖時檢查持有者活不活，死了就收回（steal）；`aos stop --kill` 的第二個 pid 來源是鎖檔。
- **P9** `aos daemon add <地> --steps|--every|--until`：只登記成 `pending` 不開跑（補「登記與起時鐘是兩個動作」缺的那支）。`aos daemon stop` 對當時 `running` 的每筆設 `resume: true`；`aos daemon start` 起 `pending` 與 `resume: true` 的。schema 加 `resume`（布林）。
- **P10** 被起的 run `--register` 時登記表已有那筆就只更新 `pid`／`pid_start`／`state`，禁止改 `clock`／`budget`。
- **P11** daemon 對自己起的子行程要收屍（`SIGCHLD` 或 `waitpid(WNOHANG)`），殭屍不算活。
- **P12** `select` 指的檔不在或第一行空＝那一步失敗 `bad_select`，禁止悄悄走 `then`。
- **P13** 同步 `call` 步的呼叫記錄只在第一次進入那一步時寫一筆；串物件多 `calls`（物件：步名→call id）與 `await_ticks`（物件：步名→已等格數）兩欄，離開該步時清掉。
- **P14** 從收件匣直接跑的 `inst`（不屬於任何串）：`AOS_SERIES` 設空字串、`AOS_FRAME`＝它的 `AOS_TMP`；不建 `frames/` 下任何東西。
- **P15** `env_inherit:false` 且 `path` 空時，PATH 保底 `/usr/bin:/bin`。
- **P16** `exclusive` 同組先後＝接力棒陣列順序；建議實作把上一格被延後的串排前面，避免餓死。
- **P17** 帳簿多 `tokens_source`（`"reported"`／`"estimated"`）；`outcome` 列舉定死：`ok`、`backend_error`、`queue_timeout`、`rejected`、`result_unknown`、`killed`。`max_parallel`＝一格內派給該單元的筆數上限；`max_wait_ms` 從投遞物的 `at` 算起。
- **P18** `endpoint` 保留三個假後端 scheme 給測試：`echo:`、`fail:<原因>`、`slow:<毫秒>`；實作必須支援、測試不准打網路。
- **P19** `aos llm serve` 的退出碼只講程式有沒有跑起來；個別請求寫壞＝該請求 `rejected` 狀態檔，不影響退出碼。不採納「請求寫壞回 2」。
- **P20** `tools` 欄不改名，但明寫：它是塞進 prompt 的純文字行，不是後端的 function calling。
- **P21** `.aos/requests/<id>.json` 記錄要把原始投遞物整份放在 `request` 欄裡，處理完不刪原文；**不採納** `.aos/llm-done/`。
- **P22** 指令面糖：`aos llm ask "<文字>"`（把字落成 `$AOS_HOME/.aos/ask/<id>.prompt`、結果 `<id>.out`）；`aos publish <落點> --from <檔>|--fail <reason> [--message]`（照 B14 原子發布結果檔或狀態檔，給 shell 腳本用）；`aos status` 印停止原因、收件匣待處理數、在等哪些落點；`aos status --triple <落點>` 印三態。
- **不採納**：`.aos/llm-done/`（用 requests/ 代替）、`.aos/inbox/.seen.json`（用 recent_ids）、「原稿＝模板不拆平」（03 已定拆平規則）、`stalled` 原因代碼（X1 之後不需要：在等就不停）、`aos init` 連子地一起建（放）、多個 LLM 世界的帳簿欄（放）、`tools` 改名（放）。

統計：FINDINGS 前五條全採（1 已做、4 新增）；刻意偏離表 12 條：採 8、以別的方式解 2（seen.json→recent_ids、llm-done→requests）、不採 2（請求寫壞退出碼、不拆平）；其餘逐條採 P8～P22 共 15 組。
