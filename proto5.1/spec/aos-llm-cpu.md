# aos-llm-cpu 程式規範（第 1 版）

← [proto5.1 README](../README.md)｜格式：[llm-cpu.md](llm-cpu.md)｜HTTP 函式：[aos-llm-ask.md](aos-llm-ask.md)

`aos-llm-cpu [dir]`：一次收屍，再同步處理一份請求；省略 dir＝`.`。沒有背景 worker、pid、容量設定、
重試、優先序或 usage；容量就是同時叫幾個 cpu 進程。

## 1. 一次做什麼

1. 讀驗 info（含指示詞），建立缺少的 requests／running／done。
2. 收屍：running 逐檔檢查，mtime 距今**大於** `engine.timeout_ms / 1000 + 30` 秒就過期。
   若結果不存在，寫 `{"ok": false, "error": "llm cpu 執行逾時或上次中止…"}`；結果已存在就保留。
   接著搬到 done。收掉本次看見的全部過期檔；done 已有同名就跳過，不覆蓋。
3. requests 照檔名排序，找第一份 running／done 都沒同名的請求，讀驗它；刷新 mtime，再 rename 到
   running＝認領。來源已被取走就試下一份。刷新是必要的：rename 本身不更新 mtime，排隊時間不能
   算成模型執行時間。壞檔退出 1 並留在原位，不自動越過。
4. 解鎖後呼叫 `aos_llm_ask.call(engine, body)`。成功包 `ok:true` 與 message；`EngineFailed` 包
   `ok:false` 與白話 error。urllib 建立錯誤 URL／header 的 ValueError 也包失敗結果。
5. 再進短鎖，確認 running 仍是自己認領的檔（device／inode）；若已被收屍搬走，丟棄這份遲到回覆。
   否則先以 `.tmp` → rename 發布結果，再搬原始請求到 done。done 已有同名也不覆蓋。
6. 有問過或有收屍＝0；完全沒處理＝101。即使結果 `ok:false`，cpu 已處理完仍是 0。

收屍沒有殺掉別的進程。HTTP timeout 是 urllib 的等待 timeout，不是整筆工作的 hard wall clock；
慢速持續回資料仍可能超過期限。另一顆 cpu 把它收屍後，原進程若終於返回，不能再蓋掉收屍結果。

## 2. 為什麼有短鎖

POSIX `rename(src, dst)` **會覆蓋已存在的 dst**，不能把「目標已在」當成 rename 會失敗；
先 exists 再 rename 也有競態。本實作以 `.queue.lock` 的 `fcntl.flock(LOCK_EX)` 包住送件、收屍、
認領與完成的檔案狀態轉移。這是對原先「不用鎖」建議的最小修正，仍用 rename 認領，仍可多 cpu
同時 HTTP；**HTTP 期間不持鎖**。鎖檔常駐，進程結束由 OS 釋放鎖，不需要收鎖檔屍體。

這是本機 POSIX 協作協議；手動改佇列、或其他不拿同一把鎖的寫入者，不在競態保證內。
同名碰撞檔保留，可能需人工排除。檔案 I/O 失敗回讀驗錯誤，尤其結果寫失敗時保留 running。

## 3. 命令列與函式庫

| 退出碼 | 意思 |
|---|---|
| 0 | 有處理請求或收屍；引擎失敗已寫結果也算 |
| 101 | 沒有可處理的請求、也沒有收屍 |
| 1 | 讀驗或檔案 I/O 錯；stderr 一行 `aos-llm-cpu: <代號>: <白話>` |
| 2 | 用法錯：未知旗標、dir 不是資料夾 |

stdout 永遠不印東西；引擎錯誤交到結果檔，不額外印 stderr。

`aos_llm_cpu.load(dir, env=None)` 只讀驗 info、回 `{"dir": 絕對路徑, "metainfo": …}`；
`queue_lock(dir)` 是 context manager，建立佇列並拿共用鎖，供 agent 交件；
`tick(dir, env=None)` 回 0／101，讀驗失敗丟 `AgentError`；`main(argv=None)` 是 CLI 入口。

## 4. 故障界線

- 同目錄 rename 保證讀者不見半份 JSON，**不是斷電持久化承諾**（未 fsync）。
- 崩在認領後、發布結果前：mtime 到期由下一顆 cpu 收屍。
- 崩在發布結果後、搬 done 前：收屍保留已存在的結果。
- agent 已收走結果、cpu 又恰好崩在搬 done 前：之後收屍可能再發布失敗；沒有 request id／交易記錄
  就不能消除這個窗口。本階段記錄限制，不擴增協議。
- 壞 requests/running 會退出 1；程式不猜 result、不幫忙丟掉請求。
