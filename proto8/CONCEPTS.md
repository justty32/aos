# proto8 概念層（第二版，AI 從使用者的話抽出來的，2026-10-11）

← [proto8](README.md)｜來源：[10-11 討論 §2、§3b](thinking/2026-10-11-restart.md)、使用者九月草稿 [9/19](../thinking/2026-09-19.md)、[9/23](../thinking/2026-09-23.md)、[9/24](../thinking/2026-09-24.md)｜對照：[10-03 核心 spec](../proto7/spec/core.md)｜三份獨立抽的合併：AI 自己第一版（f7903867）、Fable 獨立抽（已刪：AI 產出，使用者 10-12 夜要求刪除）、診斷為什麼問錯（已刪：AI 產出，使用者 10-12 夜要求刪除）

**只收使用者說過的。** 每條引出處。這份**沒有檔名、沒有格式、沒有程式結構、沒有步驤、沒有第一版**——那是下一層，使用者講了才有。「世界」「需求」「排序器」「順序表」這幾個詞是 AI 之前造的，使用者沒說過，這份不用。

<!-- wf-nav -->
## 分檔（10-15 使用者定：按主題分）

「規則」（使用者說「一定是這樣」的，條號 C-）原本是一份，10-15 起按主題拆；條號不重編，條文原樣搬過來。C-36 以後來自 10-11 晚的實作口述（restart §3g），使用者講得像定了的，所以也列進規則；要改隨時改。每份第一行寫出該主題的概念、規範、實作在哪。

| 分檔 | 主題 | 條號 |
|---|---|---|
| [01-設計理念.md](CONCEPTS/01-設計理念.md) | 設計理念 | C-01～C-04、C-07、C-24、C-43、C-45、C-48、C-51～C-56、C-64、C-68～C-72（**C-56 KISS＝最高原則，也是最後原則**；C-52／C-53 兩條總原則；C-54 命名；旁邊的 [abbr.json](CONCEPTS/abbr.json)＝aos 認可縮寫表；C-55 布局成長；C-64 用檔案為了借 Linux 權限；C-68～C-70 資料夾＝程式、aos 只訂環境變數、巢狀由程式自己訂子 stack；C-71 資料夾的比喻用 table；C-72 JSON＝埋在檔案裡的 table、入口尋址方式同樣適用；C-73 entry 的定義＝可執行檔或 aos-exec 標準實作跑得動的檔〔四種〕） |
| [02-設計理念-時空.md](CONCEPTS/02-設計理念-時空.md) | 設計理念／時空 | C-05、C-06、C-16、C-17、C-26、C-27、C-30～C-33、C-35、C-37、C-44 |
| [03-基礎設施.md](CONCEPTS/03-基礎設施.md) | 基礎設施：inst、loop 與 daemon、組合子（tasks、fsm）、資料夾程式、工作區與 stack（10-19） | C-08、C-18、C-25、C-34、C-36、C-39、C-41、C-42b、C-49、C-65～C-67 |
| [04-kernel.md](CONCEPTS/04-kernel.md) | kernel | C-09～C-15、C-28、C-29、C-38、C-47 |
| [05-agent.md](CONCEPTS/05-agent.md) | agent：腦、工具、可預測性、函數＋binding、工具（狀態機那幾條隨 fsm 在基礎設施） | C-19～C-23（含 C-22b）、C-40、C-42、C-46、C-50、C-61、C-62 |
| [附錄1-名詞.md](CONCEPTS/附錄1-名詞.md) | 附錄 | 1. 名詞（daemon 兩義各一列；10-19 加資料夾程式、入口、`aos-exec`、stack、小格，工作區、指標） |
| [附錄2-例子與待接.md](CONCEPTS/附錄2-例子與待接.md) | 附錄 | 3. 兩個例子、4. 還沒接起來的 16 條、5. AI 對自己的提醒 |

總則（跨主題的規範）沒有專屬的概念條，見 [NORMS 總則](NORMS/01-總則.md)；總則與設計理念維持分開（10-15 使用者「隨你」）。主題總表在 [NORMS.md](NORMS.md)。

## 條號 → 檔

