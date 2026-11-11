# new-tools：要補的三樣工具（grep／glob、todo、MCP client）——grep／glob、todo 已施工（11-11 線 K），MCP client 停在設計稿

← [2026-11-11](../README.md)｜[thinking](../../../README.md)

## 使用者原話

11-11 使用者問：「你覺得還需要哪些工具？就是你看市面上這些」。頂層列了五樣，使用者裁：「那就1,2,5！」——

1. 搜尋：`grep`（搜內容）與 `glob`（照檔名樣式找檔）。現在找東西只能靠 shell；專用工具輸出有上限、格式固定，小模型不會把 history 灌爆。
2. 待辦清單（市面叫 todo／plan）：agent 把長任務拆步驟、標記進度；清單放 stack 裡不會被 history 摘要摘掉。
5. 接外部 MCP 伺服器：讓 fsm agent（可行的話 eca agent）能用別人的 MCP 伺服器的工具。現在只有反方向（把 aos 工具當 MCP 給 eca 用）。

設計時照著的既有裁定：怕濫用環境變數；proto8 不留舊名、不做相容；程式輸出英文；`$` 開頭的鍵是 aos 的寫法、不遷就小模型；工具小格「真的寫才建」（[tool-cells-lazy](../tool-cells-lazy.md)）；children 系改名 subagent、每支工具都要有知識節點、`thought` 之後改名 `do_task`（線 C）。

## 三樣的白話結論

| 份 | 結論 |
|---|---|
| [01 grep／glob](01-grep-glob.md) | 兩支 base 工具，純 Python 標準庫（這台沒有 ripgrep），進第 1 包「看」。輸出照 `ls`：一行一筆 `路徑:行號:那一行`、每次最多 100 筆、`offset` 翻頁、尾巴 `... ` 行說還有多少與跳過了什麼；跳過二進位、超過 8MB 的檔、隱藏檔、`.gitignore` 擋掉的；資料夾捷徑不跟進；20 秒或 2 萬個檔先到先停。約 1 天。 |
| [02 todo](02-todo.md) | 一支 `todo`（`ls`／`set`／`add`／`mark`），存自己的小格 `tools/todo/todo.json`，每次都印整張。要「摘要後一定看得到」得讓 fsm 的 brain.py 每輪把清單（非空才）帶進 system，這要動範本，待裁。子 agent、do_task 各有 stack，清單天生分開。工具半天，自動帶再半天。 |
| [04 施工結果](04-施工結果.md) | 11-11 線 K：使用者改口「啊，grep/glob得做」「todo/goal也一起做吧」——grep、glob 兩支進 look 包，共用 `lib/base/file_walk.py`（代定 E1～E10、待裁 2 題）；todo 一支新包、不帶進 prompt（代定 F1～F9、待裁 1 題）；兩範本 40 支（含 goal） |
| [03 MCP client](03-mcp-client.md) | 一台伺服器匯入成一個包檔、每支外部工具＝一支 aos 工具；人用新指令 `aos-mcp-import` 連一次、凍結工具清單；每次叫才起伺服器、叫完收掉（stdio）。aos-tools／brain／act／aos-mcp 都不用改，eca 經 aos-mcp 自動有。外部說明加前綴、限長、凍結；JSON Schema 的 `$ref` 匯入時展開（不然會被當成 aos 指示詞）；金鑰走 env 檔。第一步 2～3 天；HTTP、sync、常駐排後面。 |

## 待裁總表

