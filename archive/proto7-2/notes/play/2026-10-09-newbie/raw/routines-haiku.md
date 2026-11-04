## 試用者
Claude Haiku（新手）
## 分鐘
0.4
## 有沒有跑成功
成功，`added routines hello next tock (every 3r)`、`added schedule once ...`、`routine hello every 3r last 13 code 0 next round 16`；out.log 有 routine 1、4、7、10、13 回合各一次與 schedule 一次；daemon 最後 stopped。
## 對外指令數
6：`aos7-daemon`、`aos7-ctl daemon register`、`aos7-ctl daemon stop --kill`、`aos7-routines add`、`ls`、`rm`
## 新概念數
8：routine、schedule、inst、node、daemon 根、keep 任務、tick／回合（`r` 單位）、wf-table/1 表
## 卡點
1. [第 34～43 行] README 沒說 daemon 會不會佔住終端；自己加 `&`，`wait "$D"` 的意思要猜。約 2 分鐘。
2. [第 35 行 timeline.json `interval_ms: 200`] 沒說明控制什麼，照抄。
3. [第 40 行 `sleep 3`] 寫死 3 秒沒說為什麼。
4. [第 42 行 `.aos/tasks/routines/out.log`] 路徑從哪來沒解釋。約 1 分鐘。
5. [第 50 行] 寫「5」、註解說 4 次 routine＋1 次 schedule，實跑得到 6（5＋1）；次數取決於睡眠時間，數字與註解對不上。
6. [回合／tick／tock／keep 任務] 第一次讀都不懂，要靠五個概念與契約卡拼；「回合差」「秒型看時間差」不直白。
7. [表格式一節] `source: workflows/routines.md`、`contract: wf-table/1` 指向讀不到的文件。
## 五條分數（0–10，10 最好）
- 容易上手：7 段落貼上就通，但要懂背景執行與等待。
- 容易理解：5 tick、回合、keep 任務、wf 表要跳讀契約卡。
- 複雜的藏起來：6 使用者面 add／ls／rm＋daemon，lock、claimed、最多一次藏在後面。
- 外層簡單但全面：6 碰到「最多一次」「錯過很久只做一次」要回去讀規則。
- 要背的少：7 常用 add、ls、rm 與起 daemon。
- 平均：6.2
## ELI5
這是一個小幫手，在「心跳」的時候去看一張清單。清單上兩種事：每隔幾次心跳做一次的，和到指定時間只做一次、做完就拿掉的。`add` 寫進清單、`ls` 看清單、`rm` 刪掉。要先啟動背景程式，心跳才會跳。
## ELI5 之後還複雜嗎
是，daemon 怎麼起、tick 與回合差別、表格式、最多做一次的保證，ELI5 都沒涵蓋。
