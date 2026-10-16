# proto8 規範

← [proto8](README.md)｜概念層：[CONCEPTS.md](CONCEPTS.md)｜語法糖：[lib/](lib/README.md)

**比起實作，更重要的是規範**（C-45）。三層：

| 層 | 是什麼 | 在哪 |
|---|---|---|
| 概念 | aos 怎麼看世界（例：時空＝tick-tock＋資料夾） | [CONCEPTS.md](CONCEPTS.md) |
| 規範 | 從概念推出來、大家都要守的 | 本檔（條文按主題放在 NORMS/ 分檔） |
| 語法糖 | 符合規範、方便用，**不要求一定用** | proto8/lib（inst、loop、daemon、tasks、aos-tick…） |

本檔（含分檔）只收使用者親口定下的規範（條號 N-）；AI 提的、還沒定的放在最後「待定」，不算數。

<!-- wf-nav -->
## 主題（10-15 使用者定：概念、規範、實作之外，再用主題分）

每個主題都有自己的概念、規範、實作；各分檔第一行寫出三者在哪。條號不重編，條文原樣搬過來。

| 主題 | 規範分檔 | 概念 | 實作 |
|---|---|---|---|
| 設計理念 | 沒有專屬的條（C-56 KISS 是最高原則，也是最後原則——先滿足需求與其他原則，最後回頭清掉多餘的，給的值照字面用、不藏暗規則；C-52 巢狀只管自己這一層、C-53 錯誤只處理自己的，各條都照它；C-54 命名＋[縮寫表](CONCEPTS/abbr.json)） | [CONCEPTS 設計理念](CONCEPTS/01-設計理念.md) | — |
| 設計理念／時空 | [02-設計理念-時空.md](NORMS/02-設計理念-時空.md)：N-01～N-03 | [CONCEPTS 時空](CONCEPTS/02-設計理念-時空.md) | lib `aos tick` |
| 總則（跨主題） | [01-總則.md](NORMS/01-總則.md)：N-05 先寫暫存再改名、N-12 stdio、N-18 實作分級、N-29 stderr 形狀、N-35 `檔#/位置`、N-43 結束碼、N-52 收到 SIGTERM＝優雅收工（10-16） | 出自 C-07、C-45、C-53 | lib `aos_cli` |
| 基礎設施／inst | [03-基礎設施-inst.md](NORMS/03-基礎設施-inst.md) | [CONCEPTS 基礎設施](CONCEPTS/03-基礎設施.md) | [lib inst](lib/inst.md) |
| 基礎設施／loop、daemon | [04-基礎設施-loop與daemon.md](NORMS/04-基礎設施-loop與daemon.md)（10-16：N-10 刪、N-54 daemon 子項寫在 ctl、N-28 表窗併進 state 窗＋`adopt`） | 同上 | [lib loop](lib/loop.md)、[daemon](lib/daemon.md) |
| 基礎設施／窗 | [05-基礎設施-窗.md](NORMS/05-基礎設施-窗.md) | 同上 | [lib ctl_state](lib/ctl_state.md) |
| 基礎設施／命令列、指示詞與路徑 | [06-基礎設施-命令列與指示詞.md](NORMS/06-基礎設施-命令列與指示詞.md)：N-21～N-23 命令列（10-16 起歸語法糖，N-46）、N-45 設計不靠指示詞 | 同上 | lib `aos_cli` |
| 基礎設施／組合子（tasks、fsm；stdlib 地位） | [07-基礎設施-組合子.md](NORMS/07-基礎設施-組合子.md) | 同上 | tasks（`aos seq|par|if`）在 lib；fsm 在 [lib fsm.md](lib/fsm.md)（基礎實作） |
| kernel | [09-kernel.md](NORMS/09-kernel.md)：N-42 兩種兩支（10-16 使用者「不併」；打包 N-03 在時空） | [CONCEPTS kernel](CONCEPTS/04-kernel.md) | — |
| 基礎設施／定義與工作區（食譜與廚房，10-16） | [10-基礎設施-定義與工作區.md](NORMS/10-基礎設施-定義與工作區.md)：N-46 stdin 正規、argv 是糖；N-47 `aos exec 工作區 定義`；N-48 `.aos` 捷徑、互指 `.aos/x`；N-49 agent stdin＝定義、話放工作區；N-50 工具＝定義資料夾、不用 PATH、參數兩層；N-51 shebang stub；N-53 aos 的 agent 被外面的 loop 一拍一拍驅動、定義不含 loop、連錯不數 | [CONCEPTS 基礎設施](CONCEPTS/03-基礎設施.md#定義與工作區食譜與廚房10-16)（C-57、C-59、C-60）、C-62（agent＝狀態機） | **還沒有**（程式待改） |
| agent | 沒有專屬的分檔；10-16 起入口與工具、怎麼被驅動在定義與工作區（N-49、N-50、N-53）；其餘用 fsm 組出來 | [CONCEPTS agent](CONCEPTS/05-agent.md) | — |
| 待定（不拆，每條標主題） | [08-待定.md](NORMS/08-待定.md) | | |

> **總則與設計理念**分兩份（設計理念只有概念、總則只有規範；總則＝跨主題的規範，設計理念＝概念）。10-15 使用者「隨你」：維持分開。時空放在設計理念下也定案（同日「隨你」）。

## 條號 → 檔

| 條號 | 檔 |
|---|---|
| N-01～N-03 | [設計理念-時空](NORMS/02-設計理念-時空.md) |
| N-04 | [基礎設施-inst](NORMS/03-基礎設施-inst.md) |
| N-05 | [總則](NORMS/01-總則.md) |
| N-06～N-09 | [基礎設施-窗](NORMS/05-基礎設施-窗.md) |
| N-10 | [基礎設施-loop與daemon](NORMS/04-基礎設施-loop與daemon.md)（10-16 使用者刪，條號留作錨點） |
| N-11 | [基礎設施-窗](NORMS/05-基礎設施-窗.md) |
| N-12 | [總則](NORMS/01-總則.md) |
| N-13～N-17 | [基礎設施-窗](NORMS/05-基礎設施-窗.md) |
| N-18 | [總則](NORMS/01-總則.md) |
| N-19 | [基礎設施-窗](NORMS/05-基礎設施-窗.md) |
| N-20 | [基礎設施-組合子](NORMS/07-基礎設施-組合子.md)（fsm） |
| N-21～N-23 | [基礎設施-命令列與指示詞](NORMS/06-基礎設施-命令列與指示詞.md) |
| N-24～N-27 | [基礎設施-inst](NORMS/03-基礎設施-inst.md)（N-26 `*_inherit` 10-15 深夜 KISS 批次 1 刪過、10-16 還原） |
| N-28 | [基礎設施-loop與daemon](NORMS/04-基礎設施-loop與daemon.md) |
| N-29 | [總則](NORMS/01-總則.md) |
| N-30 | [基礎設施-inst](NORMS/03-基礎設施-inst.md) |
| N-31 | [基礎設施-loop與daemon](NORMS/04-基礎設施-loop與daemon.md) |
| N-32、N-33 | [基礎設施-窗](NORMS/05-基礎設施-窗.md) |
| N-34 | [基礎設施-組合子](NORMS/07-基礎設施-組合子.md)（tasks） |
| N-35 | [總則](NORMS/01-總則.md) |
| N-36～N-41 | [基礎設施-組合子](NORMS/07-基礎設施-組合子.md)（fsm） |
| N-42 | [kernel](NORMS/09-kernel.md) |
| N-43 | [總則](NORMS/01-總則.md) |
| N-45 | [基礎設施-命令列與指示詞](NORMS/06-基礎設施-命令列與指示詞.md)（指示詞） |
| N-46～N-51 | [基礎設施-定義與工作區](NORMS/10-基礎設施-定義與工作區.md)（10-16；N-27 後半、N-21～N-24 的地位、N-35 的 `AOS_DIRNAME` 跟著受影響，程式未改） |
| N-52 | [總則](NORMS/01-總則.md)（10-16：收到 SIGTERM＝優雅收工、退 0） |
| N-53 | [基礎設施-定義與工作區](NORMS/10-基礎設施-定義與工作區.md)（10-16：aos 的 agent 被外面的 loop 驅動） |
| N-54 | [基礎設施-loop與daemon](NORMS/04-基礎設施-loop與daemon.md)（10-16：daemon 表上有誰寫在 ctl 的 `children`） |

## 各批出處

條文是一批一批定的（10-15 前按日期分檔）；每批的來源：

- **N-01～N-03** 時空：來自 C-05、C-37、C-44。**N-04** inst.json：來自 C-42b。
- **N-05～N-11** 控制：來自 C-36；使用者 10-12 夜授權「ctl 規範你可以開 agent 去定」、拍板「沒寫的回初始值，其他都照建議」，條文照 [thinking 10-12 ctl 規範](thinking/2026-10-12-ctl-norms.md) 寫入。
- **N-12** 呼叫程式的 stdio、**N-13** 內部狀態的外顯：來自 [thinking 10-14 JSON 入口](thinking/2026-10-14-json-entry.md)（N-13 是 §1i～§1k）。
- **N-14～N-17** 窗的族譜：來自 [thinking 10-14 JSON 入口](thinking/2026-10-14-json-entry.md) §1p、[IPC 研究頁](https://claude.ai/artifact/7QcbQjrK2h7U9LPcApwpvH)；N-13 只有 state／ctl 兩扇窗，這批把它擴成一族。
- **N-18～N-20** 實作分級、loop／daemon 的窗必填、巢狀重跑：來自 [thinking 10-14 §31](thinking/2026-10-14-json-entry/12-七題回覆.md)。
- **N-21～N-28** 命令列與參數、daemon.json 放 inst：D-1～D-6 是使用者 10-14 下午拍板的（[thinking 04](thinking/2026-10-14-json-entry/04-argv與七題.md) §4.1；D-1 後來放寬，[05](thinking/2026-10-14-json-entry/05-aos-llm-agent題.md) Q10），10-14 夜重做 inst／loop／daemon 時照 [13 §38](thinking/2026-10-14-json-entry/13-動工前拍板.md) 落成條文。N-28 是候選 g，使用者 10-14 夜末拍板。全部是**草稿**。
- **N-29～N-34** 動工細則（原待定 h）：10-14 夜重做 inst／loop／daemon 時，代理人遇到規範沒寫清楚的地方，照 N-18 挑最簡單的先做、記成待定 h1～h16；**使用者 10-14 深夜拍板「全照建議」**（[thinking 14](thinking/2026-10-14-json-entry/14-h拍板.md)）。跨程式的約定落成這幾條；只跟 daemon 實作有關的（h10～h14）寫在 [lib daemon.md](lib/daemon.md) 當實作說明；h9 補進 N-28；h1、h2 補進 N-21、N-22。全部是**草稿**。
- **N-35～N-41** 路徑寫法、aos-fsm：10-15 早使用者定：「`檔#/位置` 可以列進」「aos-fsm 可以寫入規範」。內容取自已拍板的討論（[thinking 10-13 json-path](thinking/2026-10-13-json-path.md)、[thinking 10-14 06～10、12](thinking/2026-10-14-json-entry/06-fsm.md)）；全部是**草稿**。只是 aos-fsm 程式寫法的（方法表 lib、預設表資料夾、不做繼承、一份 JSON 樹為主）不進規範，留在 thinking 與之後的 lib 說明。10-15 同日再定：fsm 第一拍、error 格、`step`、結束碼、窗與心跳（補進 N-36、N-38、N-39，[thinking 10-15](thinking/2026-10-15-topics.md)），N-35、N-37、N-40、N-41 照原意修字。
- **10-15 收工後意見 1～7**（[thinking 意見 1～4](thinking/2026-10-15-opinions-1-4.md)、[意見 5～7](thinking/2026-10-15-opinions-5-7.md)，使用者拍板「剩下都按照推薦」「都AOS_DIRNAME」「開始改吧」）：fsm 瘦身成只管「狀態→inst」（N-36～N-40 改寫：不碰格的 stdin、不存 data、出錯 phase 不動往外報、state 窗只剩 phase、不開 ctl／lock、`end` 四種情形、內層不繼承外層設定），N-19 拿掉 fsm 的 ctl，N-27 補工具的 `args.json`，N-35 補 `AOS_DIRNAME`。資料夾⇄JSON 互通只當工具與思考方式、不進規範（C-51）。同日再定：結束碼只定 0／非 0（新增 N-43，N-30、N-38、待定「argv[0] 程式的規矩」跟著簡化；格出錯 fsm 退非 0）、fsm 不擋遞迴（N-39）。
- **10-15 晚兩條總原則的盤點**（[thinking 原則](thinking/2026-10-15-principles.md)，使用者「都同意。」「都按照推薦。」）：N-08 ctl 壞檔改記 state 窗 `last_warning`；N-29 stderr 不放警告、`InputExtra` 改成入口錯；N-43 補「每層只說自己（loop／daemon 只退 0／1）」與 Unix 式例外（述詞、閘門透明、`stderr_inherit`）；N-34 寫明述詞例外；N-26 寫明 `stderr_inherit` 是使用者自選（N-26 整條 10-15 深夜 KISS 批次 1 刪過，10-16 使用者翻案還原）。
- **N-46～N-51 定義與工作區**（10-16，[稿 § 四](thinking/2026-10-16-agent-inherit.md#四使用者決定10-16)）：正規參數入口是 stdin、argv 是語法糖；agent 的 stdin 只放定義（食譜）、這次的話放工作區（廚房）；定義與工作區用 `.aos` 捷徑接、互指寫 `.aos/x`；一律 `aos exec 工作區 定義`、推廣到所有東西；工具＝定義資料夾、地址是相對捷徑、不用 PATH、參數走門房 stdin（兩層）。N-27 後半由 N-50 取代；N-21～N-24 歸語法糖；N-35／N-36／N-44／N-28 加註；同日使用者再同意刪 N-36「格從 fsm 設定檔所在資料夾算」那半句，格一律從工作區（cwd）算（實作待改）。全部**草稿、程式未改**；AI 提案沒點頭的進[待定](NORMS/08-待定.md)。
- **10-16 KISS 重審五件拍板**（[稿末尾](thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)）：使用者逐件回答 Fable 重審的五個拍板點——N-10 指令資料夾「不留」（刪，子項改由 ctl 宣告＝新 N-54）；daemon 接回子 loop「給選項，默認留」（N-28 改：`adopt` 預設開、table 窗併進 state 窗）；SIGTERM「退0……這塊也可以當原則」（新 N-52 優雅收工，N-43 改、N-34 註、翻 10-15 晚「loop 退 1」）；agent「就是一個被人驅動的狀態機，需要外面有人用loop驅動他」（新 C-62、N-53，N-38／N-44 註）；「兩隻kernel不併成一支」（N-42 維持）。全部草稿、程式未改；頂層整理時挖出的邊緣進[待定](NORMS/08-待定.md)。
- **10-16 兩條邊緣的回答**（[thinking 結束碼與權限](thinking/2026-10-16-exitcode-perm.md)）：使用者對頂層轉述的兩條待定邊緣回了兩句概念——結束碼只是參考、是 Unix 時代的遺留，結果與狀態看 JSON（新 C-63，N-43、N-52 加註；待定「退 0 後分不出被叫停」結案）；用檔案是為了能借 Linux 讀寫權限，例 kernel 當某 daemon ctl 的唯一寫者（新 C-64，N-54 加註；待定「兩人同時改 `children`」結案）。新待定：tasks 用子程式的 `code` 決定往哪走（N-34）要不要跟著調整。規範條文沒新增、程式未改。
