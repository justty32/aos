# proto5.1 第 5 段任務書：照 fable 重審修（2026-09-22）

接 [stage4-task.md](stage4-task.md)；先讀 [review-fable.md](review-fable.md)（全部）、[findings.md](findings.md) #36～#44、`stage4-report.md`。
決策來源仍是 `proto5/notes/2026-09-22-decisions.md`（不要推翻已拍板的方向）。一樣只動 `proto5.1/`；問題接第 45 條記進 findings。**保持 KISS**。

使用者拍板：R1～R3、R5～R9、R14～R21、R22～R27 這一段全部做；R4、R10～R13 不做（已進 proto5/backlog）。R8 明確接受「三種失敗回音統一成 `{"ok":false,"code":"代號","msg":"白話"}`」。

## 必修（R1～R3）
- **R1**：aos-run 帶 `--home` 時記啟動時的 `os.getppid()`，每圈比對，變了就當收到第一次 TERM（做完本次就停）。daemon 啟動時掃 `runners/*/run.json` 的 `pid`，還活著就拒起（`AlreadyRunning`）。規範寫進 aos-run.md／aos-daemon.md。
- **R2**：cpu 佇列鎖內讀驗失敗的檔搬 `bad/<name>.json`、stderr 一行、繼續處理下一份，tick 最後照樣退 1。結果寫不進去（OSError）也把請求搬 done、不留 running。統一成一條規則：**能讀出 result 路徑的壞 payload 一律認領後寫 `ok:false`**；llm 的 `_validate` 搬進 execute，`tick` 的 `validate` 參數拿掉（R27）。cpu-queue.md／llm-cpu.md 改。
- **R3**：hold 期間固定睡 50 ms 再看；`held` 只在變化時寫。aos-run.md 改。

## 回流前順手改（R5～R9）
- **R5**：run.json 加 `last_target`（完成時寫）；kernel 用它對帳，busy 時也能算一次。findings #41 的保守數法改掉。
- **R6**：daemon 主迴圈無條件 `save()` 拿掉，只在變動時寫。
- **R7**：kernel add 時固化一次；tick 只讀驗，內容相同就不重寫 `procs/*.json`。
- **R8**：cpu 結果、daemon 回音、kernel syscall 回音三種失敗一律 `{"ok":false,"code":"<代號>","msg":"<白話>"}`。cpu 結果的 code 至少：`Reaped`（結果不明）、`UnknownModel`、`Timeout`、`EngineFailed`、`BadPayload`；成功仍 `{"ok":true,...}`。agent 認「結果不明」改看 `code == "Reaped"`，tool 訊息文字照舊「結果不明：工具可能已經跑了，也可能沒有」。錯誤代號沿用 agent.md 那套命名風格。三份格式規範改。
- **R9**：daemon 家加 `info.json {"_metainfo":{"_type":"daemon","_version":1}}`（daemon 起來時沒有就建；ctl／kernel 認家先看它）；`aos-kernel boot` 把 daemon 家絕對路徑寫進 `K/info.json` 的 `daemon` 一格，之後 tick／ls／rm 都讀這格，不看環境變數；kernel state 與 rm syscall 裡的 `pid`（其實是 NAME）改名 `name`。

## 不一致與拿掉（R14～R27）
逐條照 review-fable.md §4、§5 做：R14 同名拒收改丟 AgentError `ReadFailed`（或規範改成 io 錯，二選一、規範程式一致）；R15 `submit` 驗 result 父目錄存在；R16 aos-kernel.md 改寫成「只看最後快照的 pid 欄」；R17 kernel remove 逾時與 daemon ctl 逾時用同一個代號；R18 規範補後果；R19 agent.md 連結文字改對；R20／R23 kernel state 的 `since`、`bad_exit` 拿掉；R21／R25 daemon 檔案請求的 `ls` op 拿掉；R22 `reason` 變數拿掉；R24 `queue_lock` 別名與 `--dry-run` 拿掉；R26 tool 請求 inst 的 `stdin`／`stdout` 格不驗不收。

## 測試、真跑、文件
- R1（kill -9 daemon 後 runner 自己停；重啟拒起）、R2（壞請求進 bad、後面的單照做；結果目錄不在→搬 done）、R3（hold＋interval 0 不吃 CPU：0.5 秒內 run.json mtime 最多變 1 次）、R5、R8 各至少一條測試。全套綠。
- 真跑同第 4 段（`stage5-demo.py`，可從 stage4-demo.py 改），貼 ls、最後記憶、stop 後 `pgrep -f aos-` 空。
- 文件：`README.md`（分段表第 5 段「做完」）、`lib/README.md`、規範、`notes/stage5-report.md`（檔案清單、測試數字、真跑、findings 新增幾條、R 編號逐條「做了／怎麼做」對照表）。
- 只動 `proto5.1/`；不 commit／push／stash／checkout。
