# proto8 規範

← [proto8](README.md)｜概念層：[CONCEPTS.md](CONCEPTS.md)｜慣例：[CONVENTION.md](CONVENTION.md)｜程式：[bin/](bin/README.md)、[demo/](demo/README.md)

**比起實作，更重要的是規範**（C-45）。四層：

| 層 | 是什麼 | 在哪 |
|---|---|---|
| 概念 | aos 怎麼看世界（例：時空＝tick-tock＋資料夾；資料夾＝程式） | [CONCEPTS.md](CONCEPTS.md) |
| 規範 | 從概念推出來、大家都要守的 | 本檔（條文按主題放在 NORMS/ 分檔） |
| 慣例 | 我們自己人寫 aos agent 時照抄的標準形狀（P-05～P-39），**不要求別人守** | [CONVENTION.md](CONVENTION.md) |
| 程式 | 符合規範的實作與範例，**不要求一定用** | [proto8/bin](bin/README.md)（aos-exec、aos-inst、aos-loop、aos-fsm）、[proto8/demo](demo/README.md)（agent-bob、agent-ann）；舊的 lib 10-19 進 git 歷史 |

本檔（含分檔）只收使用者親口定下的規範（條號 N-）；AI 提的、還沒定的放在最後「待定」，不算數。**10-19 併入 proto8-2**：10-16 那套（stdin 是正規入口、`.aos` 捷徑、門房、結束碼只是參考…）作廢，條號只留在下面的條號表；daemon、kernel、tasks、窗的條文留著、標「現無實作」。

<!-- wf-nav -->
## 主題（10-15 使用者定：概念、規範、實作之外，再用主題分）

每個主題都有自己的概念、規範、實作；各分檔第一行寫出三者在哪。條號不重編，條文原樣搬過來（10-19 改寫的條在括號附「10-19 改」）。

