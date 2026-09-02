# 名詞表：回合邊界與崩潰現場
← [名詞表：回合、執行與喚醒](README.md)｜[BACKGROUND](../../BACKGROUND.md)｜[workshop](../../README.md)｜[待答問題](../../OPEN-QUESTIONS.md)

一回合從哪裡開始算、到哪裡算結束，以及沒走到結束時現場長什麼樣。

### world（世界／world folder）

**白話**：就是你交給 `aos exec` 的那個資料夾；資料夾現在長什麼樣，就是它現在的狀態。
**嚴格**：一個以檔案系統為耐久狀態容器、以 `<folder>/.aos/` 為指令區的執行單位；每次 `aos exec <folder>` 把它從一個回合推到下一個回合。
**在 aos 裡具體是什麼**：已存在；是任一經 `aos init <folder>` 建立 `.aos/` 的 `<folder>`，實際版面見 `aos-folder` 第三節〈版面〉。
**為什麼會冒出這個詞**：原始回合模型就把 folder 叫世界；[核心行程場](../../records/core-process-and-subprocess.md) 又用它來區分「耐久資料夾」與 OS process、lane。

### `.runi`（未完成回合現場／回合鎖）

**白話**：那批指令已經被拿走開始跑，但沒有人走到正常收尾，所以現場檔還留著。
**嚴格**：`inst.json` 被完整讀入後原子 rename 為 `inst.json.runi`，回合正常返回後刪除；存在時拒絕新 exec，表示上一回合沒跑完，不表示某個子指令成功或失敗。
**在 aos 裡具體是什麼**：已存在；`<world>/.aos/inst.json.runi`，規格見 `aos-folder` 第六節〈交接協定：三步，每步一次 `rename`〉，拒絕啟動的退出碼是 3。
**為什麼會冒出這個詞**：這是 T2 已落地的 claim/crash 邊界；後續研討常把它與 Effect `unknown`、lane 生命週期混用，所以必須明說它只管本地回合。

### 彙整（aggregate）、取件（claim）與釋放（release）

**白話**：彙整是把大家各自丟進收件匣的紙條疊成一份清單；取件是把那份清單從檯面上拿走收進口袋；釋放是做完之後把它撕掉——而撕掉這個動作本身，就是「這一輪有正常結束」的唯一證據。
**嚴格**：三步交接協定裡投遞（Deliver）之後的三步。彙整把 `inst.tempd/*.json` 按字典序攤平併成 `inst.json`；取件把 `inst.json` 原子 rename 成 `inst.json.runi`；釋放在整批正常返回後刪除 `.runi`。「取件的行程與釋放的行程是同一個」正是 `.runi` 那條不變式成立的唯一理由。
**在 aos 裡具體是什麼**：三支都已存在，實作在 `core/inst/src/handoff.cpp`，都是以 instruction 檔路徑為參數的公開函式，由 `core/inst/src/run_exec.cpp` 依序呼叫；規格見 `aos-folder` 第六節〈交接協定：三步，每步一次 `rename`〉。把它們另外長出 argv 入口是**提案**，目前不存在。
**為什麼會冒出這個詞**：[純 CPU 場](../../records/exec-as-pure-cpu.md) 整場都在問這三步哪幾步該外放；四位一致的判斷是取件與釋放**就是回合邊界本身**，外放等於把唯一的崩潰不變式降級成約定。

### 孤兒行程（orphan）、process group 與 `setpgid`

**白話**：你叫小孩去跑腿，然後自己先走了。小孩不會因為你走了就停下來，他會把腿跑完、把東西買回來放在門口——只是你已經不在，沒人知道他回來過。`setpgid` 是「讓小孩自己站成一隊」，好處是你在鍵盤上按 Ctrl-C 不會誤傷他，壞處是你想叫他停也叫不到。
**嚴格**：`aos exec` 為每個子行程呼叫 `setpgid` 使其自成 process group，因此送給前景 process group 的終端機信號打不到子行程；parent 被外部信號終止後子行程成為 orphan（由 init 收養）並繼續執行到自然結束，包含它自己的副作用與投遞。
**在 aos 裡具體是什麼**：**已存在，而且是刻意的**——見 `aos-folder` 第十二節〈已經被實作決定的〉。`timeout_ms` 那條路徑已經有對整個 process group 送 `SIGTERM`→`SIGKILL` 的處理（`core/inst/docs/exec.md`〈逾時與行程群組〉），缺的只有「parent 被外部信號砍掉」那一條路徑。
**為什麼會冒出這個詞**：[agent loop 黑客松第 1 輪](../../../hackathon/records/agent-loop.md) 四位獨立撞到同一件事——`.runi` 宣稱「有一回合沒跑完」，而事實是那回合由孤兒完整跑完並推進了 loop。評委判定這是本輪唯一從世界內部繞不過去的坑，也是規格兩句話互相矛盾的根因。

### running marker（起跑標記）與租約（lease）

**白話**：現在的鎖只寫「有人在裡面」。租約是把鎖換成一張條子：「誰進去的、幾點進去的、進去做第幾件事」。人回來的時候不用猜，看條子就知道。
**嚴格**：在 `fork` 之前落盤、內容至少含批次序號與子行程 pid 的 in-flight 紀錄，回合正常返回時清除；與 `.runi`（只表達「有一回合沒跑完」的鎖）的差別在於它攜帶進度與持有者身分，因此可用 `kill -0` 判定持有者是否仍存活。
**在 aos 裡具體是什麼**：**提案，目前不存在。** 它只能由 `aos exec` 本身寫，因為那是那個時間點上唯一活著的東西；`exit` 欄位補不了這一半（`exit` 是 parent `wait` 完才寫的，而崩潰的定義就是沒走到那一步）。形狀限制已有既有討論：`.runi` 的內容現在**就是那批 JSON**，包一層 header 會毀掉「`cat` 一下就知道卡的是哪一批」，所以主張 receipt 另放旁邊、且先寫 receipt 後 rename。原子建立要用 `renameat2(RENAME_NOREPLACE)` 或 `link`＋`unlink`。
**為什麼會冒出這個詞**：[agent loop 黑客松第 1 輪](../../../hackathon/records/agent-loop.md) 評委把它列為 `aos agent` 第一版**唯一要先做**的一件事，理由是它是唯一有實際金額的一條（三份重複計費現場），也是唯一世界內部寫不出來的——有人用 `test -f` 手寫過，輸給了一個長度等於一次模型呼叫的 race。
