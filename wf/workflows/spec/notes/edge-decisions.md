# 邊緣狀況 83 條：主編採納決定（2026-09-05）

來源：`/tmp/claude-1000/-home-lorkhan-repo-simple-tools-aos/48a05f71-7c0e-498c-9838-324c55dfb022/scratchpad/side/edge-cases.md`。
標記：**採**＝寫成條款（〔主編補〕）；**已**＝現有條款已涵蓋；**部分**＝採一半；**放**＝不動。

## 全域改動（影響多檔，主編裁）

- **X1（B01）通用停法改寫**：「這次 exec 沒產出新指令，**且沒有任何串停在 `await` 步或同步 `call` 步上**，才停」。停在這兩種步上的串叫「在等」。只剩在等的串時，run 每格之間睡 `--every`（沒給就 500 ms）。這是改一條已升格裁決，README 矛盾表列出、待拍板。→ 06 主寫，05 定義「在等」，10 引用。
- **X2（B02）脫節工作一律由 daemon 起**：取代主編裁 #6。沒有 daemon（登記表 `daemon_pid` 不在或死）時 `call async` 立刻失敗、寫狀態檔 `reason: no_daemon`。代價明寫：daemon 不在時新的脫節工作起不來、既有的照走。→ 07、08、README #6 改。
- **X3（B10／B24／B25／B26／B27／B28）結果落點的規矩**：落點由父以父地根為原點寫成絕對 realpath；必須在父地之內、不得在任何 `.aos/` 之內、不得以 `.status.json` 結尾；投遞前落點與狀態檔都不得已存在（存在＝解析拒絕）；同一格所有落點兩兩相異；請求裡的落點＝父對子（或 LLM 世界）開的一個明示寫入洞，只涵蓋那條路徑與它的 `.status.json`、`.usage.json`。→ 07 主寫，09 引用。
- **X4（B37／B11／S02）登記表狀態**：門房偵測出生登記成 `stopped`（`pid` null、`clock` null），不是 `pending`；daemon 只起 `pending`；週期鐘（`every`）的 run 退出後登記保留為 `stopped`、下次到期 daemon 重起；`once` 跑完刪登記；重啟時 `pending` 沒 `pid` 一律當沒起過。→ 08、13。
- **X5（B19／S06）LLM 世界的用量與設定**：結果落點旁多一份 `<結果落點>.usage.json`（`tokens_in`、`tokens_out`、`unit`、`ms`）；agent 每圈把它累加進自己 `.aos/usage.json`，上限對這個檔判，不讀家的帳簿。daemon 起 LLM 世界時把 `units` 表寫進 LLM 世界的 `.aos/units.json`，LLM 世界不讀家的設定檔。→ 09、10、02。
- **X6（B17／B18）daemon 永不刪父地上的結果檔與狀態檔**：取代 C-02 預設的「連結果一起清」。daemon 到期只刪脫節子地本身；刪之前若落點沒檔就代寫狀態檔 `reason: reaped`。期限仍用 `reap_after_ms`（牆鐘），因為 daemon 讀父的格數要跨地。→ 08、07。

## 逐條