| 主題 | 規範分檔 | 概念 | 實作 |
|---|---|---|---|
| 設計理念 | 沒有專屬的條（C-56 KISS 是最高原則，也是最後原則——先滿足需求與其他原則，最後回頭清掉多餘的，給的值照字面用、不藏暗規則；C-52 巢狀只管自己這一層、C-53 錯誤只處理自己的，各條都照它；C-54 命名＋[縮寫表](CONCEPTS/abbr.json)） | [CONCEPTS 設計理念](CONCEPTS/01-設計理念.md) | — |
| 設計理念／時空 | [02-設計理念-時空.md](NORMS/02-設計理念-時空.md)：N-01～N-03 | [CONCEPTS 時空](CONCEPTS/02-設計理念-時空.md) | 現無實作（舊 `aos tick`） |
| 總則（跨主題） | [01-總則.md](NORMS/01-總則.md)：N-05 先寫暫存再改名、N-18 實作分級、N-43 結束碼（0／10／其他非 0，10-19 改） | 出自 C-07、C-45、C-53 | [bin](bin/README.md) |
| 基礎設施／inst | [03-基礎設施-inst.md](NORMS/03-基礎設施-inst.md)：N-04、N-25、N-27、N-30（10-19 改成新 aos-inst） | [CONCEPTS 基礎設施](CONCEPTS/03-基礎設施.md) | [aos-inst](bin/README.md) |
| 基礎設施／loop、daemon | [04-基礎設施-loop與daemon.md](NORMS/04-基礎設施-loop與daemon.md)：N-10（10-16 刪，條號留作錨點）、N-28、N-54 | 同上 | loop＝[aos-loop](bin/README.md)；daemon 現無實作 |
| 基礎設施／窗 | [05-基礎設施-窗.md](NORMS/05-基礎設施-窗.md)：N-06～N-09、N-11、N-13～N-17、N-32、N-33（現無實作；agent 這層只剩 N-13：內部狀態外顯成 `$AOS_STACK` 裡的檔） | 同上 | 現無實作 |
| 基礎設施／指示詞 | [06-基礎設施-命令列與指示詞.md](NORMS/06-基礎設施-命令列與指示詞.md)：N-45 指示詞只有 `$env`（10-19 改） | 同上 | [aos-inst](bin/README.md) |
| 基礎設施／組合子（tasks、fsm；stdlib 地位） | [07-基礎設施-組合子.md](NORMS/07-基礎設施-組合子.md)：N-20、N-34（tasks，現無實作）、N-36、N-38、N-39、N-41（fsm，10-19 改） | 同上 | fsm＝[aos-fsm](bin/README.md)；tasks 現無實作 |
| kernel | [09-kernel.md](NORMS/09-kernel.md)：N-42 兩種兩支（10-16 使用者「不併」；打包 N-03 在時空） | [CONCEPTS kernel](CONCEPTS/04-kernel.md) | 現無實作 |
| 基礎設施／資料夾程式與執行（10-19 整份重寫） | [10-基礎設施-定義與工作區.md](NORMS/10-基礎設施-定義與工作區.md)：N-57 三個環境變數、N-58 `aos-exec DIR [WS [args...]]`、N-59 aos-exec 只做五件事、N-60 aos-exec 自己的錯退 1；N-50 工具＝資料夾程式、不用 PATH；N-53 aos 的 agent 被外面的 loop 一拍一拍驅動；N-55 工作區位置＝`AOS_WS` | [CONCEPTS 基礎設施](CONCEPTS/03-基礎設施.md#資料夾程式工作區與-stack10-19)（C-65～C-67）、[C-68～C-70](CONCEPTS/01-設計理念.md#資料夾程式與環境變數10-19-使用者定)、C-62（agent＝狀態機） | [aos-exec](bin/README.md)、[demo](demo/README.md) |
| agent | 沒有專屬的分檔；入口與工具、怎麼被驅動在資料夾程式與執行（N-50、N-53）；其餘用 fsm 組出來；整套慣例在 [CONVENTION](CONVENTION.md) | [CONCEPTS agent](CONCEPTS/05-agent.md) | [demo](demo/README.md)（agent-bob、agent-ann） |
| 待定（不拆，每條標主題） | [08-待定.md](NORMS/08-待定.md) | | |

> **總則與設計理念**分兩份（設計理念只有概念、總則只有規範；總則＝跨主題的規範，設計理念＝概念）。10-15 使用者「隨你」：維持分開。時空放在設計理念下也定案（同日「隨你」）。

## 條號 → 檔

作廢的條號正文已刪（user.md「被推翻的直接刪、舊版靠 git」），只留號：舊版在 git 歷史 aa2fec1f（併入前的最後一版，`git show aa2fec1f:proto8/NORMS/01-總則.md` 之類）。

| 條號 | 檔 |
|---|---|
| N-01～N-03 | [設計理念-時空](NORMS/02-設計理念-時空.md) |
| N-04 | [基礎設施-inst](NORMS/03-基礎設施-inst.md) |
| N-05 | [總則](NORMS/01-總則.md) |
| N-06～N-09 | [基礎設施-窗](NORMS/05-基礎設施-窗.md)（現無實作） |
| N-10 | [基礎設施-loop與daemon](NORMS/04-基礎設施-loop與daemon.md)（10-16 使用者刪，條號留作錨點） |
| N-11 | [基礎設施-窗](NORMS/05-基礎設施-窗.md)（現無實作） |
| N-12 | 作廢（10-19，由 CONVENTION P-26 取代：stdin／stdout／stderr 不再規定成 JSON 串流，aos-exec 原樣透傳；stderr 是人話一行，N-43） |
| N-13、N-14 | [基礎設施-窗](NORMS/05-基礎設施-窗.md)（10-19 改：外顯的檔落在 `$AOS_STACK`、名字格式程式自訂） |
| N-15～N-17 | [基礎設施-窗](NORMS/05-基礎設施-窗.md)（現無實作） |
| N-18 | [總則](NORMS/01-總則.md) |
| N-19 | 作廢（10-19，由 N-13、CONVENTION P-07 取代：fsm 的 state 在 `$AOS_STACK/state`，沒設 `AOS_STACK` 退 1） |
| N-20 | [基礎設施-組合子](NORMS/07-基礎設施-組合子.md)（fsm） |
| N-21、N-22、N-23 | 作廢（10-19，舊命令列的語法糖〔TARGET、鏡射旗標、優先序〕，新程式沒有這套；命令列見 N-58） |
| N-24 | 作廢（10-19，新 aos-inst 是 `FILE [args…]`，args 接在 argv 後面） |
| N-25 | [基礎設施-inst](NORMS/03-基礎設施-inst.md)（10-19 改：`aos_inst.run()`） |
| N-26 | 作廢（10-19，由 CONVENTION P-28 取代：沒寫的串流就接呼叫者的、寫了路徑就寫檔，不需要 `*_inherit` 旗子） |
| N-27 | [基礎設施-inst](NORMS/03-基礎設施-inst.md)（10-19 改：參數怎麼進由工具說明定） |
| N-28 | [基礎設施-loop與daemon](NORMS/04-基礎設施-loop與daemon.md)（現無實作） |
| N-29 | 作廢（10-19，由 N-43、CONVENTION P-21 取代：stderr 是一行「程式名: 原因」，不再是 JSON） |
| N-30 | [基礎設施-inst](NORMS/03-基礎設施-inst.md)（10-19 改：結果給行程內呼叫者，命令列結束碼＝子程式的碼） |
| N-31 | 作廢（10-19，由 CONVENTION P-07、P-38 取代：loop 不吐 stdout，紀錄在 fsm 的 `trace.jsonl`） |
| N-32、N-33 | [基礎設施-窗](NORMS/05-基礎設施-窗.md)（現無實作） |
| N-34 | [基礎設施-組合子](NORMS/07-基礎設施-組合子.md)（tasks；10-19 改：看結束碼，現無實作） |
| N-35 | 作廢（10-19，綁著 TARGET 與 `AOS_DIRNAME`，入口改由 `AOS_ENTRY` 指，N-57） |
| N-36 | [基礎設施-組合子](NORMS/07-基礎設施-組合子.md)（fsm；10-19 改） |
| N-37 | 作廢（10-19，由 N-36、CONVENTION P-09 取代：下一狀態只看表上的 `next`，不讀格的 stdout） |
| N-38、N-39 | [基礎設施-組合子](NORMS/07-基礎設施-組合子.md)（fsm；10-19 改） |
| N-40 | 作廢（10-19，由 N-43、CONVENTION P-19、P-35 取代：停靠停止碼 10，巢狀整隻叫） |
| N-41 | [基礎設施-組合子](NORMS/07-基礎設施-組合子.md)（fsm；10-19 改） |
| N-42 | [kernel](NORMS/09-kernel.md)（現無實作） |
| N-43 | [總則](NORMS/01-總則.md)（10-19 改：0／10／其他非 0） |
| N-44 | 作廢（10-19，由 N-43、CONVENTION P-19 取代：loop 停靠停止碼 10，不靠 stdout 的 `end`） |
| N-45 | [基礎設施-命令列與指示詞](NORMS/06-基礎設施-命令列與指示詞.md)（10-19 改：只有 `$env`） |
| N-46 | 作廢（10-19，由 N-59 取代：「這次要做啥」隨意，aos-exec 原樣透傳 args 與 stdin） |
| N-47 | 作廢（10-19，由 N-58 取代：`aos-exec DIR [WS [args...]]`） |
| N-48 | 作廢（10-19，由 N-59 取代：起跑 cwd＝定義資料夾、檔用相對路徑，不掛捷徑） |
| N-49 | 作廢（10-19，由 CONVENTION P-11 取代：定義就是資料夾本身，題目在 `$AOS_WS/inbox/`） |
| N-50 | [基礎設施-定義與工作區](NORMS/10-基礎設施-定義與工作區.md)（10-19 改：工具＝資料夾程式、`tools/<名>`） |
| N-51 | 作廢（10-19，由 CONVENTION P-05、P-28 取代：入口本來就是 shebang 檔） |
| N-52 | 作廢（10-19，由 CONVENTION P-36 取代：被外層逾時殺掉＝那格失敗，不退 0；「先收好子程式再結束」那半句已寫進 P-36） |
| N-53 | [基礎設施-定義與工作區](NORMS/10-基礎設施-定義與工作區.md)（10-19 改：agent 資料夾可帶 loop 當入口） |
| N-54 | [基礎設施-loop與daemon](NORMS/04-基礎設施-loop與daemon.md)（現無實作） |
| N-55 | [基礎設施-定義與工作區](NORMS/10-基礎設施-定義與工作區.md)（工作區位置＝`AOS_WS`） |
| N-56 | 作廢（10-19，由 N-59 取代：aos-exec 一律 `cd DIR`，工具要碰工作區自己用 `$AOS_WS`） |
| N-57～N-60 | [基礎設施-定義與工作區](NORMS/10-基礎設施-定義與工作區.md)（10-19 新：三個環境變數、`aos-exec`、aos-exec 只做五件事、自己的錯退 1；從 CONVENTION P-01～P-04 升上來） |

## 各批出處

條文是一批一批定的（10-15 前按日期分檔）；每批的來源：

- **N-01～N-03** 時空：來自 C-05、C-37、C-44。**N-04** 單子可多放東西：來自 C-42b。
- **N-05～N-11** 控制：來自 C-36；使用者 10-12 夜授權「ctl 規範你可以開 agent 去定」、拍板「沒寫的回初始值，其他都照建議」，條文照 [thinking 10-12 ctl 規範](thinking/2026-10-12-ctl-norms.md) 寫入。
- **N-13** 內部狀態的外顯：來自 [thinking 10-14 JSON 入口](thinking/2026-10-14-json-entry.md)（§1i～§1k）。
- **N-14～N-17** 窗的族譜：來自 [thinking 10-14 JSON 入口](thinking/2026-10-14-json-entry.md) §1p、[IPC 研究頁](https://claude.ai/artifact/7QcbQjrK2h7U9LPcApwpvH)；N-13 只有 state／ctl 兩扇窗，這批把它擴成一族。
- **N-18、N-20** 實作分級、巢狀重跑：來自 [thinking 10-14 §31](thinking/2026-10-14-json-entry/12-七題回覆.md)。
- **N-25、N-27、N-28** 程式內呼叫、子程式參數、daemon.json 放 inst：D-1～D-6 是使用者 10-14 下午拍板的（[thinking 04](thinking/2026-10-14-json-entry/04-argv與七題.md) §4.1；D-1 後來放寬，[05](thinking/2026-10-14-json-entry/05-aos-llm-agent題.md) Q10），10-14 夜重做 inst／loop／daemon 時照 [13 §38](thinking/2026-10-14-json-entry/13-動工前拍板.md) 落成條文。N-28 是候選 g，使用者 10-14 夜末拍板。全部是**草稿**。
- **N-30、N-32、N-33、N-34** 動工細則（原待定 h）：10-14 夜重做 inst／loop／daemon 時，代理人遇到規範沒寫清楚的地方，照 N-18 挑最簡單的先做、記成待定 h1～h16；**使用者 10-14 深夜拍板「全照建議」**（[thinking 14](thinking/2026-10-14-json-entry/14-h拍板.md)）。h9 補進 N-28。全部是**草稿**。
- **N-36、N-38、N-39、N-41** aos-fsm：10-15 早使用者定：「aos-fsm 可以寫入規範」。內容取自已拍板的討論（[thinking 10-14 06～10、12](thinking/2026-10-14-json-entry/06-fsm.md)）；全部是**草稿**。10-15 同日再定：fsm 第一拍、error 格、`step`、結束碼、窗與心跳（[thinking 10-15](thinking/2026-10-15-topics.md)）。
- **10-15 收工後意見 1～7**（[thinking 意見 1～4](thinking/2026-10-15-opinions-1-4.md)、[意見 5～7](thinking/2026-10-15-opinions-5-7.md)，使用者拍板「剩下都按照推薦」「都AOS_DIRNAME」「開始改吧」；`AOS_DIRNAME` 10-19 隨 N-35 作廢，入口改由 `AOS_ENTRY` 指）：fsm 瘦身成只管「狀態→格」（N-36、N-38、N-39 改寫：不碰格的 stdin、不存 data、出錯 state 不動、不開 ctl／lock）。資料夾⇄JSON 互通只當工具與思考方式、不進規範（C-51）。同日再定：結束碼只定 0／非 0（新增 N-43，N-30、N-38 跟著簡化；格出錯 fsm 退非 0）、fsm 不擋遞迴（N-39）。
- **10-15 晚兩條總原則的盤點**（[thinking 原則](thinking/2026-10-15-principles.md)，使用者「都同意。」「都按照推薦。」）：N-08 ctl 壞檔改記 state 窗 `last_warning`；N-43 補「每層只說自己」與透明轉交的例外；N-34 寫明述詞例外。
- **10-16 KISS 重審五件拍板**（[稿末尾](thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)）：N-10 指令資料夾「不留」（刪，子項改由 ctl 宣告＝新 N-54）；daemon 接回子 loop「給選項，默認留」（N-28 改：`adopt` 預設開、table 窗併進 state 窗）；agent「就是一個被人驅動的狀態機，需要外面有人用loop驅動他」（新 C-62、N-53）；「兩隻kernel不併成一支」（N-42 維持）。第三件「SIGTERM 退 0」（當時的 N-52）10-19 作廢，見下。
- **10-16 兩條邊緣的回答**（[thinking 結束碼與權限](thinking/2026-10-16-exitcode-perm.md)）：用檔案是為了能借 Linux 讀寫權限，例 kernel 當某 daemon ctl 的唯一寫者（新 C-64，N-54 加註；待定「兩人同時改 `children`」結案）。「結束碼只是參考」（C-63）10-19 作廢。
- **10-16 夜 stack 與工作區**（[稿 § 四](thinking/2026-10-16-agent-inherit.md#四使用者決定10-16)、[§ 八](thinking/2026-10-16-agent-inherit.md#八工作區與-frame-分開10-16-夜重想ai-提案指標捷徑工具可直接-cwd-ws風險設計者自管已定)）：使用者定指標、stack 放哪是呼叫方的自由；看完稿 § 八「三分鐘看懂（五）」：「我覺得不錯。不過是不是可以採用環境變數？」→「可以用$env啊」→ N-45 兩案選「A」。新 N-55（工作區位置＝環境變數 `AOS_WS`）；概念 C-65～C-67、C-48 改。使用者另把 cwd 的稱呼從 frame 改成 stack：「不過frame那塊能不能換成stack(或heap)?。」→ 頂層推薦 stack →「好！」；heap 保留給以後跨呼叫共用的記憶，目前沒有機制。
- **10-19 proto8-2 併進 proto8**（[ideas § 1～§ 11](thinking/2026-10-19-ideas.md)）：使用者 10-19 定資料夾＝程式、入口 `AOS_ENTRY`、三個環境變數、`aos-exec`，並對 10-16 那套說「那是帶著鐐銬跳舞跳得很棒，終究不如我們現在直接把鐐銬拿掉」，一律走今天的做法；轉正時「b。這是個大工程，現行規範也要跟著改」，三件都「按照建議」。作廢 20 條（取代 15、刪 5，見上表）、改寫 21 條、新增 N-57～N-60（原 CONVENTION P-01～P-04）；舊 lib 進 git 歷史，daemon、kernel、tasks、窗的條文留著、標「現無實作」；N-52 作廢、被外層逾時殺掉＝那格失敗（P-36）。慣例整套（P-05～P-39）搬成 [CONVENTION.md](CONVENTION.md)。
