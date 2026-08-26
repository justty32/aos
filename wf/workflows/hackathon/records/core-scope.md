# core scope 黑客松紀錄

> **以下是風格模擬，不是本人的意見。** 文中的 Carmack、Armstrong、Cantrill、Thompson 都是 persona 名稱，不是本人發言或引述。

| 項目 | 內容 |
|---|---|
| 題目 | 用現有的 `aos`（不改 C++、不 build）跑出一條三回合 agent loop，中途以 Ctrl-C、`kill -9`、rename 前中止，記錄重開後必須自行補上的工作；問出 temp＋rename 手寫次數、哪種 unknown 無法由本機補回、是否出現第二個需同時管理的工作，以對應近期 core scope 的三種大小。此題承接 OPEN-QUESTIONS 第 2 題「近期 core 要回撤到哪裡」。 |
| 開場日期 | 2026-08-26 |
| 環境 | WSL Ubuntu；codex 0.149.1；`-s workspace-write`；無網路；四位平行；單輪逾時 1800 秒；R1 費時 9.5 分鐘。 |
| Reasoning effort | `model_reasoning_effort=high` |
| 狀態 | 第 3 輪已完成 |

| 參賽者 | persona | 場地 | codex thread id（續輪 resume 用） |
|---|---|---|---|
| p1 | John Carmack | `~/aos-hack/core-scope/p1` | `01a03cea-1d12-7132-9ec5-8e10bf7e113c` |
| p2 | Joe Armstrong | `~/aos-hack/core-scope/p2` | `01a03cea-1d11-74a2-97ac-ecb1356772ff` |
| p3 | Bryan Cantrill | `~/aos-hack/core-scope/p3` | `01a03cea-1d15-74a3-9e2d-6fc47eec1671` |
| p4 | Ken Thompson | `~/aos-hack/core-scope/p4` | `01a03cea-1d12-7603-bf3d-b304f25b365b` |

## 第 1 輪紀錄

### 1. 各人做了什麼

**Carmack persona。** 這一路用現成的 `./build/bin/aos` 跑一個 world，把三回合固定成「假模型產生具名 tool call → 固定 argv 工具呼叫假 provider → 假模型讀回結果」。基線三回合全到 final，三次 `aos exec` 都回 0。之後在同一條 loop 內測了 SIGINT、SIGKILL，以及 tool result rename 前 SIGTERM；三種事故最後都靠人工處理現場走回 final。SIGKILL 另做了 provider accepted／dropped 兩個外部結果不同、但本機 snapshot 相同的對照。

**Armstrong persona。** 這一路用 POSIX shell、假模型和現成 `aos` 做串行 loop，工具是 allowlist 限制的 `append_once`。所有本機狀態共用一支 `atomic-publish.sh`，`deliver.sh` 只改投遞 target。基線完整跑完；rename 前 SIGKILL、單次 exec 的 SIGINT、provider effect 後 `kill -9` 三個正式事故場也都經人工修復走到 final。Ctrl-C 案封存 `.runi` 後只重投未啟動的 schedule；`kill -9` 案則刻意做了一次盲重試，外部 ledger 由一筆變成兩筆。第一次 baseline 本身成功，但外層 `tee` 因 evidence 目錄尚不存在而沒有保存 transcript，之後另開 fresh world 重跑留證。

**Cantrill persona。** 這一路也是單一 world 的串行三回合 loop，工具是 allowlist 限制的 `write_marker`；本機結果共用 `atomic-publish.sh`，外部效果先進 world 外的假 provider ledger，故障點用 phase marker 定位。基線到 final。Ctrl-C 在 model response 尚未提交時發生，靠 provider query 補回；`kill -9` 在 tool effect 已發生而 result 尚未提交時發生，也靠 provider query 補回；delivery rename 前殺 publisher 後，人工驗 JSON、補 rename 才繼續。第一版 delivery 檔名多了一個點，`aos exec` 三次都回 0 卻完全不取件，失敗 world 保留下來。

**Thompson persona。** 這一路做最小串行鏈：假模型輸出 JSON instruction，三行 `deliver.sh` 投進 inbox，`aos exec` 執行，工具結果再回給假模型。基線三回合閉環，接著測 SIGINT、確認 child 已開始後的 `kill -9`、rename 前停住再殺，以及不可對帳 provider 的 accepted／rejected 對照；前三種靠人工搬開 `.runi` 或補 rename 繼續。最後完全拿掉 `aos`，以三行 shell 跑過同一條因果鏈。第一次 `kill -9` 太早，沒有打中預定切點，因此保留現場後重跑；SIGINT 現場起初以 `wc -l` 把沒有換行的 effect 檔誤報為 0，後以原始 bytes 更正。

### 2. 坑的總表

**四位獨立地都撞到：`.runi` 不是 instruction-level checkpoint。** 它只能表示整批沒有正常收尾，不能說批內哪一筆已完成、哪一筆未開始，更不能說外部 effect 有沒有發生。事故後直接重開的共同現場是拒絕執行；四份回報都出現同一類訊息：

```text
aos exec: refusing <world>: .aos/inst.json.runi already exists
restart_exit=3
```

Carmack persona 的原文是：

```text
aos exec: refusing /home/guanyu/aos-hack/core-scope/p1/wf/workflows/experiments/core-scope-r1/worlds/ctrl-c: .aos/inst.json.runi already exists
restart_exit=3
```

Armstrong persona 的 Ctrl-C 現場同一批內是工具後來完成、schedule 未啟動：

```text
.aos/inst.json.runi=present
turns/1/tool-result.txt=present
turns/1/tool.exit=missing
turns/2/schedule.exit=missing
provider_ledger_lines=1
ready_deliveries=0
```

因此四路的人工處理都不是「從中間續跑」：要嘛封存／搬開 `.runi`，要嘛保留它作法醫證據，再自行重造只含剩餘 instruction 的 delivery；若把原 batch 整批 replay，已發生的 effect 也會再跑。

**四位獨立地都撞到：rename 前留下 `.temp` 時，`aos` 不會讀半成品，也不會替 producer 完成提交。** 四路都看到 temp 存在、ready 不存在；重開可能 no-op 回 0，也可能先被另一份 `.runi` 擋住。恢復動作都是人先檢查內容，再手動 rename／`mv`。Thompson persona 的精確現場是：

```text
deliver_pid=41 temp=yes ready=no process_state=T
deliver_exit=137
Killed
restart_exit=0 result=missing temp_still=yes
manual_fix=rename_temp result=RENAMED_OK continued_exit=0
```

Cantrill persona 的現場還顯示，負責排下一回合的 instruction 已被殺，整輪仍回 0：

```text
schedule.exit=137
tool.exit=0
blind_restart_exit=0
final_exists=no
temp_exists=yes
ready_exists=no
runi_exists=no
```

**四位獨立地都撞到：外部 effect 已接受、回覆尚未落地時，本機沒有足夠資訊還原答案。** Carmack persona 的 accepted／dropped 兩份本機 snapshot SHA-256 相同，外部 ledger 卻分別為 1／0：

```text
case=unknown-accepted kill9_exit=137 ledger_lines=1
runi=yes
local_result=no
case=unknown-dropped kill9_exit=137 ledger_lines=0
runi=yes
local_result=no
local_snapshot_diff_exit=0
```

Thompson persona 也做出相同 client world、不同 provider 結果，且盲重試造成重複：

```text
rejected_exit=70 files=request,

accepted_exit=70 files=request,

client_worlds_diff_exit=0 provider_ledger_lines=1
blind_retry_exit=70 provider_ledger_lines=2 ledger=request-42,request-42,
```

Armstrong persona 的盲重試也留下兩筆相同 request：

```text
oracle_ledger_lines_after_retry=2
request-42
request-42
```

Cantrill persona 的兩個事故能繼續，是因假 provider 有 query：一次補 model response，一次補 tool result；這項資訊來自故障域外，不是由 world 內的檔案推回。

**三位獨立地都撞到：只看 `aos exec` 的退出碼，會把斷鏈或缺下一輪看成成功。** Armstrong persona 在工具 process group 被殺後看到 tool exit 137、schedule exit 66，但 `aos` 回 0 並清掉 `.runi`：

```text
aos_after_tool_group_kill_exit=0
.aos/inst.json.runi=missing
turns/1/tool.exit=present value=137
turns/2/schedule.exit=present value=66
plain_restart_exit=0
```

Cantrill persona 的 rename 前事故是 publisher exit 137 而回合 exit 0；Thompson persona 也記到 `aos exec` 回 0 只代表回合收完，不代表工具或後續工作成功。這三路都必須另外讀 per-instruction exit、queue、result、`.temp` 或 final 是否存在，才知道 loop 有沒有繼續。

**三位獨立地都撞到：只中止 `aos` parent 時，子行程可能繼續。** Carmack、Armstrong、Thompson persona 的 SIGINT／SIGKILL 現場都留下「parent 已停、child effect 後來完成、parent 沒寫 child exit」的組合。Carmack persona 另查了孤兒，原文中的 `orphan_alive_after_manual_kill=1` 是 `kill -0` 的退出碼 1，表示人工 kill 後孤兒已不存在。Armstrong persona 的 Ctrl-C 原文是：

```text
ctrl_c_exec_exit=130
immediate_restart_exit=3 stderr=aos exec: refusing /home/guanyu/aos-hack/core-scope/p2/p2-agent-loop/worlds/ctrl-c: .aos/inst.json.runi already exists
```

Thompson persona 確認 effect 的原始 bytes 為：

```text
$ od -An -tx1 -c round1/world-INT/effect.log
  65  66  66  65  63  74  6e
   e   f   f   e   c   t   n
```

**三位獨立地都在正常路徑看到 queue delivery 以外的 publish。** Carmack persona 統計正常 runtime 有 6 個發布位置，其中 4 組是 Deliver、5 組是一般 Publish的 9 組總數包含人工復原；Armstrong persona 的成功基線有 11 次 atomic publish，只有 3 次是 delivery；Cantrill persona 的 happy path commit 6 次，其中有非 delivery 狀態提交。三路都把 model response、effect request、attempt、tool result 或 final 寫成 temp 後 rename。Thompson persona 只替 delivery 寫 temp＋rename，沒有把其他狀態納入同一套 helper。

**Cantrill persona 單獨撞到 delivery 檔名會被安靜忽略。** 第一版 ready 檔名是 `delivery-turn1.timestamp.pid.json`；`aos exec` 連跑三次都 exit 0，queue 檔原封不動。其回報指出實作只接受從第一個 `.` 起恰好是 `.json` 的名稱，多一個點會被視為狀態後綴。這一路卡在 producer 已完成 rename、consumer 卻不取件，且沒有錯誤訊息。

**證據收集本身也出過三種事故。** Armstrong persona 第一次 baseline 已成功，但 `tee` 因 `p2-agent-loop/evidence/` 不存在而未留下 transcript；Cantrill persona 的 Ctrl-C PTY wrapper 一起被 `^C` 終止，所以沒有另外取得 `aos` 自身退出碼，只保留立即重開的 exit 3；Thompson persona 用 `wc -l` 數沒有換行的 effect 檔而誤報 0，之後以 `od` 更正。這些回報都保留了失敗或更正後的現場。

**四位都沒有測斷電 durability。** 四份回報都明寫本輪只測 process signal／rename window，沒有測 power loss、page cache、file fsync、directory fsync 或跨 filesystem rename。私有 helper 所證明的是 process crash 下的 temp／ready 可見性，沒有把結果外推到斷電。

另有三份回報提到場地複製品的 git metadata 不完整，`git status` 無法使用。Carmack persona 將新檔集中在實驗目錄；Armstrong persona 改比對 `core/` 全樹 SHA-256，前後都是 `4d4247…d0b`；Cantrill persona 改用時間戳稽核，並記錄 build artifact mtime 未變。四位都回報沒有改 C++、沒有 build 或 ctest。

### 3. 好處／壞處

#### 好處

四條路的正常基線都用現成 `aos` 完成三回合，第三回合確實讀到第二回合的工具結果；每回合都是短命 process，狀態留在 world，不需要常駐 driver、daemon 或 session。四路都以 allowlist 或固定檢查把模型輸出限制成具名工具，沒有直接把任意 argv 交給 `aos`。

四路也都看到 temp／ready 邊界會隔離 rename 前的檔案：未完成 rename 的 `.temp` 不會被當成 ready instruction 執行。`.runi` 的保守拒絕會留下事故現場，也阻止另一個 executor 直接靜默重播整批。Armstrong、Cantrill persona 另留下 per-instruction exit，能看出 137、66 與後續 schedule 是否執行；各個 request、attempt、result、batch、final 都可直接從檔案檢查。

Armstrong、Cantrill persona 分別用一支共用 publish helper 服務多種本機提交，沒有為每個輸出各寫一套 temp＋rename。Thompson persona 則實際跑過不使用 `aos` 的三行 shell 對照，留下相同因果鏈可以由更小機制完成的現場。

#### 壞處

事故後的恢復都落到人工檔案操作：判讀 `.runi` 內各 instruction 的進度、檢查 result／exit／provider 證據、搬走法醫 batch、手動提升完整 `.temp`，或重造只含剩餘工作的 instruction。沒有 instruction-level program counter 可直接續跑；選擇 replay 或 abandon 時，本機資料又不能替人判定外部 effect 的真相。

`aos exec` 的回合退出碼與 agent loop 是否還能前進不是同一件事。至少三路出現回 0、queue 卻空了或下一輪沒有排出的現場；若沒有另外掃 instruction exit、temp 與 final，會停在 no-op 0。只中止 parent 時，另有三路看到 child 繼續完成 effect，但 exit 永遠沒有回寫。

私有 publish／deliver helper 都還有限制：沒有 fsync、directory fsync、no-replace rename、durable key ledger 或跨 producer 去重；部分 helper 遇到既有 target／temp 會拒絕，恢復前仍要人保存或搬移證據。Cantrill persona 還實際遇到檔名格式錯誤被安靜忽略。四路使用的 provider 都是本機假 provider；有 query 的事故可由外部補回，沒有 query／idempotency 的事故則只能保留 unknown 或由人決定下一步。

### 4. 三個數字

**① 自己手寫了幾次 temp＋rename。** Carmack persona 報 **9 次**：正常 runtime 原始碼 6 個位置，加人工復原臨時手寫 3 組；若只算可重跑腳本則是 **6 次**。Armstrong persona 報 **1 份實作**，正式現場 prepare 48 次、helper commit 47 次，rename 前被殺的 1 次另由人手動 `mv`；成功基線 11 次發布，其中 3 次是 delivery。Cantrill persona 報 **1 份實作**、4 個靜態呼叫點、happy path commit 6 次，事故後另人工補 1 次 rename。Thompson persona 報 **1 份實作**，正常閉環呼叫兩次、故障注入再呼叫一次。這個數字目前有兩種計數口徑：Carmack persona 主要數發布位置／人工交易，其餘三位主要數共用實作份數；各自的呼叫或 commit 次數已一併保留，尚未換算成同一口徑。

