# studio：一張單怎麼走完

← [README](../README.md)｜工作室本身（開隊、預算、閘門）看 [studio.md](studio.md)

工作室裡最花錢的不是做事，是「模型自己想流程」。所以流程寫死成工具：**每個工具一次做完一串
動作**（開檔、寄信、撥額度、跑測試、複製檔案），模型只要判斷「現在該做哪一步」。

## 一張單的一生

```
甲方下單 ──order_accept──> received ──plan_set──> planned ──task_assign──> in_progress
                                                                              │
                                dev 寫程式、tester 寫測試 ──task_report──> done
                                                                              │
                                            qa_run（至少一次 exit 0）──> qa_verdict
                                                                              │
                                              全部 passed ──> qa ──deliver──> delivered
                                                                （做不出來 ──order_fail──> failed）
```

一步一步是這樣：

1. 使用者跑 `aos-user order <世界> "做一支 todo.py" --budget ... --accept ...`，訂單落進 **sales**
   的 `inbox/user/`。
2. **sales** 叫 `order_accept`：開一張單、建好專案目錄、把整張單寄給 pm、對甲方回一張確認單。
3. **chief** 叫 `plan_set`：寫下架構、把工作切成幾個任務（每個任務指定誰做、要動哪些檔），寄摘要給 pm。
   寫程式派 dev-a／dev-b，寫測試派 **tester**；派給 qa 會被擋（qa 只驗不做）。
4. **pm** 對每個任務叫 `task_assign`：**先確保那個人有 tokens**（不夠就自動從 pm 的額度撥），
   再把整份說明寄給他。單子變成 `in_progress`。
5. 做事的人（**chief／dev-a／dev-b／tester**）做完叫 `task_report`：記下改了哪些檔，帶 `test_cmd` 的話
   當場在專案目錄跑一次測試，結果存進任務檔，然後寄摘要給 pm 與 qa。tester 的回報 `files` 裡一定要有
   檔名含 `test` 的檔，不然被退回。
6. **qa** 叫 `qa_run` 跑 tester 寫的測試，再叫 `qa_verdict` 判定。任務檔上沒有任何一筆 exit 0 的測試紀錄
   （`task_report` 的 `test_cmd` 或 `qa_run` 留下的）就不能判過，工具會擋。所有任務都 passed 時，單子自動變 `qa`。
7. **pm** 叫 `deliver`：把所有任務的檔案複製到 `team/files/final/<單號>/`，寄 sales 一張交付單
   （檔案清單、每個任務的測試結果、整隊到現在花了多少 token）。
8. **sales** 收到那封信，直接把交付單的文字回給甲方就好——不用自己重寫。

任何人任何時候都可以叫 `order_status` 看現況。做不出來就 pm 叫 `order_fail`。

## 工具一句話

| 工具 | 誰用 | 一句話 |
|---|---|---|
| `order_accept(order_id?, note?)` | sales | 接下甲方最新那張單（或指定單號）：開單、建專案目錄、寄 pm、回甲方確認單。 |
| `plan_set(order_id, architecture, tasks)` | chief | 寫下架構與任務清單，每個任務開一個檔，寄摘要給 pm。 |
| `task_assign(task_id, to?, spec?, tokens?)` | pm | 派工：先保證對方有 tokens（不夠就從自己撥，預設 50000），再把整份說明寄給他。 |
| `task_report(task_id, summary, files?, test_cmd?)` | chief／dev／tester | 回報做完：記檔案、跑一次測試、寄摘要給 pm 與 qa。tester 一定要列測試檔。 |
| `qa_run(task_id? / order_id?, command)` | qa／pm | 在專案目錄跑一個指令，exit 與輸出尾巴存進任務檔。 |
| `qa_verdict(task_id, passed, evidence?)` | qa | 判這個任務過或不過（判過要有一筆 exit 0 的測試紀錄）；全部過了單子就進 `qa`。 |
| `deliver(order_id, summary?)` | pm | 複製檔案到交付區、單子標 delivered、寄 sales 交付單。 |
| `order_status(order_id?)` | 全員 | 看單子與任務的現況（狀態、負責人、檔案、最近三條紀錄）。 |
| `order_fail(order_id, reason)` | pm | 這張單做不出來：標 failed 並寄 sales。 |

