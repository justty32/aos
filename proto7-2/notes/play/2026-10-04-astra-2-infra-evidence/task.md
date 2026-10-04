# 任務：proto7-2 第二輪基礎設施回歸（回歸＋故障注入）

可以開自己的 subagent 平行做事（最多 4 條）。

（說明：這是 repo 擁有者委託的軟體品質工作——對自己寫的本機排程原型做回歸測試與故障注入，找出 bug，產出是一份測試報告。不涉及任何外部系統。）

你在一份副本裡（目前目錄），可以隨意跑、改這份副本、寫腳本。**不要碰副本以外的路徑**（/tmp 可以用，但跑完要清掉你建的 /tmp 資料夾與程序；收程序用 PID，不要用 `pkill -f`；列資料夾用 `/bin/ls` 或 python，不要用 `ls`）。不要呼叫任何 LLM；嚴禁 LM Studio、ollama、`lms`。繁體中文（台灣用語）寫報告。

## 背景
你上一輪報告：`proto7-2/notes/play/2026-10-04-astra-1-infra.md`（證據在同名 `-evidence/`），A2-01～A2-13，總評要三件核心工作：未知狀態一路保留、回合與槽有足夠身分證據、控制意圖重播只生效一次，並做成固定回歸矩陣。

之後 commit 5cf34d7f、9d59e233、cd26699c、29e142e2、fb2fb8e1 宣稱：
- A2-01～13 全修（A2-09 只改 spec §8：用量以 run 為單位、跨 run 相加、總數是已觀測下界）。
- 三態收斂：/proc 讀取單一入口（讀到／不在／讀不到）；回合只有 `open` 明確 false 才算關；birth 壞時看同槽 exit／pid 的 run，判不出停在不知道等人工。
- node 登記要求路徑無符號連結，之後變連結＝missing；restart 的 once 與 birth 帶 `ctl_id`（ctl 的 id 或內容＋mtime 雜湊），重播不重做；CLI 檔名多 `@<owner>`；rounds 倒數按 owner。
- dot tmp 清理（寫者 pid 不在）；last_error 多 `kind`；status 多 `uncertain`；history max-lines 套事件歷史、tock 先提交總結再寫 tock.json；回合中 wake 不留到 idle。
- 跟原約定不同處：environ EACCES 的程序當「不是任務」（spec §11）；tick 也檢查上一回合 open 就拒絕（退出碼 3）；root 取 realpath；after-popen 被殺時 runner 活著就當活。
- 註解疑點 14 處全修（`proto7-2/notes/problems.md` 最後一節）。
- 測試 219 項（新增矩陣 116 項：tests/test_matrix_*.py）。

## 要做
1. **回歸**：A2-01～A2-13 逐條用上一輪的重現（你的 evidence 腳本）判定 已修／部分／未修，附證據。
2. **審矩陣**：tests/test_matrix_*.py 是否真的覆蓋你上一輪的故障類別？測試鉤子（AOS7_TEST_FAULT 等）注入的位置是否等同真實故障？有沒有「測試綠但真故障仍壞」的盲點？補幾個矩陣沒涵蓋的組合實測。
3. **審「跟原約定不同處」**：environ EACCES 當不是任務是否會造成漏收（例如任務以不同 uid／setuid 程式跑）；tick 拒絕開回合會不會在某些情況永久卡住（要人工時 status 是否看得懂、恢復步驟是否寫清楚）；ctl_id 用內容＋mtime 雜湊是否會誤認兩次真正不同的請求為同一件（同內容兩次 restart）。
4. **停在「不知道／要人工」的狀態**：列出系統現在所有會停下等人工的情況，評估是否合理、status／文件是否讓人看得出該做什麼；有沒有不必要地停太多（可用性退化）。
5. **長跑與負載**：例如 50 node × 1000 回合或你判斷合適的規模，看 CPU、檔案數、延遲、是否有任何 uncertain 誤報。
6. **找新問題**：編號 A3-01 起，分〔bug〕〔技術選型〕〔要使用者決定〕（最後一類少而精）。總評：剩下的是結構性還是邊角，下一步該繼續回歸、還是可以開始接 kernel。

## 產出
- `proto7-2/notes/play/2026-10-04-astra-2-infra.md`：開頭摘要；回歸表；矩陣審查；不同處審查；人工停點表；長跑；A3- 新問題；總評。
- 證據 `proto7-2/notes/play/2026-10-04-astra-2-infra-evidence/`（腳本＋精簡 JSON，不放大檔），並把本任務書複製一份進去叫 task.md。
- 只寫這兩處，不改程式或其他文件。結束前確認沒有你的殘留程序與 /tmp 資料夾。