**② 哪種「不知道做了沒」本機補不回來。** 四位都報 **1 類**：provider 可能已接受非冪等 request，但 receipt／response／result 尚未在本機提交。Carmack、Thompson persona 都做出本機現場相同而 provider ledger 不同的 accepted／dropped 對照；Armstrong persona 實際盲重試後 ledger 從 1 變 2；Cantrill persona 在 model 與 tool 兩個位置各撞到一次，都是靠 provider query 才補回。這一項四路答案相同，且回報中同時有 snapshot／diff、外部 ledger 與盲重試紀錄。

**③ 有沒有冒出第二個要同時管的工作。** 四位都報 **0 個**。四路都是一個 world、一條 logical job、串行 instruction，沒有 parallel、lane、join、scheduler 或第二個耐久工作；子行程、假 provider process、不同事故 world 都沒有被計作第二個 logical job。回報中沒有建立並行 workload，也沒有測多 producer。

因此目前收到的原始數字是：第一項按「實作份數」為 p1 **6**、p2 **1**、p3 **1**、p4 **1**，但 p1 另以包含人工復原的「交易／位置」口徑報 **9**；第二項四位都是 **1**；第三項四位都是 **0**。這裡只保留各自的口徑與證據，不替不同口徑裁定。

### 5. 仍然不知道的

第一個數字還沒有統一計數單位。「手寫了幾次」究竟數 source 中獨立實作份數、靜態呼叫點、happy-path commit、正式現場所有 commit，還是包含事故後人工 `mv`，四份回報採了不同口徑；因此目前不能只拿 `6／1／1／1` 或 `9／1／1／1` 脫離說明比較。

本輪不知道 power loss 下檔案內容與 directory entry 是否耐久，也不知道跨 filesystem rename、兩個 producer 同時投遞、名稱碰撞、覆蓋競爭、no-replace 與 crash 後重入會發生什麼。Thompson persona 下一輪才預定攻擊雙 producer；其餘路線也沒有建立第二個長壽 world、平行 tool 或 join。

本輪不知道真實 provider 是否提供 query 或 idempotency key。Cantrill persona 的兩次恢復依賴可 query 的假 provider；Carmack、Armstrong、Thompson persona 的不可對帳對照則刻意沒有這些能力。對無 query provider，這輪只記到本機無法分辨 accepted／dropped，以及盲重試可能重複，沒有做出自動恢復。

本輪沒有試真模型 CLI，也沒有網路；四路都用假模型。Armstrong persona 的 SIGINT 是 `timeout --preserve-status -s INT` 對 parent 注入，沒有驗證所有終端前景 process group 行為；Cantrill persona 雖由 PTY 送 `^C`，wrapper 也一起終止，沒有留下獨立的 `aos` 退出碼。

最後，本輪只記到三種 scope 對應的現場數字與各 persona 後續主張；近期 core 應回撤到哪一種大小，尚未在這份書記紀錄中裁定。

## 第 1 輪評分與意見

總分是五項直接相加，滿分 25；不拿它排名。證據與誠實是門檻，沒有現場的完成宣稱，其餘三項再高也沒用。

### p1（Carmack persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 5/5 |
| **總分** | **24/25** |

accepted／dropped 的本機 SHA-256 相同、外部 ledger 卻是 1／0，這不是看法，是把「純本機自動恢復」直接判了死刑。你也明寫沒測 fsync、斷電，沒有拿 SIGKILL 冒充 durability，誠實。扣一分只因第一個數字同時報 9 與 6，計數單位沒先鎖死，不能直接拿去拍 scope。

**下一輪：**先定義唯一計數表，逐列列出「原始碼實作份數／靜態呼叫點／實際 commit／人工 rename」，再用私有 `publish`、`deliver`、`effect` 三支原語重跑原本三個 kill point；每案必須輸出恢復前狀態、唯一人工命令、恢復後 ledger，禁止用外部 oracle 替無 query provider 作答。

### p2（Armstrong persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

`tool.exit=137`、`schedule.exit=66`、`aos ... exit=0` 與盲重試後 ledger 由 1 變 2，完整地證明「回合完成」不等於「agent 還活著」，也證明 Effect 不能預設 retry。第一次 `tee` 沒留到證據也照寫並用 fresh world 重跑，這是正確的事故紀錄。11 次 publish 只有 3 次 delivery，讓只做 Deliver 的主張沒有躲閃空間。

**下一輪：**把 key＋receipt 做成可重入的 Publish，讓 rename 前重開不需人工 `mv`；再把無 query provider 的 Effect 固定成 `pending → done | unknown`，只接受明示的 `adopt | retry | abandon`。同一組故障逐個 transition 注入，驗收輸出必須證明每案最多一個高階恢復命令、零搬檔、零重造半批 instruction，並保留重複 effect 的 ledger 檢查。

### p3（Cantrill persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 5/5 |
| **總分** | **24/25** |

phase marker 把刀落在哪裡說清楚，錯檔名被三次 exit 0 安靜忽略則抓到一個別人沒抓到的真介面缺陷。PTY 把 wrapper 一起殺掉、拿不到 `aos` exit，你沒有補造數字，這點可信。扣一分同樣是第一個數字混了實作份數、呼叫點、commit 與人工 rename，還不能作橫向判斷。

**下一輪：**做一鍵 crash matrix，先修 harness，讓每一刀都留下獨立的 `aos` exit、instruction exit、queue/temp/final 狀態；再測合法與非法 delivery 名稱、同 target 重投及兩個 producer 同時提交。結果要明確回答 Publish 和 Deliver 各自拒絕什麼、是否 no-replace、錯誤是否可見，別只讓 final 出現就算過。

### p4（Thompson persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 4/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 4/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 4/5 |
| **總分** | **21/25** |

你保留了砍太早的失敗現場，也用 `od` 推翻自己的 `wc -l` 誤判，原始事故證據可信。可是「拿掉 aos 的三行 shell」只跑 happy path，沒有接受同一組 SIGINT、SIGKILL、rename 與重開測試，拿它推出「連 Deliver 都別做」沒有證據。`1` 只說 helper 沒複製，不能消除每個呼叫者仍要正確處理命名、碰撞、receipt 與 recovery 的成本。

**下一輪：**讓 no-aos 三行鏈接受完全相同的三刀與重開驗收，不能另寫人工特例；再讓兩個 producer 各投 1,000 個唯一 ID，輸出投遞數、執行數、遺失數、重複數與覆蓋數。若 shell helper 能在 crash 後無搬檔恢復且全數為零，再談不加 Deliver；否則把失敗點縮成最小 Deliver 的明確契約。

### 路線判斷

**最值得繼續的是 p2 的「共用 Publish 底座，再把 Effect 的 unknown 明文化」這條路。**理由不是它寫得完整，而是兩段輸出正中 scope：成功基線 11 次 publish 只有 3 次 delivery，證明 (a) 只收掉少數提交；盲重試後 `oracle_ledger_lines_after_retry=2`，證明 Effect 不能被一般 Publish 假裝解掉。p1 的 accepted／dropped 本機 snapshot 同 SHA-256、外部 ledger 分別 1／0，是第二份獨立證據；兩份一起足夠支持繼續驗 (b)，而不是憑架構偏好投票。

**看起來漂亮但藏成本的，也是 (b) 裡的 Effect。**只要把它說成「可靠執行副作用」，成本立刻膨脹成 provider-specific idempotency key、query／reconcile、決策 ledger 與人工權限；對不可查 provider，它仍只能誠實停在 `unknown`。Publish 也不是一支 `mv` 就結束：p2 自己已承認 `test` 再 `mv` 有競爭窗且沒有 fsync，p3 又證明檔名錯誤會被安靜吞掉；若不把 no-replace、receipt、錯誤可見性與 durability 邊界寫死，三個原語只會把檔案手術換個名字。

**致命坑只有一個：想靠本機狀態自動判定非冪等遠端 effect 是否完成。**p1 的相同 SHA-256／不同 ledger 已證明兩個真相映成同一本機狀態；任何自動 replay 或自動 abandon 必然至少錯一邊。這擋住的是「透明自動恢復／exactly-once」整個方向，不擋住一個會保留 `unknown`、要求人或 provider reconcile 的 Effect 原語。

其餘目前都是麻煩，不是方向殺手：rename 前 `.temp` 要人工提升、delivery 檔名錯了被忽略、`.runi` 太粗、孤兒 process group，以及 child 失敗但 `aos exec` 回 0。它們很難用，甚至會安靜停死，但都能用 receipt、嚴格驗證、instruction-level 狀態、process-group supervision 與 status 檢查處理；先拿實測把契約釘死，不需要因此造 lane、join 或 proc-table。

### 可信度判斷

沒有哪一份原始現場需要整份作廢；四位都主動揭露了缺證、誤測或未覆蓋範圍。**不可信的是 p4 回報裡「三行 shell 已反證 aos／Deliver 的必要性」那個 scope 結論**：它只展示 `model → tool → model` 的正常輸出，沒有展示 no-aos 版本在同一批 crash point 後能恢復，更沒有處理它自己已經撞到的 identical-client-state／different-provider-state。那段只能證明 happy path 不需要 queue，不能支撐近期 core 連最小投遞都不做。

### 現在就得拍板

我會建議使用者選 **(b) Publish → Deliver → Effect**，但把 Effect 的承諾限制為記錄 phase、保留 `unknown`、接受明示 reconcile 決策；不要承諾 exactly-once。**第一步只做 Publish**：同 filesystem 的 temp＋原子提交、no-replace、穩定 key、可重入 receipt、明確錯誤與宣告清楚的 fsync 邊界，然後把現有 model response、request、result、final 全部換到同一契約上重跑 crash matrix。Deliver 應薄薄疊在 Publish 上；第三個數字四份都是 0，在出現第二個真實工作以前，不准把控制平面塞進 core。這是評審建議，最後仍由使用者拍板。

## 下一輪的資料包

### 1. 這輪卡住的清單

- **p1（Carmack persona）**卡在第一個數字沒有唯一口徑：同一份現場同時可數成 1 份 helper、6 個可重跑發布位置或含人工復原的 9 次交易；原始整理在 `/home/guanyu/aos-hack/core-scope/p1/wf/workflows/experiments/core-scope-r1/report-r1.md` 的〈三個數字〉。
- **p1（Carmack persona）**卡在 SIGINT 後孤兒行程與 `.runi` 並存，且 provider accepted／dropped 的本機 snapshot 相同，復原仍靠人工殺行程、判斷 temp 與外部 oracle；完整現場在 `/home/guanyu/aos-hack/core-scope/p1/wf/workflows/experiments/core-scope-r1/transcript.txt`。
- **p2（Armstrong persona）**卡在 Publish rename 前中止後仍要人工 `mv`，Ctrl-C 後仍要搬走 `.runi` 並重造只含未啟動 instruction 的半批；整理與各 evidence 路徑在 `/home/guanyu/aos-hack/core-scope/p2/p2-agent-loop/ROUND-1.md`。
- **p2（Armstrong persona）**卡在無 query provider 的 effect unknown：盲重試已把 ledger 從 1 筆變 2 筆，現有狀態還沒有可直接操作的 `adopt | retry | abandon` transition；現場在 `/home/guanyu/aos-hack/core-scope/p2/p2-agent-loop/evidence/kill-9.log`。
- **p3（Cantrill persona）**卡在 crash harness 沒有為每刀留下獨立的 `aos` exit：PTY 的 `^C` 連 wrapper 一起終止；同一輪也遇到合法性藏在檔名裡、錯名被安靜忽略，以及同 target 重投／雙 producer 尚未測，整理在 `/home/guanyu/aos-hack/core-scope/p3/experiment-round1/ROUND1.md`。
- **p4（Thompson persona）**卡在 no-aos 對照只跑 happy path，還沒承受與 aos 版本相同的 SIGINT、SIGKILL、rename 前中止與重開驗收；對照腳本在 `/home/guanyu/aos-hack/core-scope/p4/round1/run-no-aos.sh`。
- **p4（Thompson persona）**卡在三行 delivery helper 的多 producer 主張尚無壓力資料；目前實作只有 `/home/guanyu/aos-hack/core-scope/p4/round1/deliver.sh`，尚未有兩個 producer 各投 1,000 個唯一 ID 的結果。

### 2. repo 裡已經有答案的

