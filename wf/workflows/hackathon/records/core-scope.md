# core scope 黑客松紀錄

> **以下是風格模擬，不是本人的意見。** 文中的 Carmack、Armstrong、Cantrill、Thompson 都是 persona 名稱，不是本人發言或引述。

| 項目 | 內容 |
|---|---|
| 題目 | 用現有的 `aos`（不改 C++、不 build）跑出一條三回合 agent loop，中途以 Ctrl-C、`kill -9`、rename 前中止，記錄重開後必須自行補上的工作；問出 temp＋rename 手寫次數、哪種 unknown 無法由本機補回、是否出現第二個需同時管理的工作，以對應近期 core scope 的三種大小。此題承接 OPEN-QUESTIONS 第 2 題「近期 core 要回撤到哪裡」。 |
| 開場日期 | 2026-08-26 |
| 環境 | WSL Ubuntu；codex 0.149.1；`-s workspace-write`；無網路；四位平行；單輪逾時 1800 秒；R1 費時 9.5 分鐘。 |
| Reasoning effort | `model_reasoning_effort=high` |
| 狀態 | R1 已完成，預計三輪。 |

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
