# proto8 概念層（第二版，AI 從使用者的話抽出來的，2026-10-11）

← [proto8](README.md)｜來源：[10-11 討論 §2、§3b](thinking/2026-10-11-restart.md)、使用者九月草稿 [9/19](../thinking/2026-09-19.md)、[9/23](../thinking/2026-09-23.md)、[9/24](../thinking/2026-09-24.md)｜對照：[10-03 核心 spec](../proto7/spec/core.md)｜三份獨立抽的合併：AI 自己第一版（f7903867）、Fable 獨立抽（已刪：AI 產出，使用者 10-12 夜要求刪除）、診斷為什麼問錯（已刪：AI 產出，使用者 10-12 夜要求刪除）

**只收使用者說過的。** 每條引出處。這份**沒有檔名、沒有格式、沒有程式結構、沒有步驤、沒有第一版**——那是下一層，使用者講了才有。「世界」「需求」「排序器」「順序表」這幾個詞是 AI 之前造的，使用者沒說過，這份不用。

<!-- wf-nav -->
## 分檔（10-15 使用者定：按主題分）

「規則」（使用者說「一定是這樣」的，條號 C-）原本是一份，10-15 起按主題拆；條號不重編，條文原樣搬過來。C-36 以後來自 10-11 晚的實作口述（restart §3g），使用者講得像定了的，所以也列進規則；要改隨時改。每份第一行寫出該主題的概念、規範、實作在哪。

| 分檔 | 主題 | 條號 |
|---|---|---|
| [01-設計理念.md](CONCEPTS/01-設計理念.md) | 設計理念 | C-01～C-04、C-07、C-24、C-43、C-45、C-48、C-51～C-56、C-63、C-64（**C-56 KISS＝最高原則，也是最後原則**；C-52／C-53 兩條總原則；C-54 命名；旁邊的 [abbr.json](CONCEPTS/abbr.json)＝aos 認可縮寫表；C-55 布局成長；C-63 結束碼只是參考、C-64 用檔案為了借 Linux 權限） |
| [02-設計理念-時空.md](CONCEPTS/02-設計理念-時空.md) | 設計理念／時空 | C-05、C-06、C-16、C-17、C-26、C-27、C-30～C-33、C-35、C-37、C-44 |
| [03-基礎設施.md](CONCEPTS/03-基礎設施.md) | 基礎設施：inst、loop 與 daemon、組合子（tasks、fsm）、定義與工作區（食譜與廚房，10-16；10-16 夜 stack 與工作區分開） | C-08、C-18、C-25、C-34、C-36、C-39、C-41、C-42b、C-49、C-57、C-59、C-60、C-65～C-67 |
| [04-kernel.md](CONCEPTS/04-kernel.md) | kernel | C-09～C-15、C-28、C-29、C-38、C-47 |
| [05-agent.md](CONCEPTS/05-agent.md) | agent：腦、工具、可預測性、函數＋binding、入口與工具（10-16）（狀態機那幾條隨 fsm 在基礎設施） | C-19～C-23（含 C-22b）、C-40、C-42、C-46、C-50、C-58、C-61、C-62 |
| [附錄1-名詞.md](CONCEPTS/附錄1-名詞.md) | 附錄 | 1. 名詞（daemon 兩義各一列；10-16 加定義／stack／捷徑／門房，10-16 夜加工作區、指標） |
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
| C-57 | [基礎設施](CONCEPTS/03-基礎設施.md)（定義與工作區：stdin 是正規入口、argv 是語法糖） |
| C-58 | [agent](CONCEPTS/05-agent.md)（stdin 只放定義、這次的話放 stack） |
| C-59、C-60 | [基礎設施](CONCEPTS/03-基礎設施.md)（定義與工作區：`.aos` 捷徑、一律 `aos exec stack 定義`） |
| C-61 | [agent](CONCEPTS/05-agent.md)（工具地址不用 PATH、工具＝定義資料夾、參數兩層） |
| C-62 | [agent](CONCEPTS/05-agent.md)（agent 的定義＝一台狀態機，怎麼跑、由誰跑概念上不管；10-16 KISS 重審拍板 4） |
| C-63、C-64 | [設計理念](CONCEPTS/01-設計理念.md)（10-16：結束碼只是參考、結果看 JSON；用檔案為了借 Linux 讀寫權限，例 kernel 當某 daemon ctl 的唯一寫者） |
| C-65～C-67 | [基礎設施](CONCEPTS/03-基礎設施.md)（10-16 夜 stack 與工作區：兩個東西、站在 stack、工作區保持乾淨；影響外部＝指標＝捷徑；stack 放哪由呼叫方自由決定） |

> **10-16 新設計**（[稿 § 四](thinking/2026-10-16-agent-inherit.md#四使用者決定10-16)）：C-57～C-61 新增，C-46（agent 當函數是概念上的，不要 args.json／ret.json／frame.json）、C-50（定義＝一個 `.aos/` 資料夾）改字；正式名詞「定義（食譜）／工作區（廚房）」（10-16 夜：廚房改叫 stack，見下）。**程式還沒改**；AI 提案裡使用者沒點頭的在 [NORMS 待定](NORMS/08-待定.md)。
>
> **10-16 KISS 重審五件拍板**（[稿末尾](thinking/2026-10-16-kiss-recheck.md#使用者拍板10-16)）：C-62 新增（agent 就是一台狀態機）；C-36 註 N-10 刪、C-25 註 agent 一次走一拍、C-50 定「定義不含 loop」。規範面見 [NORMS.md](NORMS.md)（N-52～N-54）。
>
> **10-16 兩條邊緣的回答**（[thinking](thinking/2026-10-16-exitcode-perm.md)）：C-63 結束碼只是參考（Unix 時代的遺留）、結果與狀態看 JSON；C-64 用檔案是為了能借 Linux 讀寫權限（例 kernel 當某 daemon ctl 的唯一寫者）。
>
> **10-16 夜 stack 與工作區分開**（[稿 § 四](thinking/2026-10-16-agent-inherit.md#四使用者決定10-16)）：C-65～C-67 新增；C-46、C-58～C-61 把原本叫「工作區」的 cwd 改叫 **stack**，「工作區」只留給使用者的成品區；C-48 改：`$env` 讀執行當下的環境、可當正式機制（`$ref` 照舊只是拆檔便利，N-45 同步改）；[abbr.json](CONCEPTS/abbr.json) 加 `ws`。規範面 N-55、N-56。程式還沒改。
>
> **10-16 夜 frame 改名 stack**（[稿 § 四](thinking/2026-10-16-agent-inherit.md#四使用者決定10-16)）：使用者：「不過frame那塊能不能換成stack(或heap)?。」→ 頂層推薦 stack（每次呼叫疊一層 `calls/<n>/`、結束收掉＝呼叫堆疊；frame 其實是 stack 裡的一層）→「好！」。上一段與 C-46、C-58～C-61、C-65～C-67 裡指「執行時站的資料夾」的 frame 一律改叫 **stack**；**heap** 保留給以後跨呼叫共用的記憶、目前沒有機制（[名詞表](CONCEPTS/附錄1-名詞.md)）。舊實作的 `frame.json`、lib frame.md 照舊叫 frame（程式沒改）。