- `docs/aos-folder.md`〈六、交接協定：三步，每步一次 `rename`〉已寫清 `.temp`／ready／`.runi` 的可見邊界、`.runi` 只代表一回合沒跑完、存在時退出 3，以及 crash 後刻意交人處理；〈八、退出碼〉另明寫子行程非零、signal、timeout 仍可令回合回 0，結果要讀 instruction 的 `exit` 檔。
- `core/inst/docs/handoff.md`〈彙整規則〉已寫出真正的 delivery 名稱規則：只收第一個副檔名起恰好為 `.json` 的 `<name>.json`，`name.part.json` 也會略過；對應判定就在 `core/inst/src/handoff.cpp` 的 `is_delivery_name()`，正好解釋 p3 的多一個點為何 silent stall。
- `core/inst/docs/handoff.md`〈取件與釋放〉與 `core/inst/src/handoff.cpp` 的 `claim_instruction()`／`release_instruction()` 已寫出目前只有 batch claim／release、沒有 instruction-level program counter；`core/inst/tests/test_run_handoff.cpp` 的 `exec refuses an existing runi with status three` 與 `exec claims the complete input before validating or executing it` 已踩過 `.runi` 鎖與整批先取件的邊界。
- `core/inst/docs/exec.md`〈逾時與行程群組〉與 `core/inst/src/exec.cpp` 的 `setpgid()`、group `SIGTERM`／`SIGKILL`、`WIFSIGNALED` 分支已寫出 timeout 時如何管整個 process group；`docs/aos-folder.md`〈十二、留給實作決定的〉則寫明單次 parent 被訊號中止時，子行程自成 process group 的既有語意。
- `wf/workflows/common/gotchas.md`〈使用 aos〉已記過「`aos exec` 的退出碼不反映子行程成敗」；`docs/roadmap.md`〈D10 — 回合的退出碼怎麼算？〉有 0／1／2／3 的完整契約，可直接當 p3 crash matrix 的欄位對照。
- `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉已實測直接寫 ready 會讓半份 JSON 被隔離，且同一 producer 用同一 PID 連投兩次會由第二次 rename 靜默覆蓋第一次；這是 p3／p4 下一輪測命名、同 target 重投前已有的基線。
- `wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉已保留一個無效的背景 `kill -INT` harness，再改用前景 `timeout` 得到 exit 130、孤兒 child 完成、exit 缺失與 restart 3；同節也區分 `--loop` 的優雅回合邊界，能供 p3 修 harness 時核對訊號是否真的打中。
- `wf/workflows/experiments/t5-agent-loop.md`〈7. reliability 題的補充實驗〉已有 request、effect、result.temp 三個時間點乘上 SIGINT／SIGKILL 的六格輸出，並有 query-by-key 不重做與 blind retry 令 ledger 變兩筆的對照；〈`aos recover [WORLD]`〉已列 `--replay`、`--abandon`、`--adopt RECEIPT` 三類人工動作及「證據不足就停住」。
- `wf/workflows/workshop/background/reliability.md`〈Effect（外部效果／capture／invoke）〉、〈idempotency key（冪等鍵）〉、〈ledger（耐久帳本／歷史表）〉與〈`unknown`（無法判定外部效果）〉已把 request/key、done、unknown、resolve，以及 key 沒有 ledger 就不能跨 aggregate 去重的差別分開；這些是 p2 下一輪 transition 名稱的既有詞義，不是新資料模型。
- `wf/workflows/workshop/background/delivery-contract.md`〈Publish（發布／commit／bundle）〉、〈Deliver（投遞／enqueue／handoff）〉、〈correlation ID（串接編號／request ID）〉與〈receipt（收據／completion record）〉已區分原子發布、queue 投遞、只作串接的 ID、單次完成證據與長期 ledger，能避免 p1 再把「實作份數／呼叫點／commit／人工 rename」混成同一個數字。
- `wf/workflows/workshop/background/questions-deliver.md`〈沒有耐久 ledger 時，第一版 key 要拿掉、只作 correlation、只在 queue 內去重，還是連 ledger 一起做？〉已列發布前、發布後未 aggregate、aggregate 後與重開後四個重叫時點；〈Deliver 要採哪一組成功 JSON、錯誤 JSON、receipt 欄位與退出碼編號？〉已列五種預期輸出現場。
- `wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？〉與 `wf/workflows/workshop/background/reliability.md`〈visibility atomicity 與 power-loss durability〉已明寫 rename 與 file fsync／directory fsync 是兩層承諾；本輪四位「沒測斷電」不需要重新查名詞，但仍沒有實測結果。
- `wf/workflows/workshop/records/agent-loop-architecture.md`〈R2 想法池（收攏成方向）／合併後的功能清單〉已整理 Publish、Deliver、Effect 的責任與既有痛點；〈其實是同一件事的／可以疊在一起的〉記有 Publish 作底座、Effect result／receipt 再交給 Deliver；這是 p1 下一輪三支私有原語可比對的既有分層紀錄。
- `docs/inst-directives.md`〈五、適用範圍〉只處理 instruction 欄位中的 `$ref`／`$env`／`$opt` 展開，沒有 Publish receipt、Effect unknown 或 recovery 契約；下一輪不應把這份文件誤當上述缺口已有答案。

### 3. 兄弟專案裡可以抄的

- `/mnt/c/code/mine/simple_tools/agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉與〈結果不明不是失敗，也不是重試許可〉已有「同目錄 temp、write-all、file fsync、atomic rename、directory fsync」及「已有 intent、缺可信結果就停在 unknown、不自動建立新 attempt」的完整文字基線。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` 的 `atomic_publish()`／`fsync_directory()` 是可運行的同目錄唯一 temp、`O_EXCL`、write-all、file fsync、`os.replace`、directory fsync 實作；它遇到同內容既有 target 直接返回、不同內容則拒絕，正好提供 p2 可重入發布實驗的既有程式樣本。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/test_process_after_spawn.py` 的 `AfterSpawnKill.test_side_effect_survives_killed_writer_without_respawn()` 已實測 effect 落盤後殺 writer parent，recover 保持 `waiting_for_child_repair_incomplete_evidence`，重跑 recover 也不增加 effect；精確涵蓋範圍與限制寫在同目錄 `PHASE2-EVIDENCE.md`〈已驗的窄切片〉與〈明確未驗，不可外推〉。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_process_binder.py` 的 `KnownEvidence`／`IncompleteUnknown`／`bind()`，配上 `test_process_phase2.py` 的 `test_incomplete_prefix_is_unknown()` 與 recovery tests，已有「完整證據才 commit receipt、不完整證據維持 unknown」的三態判讀樣本。
- `/mnt/c/code/mine/simple_tools/agent-machine/full/options/04-RETURN-UNKNOWN-AND-REPAIR.md`〈方案 D：unknown 停住，再由 repair 取得新證據〉與〈小原型該回答什麼〉已把「可唯一推導就補回；仍有兩種可能就不猜」及 effect 後殺 manager、重開不得重送的驗收寫成現成文字。
- `/mnt/c/code/mine/simple_tools/arc_agi_tweets/arc_tweets/storage.py` 的 `_atomic_write()` 已有同目錄 `NamedTemporaryFile`、完整寫入、`os.replace` 與殘留 temp 清理的輕量版本；它沒有 fsync、no-replace 或 receipt，適合只拿來對照 p4 所稱的三行 helper 到底已涵蓋哪些動作。
- `/mnt/c/code/mine/simple_tools/freepy/agentloop/RUNNER.md`〈operation 在中途被強行中止〉與〈整個實例被強制終止〉已明寫 tool error 不代表外部副作用 rollback、整個 process 被殺時不保收尾；`agentloop/CONTROLLER.md`〈明確不負責〉又明列它不做持久化、Task queue 或副作用 recovery，可作 no-aos 對照的能力邊界資料，不能當成 crash recovery 實作。

### 4. 還是查不到的

- `wf/workflows/hackathon/records/core-scope.md`〈5. 仍然不知道的〉只確認第一個數字口徑不一；在 `docs/`、`wf/workflows/workshop/`、`wf/workflows/experiments/t5-agent-loop.md` 與四個兄弟專案中都沒有一份既定的「實作份數／靜態呼叫點／實際 commit／人工 rename」統一計數表，**這條沒有現成資料**。
- `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉只有同一 producer 連投兩次的覆蓋證據；`/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉也明列未涵蓋 multiwriter，因此兩個 producer 各投 1,000 個 ID 的遺失／重複／覆蓋數，**這條沒有現成資料**。
- `/home/guanyu/aos-hack/core-scope/p4/round1/run-no-aos.sh` 只有 happy path；repo 的 crash 證據都在 `wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉與〈7. reliability 題的補充實驗〉且都包含 aos 或另一套假 loop，沒有 no-aos 三行鏈承受同一組三刀後的重開結果，**這條沒有現成資料**。
- `/home/guanyu/aos-hack/core-scope/p3/experiment-round1/ROUND1.md` 記錄 PTY wrapper 與 `aos` 一起被 `^C` 終止；`core/inst/tests/test_run_loop.cpp` 有 loop signal tests，`wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉有 `timeout` 現場，但都不是「PTY 真送 `^C` 且 wrapper 存活、獨立取得 aos exit」的 harness，**這條沒有現成資料**。
- `wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？〉只有測試方法與選項；`/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉也排除 power loss，故斷電後 file data／directory entry 是否仍在，**這條沒有現成資料**。
- `/mnt/c/code/mine/simple_tools/dcap/README.md`〈唯一指令〉至〈給 agent 用〉與 `/mnt/c/code/mine/simple_tools/dcap/tool/README.md`〈失敗時會怎樣〉只有 scaffold CLI、模板與一般退出碼；`/mnt/c/code/mine/simple_tools/freepy/agentloop/CONTROLLER.md`〈明確不負責〉排除持久化與副作用 recovery，兩者都沒有 Publish receipt、Effect resolve 或多 producer delivery 可抄，**這條沒有現成資料**。

## 第 1 輪白話導讀

### 1. 這一輪到底發生了什麼

四個人都用現成的 aos 把「想一步、做一步、把結果交回去」連跑三次。正常時都跑得完，但半路被停掉後都要人查現場、搬檔或重排剩下的事，而且有一種情況光看這台電腦永遠無法知道外面到底做了沒。實驗中沒有出現需要同時照看的第二件工作，所以這輪沒有替最大套方案提供實際理由。

### 2. 冒出來的新詞

- **`.runi`**
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：`aos exec <world>` 取走 `.aos/inst.json` 後改成的 `.aos/inst.json.runi`；目前只能說「這整包沒正常收尾」。

- **Publish**
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：目前還不是公開命令，是把檔案先寫好再一次換成正式名稱的提案；本輪的私有 `atomic-publish.sh` 是試作。

- **Deliver**
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：現在是投件者手寫 `.temp` 再 `mv` 成 `<name>.json`，交給 `aos exec <world>` 取件；`aos deliver` 還是提案。

- **Effect 與 `unknown`**
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：指呼叫外部服務及「可能已做、可能沒做」的結果；目前沒有 aos 命令處理，`Effect＋resolve` 仍是提案。

- **receipt**
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。  
  在 aos 裡具體是什麼：目前 `aos exec` 沒有這種可重開後查驗的收據；Publish 與 Effect 要不要留它仍是提案。

### 3. 看到的錯誤訊息各是什麼意思

- `aos exec: refusing ... .aos/inst.json.runi already exists`：aos 看到上次沒收好的整包現場，因為不知哪些已做過，所以拒絕自動再跑。
- `restart_exit=3` 或 `immediate_restart_exit=3`：重開命令不是自己壞掉，而是因上面那份 `.runi` 刻意停下來等人處理。
- `...=present` 與 `...=missing`：前者是檔案還在，後者是應有的結果或退出紀錄沒寫下來；兩者同時出現就是「有做過的跡象，但收尾不全」。
- `deliver_exit=137`、`schedule.exit=137`、`tool.exit=137` 或 `kill9_exit=137`：該行程是被 `kill -9` 強制砍掉的，137 就是 128＋第 9 號訊號。
- `Killed`：這是 shell 把「行程已被強制殺掉」直接印出來，不是另一個新錯誤。
- `ctrl_c_exec_exit=130`：這次 `aos` 是因 Ctrl-C 中止的，130 就是 128＋第 2 號訊號。
- `schedule.exit=66`：負責排下一步的測試腳本自己回報失敗，所以後面沒有新工作可跑；66 不是 `aos exec` 本身的總結果。
- `rejected_exit=70` 與 `accepted_exit=70`：這個 70 是測試腳本用來表示「本機沒收到可信的答案」，所以外部其實收了或沒收，本機看起來都一樣。
- `restart_exit=0`、`blind_restart_exit=0`、`plain_restart_exit=0` 但 `result=missing` 或 `final_exists=no`：命令本身沒找到可執行的東西並正常結束，不代表整條工作真的完成。
- `temp=yes ready=no`：內容還停在草稿名稱，aos 故意不讀；`manual_fix=rename_temp` 表示這次是人檢查後手動改名才救回來。
- `ledger_lines=1`、`ledger_lines=0` 但 `local_snapshot_diff_exit=0` 或 `client_worlds_diff_exit=0`：外面一份已收到、一份沒收到，但兩份本機現場比對完全沒差異。
- `provider_ledger_lines=2` 或 `oracle_ledger_lines_after_retry=2`：原本那次其實已被外面收到，不查就盲目重試後又做了一次。
- `aos_after_tool_group_kill_exit=0` 但 `tool.exit=137` 與 `schedule.exit=66`：aos 只報「這包命令處理完了」，包裡的工具被砍掉、下一步失敗並不會讓它改報失敗。
- `orphan_alive_after_manual_kill=1`：這裡的 1 是 `kill -0` 查無此行程，意思反而是人工殺掉後孤兒已不存在。
- `od` 印出 `65 66 66 65 63 74 6e`：檔案確實有 `effectn` 這 7 個字元，先前 `wc -l` 報 0 只是因為它數的是換行符。
- `aos exec` 連續回 0 但錯名的 `delivery-turn1.timestamp.pid.json` 原封不動：檔名多了點就不符取件規則，現行實作會安靜略過，所以它沒有可翻的錯誤訊息。

### 4. 所以呢

這輪直接對到 [OPEN-QUESTIONS 第 2 題](../../workshop/OPEN-QUESTIONS.md#2-近期-core-要回撤到哪裡)「近期 core 要回撤到哪裡」。現在仍是三個選項：

- **只留最小 Deliver**：得到最小的 core；賠掉的是這輪已實際出現的多處通用安全寫檔仍要由各人自備，外部到底做了沒也繼續交給上層或人處理。
- **先做 Publish、Deliver、Effect 三項**：得到一套共用的寫檔、投遞與外部結果記錄邊界；賠掉的是必須現在就定義命名、碰撞、收據、重開與耐久範圍，而無法查詢的外部服務仍只能留給人判斷。
- **保留完整控制平面**：得到日後可同時管多件工作、等待與收拾子工作的容量；賠掉的是要先背負一整套本輪尚未出現實際需求的設計與驗證成本。

## 第 2 輪紀錄

### 1. 各人這輪改了什麼

**Carmack persona。** 沿用上一輪方向，但把混在一起的第一個數字拆成固定四欄：1 份原始碼實作、9 個靜態呼叫點、每案 8 次實際 commit、0 次人工 rename，題目的第一個數字只取實作份數。上一輪散落的發布改由一支 publish.py 處理，另加薄的 deliver.sh、記錄 unknown 的 effect.sh，以及把每種事故收成一條具名 action 的 recover.sh。修正後跑完 baseline、SIGINT、provider accepted／dropped、Effect response rename 前五案；兩個 unknown 案在不看 oracle 的情況下都下同一條 recover.sh abandon-unknown，rename 前完整 temp 則用 recover.sh adopt-temp。原場地本輪不可寫，成果放在 /tmp/aos-core-scope-p1-r2/round2/。

**Armstrong persona。** 把上一輪單一 temp + mv helper 加成 stable key、immutable intent／payload／receipt、stable temp、file fsync、directory fsync 與 Linux renameat2(RENAME_NOREPLACE)；Effect 改成 pending → done | unknown，恢復命令只接受 adopt | retry | abandon。這輪逐點砍在 Publish target／receipt 邊界與 Effect 的 pending／accepted／result／done 邊界，也重測 Ctrl-C；九個事故場都用一條高階恢復命令走到 final，shell mv 與手造半批 instruction 都是 0。另測同 target 雙 producer 競爭，第一次撞到自己的 mkdir race，修正後用 fresh world 重跑。上一輪場地不可寫，因此先以相同 SHA-256 複製到 /tmp/aos-p2-round2.kTrhIV/p2-agent-loop 再做本輪實驗。

**Cantrill persona。** 修正上一輪拿不到獨立 aos exit 的 SIGINT harness，統一 crash matrix 欄位，補測合法／非法 delivery 名稱、same-target race 與雙 producer 各 1,000 份，並把原本有 TOCTOU 的 Publish v1 換成私有 renameat2(RENAME_NOREPLACE) Publish v2。Deliver v2 由自己產生合法 <key>.json，先拒絕壞 key、JSON、schema、world，再回 published／already／conflict。本輪固定把第一個數字數成成功三回合的 Publish transaction 數。指定場地不可寫，成果放在 /tmp/p3-core-scope-round2/，另留 tarball 與 SHA-256。

**Thompson persona。** 撤回上一輪「三行 shell 已反證 Deliver」的結論，讓 no-aos 鏈承受同樣的 SIGINT、SIGKILL、rename 前中止，且事故後只能重跑同一條命令。effect 後重開在 SIGINT 與 SIGKILL 兩案都把 effect 從 1 次做成 2 次；舊 delivery helper 在 rename 前死亡後也無法以原參數重叫。另讓兩個 producer 各投 1,000 件：共用本地序號時遺失 1,000 件，改用全域唯一 ID 時遺失、重複、覆蓋、明確失敗皆為 0。最後以 hard link 寫窄 no-replace 原型，測過 crash 前 exact retry、Already 與 Conflict，但留下孤兒 temp。原場地被沙盒拒寫，成果放在 /tmp/p4-round2。

### 2. 坑的總表

**四位獨立地都再次撞到：無 query／idempotency 的 provider 在 effect 與本機 result 之間被砍，本機仍只能留下 unknown。** Carmack persona 的 accepted／dropped 兩案不用 oracle 作決策，兩案都執行：

~~~text
MANUAL_COMMAND[unknown-accepted-fixed]: recover.sh abandon-unknown
MANUAL_COMMAND[unknown-dropped-fixed]: recover.sh abandon-unknown
~~~

兩案最後都寫 effect_outcome: unknown_abandoned；事後 oracle 才分別看到 accepted_lines=1 與 dropped_lines=0。Armstrong persona 分別實測 abandon 與明示 retry；accepted 後 retry 的原文是：

~~~text
provider_ledger_lines_before_resolve=1
provider_ledger_lines_after_resolve=2
request-42 attempt=1
request-42 attempt=2
~~~

Cantrill persona 在 model 與 tool 兩個故障點重現同一類 committed result 缺失；Thompson persona 的 no-aos 同命令重開則在 SIGINT 與 SIGKILL 兩案都留下兩行 EFFECT。上一輪這個坑沒有被消除；本輪 p1、p2 把它改成可明示 abandon／retry／adopt 的狀態與命令，p3、p4 仍只記錄重現結果。

**四位獨立地都撞到：target 的可見提交，不等於 aggregate 消費後仍有發布歷史。** Carmack persona 的 Deliver 只在 ready 檔還在時提供 Already／Conflict，aggregate 刪檔後同 key 可再次 enqueue。Armstrong persona 更精確砍在 target 已發布、receipt 尚未提交、consumer 又已取件的窗口；重開時 target、temp、receipt 都可能不在，只能留下操作員證言：

~~~json
"durability":"operator-attested-after-ambiguous-consumption",
"state":"adopted-consumed"
~~~

Cantrill persona 的 deliver_v2_after_consume 同 key 再投回 "state":"published"；Thompson persona 的 no-replace 原型也只在 target 尚留 queue 時能回 Already。上一輪「沒有 durable key ledger／跨 producer 去重」的坑，本輪 queue 尚未被吃掉時已由 no-replace 與 stable key 解掉；aggregate 後的跨回合去重仍未解，p2 另把 target 與 receipt 不是同一原子提交的窗口實際打出來。

**三位獨立地都實測了兩個 producer，但撞到的不是第二個 logical work。** Armstrong persona 的第一次 race 先敗在 transaction directory 的 mkdir TOCTOU：

~~~text
producer_a_exit=1 output={"error":"FileExistsError","message":"[Errno 17] File exists: '.../.r2/publish'","operation":"publish-put"}
producer_b_exit=0 ...
~~~

修正後同 target／不同內容只准一方 commit，另一方以 conflict 失敗。Cantrill persona 用兩個 producer 各投 1,000 個不同 target，得到 ready_before=2000、unique_before=2000、執行後 ready_after=0。Thompson persona 故意讓兩邊共用本地序號時，32 件明確失敗、968 件 helper 回成功卻覆蓋既有 ready，共遺失 1,000 件；部分原始錯誤是：

~~~text
mv: cannot stat '/tmp/p4-round2/world-shared-slot/.aos/inst.tempd/0001.json.temp': No such file or directory
mv: cannot stat '/tmp/p4-round2/world-shared-slot/.aos/inst.tempd/0002.json.temp': No such file or directory
mv: cannot stat '/tmp/p4-round2/world-shared-slot/.aos/inst.tempd/0003.json.temp': No such file or directory
~~~

改用全域唯一 ID 後 2,000 件全數執行，遺失、重複與覆蓋都是 0。Carmack persona 本輪沒有跑 multi-producer。

**三位獨立地都用 Linux no-replace 原語解掉 test 再 mv 的覆蓋競爭；第四位用 hard link 做窄對照。** Carmack、Armstrong、Cantrill persona 都使用 renameat2(RENAME_NOREPLACE)；Cantrill persona 的 Publish v1 強迫競爭時兩方都 exit 0、最後 B 無聲覆蓋 A，換 v2 後同內容是 published／already，異內容是 published／conflict、衝突方 exit 73。Thompson persona 沒用 mv -n，因它跳過時仍可能成功退出，改用 hard link 證明窄契約。上一輪缺 no-replace 的坑在這四份私有原型中已解；三份 renameat2 原型都明寫 Linux-specific，hard-link 原型則留下 crash temp，尚未形成可攜契約。

**上一輪 rename 前要人搬 .temp 的坑，在三條私有恢復路徑中已解，另一條補出可重現的 no-replace 邊界。** Carmack persona 的五案 manual_temp_rename_commands=0，以 replay-delivery 或 adopt-temp 取代；Armstrong persona 的事故恢復 shell_mv_or_half_batch_rebuild_matches=0，rename 前只下 deliver-resume；Thompson persona 的窄原型能用完全相同參數重叫，不人工搬檔。Cantrill persona 證明 Publish v2 的 no-replace 與可重入結果，但本輪回報沒有另外列出 rename 前事故的一條恢復命令。Thompson persona 的舊 helper 對照仍失敗在：

~~~text
same_retry_exit=1 stderr=mv: cannot stat '/tmp/p4-round2/deliver-retry/source': No such file or directory
~~~

**上一輪 .runi 擋住重開且要重造半批 instruction 的坑，只在兩條具名恢復路徑中被處理。** Carmack persona 的 SIGINT 案改用一條 recover.sh replay-delivery，最後 actual_commits=8、external_ledger_lines=1；Armstrong persona 的 Ctrl-C 現場仍先出現：

~~~text
ctrl_c_exec_exit=130
immediate_restart_exit=3 stderr=aos exec: refusing /tmp/aos-p2-round2.kTrhIV/p2-agent-loop/round2/worlds/ctrl-c: .aos/inst.json.runi already exists
~~~

但這次只下 recover-world，先驗 Effect done 與 continuation receipt，再保存 forensic .runi 並解鎖，沒有人工重造 schedule。兩份回報都明寫這不是一般 instruction program counter。Cantrill persona 修好 SIGINT harness 並取得獨立 130，但只留下 crash matrix，沒有回報通用 .runi recovery；Thompson persona 本輪 no-aos 對照沒有 .runi。

**Cantrill persona 上一輪的錯名 silent stall，在私有 Deliver v2 已解，現有 aos 行為未改。** 本輪再次量到 name.part.json、.json、name.json.temp、無副檔名都 aos_exit=0、stderr 空白、source 留在 inbox；壞 JSON 才會被取走並印：

~~~text
delivery_stderr aos exec: warning: .aos/inst.tempd/bad.json: JsonSyntax
~~~

Deliver v2 改由自己產生合法檔名，並讓壞 key／JSON／schema／world 都 exit 65、回 rejected。這只解掉經 Deliver v2 投件的路徑，沒有改掉 aos 對錯名安靜忽略的既有行為。

**失敗的量測與 harness 都有保留。** Carmack persona 第一個 baseline 因 Effect Publish receipt 混入 provider stdout，三次 aos exec 都回 0 但 final JSON 壞掉；修 receipt channel 後才重跑乾淨 baseline。其第一版 recovery 又卡在 dash 的：

~~~text
/tmp/aos-core-scope-p1-r2/round2/recover.sh: 15: kill: Illegal number: -
~~~

改用 /bin/kill 後才重跑。Armstrong persona 的第一次雙 producer 測試因上述 mkdir race 作廢。Cantrill persona 第一版背景 SIGINT 再次無效，matrix 卡在 .runi 與 paused worker，改用前景 timeout --preserve-status --signal=INT 才取得 130；收據統計也曾把 rg -h 當成 no-filename 而數出 135 行，改用 --no-filename 後才得到 9／3／6。Thompson persona 的舊 helper 與 shared-slot 壓力測試都保留失敗輸出，窄原型也明寫殘留：

~~~text
r2 prototype residual temps=4xs0X5DXNzZb.json.temp,
~~~

**四位本輪仍都沒有真實 power-cut 證據。** Carmack、Cantrill、Thompson persona 的原型只承諾 visibility atomicity；Armstrong persona 執行了 file fsync 與 directory fsync，但明寫沒有真實斷電、NFS、虛擬磁碟或裝置快取測試。四位也都沒有改 C++、build 或 ctest。四人的原場地本輪都因沙盒不可寫而改存 /tmp；Thompson persona 保留的拒絕原文是：

~~~text
patch rejected: writing outside of the project; rejected by user approval settings
~~~

### 3. 好處／壞處

#### 好處

四條路都把上一輪只能靠人搬檔或盲目重開的差異做得可觀察。Carmack persona 把 9 個靜態 Publish 呼叫點收進 1 份實作，五個乾淨案例都以 8 次 commit 收尾，人工 rename 為 0。Armstrong persona 的九個事故場各只用一條高階命令，rename 前 temp、target 後缺 receipt、Effect result-ready、done 後缺 continuation 與 Ctrl-C 現場都有各自的恢復輸出；明示 retry 也真的留下兩筆 provider ledger，沒有把命令名稱當成安全保證。

Cantrill persona 修正 SIGINT harness 後，golden、SIGINT、SIGKILL、delivery rename 前四案有一致欄位；Publish v2 的 same-target 競爭實際跑出同內容 Already、異內容 Conflict，Deliver v2 也讓錯 key、JSON、schema、world 成為可見拒絕。Thompson persona 用同一命令重開 no-aos 對照，實際推翻上一輪只有 happy path 的三行論；雙 producer 的 shared-slot／global-ID 對照把遺失歸到命名與覆蓋競爭，而不是 2,000 件負載或 aos 執行。

三份 multi-producer 回報把「同時有 writer」與「同時有第二個耐久工作」分開記錄：同 target 需要原子排他，不同全域 key 的 2,000 件路徑可全數處理；三份答案仍都把 concurrent logical agent jobs 記為 0。

#### 壞處

私有原型已明顯增厚。Carmack persona 的 Publish／Deliver／Effect／Recovery 共 327 行；Armstrong persona 的私有 CLI 618 行，成功基線留下 12 個 transaction 目錄與 12 張 receipt，清理與保留期未定。Effect 仍要 phase、stable key、attempt、decision、receipt 與 recovery transition，卻不能回答 provider 到底做沒做。

Publish 的 no-replace 只處理 target commit，沒有一併解掉 transaction directory、receipt 與 consumer acknowledgment 的並行邊界。Armstrong persona 的 mkdir race 與 consumed-before-receipt 現場、其餘三份 aggregate 後同 key 可再次發布的結果，都留下額外帳本或 acknowledgment 尚不存在的狀態。三份 renameat2 實作是 Linux-specific；四份原型都沒有可外推的斷電結果。

Deliver 的私有 validator 也不是現有 instruction schema 的唯一真源。Armstrong persona 只支援本輪的 string argv；Cantrill persona 的 Python validator 是窄原型；Thompson persona 的 hard-link 原型沒有 JSON／schema 驗證。現有 aos 仍會安靜忽略錯名，child exit 137 時仍可能讓 aos exec 回 0，也沒有通用 status 一次列出 .runi、temp、instruction exit 與 result 缺口。

### 4. 三個數字

**① 自己手寫了幾次 temp＋rename。** Carmack persona 回 **1**，並固定分列 1 份實作、9 個靜態呼叫點、每案 8 次 commit、0 次人工 rename，題目只取第一欄；這比上一輪的 9／6 雙口徑硬。Armstrong persona 回 **1** 個 rename_noreplace() 實作，另列 2 個靜態 commit call sites、基線 12 個 transaction／receipt、0 次 shell mv、0 次手造半批 instruction；口徑延續上一輪，但把各欄分開，證據更完整。Cantrill persona 回 **9** 筆成功三回合的 Publish transaction，其中 3 筆 Deliver、6 筆非 Deliver；它把 transaction 明定成唯一主口徑，並以更正後的 9／3／6 統計支持，但這個口徑不是實作份數。Thompson persona 回 **4** 個靜態 temp→commit 實作位置：delivery helper 1 個、no-aos model-call／tool result／final 3 個；hard-link no-replace 原型不計，較上一輪只報 1 份 helper 多列出三個呼叫者自行實作的位置。

因此本輪收到的第一項原始答案是 **1／1／9／4**，但四位分別數原始碼實作份數、no-replace primitive、實際 transaction、靜態 temp→commit 位置，仍不是同一單位。p1 依評委要求已把四欄鎖死；p2 也完整分欄；p3、p4 各自選了唯一主口徑，但彼此仍不可直接橫比。

**② 哪種「不知道做了沒」本機補不回來。** 四位都回 **1 類**：provider 可能已接受，但 committed response／result 不存在，且 provider 不能依 key 查詢。Carmack persona 有不看 oracle 的同命令處置與事後 accepted／dropped 對照；Armstrong persona 有 abandon 保持 ledger 1、retry 令 ledger 1→2、result-ready 可安全 adopt 的 transition 證據；Cantrill persona 在 model／tool 兩點重現；Thompson persona 的 no-aos blind restart 讓 effect 1→2。答案數字沒變，但本輪多了明示 resolve、transition 與 no-aos 同命令重開，證據比上一輪更硬。Armstrong persona 另報一個 Deliver consumed-before-receipt 的本機 ambiguous window，但將它與遠端 Effect unknown 分開，沒有把題目數字改成 2。

**③ 有沒有第二個要同時管的工作。** 四位都回 **0**。Carmack persona 仍是一個 world、一條 loop、一筆 instruction。Armstrong、Cantrill、Thompson persona 雖都啟動兩個 producer 做競爭或壓力測試，但明列它們是短命 writer／contention，不是第二個長壽 agent、lane、join 或 scheduler。本輪比上一輪多了真實 multi-producer 證據，但 concurrent logical agent job 的數字仍是 0。

### 5. 評委上一輪要他們做的事，做到了沒

**Carmack persona。** 做到固定四欄計數，並以私有 Publish／Deliver／Effect 重跑原故障類型；每案都有恢復前狀態、單一具名命令與恢復後 ledger，accepted／dropped 的決策沒有偷看 oracle，人工 rename 為 0。第一版 baseline 與 recovery 各失敗一次，修正後另跑乾淨案例。

**Armstrong persona。** 做到 stable key＋receipt 的可重入 Publish、pending → done | unknown 與 adopt | retry | abandon，逐 transition 注入；九案各最多一條高階恢復命令，搬檔與半批 instruction 重造都是 0，明示 retry 的 ledger 由 1 變 2。另打出評委未明列的 consumed-before-receipt 缺口。

**Cantrill persona。** 做到修 harness 並留下獨立 aos exit、instruction exit、queue／temp／final 等一致欄位；合法／非法名稱、same-target 重投與雙 producer 都已測，Publish／Deliver 的拒絕、no-replace 與錯誤可見性也有輸出。第一版背景 SIGINT 與第一次 receipt 統計作廢後有更正重跑。

**Thompson persona。** 做到讓 no-aos 鏈承受同樣三刀且只用同一命令重開，結果在 effect 後重做副作用；也完成兩個 producer 各 1,000 件，shared-slot 有 1,000 遺失，global-ID 五項結果全綠。依這些失敗點收出窄 Deliver 契約，並撤回上一輪「連 Deliver 都別加」的結論。

### 6. 仍然不知道的

第一個數字仍沒有跨四人的共同單位。p1 已按評委要求固定四欄，p2 也分列 primitive／call site／transaction／人工操作；p3 的唯一主口徑是 9 筆 transaction，p4 是 4 個靜態實作位置。因此本輪能看出每份回報內部的計數比上一輪穩定，仍不能把 **1／1／9／4** 當成同一尺度排序。

仍不知道不靠操作員 adopt-consumed 時，Deliver 要如何跨越「target 已 commit、aggregate 已 claim／刪除、receipt 尚未 commit」的窗口。四份回報都顯示 queue target 消失後 key 歷史會失憶；本輪沒有 consumer acknowledgment 或共享 commit layout 的完成實驗，也沒有證明這份 ledger 應放在 Deliver 私有層或 aggregate／core。

仍不知道真實 power cut、NFS、非 Linux filesystem、虛擬磁碟與裝置快取下的結果。p2 只證明 file fsync／directory fsync 的 syscall path 有跑；其餘原型只承諾 visibility atomicity。renameat2(RENAME_NOREPLACE) 的非 Linux 替代契約、跨 filesystem 行為與孤兒 temp 的容量／清理政策也沒有答案。

仍不知道正式 Deliver 如何共用 core/inst 的 canonical parser，而不長出第二套 schema。兩份 Python validator 與一份 shell prototype 都是窄版；現有 aos 對錯 delivery 名稱的 silent ignore、child 失敗但回合 exit 0、通用 .runi recovery／status 仍未改變。

仍不知道無 query provider 的 unknown 最後應由誰、依什麼權限選 abandon 或 retry。這輪證明命令與 ledger 可以保存決策，也證明 retry 會重複 effect；沒有任何一路補出 provider 真相或 exactly-once。四份回報依然沒有真模型、真 provider 或第二個長壽 logical work 的現場。

## 第 2 輪評分與意見

總分仍是五項直接相加，滿分 25；不拿來排名。這輪先看上輪指示有沒有做，再看輸出是否撐得住結論。

### p1（Carmack persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：24 → 25，進步。** 上輪扣的計數單位這次已拆成 1 份實作、9 個呼叫點、每案 8 次 commit、0 次人工 rename，而且題目答案明確取 1。

上輪要的三支私有原語、故障前後狀態、單一恢復命令和禁止 oracle 作答，全部有做。accepted 與 dropped 用同一條 `abandon-unknown`，完成後才讀到 ledger 為 1 與 0，這才是「本機無解」的有效證明。兩次原型失敗都留了原文並用乾淨案重跑，沒有把修過的故事偽裝成一次成功。

**下一輪：**只打兩個未測窗口：response 已 commit、done 未 commit，以及 decision 已 commit、done 未 commit。每案必須用同一條 resolve 命令連續跑兩次，輸出 provider ledger、commit 數與 final hash，證明可重入且沒有第二次 effect。

### p2（Armstrong persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：25 → 25，持平。** 不是沒進展，是上輪已滿分；這次把 key＋receipt、`pending → done | unknown`、`adopt | retry | abandon` 和零搬檔都真正跑出來，還多打出 consumed-before-receipt。

上輪的驗收條件全數交付，尤其 retry 後 ledger 從 1 變 2，沒有拿「高階命令」四個字假裝安全。更有價值的是 target 被 consumer 吃掉、receipt 未落盤後，只能發出 `operator-attested-after-ambiguous-consumption`；這直接打穿「Deliver 永遠只是 Publish 的薄 wrapper」。第一次 race 死在 mkdir TOCTOU 也照留，誠實度沒有折價。

**下一輪：**就做 consumer acknowledgment，分別砍在 target commit、aggregate claim、delivery deletion、ack commit 後。同一 key 重開必須只得到一個機械可證的結果，且 `adopt-consumed` 必須消失；做不到就用兩個相同磁碟現場、不同歷史的輸出宣告獨立 Deliver receipt 方案死亡。

### p3（Cantrill persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 5/5 |
| **總分** | **24/25** |

**較上輪：24 → 24，持平。** harness、錯名、same-target race 與 2,000 件壓力測試全部補齊，但第一個數仍扣一分：題目問「手寫幾次 temp＋rename」，你回的 9 是 runtime transaction，不是手寫位置。

上輪指示的一鍵 matrix 和可見錯誤已做到；Publish v1 兩方 exit 0、B 無聲覆蓋 A，v2 變成單一 published 與 conflict，路線邊界很硬。你也把無效 SIGINT harness 和 `rg -h` 的 135 行誤計數作廢，沒有偷刪失敗。但「自己宣告主口徑」不能改寫題目的單位；9 只能支持 Publish 使用面，不能當第一個數字。

**下一輪：**不要先回填 tarball；先用同一份 source inventory 輸出四欄：實作份數、靜態呼叫點、runtime transaction、人工 rename，題目答案固定取實作份數。然後用現有 `libaos_inst` C ABI 驗證同一批合法／非法 instruction，輸出私有 validator 與 canonical parser 的逐案差異，不准複製第二套 schema。

### p4（Thompson persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：21 → 25，進步。** 上輪沒證據的「三行 shell 足夠」這次被自己的三刀推翻，而 2,000 件對照又把負責點精確縮到 key 與 no-replace 契約。

上輪指示全部照做：no-aos 在 SIGINT／SIGKILL 後都把 effect 從 1 做成 2，shared-slot 實測遺失 1,000 件，global-ID 則 2,000 件全數到達。最值錢的不是改口號，是公開撤回上輪結論，而且用兩行 effect log 和精確集合差來撤。hard-link 原型留下孤兒 temp 也照報，這份回報可信。

**下一輪：**只打 publish-success-before-receipt 與 consumer-delete-before-retry 兩個窗口。對每個磁碟現場用完全相同的 Deliver 重試命令，輸出是 `Already`、`Unknown` 還是 `Conflict`；若沒有 ledger 就無法唯一判定，不要用操作員證言補答案。

### 路線判斷

**最值得繼續走的是 p2 這條，但下一步只准攻 consumer acknowledgment。** 具體證據是 p2 的 consumed-before-receipt 輸出：consumer 後 ready 與 receipt 都不存在，最後只能產生 `"durability":"operator-attested-after-ambiguous-consumption"`。這比繼續加 Effect 狀態更值錢，因為它正在決定 Deliver 能否獨立於 aggregate，也決定 (b) 裡 Publish 與 Deliver 的真正分界。p3 的 v1 race 「兩方 exit 0、final target=B」和 p4 的 shared-slot「968 次無聲覆蓋、1,000 件遺失」則已經把 no-replace 的需求證完，不用第三輪再證一次。

**這輪有推翻上輪的一部分判斷。** 「選 (b)」沒被推翻，但「Deliver 應薄薄疊在 Publish 上」已經站不住：p2 證明 queue target 可以在 receipt 前被 consumer 消費，p3 與 p4 又證明 aggregate 後同 key 會失憶。另一個被明確推翻的是上輪 p4 那個「三行 shell 已反證 Deliver」的結論；這輪同命令重開直接把 effect 做了兩次。

**致命的坑仍只有一個：無 query／idempotency 的遠端 effect，在 acceptance 與 committed result 之間被砍後，本機不可能自動還原真相。** p1 的同命令對應 ledger 1／0、p2 的明示 retry 對應 ledger 1→2，p4 的 blind restart 對應 effect 1→2，三份證據已把自動 exactly-once 判死。consumed-before-receipt 則對「獨立 Deliver 自己發完成收據」是致命坑，對 Deliver 本身不是；把 acknowledgment 交給 consumer／aggregate 就能繼續驗。Linux-only `renameat2`、fsync 未做斷電測試、孤兒 temp、receipt 清理、schema 共用與 `.runi` 恢復都只是麻煩；必須解，但沒有一個為控制平面創造了需求。

### 可信度判斷

沒有一份整體回報需要作廢，四位都保留了失敗現場。**若必須指出一份不可相信的題目答案，是 p3 回報裡的第一個數字 `9`。** 它有可重現的 transaction 統計，但題目問的是手寫 temp＋rename 幾次；把計數單位改成 runtime transaction，再宣布這是「唯一主口徑」，那個數不能拿來拍 scope。這不是說 p3 造假；正因為他把單位寫得很清楚，才能確定是答錯問題，所以誠實度仍是 5。

### 現在就得拍板

我會建議使用者仍選 **(b) Publish → Deliver → Effect**，但這是三個分段驗收的窄原語，不是一次吞下 618 行原型；Effect 只能保存 `unknown` 與明示決策，不准宣稱 exactly-once。**第一步仍是 Publish**：只做同 filesystem 的唯一 temp、atomic no-replace、stable key、同 bytes `Already`、異 bytes `Conflict` 與 visibility receipt；緊接著在公開 Deliver completion receipt 前，必須用 p2 下一輪的 consumer acknowledgment 實驗決定 ledger 邊界。

跟上輪比，**scope 選擇沒變，第一步也沒變；變的是 Deliver 不再被假定為獨立薄 wrapper**。第三個數四份仍是 0，而且三份 multi-producer 實驗只證明 writer contention，沒有第二個長壽工作；所以 (c) 仍然是為將來虛構需求，不做。這是評審建議，最後由使用者拍板。

## 第 2 輪之後的資料包

### 1. 這輪卡住的清單

- **p1（Carmack persona）**卡在 Effect response 已 commit、done 未 commit，以及 decision 已 commit、done 未 commit 的兩個窗口尚未測重複 resolve；本輪未測範圍寫在 `/tmp/aos-core-scope-p1-r2/round2/report-r2.md`。
- **p2（Armstrong persona）**卡在 target commit 後被 aggregate 取走，receipt 卻尚未 commit，只能人工 `adopt-consumed`；完整現場在 `/tmp/aos-p2-round2.kTrhIV/p2-agent-loop/round2/evidence/delivery-consumed-no-receipt.log`。
- **p3（Cantrill persona）**卡在第一個數仍把 runtime transaction 當成手寫實作份數，且私有 validator 尚未與 canonical parser 做逐案差異對照；來源 inventory、validator 行為與未測項都整理在 `/tmp/p3-core-scope-round2/ROUND2.md`。
- **p4（Thompson persona）**卡在 publish 成功但 receipt 未回傳、以及 consumer 刪除 target 後重試的兩個窗口，沒有 ledger 時尚不能唯一回答 `Already`、`Unknown` 或 `Conflict`；原型與未測項在 `/tmp/p4-round2/ROUND2.md`。

### 2. 上一輪給過的料，有沒有人真的用

- **有用。** p3 實測的錯名 silent stall、p1／p2 的 `.runi` 拒絕重開與多人對 visibility-only 的表述，都對上 `docs/aos-folder.md`〈六、交接協定〉與〈八、退出碼〉。
- **有用。** p3 重測 `<name>.json` 與 `name.part.json` 的差別，正面使用了 `core/inst/docs/handoff.md`〈彙整規則〉與 `core/inst/src/handoff.cpp` 的 `is_delivery_name()` 契約。
- **有用。** p1 的 `replay-delivery`、p2 的 `recover-world` 都是針對 `core/inst/docs/handoff.md`〈取件與釋放〉及 `core/inst/tests/test_run_handoff.cpp` 所呈現的整批 `.runi` 邊界，但兩者都明寫沒有變成 instruction program counter。
- **有用。** p1 第一版 recovery 因 dash `kill` 失敗後改用 `/bin/kill` 管 process group，與 `core/inst/docs/exec.md`〈逾時與行程群組〉、`core/inst/src/exec.cpp` 的 group-signal 路徑直接相關。
- **有用。** p3 的 crash matrix 分開 `aos_exit` 與 `fault_instruction_exit`，p1 也抓到三次 exit 0 但 final JSON 已壞，用到 `wf/workflows/common/gotchas.md`〈使用 aos〉與 `docs/roadmap.md`〈D10 — 回合的退出碼怎麼算？〉的區分。
- **有用。** p3 以合法／非法名稱、same-target race 與錯誤可見性擴充了 `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉的基線。
- **有用。** p3 改用前景 `timeout --preserve-status --signal=INT`、p4 讓 no-aos 鏈接受同樣三刀，明確沿用 `wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉的 harness 經驗。
- **有用。** 四人都再測 request／effect／result 窗口，p1／p2 更將 `adopt | retry | abandon` 做成命令，實際用上 `wf/workflows/experiments/t5-agent-loop.md`〈7. reliability 題的補充實驗〉與〈`aos recover [WORLD]`〉。
- **有用。** p1／p2 將 Effect 的 `pending／done／unknown`、stable key、decision 與 ledger 分開，落實了 `wf/workflows/workshop/background/reliability.md`〈Effect〉〈idempotency key〉〈ledger〉與〈`unknown`〉。
- **有用。** 四人都分開 Publish、Deliver、key 與 receipt，並用 Already／Conflict 實測其邊界，直接用到 `wf/workflows/workshop/background/delivery-contract.md`〈Publish〉〈Deliver〉〈correlation ID〉與〈receipt〉。
- **有用。** p1／p3／p4 都實測 aggregate 後同 key 重投，p2 更打出 consumed-before-receipt，正是 `wf/workflows/workshop/background/questions-deliver.md`〈沒有耐久 ledger 時…〉的四個重叫時點。
- **沒有。** `wf/workflows/workshop/background/questions-deliver.md`〈Deliver 要採哪一組成功 JSON、錯誤 JSON…〉沒有被做成共同輸出契約，四份私有原型各用一套欄位；猜是本輪主題是 crash window，這條**不相干**。
- **有用。** p2 跑了 file fsync＋directory fsync 路徑，其餘三人則明寫 visibility-only，對應 `wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename…〉與 `wf/workflows/workshop/background/reliability.md`〈visibility atomicity 與 power-loss durability〉。
- **有用。** p1 依 Publish → Deliver → Effect 分層，p2 反過來用 consumed-before-receipt 修正它，實際檢驗了 `wf/workflows/workshop/records/agent-loop-architecture.md`〈R2 想法池（收攏成方向）／合併後的功能清單〉與〈其實是同一件事的／可以疊在一起的〉。
- **沒有。** p2／p3 仍寫了只支援窄版 string argv 的 Python validator，沒有使用 `docs/inst-directives.md`〈五、適用範圍〉指向的 canonical schema；猜是第二輪尚未要求 parser conformance，這條**不相干**。
- **有用。** p2 的 stable temp、write-all、file／directory fsync 與 incomplete evidence 保持 unknown，明顯對上 `/mnt/c/code/mine/simple_tools/agent-machine/full/05-DURABLE-STATE.md`〈持久屏障〉與〈結果不明不是失敗，也不是重試許可〉。
- **有用。** p2 的 Publish 與 `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_store.py` `atomic_publish()`／`fsync_directory()` 具有同目錄 temp、write-all、fsync 與再入判讀的同一組元件。
- **有用。** p1／p2 在 parent 中止後都不重做已有完整證據的 effect，命中 `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/test_process_after_spawn.py` 的 kill-parent 後不 respawn 邊界。
- **有用。** p1 的 `adopt-temp`、p2 的 result-ready／unknown 分流，對上 `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/p1a2_process_binder.py` 的 `KnownEvidence`／`IncompleteUnknown`／`bind()` 三態判讀。
- **有用。** p1／p2 都把「可唯一推導就 adopt、仍有兩種真相就 unknown」做成實際恢復分支，對應 `/mnt/c/code/mine/simple_tools/agent-machine/full/options/04-RETURN-UNKNOWN-AND-REPAIR.md`〈方案 D〉與〈小原型該回答什麼〉。
- **沒有。** p4 改用 hard link 實作 no-replace，沒有取用 `/mnt/c/code/mine/simple_tools/arc_agi_tweets/arc_tweets/storage.py` `_atomic_write()` 的 `os.replace` 版；猜是後者可覆蓋 target，與本輪 no-replace 契約**不相干**。
- **有用。** p4 把 no-aos 鏈的能力邊界實測到「中止不代表副作用 rollback」，與 `/mnt/c/code/mine/simple_tools/freepy/agentloop/RUNNER.md`〈operation 在中途被強行中止〉〈整個實例被強制終止〉及 `agentloop/CONTROLLER.md`〈明確不負責〉一致。