| # | 決定 | 進哪檔 |
|---|---|---|
| B01 | 採（X1） | 06、05、10 |
| B02 | 採（X2） | 07、08 |
| B03 | 採：LLM 世界為每筆請求維護 `.aos/requests/<id>.json`（`queued`／`sent`／`done`／`failed`）；`aos status --request <id>` 查 | 09、12 |
| B04 | 採：不重送寫死；LLM 世界重啟把 `sent` 標 `failed` `reason: result_unknown`；agent 禁止自行重發 | 09、10 |
| B05 | 已（S-06-31） | — |
| B06 | 已（`.aos/lock`） | — |
| B07 | 採：登記表多 `pid_start`（該 pid 的啟動時間，讀 `/proc/<pid>/stat`），判活兩者都對 | 08 |
| B08 | 採：同一條串同一步連續失敗 3 次強制 `stopped`、`reason: repeat_fail`；計數在串的 `ext.fail_streak`，父腳本關不掉 | 06、05 |
| B09 | 採：`AOS_CALL_CHAIN` 環境變數帶鏈上 realpath；撞到自己或深度超過 8 就失敗 `reason: call_cycle`／`call_depth` | 07 |
| B10 | 採（X3） | 07 |
| B11 | 採（X4） | 08 |
| B12 | 採：run 決定停之後、放鎖之前再掃一次收件匣；門鈴收件人是 daemon，daemon 看該地沒 run 就重起 | 06、13、08 |
| B13 | 採：timeout 不可無限；格的上限＝各筆 timeout 最大值 | 06 |
| B14 | 採：結果檔與狀態檔一律暫存→fsync→rename→fsync 目錄；父只認正式名；解析失敗判壞、不重讀 | 07 |
| B15 | 採：暫存檔開在落點同目錄；禁止 copy 代替 rename | 07 |
| B16 | 採：非子行程走輪詢判死，5 秒一次 | 08 |
| B17 | 採（X6） | 08 |
| B18 | 部分（X6） | 08 |
| B19 | 採（X5） | 09、10 |
| B20 | 已（S-05-41） | — |
| B21 | 採：exec 在跑之前先寫 `.aos/ticks/<N>/started`；重啟時該格 `results/` 齊全就直接判成敗推游標，不重跑；不齊就該串 `stopped` `reason: crashed` | 06 |
| B22 | 採：`layout_version` 不合就拒跑退出 3；只准人工 `aos migrate`，第一版 `aos migrate` 只印訊息 | 02、12 |
| B23 | 採：寫落點前確認父地 `.aos/` 在；不在就放棄、登記表 `ext` 留一筆；禁止 mkdir | 07 |
| B24～B28 | 採（X3） | 07 |
| B29 | 已（S-08-48 代寫；`max_ticks`）；補「建議每個 `await` 都給 `max_ticks`」 | 07 |
| B30 | 已；補「落點不得以 `.status.json` 結尾」 | 07 |
| B31 | 已（傳輸層失敗一律失敗） | — |
| B32 | 已 | — |
| B33／B34 | 採：接力棒檔頭多 `recent_ids`（最近 1000 個收過的投遞 id）；重啟去重只在 `.aos/` 持久時成立 | 05、07 |
| B35 | 部分：寄件人解析不出就寫 `.aos/errors.log` 一行，不改檔名規矩 | 07 |
| B36 | 採：投遞絕不建目錄；目標沒 `.aos/` 就失敗回報 | 07、11 |
| B37 | 採（X4） | 13、08 |
| B38 | 採：`aos llm` 只准 LLM 世界用；工具登記表禁止登記它；`aos check` 擋 | 11、09 |
| B39 | 已（S-03-37）；補「父看到的是狀態檔 `reason: no_source`」 | 03、07 |
| B40 | 採：載入一律重編，不看 mtime；`.aos/program/` 檔頭記原稿 `source_hash` 只供 `aos status` 顯示 | 03 |
| B41 | 採：run 期間禁止讀頂層原稿任何位元組 | 06 |
| B42 | 部分：建議每格開頭 stat 自己的 `.aos/`，不在就停 | 06 |
| B43 | 部分：`layout.json` 多 `land_id`（init 時隨機）；登記表每筆帶 `land_id`；daemon 禁止自動改登記路徑；不做以 id 為主鍵 | 02、08 |
| B44 | 採：`aos mv` 連 `.aos/` 一起搬、游標保留，`layout.json` 的 `ext.moved_from` 記前身；是唯一例外 | 08、02 |
| B45 | 已（02 白名單表） | — |
| B46 | 已 | — |
| B47 | 採：LLM 世界 `.aos/requests/` 保留 `reap_after_ms` 後刪 | 09 |
| B48 | 採：控制收件匣在每格開頭、每筆指令的逾時輪詢、等待輪詢三個點讀；「停」最壞等一筆指令 timeout | 06、12 |
| B49 | 採：`--kill` 之後 daemon 代寫 `killed` 狀態檔、把 `ticks/<N>/` 留作現場；`aos fix` 預設把現場丟棄、`--requeue` 退回收件匣 | 12、08 |
| B50 | 已（stopped.json 一律寫） | — |
| S01 | 採：run 自成行程群組，停＝對群組送訊號 | 06、08 |
| S02 | 採（X4） | 08 |
| S03 | 採：`aos daemon stop` 正常關閉＝全停；`start` 印出接管幾個孤兒 | 08 |
| S04 | 採：`aos daemon exec` 帶 id，同 id 拒絕 | 08 |
| S05 | 已（09 自己數）；08 補「daemon 不數 LLM 併發」 | 08 |
| S06 | 採（X5） | 09、02 |
| S07 | 採：進 prompt 的信同格搬到 `.aos/mail/read/`，搬不成不進 prompt | 10 |
| S08 | 採：同格兩筆宣告的 `footprint.writes` 相交＝整格拒跑退出 3 | 04、06 |
| S09 | 採：等待中落點每格只在格頭取樣一次 | 06 |
| S10 | 採：地的誕生以 `layout.json` 原子 rename 出現為準；門房只認它 | 13、02 |
| S11 | 採：`on_fail` 那步再失敗就不再處置，串 `failed`，`fail_reason` 記兩層 | 05 |
| S12 | 採：狀態檔 `message` ≤ 4 KB、截斷標明；是不可信資料，禁止自動展開成指令參數 | 07 |
| S13 | 放（128 bit 隨機夠） | — |
| S14 | 已（S-07-43） | — |
| S15 | 採：tmpfs 重建＝從頭跑、副作用可能重做；列出不能放 tmpfs 的檔 | 13、02 |
| S16 | 採：第一版迴圈只讀 `slow`，其餘保留無消費者 | 11 |
| S17 | 採：工具的 cwd＝呼叫它的那塊地 | 11 |
| S18 | 採：`aos llm` 退出碼全歸「跑沒跑起來」；可否重試寫封套／狀態檔 | 09 |
| S19 | 放 | — |
| S20 | 採（建議）：`aos status` 顯示原稿雜湊是否跟 `.aos/program/` 記的一樣 | 12 |
| S21 | 已（S-03-34）；補「載入失敗＝這格失敗、寫狀態檔」 | 03 |
| L01 | 放 | — |
| L02 | 已（S-10-12 用格數） | — |
| L03 | 採：處理單元表每筆 `timeout_ms`，沒填 300000；LLM 世界的 run 用它不用 60000 | 09 |
| L04～L07 | 放 | — |
| L08 | 已 | — |
| L09 | 已（04 的 b64） | — |
| L10 | 採：兩個收件匣的 id 去重分開 | 12 |
| L11、L12 | 放 | — |

統計：採 53、已 17、部分 4、放 9（合計 83）。

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