| 條號 | 檔 |
|---|---|
| C-01～C-04 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-05、C-06 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-07 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-08 | [基礎設施](CONCEPTS/03-基礎設施.md)（inst） |
| C-09～C-15 | [kernel](CONCEPTS/04-kernel.md) |
| C-16、C-17 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-18 | [基礎設施](CONCEPTS/03-基礎設施.md)（fsm） |
| C-19～C-23（含 C-22b） | [agent](CONCEPTS/05-agent.md) |
| C-24 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-25 | [基礎設施](CONCEPTS/03-基礎設施.md)（fsm） |
| C-26、C-27 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-28、C-29 | [kernel](CONCEPTS/04-kernel.md) |
| C-30～C-33 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-34 | [基礎設施](CONCEPTS/03-基礎設施.md)（inst） |
| C-35 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-36 | [基礎設施](CONCEPTS/03-基礎設施.md)（loop 與 daemon） |
| C-37 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-38 | [kernel](CONCEPTS/04-kernel.md) |
| C-39 | [基礎設施](CONCEPTS/03-基礎設施.md)（fsm） |
| C-40 | [agent](CONCEPTS/05-agent.md) |
| C-41 | [基礎設施](CONCEPTS/03-基礎設施.md)（tasks） |
| C-42 | [agent](CONCEPTS/05-agent.md) |
| C-42b | [基礎設施](CONCEPTS/03-基礎設施.md)（inst） |
| C-43 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-44 | [設計理念-時空](CONCEPTS/02-設計理念-時空.md) |
| C-45 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-46 | [agent](CONCEPTS/05-agent.md) |
| C-47 | [kernel](CONCEPTS/04-kernel.md) |
| C-48 | [設計理念](CONCEPTS/01-設計理念.md) |
| C-49 | [基礎設施](CONCEPTS/03-基礎設施.md)（fsm） |
| C-50 | [agent](CONCEPTS/05-agent.md) |
| C-51～C-56 | [設計理念](CONCEPTS/01-設計理念.md)（C-56 KISS＝最高原則，也是最後原則：先滿足需求與其他原則，最後做減法；寫什麼就做什麼，不把規則藏進特定值） |
| C-57 | 作廢（10-19，由 C-69 取代） |
| C-58 | 作廢（10-19，由 C-69 取代） |
| C-59、C-60 | 作廢（10-19，由 C-68 取代） |
| C-61 | [agent](CONCEPTS/05-agent.md)（工具地址不用 PATH、工具＝資料夾程式、放在呼叫它的那一格裡） |
| C-62 | [agent](CONCEPTS/05-agent.md)（agent 的定義＝一台狀態機，怎麼跑、由誰跑概念上不管；10-16 KISS 重審拍板 4） |
| C-63 | 作廢（10-19，由停止碼 10 取代，見 [CONVENTION P-19](CONVENTION.md)） |
| C-64 | [設計理念](CONCEPTS/01-設計理念.md)（用檔案為了借 Linux 讀寫權限，例 kernel 當某 daemon ctl 的唯一寫者） |
| C-65～C-67 | [基礎設施](CONCEPTS/03-基礎設施.md)（stack 與工作區：兩個東西、工作區保持乾淨；影響外部＝指標＝`AOS_WS`；stack 放哪由呼叫方自由決定；10-19 改成環境變數） |
| C-68～C-70 | [設計理念](CONCEPTS/01-設計理念.md)（10-19 新：資料夾＝程式、入口 `AOS_ENTRY`；aos 只訂環境變數〔10-19 下班前加 `AOS_CF`、`AOS_CD`，五個〕；巢狀由程式自己訂子 stack） |
| C-71 | [設計理念](CONCEPTS/01-設計理念.md)（10-19 晚：資料夾的比喻用 lua 的 table、不用 lisp 的 list；本質是用 index＋巢狀分資料、只是 index 格式不同；入口之外的東西就是其他元素） |
| C-72 | [設計理念](CONCEPTS/01-設計理念.md)（10-19 晚：JSON＝埋在檔案裡的 table＝單檔的微型檔案系統，入口尋址方式同樣適用，例 `js[".aos"]["inst"]`；10-19 下班前落成 `js[$AOS_ENTRY]` 與 `檔#/指標`，impls 已做、bin 版未改） |
| C-73 | [設計理念](CONCEPTS/01-設計理念.md)（10-19 下班前：entry＝可執行檔，或 aos-exec 標準實作跑得動的檔——inst 單子、argv 陣列、shebang／可執行檔、`js[$AOS_ENTRY]` 的值〔單子、陣列、字串路徑〕） |

> **10-16 KISS 重審五件拍板**（[稿末尾](thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)）：C-62 新增（agent 就是一台狀態機）；C-36 註 N-10 刪、C-25 註 agent 一次走一拍。規範面見 [NORMS.md](NORMS.md)（N-53、N-54）。
>
> **10-16 兩條邊緣的回答**（[thinking](thinking/2026-10-16-exitcode-perm.md)）：C-63 結束碼只是參考（10-19 作廢）；C-64 用檔案是為了能借 Linux 讀寫權限（例 kernel 當某 daemon ctl 的唯一寫者）。
>
> **10-16 夜 stack 與工作區分開**（[稿 § 四](thinking/2026-10-16-agent-inherit.md#四使用者決定10-16)）：C-65～C-67 新增；C-48 改：`$env` 讀執行當下的環境、可當正式機制；[abbr.json](CONCEPTS/abbr.json) 加 `ws`。使用者另把 cwd 的稱呼從 frame 改成 stack（「不過frame那塊能不能換成stack(或heap)?。」→ 頂層推薦 stack →「好！」），**heap** 保留給以後跨呼叫共用的記憶、目前沒有機制（[名詞表](CONCEPTS/附錄1-名詞.md)）。
>
> **10-19 proto8-2 併進 proto8**（[ideas § 1～§ 11](thinking/2026-10-19-ideas.md)）：使用者 10-19 定「資料夾＝程式、入口 `AOS_ENTRY`、三個環境變數、`aos-exec`」，並說「那是帶著鐐銬跳舞跳得很棒，終究不如我們現在直接把鐐銬拿掉」，所以 10-16 那套（stdin 是正規入口、`.aos` 捷徑、一律走門房、agent 的 stdin 只放定義、結束碼只是參考）**作廢**：C-57、C-58、C-59、C-60、C-63 正文刪、條號留在上表；新增 C-68～C-70；C-46、C-48、C-50、C-51、C-52、C-53、C-61、C-65～C-67、C-25、C-36、C-42b、C-49 改寫。daemon、kernel、tasks 的概念條都留著，各標「現無實作」，等照新做法重寫。舊的實作與說明在 git 歷史 aa2fec1f。
>
> **10-19 下班前～晚 entry／aos-exec／impls**（[ideas § 14～§ 20](thinking/2026-10-19-ideas.md)）：使用者口述 entry 的定義（四種）、`js[$AOS_ENTRY]` 的值可為字串路徑、再加 `AOS_CF`／`AOS_CD`、`#/` 尋址、impls 只提供 aos-exec 一支 CLI 且 inst 是 C lib。新增 C-73；C-68、C-69、C-72 加註；[abbr.json](CONCEPTS/abbr.json) 加 `cf`、`cd`；名詞表「入口」「aos-exec」「inst」改。規範面 N-57～N-62（[NORMS.md](NORMS.md)）。