### 3. repo 裡已經有答案的

- `core/inst/src/handoff.cpp` `aggregate_instructions()` 中「`rename(paths.temp, paths.base)` 成功 → `result.published = true` → `remove_accepted_deliveries()`」是 p2／p4 下一輪四個 kill point 的現行精確順序；這裡沒有 acknowledgment，只有發布後刪來源 delivery。
- `core/inst/docs/handoff.md`〈彙整規則〉與 `docs/roadmap.md`〈T3 — 彙整與發布：接出下一回合〉明寫「發布成功之後才刪投遞」，`core/inst/tests/test_handoff.cpp`〈handoff aggregates deliveries in filename order and flattens batches〉已有發布後 delivery 消失的可直接改造測例。
- `core/inst/docs/capi.md`〈讀取、寫入與執行〉明寫 C ABI 的 `aos_instruction_read_buffer()` 只接受單筆 instruction object、不接受 batch array；`core/inst/docs/capi.md`檔頭又明寫 C ABI 沒有 batch／handoff API，所以 p3 若要驗 Deliver 的 object／array 全契約，不能只呼叫這一支 C API。
- `core/inst/src/format.cpp` `read_all()` 才是 object／array 共用、失敗時整批不交付且回報 one-based `error_record` 的 canonical batch parser；`core/inst/tests/test_format_read.cpp`〈read_all accepts a single instruction object〉〈read_all accepts a formatted array〉〈read_all is atomic and reports a one-based record number〉已是 p3 可照抄的 conformance cases。
- `docs/inst-directives.md`〈六、擺在哪一層？〉與 `core/inst/docs/architecture.md`〈架構〉已定 `format` 是唯一懂 instruction schema 的分層，`resolve`、`handoff`、`exec` 不得重新解讀 schema；這是 p3 對照私有 validator 時的現成分層答案。
- `docs/aos-folder.md`〈十二、留給實作決定的〉子節〈仍然開著的〉已記殘存 `.bad`／`.runi` 清理的容量上限方向與「不能自動清掉 crash 現場」的衝突；可作 p2 的 12 個 transaction 目錄與 p4 孤兒 temp 保留政策的現成邊界資料。

