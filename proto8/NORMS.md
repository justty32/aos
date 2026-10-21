# proto8 規範

← [proto8](README.md)｜概念層：[CONCEPTS.md](CONCEPTS.md)｜慣例：[CONVENTION.md](CONVENTION.md)｜程式：[bin/](bin/README.md)、[demo/](demo/README.md)

**比起實作，更重要的是規範**（C-45）。四層：

| 層 | 是什麼 | 在哪 |
|---|---|---|
| 概念 | aos 怎麼看世界（例：時空＝tick-tock＋資料夾；資料夾＝程式） | [CONCEPTS.md](CONCEPTS.md) |
| 規範 | 從概念推出來、大家都要守的 | 本檔（條文按主題放在 NORMS/ 分檔） |
| 慣例 | 我們自己人寫 aos agent 時照抄的標準形狀（P-05～P-40），**不要求別人守** | [CONVENTION.md](CONVENTION.md) |
| 程式 | 符合規範的實作與範例，**不要求一定用** | [proto8/bin](bin/README.md)（aos-exec、aos-inst、aos-loop、aos-fsm、aos-daemon、aos-tick；Python，10-19 晚照 § 14～§ 21 改完，aos-daemon 10-20、aos-tick 10-21 晚）、[proto8/demo](demo/README.md)（agent-bob、agent-ann、daemon、tick）；`proto8/impls/`（使用者假日的 C／C++ 參考實作，git 未追蹤：提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列，inst 是 C lib；10-21 已對齊 bin 版 10-20：daemon 重寫、指示詞與 argv D1～D15）；舊的 lib 10-19 進 git 歷史 |

本檔（含分檔）只收使用者親口定下的規範（條號 N-）；AI 提的、還沒定的放在最後「待定」，不算數。**10-19 併入 proto8-2**：10-16 那套（stdin 是正規入口、`.aos` 捷徑、門房、結束碼只是參考…）作廢，條號只留在下面的條號表；daemon、kernel、tasks、窗的條文留著、標「現無實作」。**10-19 下班前～晚**（[ideas § 14～§ 21](thinking/2026-10-19-ideas.md)）：入口放寬成四種、`aos-exec XXX`、五個環境變數、`#/` 尋址（N-57～N-60 改、新增 N-61、N-62）；兩版實作（impls 的 C++、bin 的 Python）都已照做，仍不同的兩處（impls 沒有 aos-inst 命令列、錯誤一行有沒有代號；10-20 的 `$ref` `#/`、`at`、argv 陣列等 impls 10-21 已對齊）在 [NORMS/10](NORMS/10-基礎設施-定義與工作區.md) 開頭。**10-19 晚規範總覽四題**（[ideas § 22](thinking/2026-10-19-ideas.md)）：daemon／窗的 key 改用現行 loop.json 的 `run`／`max`（N-06、N-07、N-11、N-28）、設定只認設定檔（N-11）、指示詞保留 `$ref`（N-45）；「+x 沒 `#!`」的檔三處一致改用 `/bin/sh` 跑（使用者「乙」，N-59 第 5 件、N-60）。

<!-- wf-nav -->
## 主題（10-15 使用者定：概念、規範、實作之外，再用主題分）

每個主題都有自己的概念、規範、實作；各分檔第一行寫出三者在哪。條號不重編，條文原樣搬過來（10-19 改寫的條在括號附「10-19 改」）。