回值都是很短的 JSON，成功是 `{"ok": true, ...}`，出事是 `{"ok": false, "error": "..."}`。

**誰能用哪個**照上表擋：dev 叫 `deliver` 會被回一句「你不能用」。**做的人跟驗的人分開**：`plan_set`／`task_assign` 不能把任務派給 qa（09-07 決定：qa 不能又寫又驗，寫測試另設 tester）。owner 是老闆，什麼都能用（收爛攤子用）。
不在工作室裡（找不到 `team/team.json`）時每個工具都直接回 `{"ok": false, "error": ...}`。

## 檔案長什麼樣

全部在 owner 世界的 `team/` 底下（每個成員家裡的 `team` 都是指向它的 symlink，所以大家寫的是同一份）：

```text
team/orders/<order_id>.json          一張單
team/tasks/<order_id>-t1.json        單子底下的第一個任務
team/projects/<order_id>/            這張單的工作目錄（測試就在這裡跑）
team/files/final/<order_id>/         交付時複製過來的成品
```

單子：

```json
{"id": "order-20260907-101500-000123", "task": "做一支 todo.py",
 "budget": {"tokens": 200000, "hours": 1}, "acceptance": ["加列刪都能用"],
 "status": "in_progress", "client": "user", "project": "team/projects/order-...",
 "plan": {"architecture": "一支 todo.py 加一支 test_todo.py", "by": "chief", "time": "..."},
 "tasks": ["order-...-t1", "order-...-t2"],
 "history": [{"time": "...", "by": "pm", "what": "派 order-...-t1 給 dev-a"}]}
```

任務：

```json
{"id": "order-...-t1", "order": "order-...", "title": "寫 todo.py",
 "spec": "加、列、刪三個函式", "owner": "dev-a", "files": ["todo.py"],
 "status": "passed", "report": "加列刪寫好了",
 "tests": [{"cmd": "python3 -m unittest", "exit": 0, "output": "…OK"}],
 "qa": {"passed": true, "evidence": "unittest 全過", "by": "qa"}}
```

單子的狀態只有 `received → planned → in_progress → qa → delivered`，外加隨時可以掉進 `failed`；
任務的狀態只有 `assigned → done → passed / failed`。

## 幾個實作上的規矩

- **測試怎麼跑**：`task_report` 的 `test_cmd` 與 `qa_run` 的 `command` 都用 shell 在
  `team/projects/<order_id>/` 底下跑，**最多 60 秒**，只留 exit 與 stdout＋stderr 的**尾巴 2000 字**。
  超時或跑不起來就記 `exit: null` 與一句原因，不會弄死那一格。
- **額度自動撥**：`task_assign` 先看那個人還剩多少 tokens，不夠就用 `team_grant` 從 pm 的額度補到你
  要求的數字（預設 50000）。pm 自己也不夠時整個 `task_assign` 失敗、什麼都不改，錯誤訊息告訴你差多少。
- **檔案清單是相對專案目錄的**：`files: ["todo.py"]` 指的是 `team/projects/<order_id>/todo.py`。
  `deliver` 找不到的檔會列在回值的 `missing` 裡，其他照複製。
- **`order_accept` 找信的方式**：掃 `inbox/user/` 的未讀與 `read/`，挑**最新那封帶 `order_id` 的**。
  所以就算 agent 已經把信收進記憶（`user` 來源的信會當場搬進 `read/`），還是找得到。讀掉的信會搬進
  `read/`。同一張單接第二次會被擋。
- **`on_system_prompt` 每次問模型前塞 2～3 行**：你手上還沒結束的單是哪張、什麼狀態、你負責的任務
  和它的說明前 200 字。沒有就一個字都不加。所以模型不必為了知道「我現在在幹嘛」再開一輪讀檔。
- 這個包**不掛 `on_idle`**，不會自己寄信給自己。

## 已知坑

- 共用檔沒有鎖。兩個人同時對同一張單寫東西，後寫的會蓋掉前面的（跟 `team/` 其他共用檔一樣）。
- `plan_set` 可以重下，任務編號是 `<單號>-t1`、`-t2`… 照順序重編，舊任務檔不會刪掉。
- 交付只複製檔案的**檔名**到交付區（不保留子目錄結構）；同名的檔會互相蓋掉。
- 單子與任務只有狀態機，沒有時限、沒有自動催辦、沒有換人。
