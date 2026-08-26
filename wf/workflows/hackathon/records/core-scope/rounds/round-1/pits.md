# 第 1 輪紀錄 — 坑的總表

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 →](../round-2/pits.md)

這一輪撞到的坑，按「幾位獨立撞到」排序，每條都附四路的現場原文與錯誤訊息。

## 2. 坑的總表

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