### 4. 兄弟專案裡可以抄的

- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/aos_p0.py` 的 `_save_result()`、`_terminal()` 與 `recover()` 已把 receipt JSON、receipt-ready 與 terminal 分成三步；receipt 完整時 recover 只補後續 marker，不再執行 effect。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/test_p0.py` `test_recover_receipt_without_terminal_only_projects_terminal()` 正好是 p1 的 response／receipt 已 commit、done／terminal 未 commit 窗口；`test_invocation_id_table_cannot_escape_root()` 後段還已呼叫同一 invocation 的 `recover()` 驗重複恢復仍 terminal。
- `/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p0-function-python/README.md`〈由小到大：一次呼叫〉已寫出「完整 receipt 缺 terminal 時只補 terminal projection」與「dispatch intent 後不自動重跑」，可直接當 p1 兩個 transition 的文字對照。

### 5. 還是查不到的

- 在 `core/inst/`、`docs/`、`wf/workflows/experiments/t5-agent-loop.md`、`wf/workflows/workshop/records/` 與 `wf/workflows/workshop/background/` 中都沒有 consumer acknowledgment 的實作或「target commit → aggregate claim → delivery deletion → ack commit」故障矩陣，**這條沒有現成資料**。
- `core/inst/docs/capi.md`檔頭已明寫 C ABI 不提供 batch／handoff API，而 `core/inst/include/aos/inst.h` 也只有單筆 instruction handle；因此「不改 C++ 卻只用現有 C ABI 驗完 Deliver object／array 全契約」，**這條沒有現成資料**。
- `/mnt/c/code/mine/simple_tools/agent-machine/`、`/mnt/c/code/mine/simple_tools/freepy/`、`/mnt/c/code/mine/simple_tools/dcap/` 與 `/mnt/c/code/mine/simple_tools/arc_agi_tweets/` 都沒有 aggregate 取件／刪件與 producer receipt 共享同一份耐久 acknowledgment 的實作，**這條沒有現成資料**。
- `wf/workflows/hackathon/records/core-scope.md`〈第 2 輪紀錄〉〈第 2 輪評分與意見〉仍只能列出 1 份實作／9 個呼叫點／8 或 12 筆 transaction／4 個實作位置，repo 與四個兄弟專案都沒有一張既定的跨實驗統一計數表，**這條沒有現成資料**。
- `docs/aos-folder.md`〈十二、留給實作決定的〉只有殘存檔清理方向，`wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename…〉也只有測試方法；真實 power-cut、NFS、非 Linux no-replace 與孤兒 temp 容量數據，**這條沒有現成資料**。

## 第 2 輪白話導讀

### 1. 這一輪到底發生了什麼

四個人把上輪撞壞的地方做成「出事後重下同一條命令」的版本，再用兩個人同時投件、半路中止和重開去砍它。待辦還沒被取走時，多數撞名、覆蓋和人工搬檔問題已能擋住或救回；待辦一旦被取走卻還沒留下收件證明，現場又會失憶。外面的服務到底收到沒有，這台電腦仍然猜不回來。

### 2. 跟上一輪比，變了什麼

上輪只是知道「人得搬檔、盲目重跑可能做兩次」，這輪換到三件實物：人工搬檔降到零、同名投件不再互相蓋掉、盲目重跑確實被量到做了兩次。也推翻了兩個上輪說法：三行腳本並不足夠，Deliver 也不能只當 Publish 外面一層薄殼，因為檔案被取走後還缺一張由收件方留下的證明。沒有換到的是 scope 答案：仍沒有第二件長期工作需要 core 管，也仍無法替不可查詢的外部服務自動判真相。

### 3. 新冒出來的詞

- **no-replace／`renameat2(RENAME_NOREPLACE)`**<br>
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：現行 `aos` 沒有這支公開命令；本輪三份私有 Publish 原型用 Linux `renameat2(..., RENAME_NOREPLACE)`，另一份用 hard link，做到同名時明確回 Already 或 Conflict、不偷偷覆蓋。

- **consumer acknowledgment**<br>
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：目前不存在，是下一輪提案；現行 `core/inst/src/handoff.cpp` 的 `aggregate_instructions()` 取走並刪除 delivery 後，沒有另留一張「已收走」的證明。

- **TOCTOU**<br>
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：不是 aos 命令；本輪私有原型先看目錄／檔案在不在、稍後才建立或搬入，中間被另一個投件者插隊，分別撞出 `FileExistsError` 與無聲覆蓋。

- **stable key、ledger、fsync、Publish、Deliver、Effect、receipt、`unknown`**<br>
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：本輪仍全是私有試作；公開命令尚未存在，現行投遞入口仍是 `aos exec <world>` 讀 `.aos/inst.tempd/*.json`。

- **canonical parser／schema**<br>
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md) 的 ABI／schema。<br>
  在 aos 裡具體是什麼：正式的整批讀取在 `core/inst/src/format.cpp` 的 `read_all()`；本輪兩份 Python validator 沒有共用它，若直接做成 Deliver 會多長一套規則。

### 4. 這輪新看到的錯誤訊息各是什麼意思

- `FileExistsError: [Errno 17] File exists`：兩個投件者同時建立同一個位置，其中一個慢半步撞到已存在的目錄；這次是原型自己的競爭漏洞。
- `mv: cannot stat '...json.temp': No such file or directory`：兩個投件者共用同一份草稿名，其中一個先搬走後，另一個回頭已找不到自己的來源檔。
- `conflict`／`exit 73`：同一個正式名稱已有不同內容，新版原型明確拒絕覆蓋；這是預期的保護，不是檔案莫名壞掉。
- `same_retry_exit=1 ... mv: cannot stat '.../source'`：舊腳本第一次已把來源搬走，事故後用原參數重跑時沒有材料可搬，所以無法自救。
- `aos exec: warning: .../bad.json: JsonSyntax`：檔名合格所以 aos 有取件，但內容不是合法 JSON；相對地，錯名檔仍是安靜略過、回 0。
- `kill: Illegal number: -`：恢復腳本把負的行程群組編號交給不支援該寫法的 shell 內建 `kill`；改叫 `/bin/kill` 後才成功。
- `final JSON` 壞掉但三次 `aos exec` 都回 0：測試把收據文字混進本來應是純 JSON 的輸出；0 只表示 aos 跑完那包，不能替產物內容背書。
- `patch rejected: writing outside of the project; rejected by user approval settings`：參賽者想寫上一輪場地，但沙盒不准；所以四份本輪成果改放 `/tmp`，不是原型本身失敗。
- `residual temps=...json.temp`：窄版 hard-link 做法成功保住正式檔不被蓋，但事故草稿沒有清掉，久了會堆垃圾。

### 5. 所以呢

這輪仍直接影響 [OPEN-QUESTIONS 第 2 題](../../workshop/OPEN-QUESTIONS.md#2-近期-core-要回撤到哪裡)，但沒有替使用者把三選一改成唯一答案：

- **只留最小 Deliver**：core 最小；賠掉共用 Publish、外部結果的 `unknown`／resolve，以及本輪已證實需要的收件歷史，這些仍得由上層或人各自補。
- **保留 Publish → Deliver → Effect 三項**：得到共用的安全發布、投遞與外部結果記錄；賠掉的是 Deliver 不能再假定只是薄殼，還要決定收件證明和 ledger 放在 Deliver、aggregate 還是 core，Effect 也只能誠實停在 `unknown`，不能保證只做一次。
- **連完整控制平面一起保留**：得到日後同時管理多件長期工作、等待與收尾的空間；賠掉的是現在就背 lane、proc-table、join 等整套設計與驗證成本，而兩輪實驗仍只找到多個短命投件者，沒有找到第二件需要長期管理的工作。

所以多跑這輪改變的是中間選項的內部代價與分界，不是三個選項本身：最小 Deliver 比上輪看起來少算了一張收件證明，三項 core 比上輪看起來不再是三層簡單相疊，完整控制平面則仍沒有新增的實測需求。

## 第 3 輪紀錄

### 1. 各人這輪改了什麼

**Carmack persona。** 沒有再擴充整條 loop，只補評委指定的兩個 Effect 窗口：response 已 commit、done 未 commit，以及 decision 已 commit、done 未 commit。兩案都把同一條 resolve 連跑兩次，量第二次的 commit delta、provider ledger delta 與 final hash；另新增 `response_ready_done_missing`、`decision_ready_done_missing` 與 `adopt-ready-response`。上一輪只做到 unknown 的明示決策，這輪補的是已有完整 response 或已有 decision 後，重開只投影 done、不得再叫 provider。R2 的 `/tmp` 已消失，因此先以 R1 baseline 做 byte-for-byte continuity gate，再於 `/tmp/aos-core-scope-p1-r3/round3/` 重建最小 R3 原語。

**Armstrong persona。** 沒有重跑前兩輪的整條假模型 loop，改攻上一輪尚未解的 consumer acknowledgment。producer receipt 降為 visibility evidence；completion ack 改由 aggregate consumer 在 `claim → aggregate publish → delete delivery → ack commit` 中留下，且 `aos exec` 前必須先通過 ack gate。四刀分別砍在 target、claim、delete、ack 之後，每案重開兩次、再把 `aos exec` 叫兩次；另加一個不合作 consumer 直接刪 ready、但不寫 claim／ack 的反例。上一輪的 `adopt-consumed`、人工 `mv` 與重造半批 instruction 在這份原型裡消失。R2 的 `/tmp` 已消失，R3 重建於 `/tmp/aos-p2-round3.KcFA3d/`。

**Cantrill persona。** 沒有再改 Publish／Deliver 路線；這輪修正上一輪第一個數字的量詞，把同一份 source inventory 分成實作份數、靜態呼叫點、runtime transaction、人工 rename，題目答案固定取實作份數。另以 `ctypes` 直接呼叫現有 `libaos_inst` C ABI，逐案對照私有 validator 與 canonical parser，不再把私有 schema 當成等價。R2 的 `/tmp` 已消失；兩支 v2 腳本依上一輪內容復原後，SHA-256 與 manifest 相同，再於 `/tmp/p3-core-scope-round3/` 重跑三回合閉環。沒有 hash 的其他 R2 raw artifacts 沒有宣稱復原。

**Thompson persona。** 只測評委指定的 publish 成功但 receipt 未回，以及 consumer 已取走 target 但 ack 未寫。新增只回 `Already`、`Unknown`、`Conflict` 的窄 Deliver 分類器，並製造「publish 前被殺」與「已消費、ack 前被殺」兩段 producer 可見現場，再用完全相同的 Deliver 命令重試。第一版 consumer 用 `mv`，因 hard-link 的 `st_nlink` 洩漏歷史而整案作廢；固定版改成 copy＋unlink，確認兩邊 `links=1` 後重跑於 `/tmp/p4-round3-fixed/`。R2 的 `/tmp` 同樣已消失。

### 2. 坑的總表

**四位獨立地都撞到上一輪 `/tmp` 現場已被清除，而且原指定場地仍不可寫。** Carmack persona 實測 `r2_present=no`；Armstrong persona 找不到 `/tmp/aos-p2-round2.kTrhIV`；Cantrill persona 找不到 `/tmp/p3-core-scope-round2`；Thompson persona 記下：

~~~text
round1=present round2=missing
~~~

四位因此都在新的 `/tmp` 重建。Carmack persona 用 R1 baseline 做 continuity gate：

~~~text
baseline_commits=8
baseline_provider_ledger=1
c1dd00e199be4cb62a8db6833ed1fe3b5e6d6352566590184aa2d33d31f6a6ac  .../round3/worlds/baseline/agent/final.json
c1dd00e199be4cb62a8db6833ed1fe3b5e6d6352566590184aa2d33d31f6a6ac  .../core-scope-r1/worlds/baseline/agent/final.json
continuity_cmp_exit=0
~~~

Cantrill persona 復原的兩支 v2 腳本 SHA-256 與上一輪 manifest 相同；Armstrong、Thompson persona 則明寫本輪是重建現場，沒有把 `/tmp` 當成永久保存。上一輪已發生「原場地不可寫、成果改放 `/tmp`」，這輪沒有解掉；四份 R2 暫存證據反而都已遺失。

**三位獨立地實測 consumer acknowledgment，撞到同一條分界：target 被 consumer 取走後，producer 自己的 receipt 不能回答以前是否完成。** Armstrong persona 把 ack 放到 consumer／aggregate 一側；四個合作 consumer 案在第一個 recover 後都有 ack，後兩次只讀既有 ack，兩次 `aos exec` 後 ledger 仍各一筆：

~~~text
MATRIX_RESULTS
fault_point=after-target victim_pid=13 victim_exit=137
case=after-target first_recover_exit=0 second_recover_exit=0 post_exec_recover_exit=0 first_exec_exit=0 second_exec_exit=0 ledger_lines=1
fault_point=after-claim victim_pid=30 victim_exit=137
case=after-claim first_recover_exit=0 second_recover_exit=0 post_exec_recover_exit=0 first_exec_exit=0 second_exec_exit=0 ledger_lines=1
fault_point=after-delete victim_pid=47 victim_exit=137
case=after-delete first_recover_exit=0 second_recover_exit=0 post_exec_recover_exit=0 first_exec_exit=0 second_exec_exit=0 ledger_lines=1
fault_point=after-ack victim_pid=64 victim_exit=137
case=after-ack first_recover_exit=0 second_recover_exit=0 post_exec_recover_exit=0 first_exec_exit=0 second_exec_exit=0 ledger_lines=1
~~~

Thompson persona 做出兩段不同歷史、但 producer 可見 manifest 完全相同的現場；同一條 Deliver 重試都只能回 Unknown：

~~~text
diff_exit=0
beeffff3aa93323b4c0df0666353a22f54de40afa7099a70405d11598aefa899  /tmp/p4-round3-fixed/never.manifest
beeffff3aa93323b4c0df0666353a22f54de40afa7099a70405d11598aefa899  /tmp/p4-round3-fixed/consumed.manifest
never_published_exit=5 output=Unknown key=K evidence=temp-without-target-or-ack
consumed_no_ack_exit=5 output=Unknown key=K evidence=temp-without-target-or-ack
~~~

加入由 claimed payload 算出的 consumer ack 後，同一分類器才改回：

~~~text
Already key=K evidence=consumer-ack
retry_with_ack_exit=0
~~~

Cantrill persona 沒另開 ack 原型，但重跑後仍記到 Publish receipt 在 aggregate 刪除 target 後失去發布歷史，並指出現有 `aggregate_instructions()` 沒有 ack commit。Carmack persona 本輪沒有測 consumer acknowledgment。上一輪的 consumed-before-receipt 坑，**對遵守 ack 協定的 consumer 已解**：completion 由 consumer 留下，重開可機械取得既有 ack，不再 `adopt-consumed`；**對不合作 consumer 仍未解**。Armstrong persona 的反例原文是：

~~~text
{"ack":false,"aggregate":false,"aggregate_receipt":false,"claim":false,"command":"status","key":"key-rogue-evidence","ledger_lines":0,"payload":true,"publish_receipt":true,"ready":false}
{"command":"recover","error":"unknown-consumer-history: producer published, but ready, claim, and ack are absent","state":"stopped"}
rogue_recover_exit=1
~~~

**Carmack persona 上一輪未測的兩個 Effect terminal 窗口已解。** response 已 commit 時，resolve 只補 done；第一次由 4 commits 變 5，第二次 commit delta 0、ledger delta 0，最後 hash 與 baseline 相同：

~~~text
RESOLVE_COMMAND=effect.sh resolve EFFECT adopt-ready-response
{"request_id":"request-7","state":"done","outcome":"success"}
{"request_id":"request-7","state":"done","outcome":"success"}

resolve_first exit=0 commits=5 provider_ledger=1
resolve_second exit=0 commits=5 commit_delta=0 provider_ledger=1 ledger_delta=0
final_cmp_baseline_exit=0
~~~

decision 已 commit 時，兩次 `abandon` 同樣不增加 commit 或 provider ledger，final 保留 `unknown_abandoned`：

~~~text
RESOLVE_COMMAND=effect.sh resolve EFFECT abandon
{"request_id":"request-7","state":"done","outcome":"unknown_abandoned"}
{"request_id":"request-7","state":"done","outcome":"unknown_abandoned"}

resolve_first exit=0 commits=5 provider_ledger=1
resolve_second exit=0 commits=5 commit_delta=0 provider_ledger=1 ledger_delta=0
~~~

這只補上「response／decision 已有耐久證據，done 尚未 commit」的投影；provider acceptance 到 committed response 之間的 unknown 沒有被這兩案消除。

**Cantrill persona 實測私有 validator 與 canonical object parser 已分叉，且現有 C ABI 沒有 batch parser。** 16 案統計為 3 個共同接受、4 個共同拒絕、4 個私有接受但 canonical 拒絕、2 個私有拒絕但 canonical 接受，另有 3 個 batch C ABI 缺口：

~~~text
      3 AGREE_ACCEPT
      4 AGREE_REJECT
      3 CAPI_BATCH_GAP
      4 PRIVATE_ACCEPTS_CANONICAL_REJECTS
      2 PRIVATE_REJECTS_CANONICAL_ACCEPTS
~~~

實際差異包含 unknown key 與錯型別欄位被私有 validator 放行，`argv` 的 `$env` directive 與 duplicate `argv` key 則被私有 validator 擋下、canonical 接受。array 三案得到 `3:NotAnObject`，只對應 C ABI 只收 single object，沒有完成 object／array 全契約。上一輪「私有 validator 可能長出第二套 schema」的坑，這輪已量出逐案差異；沒有公開 batch C ABI 的缺口未解。

**本輪三個 harness／量測錯誤都保留了原文，修正後才重跑。** Carmack persona 第一個 response-window 案在 marker 已出現、PGID 檔尚未建立時就動手殺，卡在：

~~~text
cat: .../child.pgid: No such file or directory
/bin/kill: failed to parse argument: '-'
~~~

該案作廢；改成先寫 PID／PGID、最後發布 marker，再用新 world 重跑。Armstrong persona 第一次 audit 把 instruction exit 找在 `.aos/`，四案都數成 0；檢查目錄樹後改查 world 根，重跑為每案恰好一個內容 `0` 的 exit 檔。Thompson persona 第一版用 `mv target claimed`，publish 的 hard link 使 temp `st_nlink=2`，兩段歷史其實可分；該案作廢，改成 copy＋unlink 後兩邊都得到：

~~~text
never_temp_meta=mode=81a4 size=11 links=1
consumed_temp_meta=mode=81a4 size=11 links=1
~~~

**四份原型仍都沒有真實 power-cut 或跨平台證據。** Armstrong persona 的共用 `immutable_publish()` 做了 file fsync 與 directory fsync；Carmack、Cantrill、Thompson persona 都只把結果限定在 visibility。`renameat2(RENAME_NOREPLACE)` 仍是 Linux-only；NFS、磁碟滿、部分 fsync 失敗、非 Linux、receipt／ack 清理與 retention 都未測。四位都沒有改 C++、沒有 build、沒有 ctest。

### 3. 好處／壞處

#### 好處

上一輪留下的兩個窄缺口這輪都有實際輸出。Effect 這邊，response-ready 與 decision-ready 的第二次 resolve 都是 commit delta 0、provider ledger delta 0；response-ready 的 final hash 與 baseline 相同，decision-ready 則保留 `unknown_abandoned`。Deliver 這邊，合作 consumer 的四個死亡窗都能由一個高階 recover 收斂到 ack，重跑 recover 與 `aos exec` 沒再增加 effect ledger；`adopt-consumed`、人工搬檔與重造半批 instruction 沒再出現。

Thompson persona 的相同 manifest 對照把「沒有 target」保留成 Unknown，加入由 consumer claimed bytes 算出的 ack 後才成為 Already。Cantrill persona 把第一個數字拆成四欄，並直接量出私有 validator 與 C ABI object parser 的接受／拒絕差異。四份第三個數字仍是 0，producer、consumer、aggregate 被記為同一條 protocol 的階段，沒有新增 lane、join、scheduler 或 proc-table 現場。

#### 壞處

Deliver completion 現在包含 payload、visibility receipt、claim、aggregate receipt、delivery deletion 與 ack；ack 若要讓 producer 在 aggregate 後仍可查，就會留下需要 retention／GC 的紀錄。ack 清太早會重新失憶，不合作 consumer 則直接停在 `unknown-consumer-history`。Armstrong persona 的 gate 目前還要求 ack commit 後才讓 `aos exec` 取 aggregate；若有另一個 executor 在 receipt／ack 前搶走 `inst.json`，本輪沒有涵蓋該並行窗口。

Effect 仍需 request、response、decision、done 四類 evidence，unknown 仍不能由本機檔案推成 success、failure 或 exactly-once。Publish 仍需唯一 temp、no-replace、內容比對與 receipt；canonical batch parser 沒有公開 C ABI，私有 validator 的差異已是實際輸出。四份 R2 `/tmp` 現場全部消失，R3 產物仍放在相同類型的暫存位置。

### 4. 三個數字

**① 自己手寫了幾次 temp＋rename。** Carmack persona 回 **1**：一份 `publish.py`，三案另列 8 commits；與上一輪同答案，這輪 continuity hash 與兩次 resolve delta 讓 recovery 共用同一實作的證據更硬。Armstrong persona 回 **1**：一份 `immutable_publish()`、8 個呼叫點、recovery 人工 `mv` 為 0；與上一輪同答案，這輪同一 primitive 實際用於 payload、ready、claim、aggregate receipt、ack，並附 `primitive_definitions=1`，證據更硬。Cantrill persona 回 **2**：R1 shell 與 R2 Python/no-replace 各一份，另列 7 個靜態呼叫點、9 筆 runtime transaction、1 次人工 rename；上一輪答 9 筆 transaction，這輪依題目改取實作份數，並有 source inventory，答案比上一輪硬。Thompson persona 回 **6** 個靜態 temp＋rename 實作位置：R1 delivery 1、R2 model-call／tool result／final 3、R3 producer receipt／consumer ack 2；R3 兩處有逐行輸出，R2 三處因 `/tmp` 消失只能沿用上一輪紀錄，因此總數的本輪證據沒有全部重新取得。四人的原始答案是 **1／1／2／6**；p1、p2、p3 取實作份數，p4 取靜態實作位置。

**② 哪種「不知道做了沒」本機補不回來。** 四位都回 **1 類**：沒有 query、idempotency 或其他 durable witness 的邊界外 actor，可能已做完，但本機結果尚未 commit。p1 指向 provider acceptance 到 committed response；p2 把第一輪遠端 provider 與本輪 rogue consumer 記為同一根因；p3 指向非冪等外部 effect；p4 指向無 query／idempotency 的遠端 effect，並把可由 claimed evidence＋ack 修復的本機 consumer ambiguity 排除在外。數字與上一輪相同；本輪新增合作 consumer 已解、rogue consumer 仍停住的對照，以及 Effect 兩個 terminal window 的重複 resolve，邊界比上一輪更硬。

**③ 有沒有第二個要同時管的工作。** 四位都回 **0**。p1 三輪均沒有第二個長壽工作；p2 把 producer／aggregate 列為協定階段，每個 crash world 仍只有一個 instruction exit；p3 的 model、adapter、tool、scheduler、model 是單線序列；p4 把 producer／consumer列為 queue protocol 兩端，而非兩個需排程、取消、join、恢復的 agent jobs。答案與上一輪相同；這輪沒有新增第二個 logical work 的現場，硬度持平。

### 5. 評委上一輪要他們做的事，做到了沒

**Carmack persona。** 做到只打 response-ready／done-missing 與 decision-ready／done-missing 兩窗；兩案都將同一 resolve 連跑兩次，並輸出 provider ledger、commit 數與 final hash，第二次 delta 都是 0。第一個 response-window harness race 作廢後，用新 world 重跑。

**Armstrong persona。** 做到在 target、claim、delivery deletion、ack commit 後各砍一刀；合作 consumer 的同一 key 都能由 ack 機械恢復，`adopt-consumed` 消失。不合作 consumer 另以 `unknown-consumer-history` 停住，沒有用操作員證言補答案。

**Cantrill persona。** 做到同一份 inventory 輸出 2／7／9／1 四欄，題目答案改取 2 份實作；也直接呼叫現有 `libaos_inst` C ABI，逐案列出私有 validator 與 canonical object parser 的差異，沒有再複製一套 schema。batch 因 C ABI 不提供 `read_all()`，只記為 API gap。

**Thompson persona。** 做到只打 publish-success-before-receipt 與 consumer-delete-before-retry，對不可區分的兩份現場使用完全相同的 Deliver 重試命令，兩案都回 Unknown；consumer ack 存在後才回 Already。第一版 hard-link／`mv` 現場因 link count 可分而作廢，固定版另跑。

### 6. 仍然不知道的

仍不知道 consumer acknowledgment 正式放進現有 `aggregate_instructions()` 時，claim、aggregate target、刪 delivery、ack 與下一個 executor claim 之間的完整原子順序。Armstrong persona 用 gate 避免 ack 前執行 aggregate，但沒有測並行 executor 插入；現有 C++ 仍是發布 aggregate 後直接刪 deliveries，沒有 ack commit。

仍不知道 ack／receipt ledger 的保留期、清理責任與容量上限。合作 consumer 的歷史能靠 ack 補回，但清太早會再變 Unknown；不合作 consumer 沒有 claim／ack 時，本輪只能停住。也沒有多 producer、並行 aggregate、receipt 清理、磁碟滿與部分 fsync 失敗的 consumer-ack matrix。

仍不知道正式 Deliver 如何在不複製 schema 的前提下驗完整 object／array batch。現有 C ABI 只驗 single object；本輪已量到私有 validator 與 canonical object parser 互相有接受／拒絕差異，但 `read_all()` 沒有 C ABI，array 三案沒有 canonical conformance 結果。

仍不知道 power loss、NFS、非 Linux filesystem 與裝置快取下的結果，也不知道 `renameat2(RENAME_NOREPLACE)` 的可攜替代與 orphan temp 清理契約。R2 四份 `/tmp` 現場全數消失後，R3 證據仍只暫存在 `/tmp`。

仍不知道無 query／idempotency provider 的 unknown 最後由誰、依什麼權限選 retry、adopt 或 abandon。這輪只證實完整 response 或既有 decision 能重複投影 terminal state，不會重叫 provider；acceptance 到 response commit 之間的真相仍沒有本機答案。三輪也仍沒有真模型、真遠端 provider 或第二個長壽 logical work 的現場。

## 第 3 輪評分與意見

總分是五項直接相加，滿分 25；不拿來排名。這輪先查上輪指令，再查輸出能不能撐住結論。

### p1（Carmack persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：25 → 25，持平。** 上輪要的兩個 terminal 窗口、同一 resolve 連跑兩次、commit、provider ledger 與 final hash 全部交付；滿分後沒有更高的分可加。

response-ready 案第二次 `commit_delta=0`、`ledger_delta=0`，而且 final hash 與 baseline 相同；decision-ready 案也是零 delta，且沒把 `unknown_abandoned` 偽裝成 success。第一個 harness race 有留原文、作廢、換新 world 重跑，這份回報可信。

**下一輪：**不要再增加 Effect 狀態。換一個支援 query 或 idempotency key 的真實 provider stub，與一個兩者都不支援的 stub，各在 acceptance 後破壞本機 result commit；用同一張轉移表輸出前者可 resolve、後者必須停在 unknown。

### p2（Armstrong persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：25 → 25，持平。** 上輪指定的 target、claim、delete、ack 四刀全部真殺到 exit 137，合作 consumer 四案都收旂，不合作 consumer 則明確 exit 1 停在 unknown；這正是要測的邊界。

最硬的不是 `matrix_assertions=PASS`，而是四份 `PRE_RECOVERY_STATES` 真的不同，而且每案兩次 recover、兩次 `aos exec` 後 `ledger_lines=1`。rogue consumer 的 `unknown-consumer-history` 反例也證明 ack 是協定，不是 producer 自己寫張紙就算完成。

**下一輪：**只補並行 executor 窗口。在 aggregate target commit 後、ack commit 前強制另一個 executor 搶 `inst.json`，輸出 claim 是被 gate 擋住還是真的取走；若取走了，這份 CLI 原型就不能當成可落地的 Deliver 協定。

### p3（Cantrill persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 5/5 |
| 路線價值 | 5/5 |
| **總分** | **25/25** |

**較上輪：24 → 25，進步。** 上輪唯一的扣分點已修掉：這次用同一份 inventory 把 2 份實作、7 個 call site、9 筆 transaction、1 次人工 rename 分開，沒再用 runtime 次數回答原碼數量。

直接打現有 C ABI 的結果是 4 案私有 validator 錯放、2 案錯擋，還有 3 案 batch API gap；這比說「schema 可能分叉」有價值。R2 原始現場丟了就只宣稱兩支有 hash 的腳本已復原，沒有為了閉環造假。

**下一輪：**不准寫第三套 parser。做一個最小的 canonical `read_all()` conformance harness，對 single object、array 與錯在第二筆的 batch 各輸出結果；若現有公開邊界根本叫不到 `read_all()`，就把「需要公開 batch validation」當成唯一結論，不要再造 wrapper。

### p4（Thompson persona）

| 項目 | 分數 |
|---|---:|
| 證據強度 | 5/5 |
| 誠實度 | 5/5 |
| 走了多遠 | 5/5 |
| 回答了三個數字 | 4/5 |
| 路線價值 | 5/5 |
| **總分** | **24/25** |

**較上輪：25 → 24，退步。** 兩個指定窗口都做對，但第一個數字 `6` 裡有 3 個 R2 位置只靠上輪文字，本輪的原檔已消失，沒有像 p3 那樣用一次 inventory 把全數釘死。這扣的是答案硬度，不是誠實度。

作廢 hard-link／`mv` 版本是對的；`st_nlink` 洩漏歷史就不是不可區分性證明。修正後 `diff_exit=0`，同一 Deliver 命令對兩種歷史都回 Unknown，加上由 claimed bytes 算出的 consumer ack 才回 Already；這段證據很強。

**下一輪：**先把六個 temp＋rename 位置放進同一個可持久、可寫的現場，用一條 source inventory 印出全部六個；做不到就把第一個數字降為「本輪可驗 2，累計主張 6」。別再重測 Already／Unknown／Conflict，那條邊界已經證完。

### 路線判斷

**最值得繼續走的仍是 p2 的 consumer-acknowledged Deliver，下一刀是並行 executor，不是再加 ledger 欄位。** 具體證據是 p2 四刀的 `MATRIX_RESULTS`：target、claim、delete、ack 之後殺掉都能 `first_recover_exit=0`，且兩次 `aos exec` 後 `ledger_lines=1`。同一份回報的 rogue consumer 又給出 `unknown-consumer-history` 與 `rogue_recover_exit=1`，證明這條路只對遵守 ack 協定的 consumer 成立，沒有超賣。p4 的 `diff_exit=0` 加上兩歷史都回 Unknown，則從反面證明 producer-only receipt 已經死了。

**這輪沒有推翻上輪的 scope 判斷。** 上輪說選 (b)、Publish 先做、Deliver 不能當薄 wrapper、(c) 沒有證據，這輪全部維持。改變的是證據等級：consumer ack 從「下輪該驗的解法」變成「協定內四個死亡窗口已跑通」，Effect 也從未測 terminal projection 變成重複 resolve 零 delta。這是確認，不是翻案。

**致命的坑有兩個，但致命對象不同。** 無 query、idempotency 或 durable witness 的外部 effect，在 acceptance 與本機 result commit 之間死掉，對「本機自動 exactly-once」是整條路線致命；不支持 consumer ack 的 producer-only Deliver，在 target 被取走後對「獨立 completion receipt」致命。後者不會殺死 Deliver，只是強迫 ack 進 aggregate commit domain。Linux-only no-replace、receipt／ack retention、orphan temp、batch C ABI、parser 共用與 `.runi` replay 都是麻煩，不是推出控制平面的理由；power-cut 沒測則是證據缺口，在補測前不准把 visibility 叫 durability。

### 可信度判斷

**沒有一份整體回報不可信。** 四位都留下自己的 harness 錯誤、作廢原因與未測邊界，沒有人用「做完了」代替輸出。**但 p4 的第一個數字 `6` 不能當成本輪已獲得獨立證明：**其中 3 個只存在上輪文字紀錄，原檔已被 `/tmp` 清掉。說清楚這點使 p4 的誠實度仍是 5，但不會讓證據自動長回來。

### 現在就得拍板

我會建議使用者選 **(b) Publish → Deliver → Effect**，而且必須分段驗收；不是把四份 Python／shell 原型合併就算 core。Publish 只承諾同 filesystem 的唯一 temp、atomic no-replace、stable key、同 bytes `Already`、異 bytes `Conflict` 與明示的 visibility／fsync 邊界；Deliver 的 completion 必須由 consumer／aggregate ack；Effect 只保存 phase、evidence、unknown 與明示 reconcile，不承諾 exactly-once。

**第一步仍是 Publish，答案跟上輪沒變。** 這不是因為架構圖好看，而是 p2 實測一份 primitive 已有 8 個 call site，p3 的 inventory 也是 7 個 call site，而 p4 本輪又為 producer receipt 與 consumer ack 多寫兩處 temp＋rename。第三個數則四份仍是 0，沒有任何 lane、join、cancel 或第二個長壽 job 的輸出；所以 (c) 仍是為將來臆測的抽象，不做。這是評審建議，最後由使用者拍板。

## 第 3 輪白話導讀

### 1. 這一輪到底發生了什麼

四個人沒有再把整套東西重做一遍，而是專打上輪還沒釘死的幾個縫。收件方肯留下證明時，半路被砍後已能自己接回去；外面的服務若無法查詢，這台電腦仍然不可能猜出它到底做了沒。這輪也抓到自己另寫的資料檢查規則，已經跟 aos 真正接受的規則不一樣。

### 2. 跟上一輪比，變了什麼

上輪只是推定「收件方留證明」可能救回檔案被取走後的失憶，這輪把四個中止位置都跑通了，還證明重跑不會多做一次；但不留證明的收件方仍只能停住。外部服務那邊則只補實了「已有答案或已有人的處置決定時，重開只做收尾」，沒有換回未知那一段的真相。scope 沒翻案：中間選項的可行性變硬、代價也更清楚，完整控制平面仍沒有第二件長期工作替它提供理由。

### 3. 新冒出來的詞

- **consumer acknowledgment／completion ack／ack gate**<br>
  白話：見前；就像收件人簽收後，門口才准把下一箱貨放行。<br>
  在 aos 裡具體是什麼：仍是私有提案；本輪原型讓收件方在 `claim → aggregate publish → delete delivery → ack commit` 後留證明，並在 `aos exec` 前設 gate，現行 `core/inst/src/handoff.cpp` 的 `aggregate_instructions()` 還沒有這段。

- **terminal projection**<br>
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：不是現行 aos 命令；本輪私有 `effect.sh resolve EFFECT adopt-ready-response`／`effect.sh resolve EFFECT abandon` 只補 `done`，Effect／resolve 本身仍是提案。

- **C ABI／conformance／canonical parser／schema**<br>
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：單筆公開入口在 `core/inst/include/aos/inst.h`，正式整批讀取規則在 `core/inst/src/format.cpp` 的 `read_all()`；後者尚無公開 C ABI，本輪只做對照，沒有新增命令。

- **retention／GC**<br>
  白話：見 [BACKGROUND](../../workshop/BACKGROUND.md) 的 ledger。<br>
  在 aos 裡具體是什麼：目前不存在，是 completion ack／receipt 若進 core 後仍待決的保存與清理提案。

- **Publish、Deliver、Effect、receipt、ledger、`unknown`、no-replace、fsync、idempotency key**<br>
  白話：見前／見 [BACKGROUND](../../workshop/BACKGROUND.md)。<br>
  在 aos 裡具體是什麼：本輪仍是 `/tmp` 裡的 Python／shell 私有原型；公開入口仍只有 `aos exec <world>`，沒有 `aos publish`、`aos deliver`、`aos effect` 或 `resolve` 命令。

### 4. 這輪新看到的錯誤訊息各是什麼意思

- `r2_present=no`／`round2=missing`：上一輪放在 `/tmp` 的現場已被系統清掉，不是本輪原型跑壞。
- `victim_exit=137`：見前；這是測試故意把行程強制砍掉，用來驗重開。
- `unknown-consumer-history: producer published, but ready, claim, and ack are absent`／`rogue_recover_exit=1`：東西曾投出去，但現在待辦、取件痕跡和簽收證明全不在，程式拒絕猜它是否已被處理。
- `Unknown key=K evidence=temp-without-target-or-ack`／`exit=5`：只剩草稿，既看不到正式件也看不到簽收單，所以同一條重試命令只能回答「不知道」。
- `3:NotAnObject`：拿整批陣列去問只會檢查單筆資料的公開入口，它看到的不是單一物件；這也表示整批檢查尚無可用的公開入口。
- `cat: .../child.pgid: No such file or directory`：測試太早動手，子行程編號檔還沒寫好；該次結果已作廢重跑。
- `/bin/kill: failed to parse argument: '-'`：上一個缺檔讓殺行程命令拿到空值，因而只剩一個無法解析的減號；不是被測功能本身的錯。
- 第一次 audit 顯示四案 exit 都是 `0` 筆：檢查腳本找錯資料夾，不是四案都沒執行；改看 world 根目錄後每案各找到一筆內容為 `0` 的退出紀錄。
- `st_nlink=2`：第一版測法留下兩個檔名指向同一份內容，意外洩漏了先前發生過什麼，因此那次「兩種歷史看起來一樣」的證明不成立，已作廢重跑。

### 5. 所以呢

這輪仍影響 [OPEN-QUESTIONS 第 2 題](../../workshop/OPEN-QUESTIONS.md#2-近期-core-要回撤到哪裡)，三個選項仍都在，但各自要賠的東西更明確：

- **只留最小 Deliver**：得到最小 core；賠掉共用的安全發布與外部結果記錄，而且若 Deliver 不含收件方的簽收證明，待辦被取走後仍會失憶。若把簽收也算進「最小 Deliver」，就得一併承擔簽收順序、保存多久與清理責任。
- **保留 Publish → Deliver → Effect 三項**：得到本輪已跑通的共用發布、收件證明與有證據才收尾的邊界；賠掉的是三項不能只是薄薄相疊，還要處理整批資料共用同一套檢查規則、並行取件、簽收保存，以及外部服務無法查詢時永遠只能停在 `unknown`。
- **連完整控制平面一起保留**：得到未來同時管理多件長期工作、等待、取消與收尾的空間；賠掉 lane、join、proc-table 等整套設計與驗證成本，而三輪的「第二件需要同時管理的工作」仍是 0，這輪沒有替那些成本換到新證據。

因此，多跑這輪沒有替使用者選答案；它把中間選項從「看起來可試」推到「幾個窄故障點確實跑通」，同時把它必須包含的簽收、共用檢查與保存責任攤開。最小選項的界線也變得不能只用一層薄包裝帶過；最大選項則仍沒有新增實測需求。
