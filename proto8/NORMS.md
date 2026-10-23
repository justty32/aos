# proto8 規範

← [proto8](README.md)｜概念層：[CONCEPTS.md](CONCEPTS.md)｜慣例：[CONVENTION.md](CONVENTION.md)｜程式：[bin/](bin/README.md)、[demo/](demo/README.md)

**比起實作，更重要的是規範**（C-45）。四層：

| 層 | 是什麼 | 在哪 |
|---|---|---|
| 概念 | aos 怎麼看世界（例：時空＝tick-tock＋資料夾；資料夾＝程式） | [CONCEPTS.md](CONCEPTS.md) |
| 規範 | 從概念推出來、大家都要守的 | 本檔（條文按主題放在 NORMS/ 分檔） |
| 慣例 | 我們自己人寫 aos agent 時照抄的標準形狀（P-05～P-40），**不要求別人守** | [CONVENTION.md](CONVENTION.md) |
| 程式 | 符合規範的實作與範例，**不要求一定用** | [proto8/bin](bin/README.md)（aos-exec、aos-loop、aos-fsm、aos-daemon、aos-tick，inst 是庫 `aos_inst.py`、aos-inst 命令列 10-22 刪；Python，10-19 晚照 § 14～§ 21 改完，aos-daemon 10-20、aos-tick 10-21 晚）、[proto8/demo](demo/README.md)（agent-bob、agent-ann、daemon、tick）；`proto8/impls/`（使用者假日的 C／C++ 參考實作，10-23 起進 git：提供 `aos-exec`、`aos-loop`、`aos-fsm`、`aos-daemon` 四支命令列，inst 是 C lib；10-21 已對齊 bin 版 10-20：daemon 重寫、指示詞與 argv D1～D15；10-21 晚再對齊 bin 版 10-21 傍晚：aos-exec 的 `--ws`、`.env`、`AOS_CO`，設定檔是唯一參數、`run`／`val` 陣列〔10-23 統合：`run` 改名 `val`〕、daemon 經 aos-exec、`$path` 字串拼接；刻意沒有 aos-inst 命令列，也沒有 aos-tick）；舊的 lib 10-19 進 git 歷史 |

本檔（含分檔）只收使用者親口定下的規範（條號 N-）；AI 提的、還沒定的放在最後「待定」，不算數。**10-19 併入 proto8-2**：10-16 那套（stdin 是正規入口、`.aos` 捷徑、門房、結束碼只是參考…）作廢，條號只留在下面的條號表；daemon、kernel、tasks、窗的條文留著、標「現無實作」。**10-19 下班前～晚**（[ideas § 14～§ 21](thinking/2026-10-19-ideas.md)）：入口放寬成四種、`aos-exec XXX`、五個環境變數、`#/` 尋址（N-57～N-60 改、新增 N-61、N-62）；兩版實作（impls 的 C++、bin 的 Python）都已照做，仍不同的兩處（10-22 後只剩代號一處，另有使用者接受的 `run_cli` 那條，見 NORMS/10 開頭；impls 沒有 aos-inst 命令列〔10-22 bin 版也刪了，不再是差異〕、錯誤一行有沒有代號〔10-22 使用者要 bin 也帶，等回家照 impls 補〕；10-20 的 `$ref` `#/`、`at`〔10-23 改名 `$at`〕、argv 陣列等 impls 10-21 已對齊，10-21 的旗標、`.env`、設定檔唯一參數等 impls 10-21 晚也對齊了；impls 另沒有 aos-tick）在 [NORMS/10](NORMS/10-基礎設施-定義與工作區.md) 開頭。**10-19 晚規範總覽四題**（[ideas § 22](thinking/2026-10-19-ideas.md)）：daemon／窗的 key 改用現行 loop.json 的 `run`／`max`〔10-23 統合改名：`run` → `val`，[thinking](thinking/2026-10-23-naming.md)〕（N-06、N-07、N-11、N-28）、設定只認設定檔（N-11）、指示詞保留 `$ref`（N-45）；「+x 沒 `#!`」的檔三處一致改用 `/bin/sh` 跑（使用者「乙」，N-59 第 5 件、N-60）。

**10-23 命名統合**（[thinking 2026-10-23-naming](thinking/2026-10-23-naming.md)，使用者「都先幫我統合。統合好後更新文件和artifact，我等一下重看」）：只換名字、不改原意——`run` → `val`、`children` → `loops`、state 窗的 `state` 欄 → `phase`、`started` → `start_ticks`、`beat` → `at`、子項 `exited` → `done`／`stopped`、trace 的 `ms` → `elapsed_ms`、指示詞 `at` → `$at`、錯誤代號照 C-54 三種寫法改（`Usage` → `ArgumentsBad` 等）；翻案 N-17「兩套撞名不改名」與 C-54「代號照舊沿用」。使用者 10-23 逐條重看代定後再改三處：純文字檔帶 `.txt`（fsm 的 `state.txt`、daemon 小格的 `stderr.txt`、demo 的 `current.txt`／`plan.txt`）、`AOS_STACK` 預設 `$AOS_WS/.aos/` → `$AOS_WS/.stack/`、題目資料夾 `inbox/` → `new/`（認領搬 `cur/`、做完 `done/`，答案照舊 `out/`）（N-57、N-13、N-39、N-28）。舊名在歷史敘述裡照留、旁邊加〔10-23 統合…〕註；各條改了哪些見[各批出處](NORMS/附錄2-各批出處.md)。

