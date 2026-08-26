# core scope 黑客松 — 每輪紀錄（書記）

← [本場索引](README.md)｜[hackathon](../../README.md)

發生了什麼：各人做了什麼、坑的總表、三個數字收到什麼答案。不含判斷。

---

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