| 主題 | 規範分檔 | 概念 | 實作 |
|---|---|---|---|
| 設計理念 | 沒有專屬的條（C-56 KISS 是最高原則，也是最後原則——先滿足需求與其他原則，最後回頭清掉多餘的，給的值照字面用、不藏暗規則；C-52 巢狀只管自己這一層、C-53 錯誤只處理自己的，各條都照它；C-54 命名＋[縮寫表](CONCEPTS/abbr.json)） | [CONCEPTS 設計理念](CONCEPTS/01-設計理念.md) | — |
| 設計理念／時空 | [02-設計理念-時空.md](NORMS/02-設計理念-時空.md)：N-01～N-03 | [CONCEPTS 時空](CONCEPTS/02-設計理念-時空.md) | 時鐘＝[aos-tick](bin/README.md)（10-21 晚，bin 版；舊 `aos tick` 在 git 歷史）；打包（N-03）現無實作 |
| 總則（跨主題） | [01-總則.md](NORMS/01-總則.md)：N-05 先寫暫存再改名、N-18 實作分級、N-43 結束碼（0／10／其他非 0，10-19 改） | 出自 C-07、C-45、C-53 | [bin](bin/README.md) |
| 基礎設施／inst | [03-基礎設施-inst.md](NORMS/03-基礎設施-inst.md)：N-04、N-25、N-27、N-30（10-19 改成新 aos-inst；impls 線沒有 aos-inst 命令列、inst 是 C lib，§ 20） | [CONCEPTS 基礎設施](CONCEPTS/03-基礎設施.md) | [aos-inst](bin/README.md)（bin 版）；impls：aos-exec 行程內跑 |
| 基礎設施／loop、daemon | [04-基礎設施-loop與daemon.md](NORMS/04-基礎設施-loop與daemon.md)：N-10（10-16 刪，條號留作錨點）、N-28、N-54 | 同上 | loop＝[aos-loop](bin/README.md)；daemon＝[aos-daemon](bin/README.md)（10-20，bin 版） |
| 基礎設施／窗 | [05-基礎設施-窗.md](NORMS/05-基礎設施-窗.md)：N-06～N-09、N-11、N-13～N-17、N-32、N-33（現無實作；agent 這層只剩 N-13：內部狀態外顯成 `$AOS_STACK` 裡的檔；節奏 key 10-19 晚改用 `max`、設定只認設定檔） | 同上 | 現無實作 |
| 基礎設施／指示詞 | [06-基礎設施-命令列與指示詞.md](NORMS/06-基礎設施-命令列與指示詞.md)：N-45 指示詞 `$env` 與 `$ref`（10-19 晚改；10-20 起 bin 版也有 `$ref`，含 `#/` 與 `at`；10-20 晚 `path` 改名 `$path`、加 `$prefix`、寫法寬容；impls 10-21 已對齊） | 同上 | [aos-inst](bin/README.md)（bin 版，`$env` 與 `$ref`）；impls：aos-exec＋aos-directive 庫 |
| 基礎設施／組合子（tasks、fsm；stdlib 地位） | [07-基礎設施-組合子.md](NORMS/07-基礎設施-組合子.md)：N-20、N-34（tasks，現無實作）、N-36、N-38、N-39、N-41（fsm，10-19 改） | 同上 | fsm＝[aos-fsm](bin/README.md)；tasks 現無實作 |
| kernel | [09-kernel.md](NORMS/09-kernel.md)：N-42 兩種兩支（10-16 使用者「不併」；打包 N-03 在時空） | [CONCEPTS kernel](CONCEPTS/04-kernel.md) | 現無實作 |
| 基礎設施／資料夾程式與執行（10-19 整份重寫；10-19 下班前～晚補 § 14～§ 21） | [10-基礎設施-定義與工作區.md](NORMS/10-基礎設施-定義與工作區.md)：N-57 六個環境變數（加 `AOS_CF`、`AOS_CD`；10-21 晚加 `AOS_CO`）與入口四種、N-58 `aos-exec [旗標...] XXX [args...]`（10-21 改收旗標，目前只有 `--ws`）、N-59 aos-exec 只做這幾件事（找入口、export、cd、讀 `.env`〔10-21 加；10-21 晚改成讀完才挑入口、一路往下每層讀〕、exec 或行程內跑單子）、N-60 aos-exec 自己的錯退 1、N-61 找入口與種類判斷（補 `.json`、`js[$AOS_ENTRY]`、字串轉向、繞圈偵測）、N-62 `#/` 尋址；N-50 工具＝資料夾程式、不用 PATH；N-53 aos 的 agent 被外面的 loop 一拍一拍驅動；N-55 工作區位置＝`AOS_WS` | [CONCEPTS 基礎設施](CONCEPTS/03-基礎設施.md#資料夾程式工作區與-stack10-19)（C-65～C-67）、[C-68～C-73](CONCEPTS/01-設計理念.md#資料夾程式與環境變數10-19-使用者定)、C-62（agent＝狀態機） | [aos-exec](bin/README.md)（bin 版）與 impls 的 aos-exec（兩版都已照做）、[demo](demo/README.md) |
| agent | 沒有專屬的分檔；入口與工具、怎麼被驅動在資料夾程式與執行（N-50、N-53）；其餘用 fsm 組出來；整套慣例在 [CONVENTION](CONVENTION.md) | [CONCEPTS agent](CONCEPTS/05-agent.md) | [demo](demo/README.md)（agent-bob、agent-ann） |
| 待定（不拆，每條標主題） | [08-待定.md](NORMS/08-待定.md) | | |

> **總則與設計理念**分兩份（設計理念只有概念、總則只有規範；總則＝跨主題的規範，設計理念＝概念）。10-15 使用者「隨你」：維持分開。時空放在設計理念下也定案（同日「隨你」）。

## 條號表與各批出處（2026-10-20 tidy：本檔超過 8 KB，兩段逐字下放）

<!-- wf-nav -->
| 分檔 | 涵蓋的段 |
|---|---|
| [附錄1-條號表.md](NORMS/附錄1-條號表.md) | 條號 → 檔（含作廢條號） |
| [附錄2-各批出處.md](NORMS/附錄2-各批出處.md) | 各批出處 |
