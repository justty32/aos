# 人手打的操作 CLI

← [規格入口](../README.md)｜[協議](../protocol/README.md)｜[全部裁定，後批優先](../../notes/2026-09-29-verdicts.md)

**待實作規格**；指令／畫面為驗收預期，七步使用本地測試 LLM。

## H-001．共用讀法〔使用者方向；工程預設〕

形狀 `aos <用途> <動作> [更深]`，第一層 daemon/node/kernel/agent/llm/attend/clean/inst；短形見 alias。N 是 node、K 是 kernel、R 是發件／回件 node、T 是 inst 目標、F 是檔案、S 是 socket；[] 可省，| 擇一。

路徑按 cwd，--to 相對 N；底層 --node 省略用 cwd，tick 跑任務時 cwd 是 node 根。IPC 用 --socket S 或 --daemon-config F。通常 stdout 放結果，stderr 放診斷／確認；daemon 例外見下。表中 --json：IPC 印原 RpcResponse，投件印 FileRpcRequest，其餘依該列；每筆加換行。沒列 --json 的命令傳它回 2。

設定指令持 tick 鎖提交，下格採用；草稿放樹外，work/ 放暫存。手改先 pause、排空、持鎖改，resume 驗證提交。unregister、特權佈建、提高額度、採用手改、delete 清理先問 y/n；有 --yes 的列可明示略過，未確認回 125。Ctrl-C 本身就是停機指令。

### H-002．失敗代稱

成功回 0；空清單合法，缺用量不補零。

| 代稱 | 結束碼與處理 |
|---|---|
| IPC | 2 參數錯；125 前置失敗；1 拒絕／斷線／結果未確認。保留原 error，stderr 印代號與白話。 |
| 查詢 | 2 用法；125 前置；1 無資料／損壞／讀取失敗。 |
| 改檔 | 2 格式／路徑錯；75 鎖忙；125 前置；1 寫入失敗已還原；3 提交／還原故障並擋新格。 |
| 投件 | 2 輸入錯；75 鎖忙；125 前置；1 讀取／投遞失敗或未確認；3 提交／還原故障。保留原件與 ID。 |
| module | 2 用法／設定；75 鎖忙；125 前置；1 處理／保存失敗；3 提交／還原故障。0 可以是等待結果。 |

75 未動手，可稍後重下；斷線先查、unknown 不重做。訊號看 wait，125 不證明未啟動。

## 章節導航

- [H-004 指令總表](commands.md)：daemon、node、kernel、agent、llm／attend／clean／inst 五組。
- [H-030 CLI 怎麼變成 method、H-035 常用 alias](mapping-and-alias.md)
- [H-036 七步走到底](walkthrough.md)
- [H-034 舊缺口](gaps.md)
