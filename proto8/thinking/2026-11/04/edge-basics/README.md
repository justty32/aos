← [2026-11-04](../README.md)｜同晚 A 線（llm kernel）：[think-as-function 08](../think-as-function/08-邊緣狀況實測.md)｜B 線（daemon／aos-agent）：[four-elements 09](../four-elements/09-邊緣狀況實測-11-04-夜.md)

# 基礎積木邊緣狀況實測（11-04 夜，C 線：aos-exec、aos-loop、aos-json、aos-post、aos-tools、aos-mcp）

使用者 11-04 夜（在打遊戲、沒空回答）：「你先多嘗試，看看各種邊緣狀況」「我還在打遊戲，麻煩你繼續...」。

本檔只留結論：修了什麼、照設計就是這樣但容易踩的、風險自擔的、使用者裁的題。編號（#N）是當晚試的情境號。沒列的情境都照設計／docs 報錯，訊息說得清楚。

## 修了的（11-04 夜）

- **aos-exec**：XXX 是空字串＝`ArgumentsBad`（不再默默跑 cwd 的 `_entry`）（#1）；JSON 字串轉向寫 `""`＝`EntryBad`（#2）；串流開不了時說哪個串流、哪個路徑、為什麼（上層不在時提示 `stdout_mkdir: true`）（#3）；`stderr_merge: true` 又寫 `stderr` 的 `PathConflict` 說清楚二選一（#4）；`檔#/指標` 報錯帶指標（#5）；`.env` 帶 BOM 時提示存成不帶 BOM 的 UTF-8（#6）。
- **aos-loop README 範例**用單子寫 `exec`、附一行注意（原範例 `{"exec": ["aos-fsm", "fsm.json"]}` 跑不起來）（#14）。
- **aos-json**：「多了參數」的提示與 docs 改對（負數值照寫）（#20）。
- **aos-post**：信件名稱有換行、tab 等控制字元＝`ArgumentsBad`（#26）；`done --reply` 時 `reply_to` 信箱不在，報「回信寄不出去……原信留在 cur/」（#28）。
- **aos-tools**：`--tooldef` 卡住時整群收掉、不留孫行程（#35）。

## 照設計，但容易踩

- loop.json 的 `exec` 陣列是「aos-exec 目標＋參數」，不是 argv；要 argv 寫單子 `{"argv": …}`（#13）。
- `envs_clear: true` 只剩五個 `AOS_*`，PATH 也沒了（#8）。
- `AOS_ENTRY` 不收絕對路徑，入口名一段段走（N-61）（#11）。
- aos-json：物件 key 上萬時平方慢（2 萬 key 0.17 秒、20 萬 16 秒；`ordered_json` 保序的代價），陣列不受影響；aos 的設定、表、history 都遠低於此（#25）。重複 key 寫回時只留後者（#24）。壞檔一律 `FileBad`、整份覆蓋也不准（#21）。
- aos-post：`order.lock/` 是空資料夾時等 10 秒收屍才寄出（#30）；序號超過 12 位的名字不再算有序（#31）；被打斷的 `send --ordered` 半截留在 `tmp/`，收屍歸寄信人上層（#32）；只有「12 位數字＋點」的名字被擋（像有序名）（#27）。
- aos-tools 不替工具驗 arguments，原樣進 stdin（#39）；call 時 `AOS_STACK` 資料夾不在會建、相對路徑照 cwd（#40）。

## 風險自擔（照使用者「很多都是自己要承擔的風險」，不處理）

- loop.json 的 `ctl` 與 `state` 同名（state 被當 ctl 讀、無害）、`ctl: "../x"` 出 stack 照用（#16）。
- aos-json 寫唯讀檔（444）照寫（rename 換新檔、權限設回 444；同 `sed -i`）；唯讀資料夾裡＝`WriteFailed`（#23）。
- 登記的工具有一個壞掉，整份 `aos-tools ls` 失敗，aos-mcp 的 tools/list 也整份失敗（「不猜不跳過」）（#37）。

## 要你看的題

### 題 1：工具失敗時，外部 agent（Claude Code 等）看不到原因

Claude Code 經 aos-mcp 叫 aos 的工具失敗時，原因（工具的 stderr、aos-exec 的「入口壞」等）只進 aos-mcp 自己的 stderr（MCP 用戶端的 log），agent 只看到「失敗」和 stdout（#43、#44）。

**11-05 使用者選「附 stderr 尾巴（推薦）」**，已落實：aos-mcp 接住工具（含 aos-tools、aos-exec）的 stderr、照樣轉印到自己的 stderr；退非 0 或逾時時，回給外部 agent 的內容多一段 text「stderr（最後 2048 位元組以內）」（超過 2 KB 前面加「…」）；跑起來之後 `tools/list` 失敗的 JSON-RPC 錯誤訊息也附 aos-tools 那次 stderr 的最後一段；成功的不附。例外加在 [C-52](../../../../docs/CONCEPTS/01-設計理念/03-最高原則與兩條總原則.md#兩條總原則10-15-使用者定原文10-15-深夜加嚴)，只限 aos-mcp 這個對外出口。

## 沒測到的

- aos-agent／agent-fsm 的 act 格怎麼把工具失敗交給腦（B 線範圍）；aos-mcp 的 `--enable-logs`、多份登記檔撞名。
- aos-loop 內嵌單子在新 libaos-exec 下的訊息（當晚 aos-loop 沒重建）。