| 題 | 選項（推薦在前） | 在哪 |
|---|---|---|
| G1 搜尋一支還是兩支 | 甲 `grep`＋`glob` 兩支／乙 一支 `search` 分 mode／丙 只做 grep | [01](01-grep-glob.md#待裁) |
| G2 搜尋引擎 | 甲 純 Python／乙 有 rg 就用／丙 一律 rg | [01](01-grep-glob.md#待裁) |
| G3 尊重 .gitignore | 甲 預設尊重（問 git）／乙 不尊重只跳隱藏／丙 自己解析 | [01](01-grep-glob.md#待裁) |
| T1 清單每輪自動帶進 prompt | 甲 brain.py 接在 system 最後／乙 接在 history 尾巴／丙 不帶、靠腦自己 ls | [02](02-todo.md#待裁) |
| T2 子 agent／do_task 的清單 | 甲 各自獨立／乙 do_task 帶父清單唯讀／丙 共用 | [02](02-todo.md#待裁) |
| M1 外部工具怎麼進工具表 | 甲 匯入成包、每支一支／乙 通用 ls＋call 兩支／丙 aos-tools 新種類即時展開 | [03](03-mcp-client.md#待裁) |
| M2 伺服器設定放哪 | 甲 寫在包檔裡／乙 定義資料夾另一份 mcp.json／丙 `~/.aos/mcp.json` | [03](03-mcp-client.md#待裁) |
| M3 金鑰 | 甲 env 檔只記位置／乙 `${VAR}` 環境展開／丙 都收 | [03](03-mcp-client.md#待裁) |
| M4 伺服器行程 | 甲 先每次起、有狀態另議／乙 一開始就常駐／丙 永遠只每次起 | [03](03-mcp-client.md#待裁) |
| M5 誰能加伺服器 | 甲 只有人／乙 腦也能／丙 腦提人核准 | [03](03-mcp-client.md#待裁) |
| M6 工具全收還是挑 | 甲 全收可挑、超過 20 支 warning／乙 一定要列／丙 全收不給挑 | [03](03-mcp-client.md#待裁) |
| M7 外部說明怎麼更新 | 甲 凍結、人 sync 看差異／乙 每次重問 | [03](03-mcp-client.md#待裁) |
| M8 eca 怎麼用 | 甲 走 aos 轉接／乙 原生掛給 claude／codex／丙 每台自己選 | [03](03-mcp-client.md#待裁) |

各份的「代定」段是我先定的小事（名字、上限、代號、包），可翻案。

## 裁定（2026-11-11，使用者選項框）

| 題 | 裁定 |
|---|---|
| G1 搜尋幾支 | 「grep 和 glob 兩支」 |
| G2 引擎 | 「純 Python」 |
| G3 .gitignore | 「預設跳過，問 git」 |
| T1 清單每輪自動帶進 prompt | 「不帶，腦自己查」（不照推薦；所以不動 brain.py／範本，`--todo` 那半不做） |
| T2 子 agent／do_task 的清單 | 「各自獨立」 |
| M1 外部工具怎麼進工具表 | 「匯入成包、每支一支」 |
| M2 伺服器設定 | 「寫在包檔裡」 |
| M3 金鑰 | 「env 檔，只記位置」 |
| M4 伺服器行程 | 使用者自己寫的：「先做每次呼叫起一台。後續我們可以做一個專門的常駐aos proc，有需求的話就指向他，將request丟給他。」 |
| M5 誰能加伺服器 | 使用者自己寫的：「不限制，有權限就能用。」（頂層的解讀，非原話：不另設「只有人能加」的限制；匯入功能誰拿得到誰就能用，腦若有那支指令／工具的權限也能加。） |
| M6 全收或挑 | 「預設全收、可以挑」 |
| M7 外部說明怎麼更新 | 使用者自己寫的：「可選。默認用凍結的。」（頂層的解讀，非原話：每台伺服器可選「凍結」或「每次重問伺服器」，預設凍結。） |
| M8 eca 怎麼用外部伺服器 | 「每台伺服器自己選」（不照推薦；包檔裡標記走 aos 轉接或原生掛給 claude／codex，兩條路都要做） |

背景：同日使用者決定 `thought` 改名 `do_task`（殘留選項不加），以及「stack只能在aos-exec建<-這個規則刪除」。

同日稍後使用者：「mcp這塊先到這邊就好，不急著做。」——MCP client 停在設計稿，不排施工。

同日稍後使用者：「grep/glob、todo也可以之後再做」——三樣新工具都停在設計稿與裁定，不排施工。

再稍後使用者改口：「啊，grep/glob得做」「todo/goal也一起做吧」——grep／glob、todo 施工，結果見 [04](04-施工結果.md)（goal 見 [goal/02](../goal/02-裁定與施工結果.md)）。

## 建議施工順序

1. grep／glob（獨立、最小、馬上減少 shell 灌爆 history）。
2. todo 工具本身；T1 裁了再做 brain.py 那半。
3. MCP 階段 1（stdio、人匯入、凍結）；用 `uvx mcp-server-time` 實跑。
4. MCP 階段 2（HTTP、sync；看 M5 決定要不要給腦匯入）。階段 3（常駐或 eca 原生掛）另開設計。

三樣都要等線 C（subagent 改名、知識節點格式）收進 main 之後再動，知識節點照它的格式補。
