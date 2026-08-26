# 第 2 輪紀錄 — 坑的總表

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：← R1](../round-1/pits.md)｜[R3 →](../round-3/pits.md)

這一輪撞到的坑，含上一輪哪些坑被解掉、哪些還在，每條都附現場原文與錯誤訊息。

## 2. 坑的總表

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