**10-23 晚入口改名**（[thinking 2026-10-23-naming](thinking/2026-10-23-naming.md)，使用者「改。然後_開頭=附註這個概念刪掉。」「不認得的key就是忽略」）：入口預設名 `_exec` → `_entry`（`AOS_ENTRY` 預設值、入口檔、JSON 的 key；使用者原話裡的 `_exec` 照留）；不認得的 key 一律忽略（C-48），`_` 開頭不再有特別意思。

**10-23 晚命名方法**（[thinking 2026-10-23-naming-method](thinking/2026-10-23-naming-method.md)，使用者「寫進去吧」；規則在 [C-54 命名方法](CONCEPTS/01-設計理念/C-54-命名方法.md)）：照規則改三個名字——ctl 的 `stop` → `stopped`（N-06、N-07；跟 state 的 `phase: stopped` 同字）、state 窗的 `last_warning` → `ctl_warning`（N-08、N-28）、`start_ticks` → `started_at_ticks`（N-32、N-17）。

<!-- wf-nav -->
## 主題（10-15 使用者定：概念、規範、實作之外，再用主題分）

每個主題都有自己的概念、規範、實作；各分檔第一行寫出三者在哪。**主題不是層**（10-22，[C-74](CONCEPTS/01-設計理念.md#分層10-22-使用者定)：層照誰依賴誰分）——基礎層＝資料夾程式與執行（核心 aos-exec）、inst、命令列與指示詞、loop、daemon、窗；標準庫＝組合子（fsm、tasks）；最上層＝agent、kernel；時空的時鐘 aos-tick 擱置、不歸層；設計理念、總則跨層。條號不重編，條文原樣搬過來（10-19 改寫的條在括號附「10-19 改」）。

| 主題 | 規範分檔 | 概念 | 實作 |
|---|---|---|---|
| 設計理念 | 沒有專屬的條（C-56 KISS 是最高原則，也是最後原則——先滿足需求與其他原則，最後回頭清掉多餘的，給的值照字面用、不藏暗規則；C-52 巢狀只管自己這一層、C-53 錯誤只處理自己的，各條都照它；C-54 命名＋[縮寫表](CONCEPTS/abbr.json)） | [CONCEPTS 設計理念](CONCEPTS/01-設計理念.md) | — |
| 設計理念／時空 | [02-設計理念-時空.md](NORMS/02-設計理念-時空.md)：N-01～N-03 | [CONCEPTS 時空](CONCEPTS/02-設計理念-時空.md) | 時鐘＝[aos-tick](bin/README.md)（10-21 晚，bin 版；舊 `aos tick` 在 git 歷史）；打包（N-03）現無實作 |
| 總則（跨主題） | [01-總則.md](NORMS/01-總則.md)：N-05 先寫暫存再改名、N-18 實作分級、N-43 結束碼（0／10／其他非 0，10-19 改） | 出自 C-07、C-45、C-53 | [bin](bin/README.md) |
| 基礎設施／inst | [03-基礎設施-inst.md](NORMS/03-基礎設施-inst.md)：N-04、N-25、N-27、N-30（10-19 改成新 aos-inst；impls 線沒有 aos-inst 命令列、inst 是 C lib，§ 20；10-22 bin 版也刪了 aos-inst 命令列） | [CONCEPTS 基礎設施](CONCEPTS/03-基礎設施.md) | [aos_inst 庫](bin/README.md)（bin 版）；兩版都是 aos-exec 行程內跑 |
| 基礎設施／loop、daemon | [04-基礎設施-loop與daemon.md](NORMS/04-基礎設施-loop與daemon.md)：N-10（10-16 刪，條號留作錨點）、N-28、N-54（10-22 定稿；loop 不管、使用者自行承擔的四件寫在分檔開頭） | 同上 | loop＝[aos-loop](bin/README.md)；daemon＝[aos-daemon](bin/README.md)（10-20，bin 版） |
| 基礎設施／窗 | [05-基礎設施-窗.md](NORMS/05-基礎設施-窗.md)：N-06～N-09、N-11、N-13～N-17、N-32、N-33（原註「現無實作」，10-20 起 ctl／state 已做；agent 這層只剩 N-13：內部狀態外顯成 `$AOS_STACK` 裡的檔；節奏 key 10-19 晚改用 `max`、設定只認設定檔；N-13、N-17、N-32、N-33 10-22 定稿，總則 N-14、鎖 N-15、信箱 N-16 仍草稿） | 同上 | ctl／state＝`bin/aos_window.py`（aos-loop、aos-daemon 用，10-20；原寫「現無實作」）；鎖、信箱等其他窗現無實作 |
| 基礎設施／指示詞 | [06-基礎設施-命令列與指示詞.md](NORMS/06-基礎設施-命令列與指示詞.md)：N-45 指示詞 `$env` 與 `$ref`（10-19 晚改；10-20 起 bin 版也有 `$ref`，含 `#/` 與 `at`〔10-23 改名 `$at`〕；10-20 晚 `path` 改名 `$path`、加 `$prefix`、寫法寬容；impls 10-21 已對齊） | 同上 | [aos_inst 庫](bin/README.md)（bin 版，`$env` 與 `$ref`）；impls：aos-exec＋aos-directive 庫 |
| 基礎設施／組合子（tasks、fsm；stdlib 地位） | [07-基礎設施-組合子.md](NORMS/07-基礎設施-組合子.md)：N-20、N-34（tasks，現無實作，仍草稿）、N-36、N-38、N-39、N-41（fsm，10-19 改；10-22 定稿；fsm 不管、使用者自行承擔的八件寫在分檔開頭） | 同上 | fsm＝[aos-fsm](bin/README.md)；tasks 現無實作 |
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
