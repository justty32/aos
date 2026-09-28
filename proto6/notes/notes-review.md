# proto6 notes 審查

← [筆記索引](README.md)

日期：2026-09-28。審查者：Fable 派出四隊獨立審查——A 隊（Opus，概念與草案內在一致性）、B 隊（Opus，計畫與 Linux 技術可行性）、C 隊（Sonnet，收錄忠實度與連結機械檢查）、codex gpt-6-astra（唯讀，獨立意見）。四隊互不看彼此的報告，本檔由 Fable 彙整。

**這是審查紀錄，不代表其中建議已採納。**

範圍：`notes/` 全部筆記（含 `plan/`、`investigations/`、`probes/`）與 `spec/` 全部 22 篇對照；C 隊另外核對 `notes/README.md`「完整來源對照」表宣稱的 15 份收錄與兩支探針程式。四隊皆只讀、未改 repo、未執行探針（B 隊在本機做過唯讀的核心機檢查，見下方「機器查證結果」）。以下路徑一律相對於 `proto6/`。

## 必修（14 條）

1. **（A 隊）needs_attention 的「人工 resume」沒有定義的路可走。**
   `spec/agent/configuration.md:19`「修復原內容並經人工 resume 後重新驗證」；`spec/agent/memory.md:11`「修復後人工 resume 驗證再繼續」。但 `spec/agent/input.md:23` 的 resume 只定義 paused→queued／active；`spec/scheduling/operations.md:9` 的 run.resolve 要 job_id、只處理 unknown。設定遺失、blob 損壞、storage_blocked、連兩次壞回覆（`spec/agent/tools.md:9`）、context_over_budget 進了 needs_attention 以後，只剩 cancel 一條路，和條文說的「可 resume」打架。遺漏審查說「已關閉」，但沒涵蓋這一點。建議：在 A-203 或 S-102 補一句「非 unknown 原因的 needs_attention，修好後可以用 run.resume 重新驗證、回到 active」，或者改成明說「只能取消」。

2. **（A 隊）兩份舊筆記的開頭標示只講了一半，會讓人以為固定 worker 還是現行要求。**
   `notes/2026-09-28-host-root-design.md:7,13`：開頭只補了「工具繼承權限」的後續決定，正文第 13 行仍寫「使用者已定：正式員工……固定負責其 tick 的 CPU worker」。`notes/2026-09-28-linux-employee-implementation.md:7,17,33`：一樣，還有整節「專屬 tick worker 可以復用多少 cpu」。兩份的標示都連到「已定方向」employee-identity，沒提「分類已放下、worker 改為取消方向」。建議：兩份開頭各加一句「正式員工分類與固定 worker 已被〔資源與任務排程〕取代，只是演進脈絡」。

3. **（A 隊）base.md 把「tick 當 JSON-RPC server」寫成定論，spec 和另一份筆記都不是這樣。**
   `notes/base.md:33`「tick 讀請求、寫回應，就能履行 server 的角色」。spec 的 B-501／B-502 把收件的角色（server）交給控制接入口，tick 只是發出 checkpoint.commit 的一方。`notes/between-ticks-configuration.md:9` 也寫「JSON-RPC 交給 tick 處理只是曾討論的可能做法，尚未採納」。原文（`notes/2026-09-28-linux-resources-and-task-scheduling.md:57` 附近）講的 tick 是 proto5 的 kernel tick，不是 agent tick。建議：改成「某次處理可以扮演 server，spec 目前由控制接入口承擔」。

4. **（A 隊）A-302「調整預算後恢復」和另外兩條規定衝突。**
   `spec/agent/memory.md:21`「調整預算或提出較小輸入後由人工選擇恢復」。可是 context policy 屬於每輪固定的設定（A-102：改了只能取消再建新輪）；`spec/scheduling/llm.md:53` 也說「首版沒有同 run 加額 API」。建議：改成「只能取消，再建新 run」，或者明列哪一個預算可以在同一輪裡調。

5. **（A 隊）遇到 429 可不可以重試，兩處規定對不起來。**
   `spec/scheduling/llm.md:25,29`：遇 429 直接把 job 轉 waiting；驗收寫 max_attempts=2 時會重試。`spec/scheduling/runs.md:33`：只有 retry_class=safe 的工作才能從 failed 回到 waiting；而 `spec/contracts.md:49` 的 JobDraft 預設 retry_class=never。照字面看，LLM job 預設根本不能重試。建議：S-303 寫清楚「429 重試需要 retry_class=safe」，或者把 429 列為 retry_class 的例外。

6. **（A 隊）agent.md 說「不發明版本欄位」，spec 已經發明了。**
   `notes/agent.md:11`「目前不先發明版本欄位」。spec A-102／C-02 已經定了 config／context／tools 三個版本欄位（冗餘審查 B3 也在談這件事）。建議：agent.md 加一句「spec A-102 已提出建議預設」，像 `notes/concepts.md:39` 那樣標出來。

7. **（B 隊）「特權只在佈建」講錯：日常每次開工作都要特權。**
   `notes/plan/linux-and-storage.md:13`「把有特權的佈建與日常運行分開…runtime 只使用已批准的登記啟動」，以及 `notes/plan/README.md:42`「不承諾在使用者真機部署 root daemon」。問題：切到另一個宿主 UID（setresuid／setgroups）必須有 CAP_SETUID／CAP_SETGID，而且要在最外層的 user namespace 裡；把程序放進 root 擁有的 cgroup 也要權限。所以日常路徑一定要有一個常駐的特權點，可能是 root daemon、setuid 或帶檔案 capability 的 launcher，或經 polkit 的 systemd-run，不是只有佈建才要。user namespace 路線也一樣：project ID 只准在最外層 namespace 改（kernel fileattr_set_prepare），佈建還是要宿主 root。建議：寫明「日常一定有一個特權點」，把它是誰列成待裁定（見待裁定 A）。

8. **（B 隊）第 2 階段有循環依賴。**
   `notes/plan/README.md:40`「接入…整套 aos 的外牆」、`:42`「外牆…仍待選定」、`:42`「取消逐工具 bwrap 要和…外牆一起落地」。問題：驗收要有外牆，外牆卻還沒選，所以第 2 階段永遠結不了案。建議：拆成兩段。2a 在 VM 裡用 root 驗 UID、cgroup、quota，不含外牆；2b 做外牆。「外牆選定」寫成進 2b 的門檻。其中 cgroup 部分這台機器不用 root 就能先做（見機器查證結果）。

9. **（B 隊）三篇的階段編號互相打架。**
   `notes/plan/runtime.md:25`「第二階段：持久排程索引」、`:37`「第二階段一併做」、`:53`「第三階段」做 direct exec。`notes/plan/README.md` 的說法不同：第 1 階段就做 ready／due 索引（`:34`），第 2 階段做 direct exec（`:42`）。`notes/plan/linux-and-storage.md:101` 的「第一階段」是帳號加 quota 原型，等於 README 的第 2 階段。建議：統一照 README 的 0–4 編號。

10. **（B 隊）project quota 擋不住檔案擁有者，不是硬邊界。**
    `notes/plan/README.md:15`「自有資料用…project quota」，spec B-304 也把它當硬上限。問題：kernel 改 project ID（FS_IOC_FSSETXATTR，也就是 `chattr -p`）只檢查「是不是檔案擁有者」。擁有者可以在最外層 namespace 把自己的檔改到一個沒設上限的 project ID，也能清掉 PROJINHERIT。方向又是工具跟 agent 同 UID、檔案歸 agent 所有，所以 agent 自己就能跳出額度。`notes/plan/linux-and-storage.md:68` 只把這件事列成「待測」，其實答案已知：逃得掉。建議：launcher 用 seccomp 擋 ioctl 的 FS_IOC_FSSETXATTR（ioctl 的命令碼是純數值，seccomp 過濾得到）；做不到就改稱「只記帳」。

11. **（B 隊）systemd 預設會在重啟時殺光在途工作，計畫沒交代。**
    `notes/plan/linux-and-storage.md:36-41` 把 control 和 work 放在同一個委派根，也就是同一個 unit。問題：systemd 預設 KillMode=control-group。stop、restart 或崩潰後自動重啟，都會 SIGKILL 整棵樹，包含所有 job。`notes/plan/runtime.md:57`「daemon 重啟需依執行 ID 清理」和 `:71`「tick 執行中殺 daemon」這兩個恢復情境，在預設設定下根本沒有在途工作可以對帳。建議：work 子樹放到獨立的 slice／unit，或明寫 KillMode 的選擇，並把「重啟就殺光」列成已知行為。

12. **（B 隊）用 VM 做真機驗收，但沒人負責、也沒寫 quota 在本機的現況。**
    `notes/plan/README.md:40`「先證明檔案系統真的啟用並強制 quota」。本機現況：根檔案系統就是 repo 所在的 ext4，掛載選項是 `noquota`；quota 相關工具都沒裝；非 root 讀不到 superblock 的 feature。ext4 要開 project feature 得先卸載再 tune2fs，根檔案系統做不到。`notes/plan/linux-and-storage.md:95` 只寫了 `rw,relatime`，漏了 noquota 這件事。建議：第 2 階段開頭就寫明「需要 VM，或專用分割區／loop 映像加上 root」，並指定由誰提供。

13. **（astra）五分鐘是到期時間，不是重訪上限。**
    `notes/plan/runtime.md:11`：「idle 無輸入會停車，預設最晚五分鐘重訪。」實際 `../proto5/lib/aos_kernel_info.py:328` 只設定 `not_before`；`../proto5/lib/aos_kernel_ledger.py:100` 到期後把工作接到 ready 隊尾，還要等空 worker（`../proto5/lib/aos_kernel_engine.py:195`）。池滿或 kernel 延遲時可以超過五分鐘。應改成「預設五分鐘後重新具備派工資格」；每秒約 33 次也只是理想均攤估算（另見建議：B 隊「停車重訪沒估 CPU」同一段，是兩個不同角度的問題）。

14. **（astra）daemon 池式啟動的開檔描述不符程式。**
    `notes/2026-09-28-linux-employee-implementation.md:21`：「`_execute_inst` 先建 cwd、開 stdin／stdout／stderr，再執行。」此處正在描述 daemon 池式路徑，但 `../proto5/lib/aos_exec_spawn.py:89` 會拒絕顯式 stdin/stdout；帶 launcher 時，`../proto5/lib/aos_exec_run.py:58` 也跳過這兩個檔案的開啟。應分開描述一般 exec 與 daemon 啟動。**先降權的結論仍成立**：讀 target、解析指示詞、條件式建目錄與開 stderr 等操作仍在前面。

## 建議

- **（A 隊）README 的最新方向摘要漏了三個重要限制。** `notes/README.md:17-19` 跟原文對得上，沒有另外加東西；只有「不需逐工具 bwrap／外牆保留」是出自 employee-identity，不是資源筆記。漏了三個重要限制：資源歸屬要跟著可信派工走（`notes/2026-09-28-linux-resources-and-task-scheduling.md:43` 附近）；外部 workspace 不算進自有容量，但它造成的記憶體用量照樣計入（`:17`）；任務途中來的新訊息算哪一輪，使用者尚未決定（`:61`）。建議補進 README。
- **（A 隊）`notes/README.md:25`「現行程式、spec……仍指向 proto5」措辭易混淆。** 這裡的 spec 指 proto5 的 spec，容易和 proto6/spec 搞混，建議寫成「proto5 spec」。
- **（A 隊）`notes/investigations/*.md` 個別檔只有通用的快照標示，要回到 investigations/README 才看得到「員工／worker 是當時用語」。** 建議每份各加一行。
- **（A 隊）「一輪任務」的結束點講法不一。** `notes/2026-09-28-linux-resources-and-task-scheduling.md:37` 說「接受工作……到回到 idle」，但 `notes/scheduling.md:11`、`notes/agent.md:35`、A-503 都說 idle 不等於完成。建議在資源筆記旁註明 spec 已經把兩者分開。
- **（A 隊）`notes/concepts.md:35`「執行底座則對應基底」不夠精確。** human-architecture 的執行底座包含排程器（kernel），那部分現在屬於「任務與排程」。建議改成「執行底座分到基底和排程」。
- **（A 隊）術語不統一，共六處。** owner 有三種意思：T-02 的「三層 owner」（哪一層負責）、各條開頭的「Owner：控制層」（哪個元件負責）、C-05／B-403 的「跨 owner」（哪個 agent 擁有這份工作），建議第三種統一叫「所屬 agent」。`spec/terms.md` 沒有定義 tick 和任務（task），資源筆記同時用 kernel tick 和 agent tick，notes 的「任務」大致等於 run，但沒寫明。「輪」同時指 run（輪次）和排程器的一次循環（`spec/scheduling/admission.md:9,35`「每輪」）。等待原因有兩套寫法：A-502 的 wait_reason 是 `result|budget|due|operator`，S-402 的是 `not_due|quota_wait…`。run_id 可以是 null 的 tick：`spec/base/work.md:12`、A-501 叫「維護／空收件探查 tick」，C-03／C-05 只叫 maintenance。generation 什麼時候加 1：B-602（`spec/base/lifecycle.md:13`）說 claim 時，S-103（`spec/scheduling/runs.md:27`）說 released 時。
- **（A 隊）人工核對過遺漏審查與冗餘審查引用的條文，沒有發現講錯的主張。** 缺口 G-01～G-07、「已有保證」清單、冗餘 A1、B1～B5、C1、C2 引用的條文都真的存在，也真的重複或已修，也符合「spec 共 22 篇」的說法。唯一的漏洞就是必修 1 那條不在它的「已關閉」範圍內。
- **（B 隊）Popen 降權會漏群組。** `notes/2026-09-28-linux-employee-implementation.md:27` 只說有 `user=`／`group=`／`extra_groups=` 可以用。但 root 端只給 `user=` 時，GID 會留在 0，root 的補充群組也會保留。應寫明三個參數都必給，`extra_groups=[]` 要明寫。
- **（B 隊）逃出 cgroup 的路不只 fork／setsid。** `notes/plan/linux-and-storage.md:101` 之外，還有 cron／at（預設所有帳號都能用）、D-Bus 啟動的系統服務、以及 ssh 回本機。驗收要加這幾條，佈建要放 cron.allow／at.allow。
- **（B 隊）被 cgroup 殺掉要分辨得出來。** rmdir 之前要先讀 leaf 的 memory.events（oom_kill、oom_group_kill）。spec 設了 oom.group=1，包裝程序會跟著一起死，exit 檔就寫不出來。應定義「leaf 已空、沒有 exit 檔、oom_group_kill>0」算 OOM。另外 memory.high 只會拖慢、不會殺，可能讓 tick 無限變慢，一定要配逾時。
- **（B 隊）時鐘跳動沒人提。** 現行 `not_before` 用 `time.time()`（`../proto5/lib/aos_kernel_info.py:329`）；spec 的 due 用 `*_at_ms`，lease 30 秒也看牆上時間。時鐘往前跳，所有 due 會同時到期、所有 claim 同時變 suspect；往回跳，全部延後。建議持久欄位存牆上時間，比較時改用 monotonic 加開機 ID。
- **（B 隊）帳本斷電耐久沒交代。** 現行 SQLite 是 WAL 加 `synchronous=NORMAL`（`../proto5/lib/aos_kernel_store.py:69`），斷電會掉最後幾筆已經 commit 的交易。`notes/plan/runtime.md:37` 談了收件的 fsync 時點，但沒談帳本本身的耐久等級。
- **（B 隊）磁碟滿時控制區的保留空間沒交代。** ext4 保留區只給 resuid=0。`notes/2026-09-28-host-root-design.md:20-26` 建議 kernel 改用一般服務 UID，這樣就用不到保留區。可以用 resgid 保留給控制群組。
- **（B 隊）/tmp 在本機是 tmpfs，寫進去吃的是記憶體，不是磁碟。** 用量記在寫入者的 memcg，leaf 刪掉後會掛在 dying memcg 或父層，一萬個 UID 共用。`notes/plan/linux-and-storage.md:91` 只說要有「全局容量政策」，應寫明這一點。
- **（B 隊）每個 job 一個 leaf 會累積 dying memcg。** page cache 還掛在已刪的 leaf 上。壓測要記 `cgroup.stat` 的 nr_dying_descendants（`notes/plan/linux-and-storage.md:48`）。
- **（B 隊）UID 範圍該給實數。** `notes/plan/linux-and-storage.md:21` 沒給。本機 `login.defs`：UID_MAX=60000、SUB_UID_COUNT=65536、SUB_UID_MAX=600100000，照預設 useradd 自動配 subuid，大約到第 9,155 個帳號就配不出來。lorkhan 已占 100000–165535。systemd 保留 60001–60513、61184–65519、65534、524288 以上。
- **（B 隊）第 1 階段驗收自相矛盾。** `notes/plan/README.md:36`「不被週期性派 tick」和 `notes/plan/runtime.md:15`「外部檔案條件保留有界補查」衝突。要說清楚補查是不是 tick、是誰在評估條件。
- **（B 隊）btrfs 沒提。** btrfs 沒有 project quota，只有 subvolume 的 qgroup，一萬個 qgroup 效能很差。建議明寫只支援 XFS／ext4 的專用卷。
- **（B 隊）程式引用大致正確，只有行號漂移。** `notes/plan/runtime.md` 的每條都查證屬實：停車 300 秒、tick 前就讀 history 與工具表、load() 全讀、只寫變了的列、`while queue and free`、tick 鎖、daemon 只盯 kernel 家。漂移兩處：`notes/2026-09-28-linux-employee-implementation.md:31` 寫的 `../proto5/lib/aos_daemon_pools.py:292` 實際是 296；`:104` 寫的 `../proto5/lib/aos_exec_cpu.py:274` 實際是 262–263。另外 runtime §2 沒提現行已經有 due 堆積與 ready 佇列（`../proto5/lib/aos_kernel_ledger.py:70-120`），只是整份存成 meta 裡的一個 JSON。
- **（B 隊）過時說法沒同步。** `notes/investigations/proto5-host-root-second-wall.md:15`「systemd --version 找不到」。實際 PID 1 就是 systemd 261，另一篇 feasibility 已經更正，這篇沒同步。
- **（B 隊）CPU 門檻比現況還低。** `notes/plan/llm-and-validation.md:69` 要求「控制層 CPU 平均低於單核 1%」。但 one-boot 實測只有 1 個停車 agent，閒置 60 秒就用了 2.31–2.44 CPU 秒，約 4%，因為 kernel 每秒開一個 Python 程序。計畫沒寫要拿掉這個每秒一格。
- **（B 隊）停車重訪沒估 CPU。** `notes/plan/runtime.md:11` 算出每秒約 33 次重訪，算術正確。但每次都是一個 Python 程序，CPU 成本沒估。
- **（B 隊／astra）巡檢一圈要兩個半小時，計畫沒寫恢復時間上限。** spec `spec/scheduling/admission.md:21`（S-202）每 60 秒巡 64 位，一萬位巡完一圈約 157 分鐘。`notes/plan/runtime.md:41,45` 說週期「依承諾的恢復時間」決定、要求「恢復時間有上限」，卻沒寫承諾值，第 1 階段的漏通知驗收也沒有上限。應說清每次能跑幾批、如何安排尚未交接項，以及漏通知恢復指標；正常喚醒的 0.5 秒不能代替它。
- **（B 隊）0.5 秒沒定起訖點。** 從收件回執算？daemon 看到算？還是 tick 程序啟動算？也沒寫機器規格。現況投件到回音約 0.04 秒，所以難點不在延遲本身，而在萬級規模下 kernel 每格都整份載入帳本。
- **（B 隊）少量帳號的數量不一致。** `notes/plan/README.md:38`「兩個」、`notes/plan/linux-and-storage.md:101`「2～3」、`notes/plan/llm-and-validation.md:57`「2–5」。
- **（astra）把巢狀受管委託補成一條完整流程。** `notes/plan/llm-and-validation.md:29` 要求工具內部模型呼叫經同一可信入口；但現有 methods 沒有工具提交同 run 子 job 的操作，建立 job 主要靠持有 live claim 的 tick proposal。若工具改用 `agent.submit` 並等待，後輪又被目前 run 擋住；即使新增子 job 入口，`per_agent_inflight=1` 時也可能父等子、子等票。應明定提交入口、父子關係、等待時如何處理名額，以及取消父工作時如何收尾子工作。歷史稿已在 `notes/2026-09-28-host-root-design.md:68` 提醒過死鎖，新版契約尚未接完整。
- **（astra）大 token 請求的公平性不能只靠等待年齡。** `notes/plan/llm-and-validation.md:45` 說大請求不能被小請求餓死；S-204（`spec/scheduling/admission.md:35`）卻只優先選「可入場」的老工作。若小請求持續耗用同 scope，餘額可能一直不足以容納大請求，保留年齡也無效。建議加入同 scope 暫停小單以累積額度的案例；另明定需求超過 scope 整個窗口上限時立即拒絕，不能當普通 quota_wait。
- **（astra）舊快照回退不同於一般崩潰恢復。** `notes/plan/README.md:58` 允許備份恢復作為回退路徑，但快照之後可能已完成寄信、寫外部 workspace 或模型扣款。恢復舊帳本會連去重證據一起倒退。建議補「快照後已產生副作用再回退」案例，保留該期間執行／收據紀錄供對帳；缺證據的工作不得直接重派。

## 沒交代的邊緣狀況（A 隊）

你（使用者）點名的五個情況都已經有條款處理：控制程序崩潰見 B-603，LLM 逾時見 S-304／A-404，子程序殘留見 B-202，寫到一半的 history 見 A-301 孤立 blob＋C-05，兩個 tick 同時跑見 B-602。真正沒人管的是下面這些：

1. **tick 自己一直失敗**：控制程序沒倒，但 tick 逾時、崩潰、交不出提案。S-306 的 max_jobs 不算控制 tick（`spec/scheduling/llm.md:49`），也沒有 tick 重試上限或退避，一份壞掉的 checkpoint 就會讓它無限重來。
2. **工具用 agent 身分投件，可以繞過每輪預算**：B-501（`spec/base/transport.md:7`）允許工具做 owner 的普通操作，所以工具可以 agent.submit 給自己，開出帶全新預算的新 run，一直循環下去。另外「誰可以投給誰」（methods.json 寫的是「可投該 agent 者」）也沒定義。
3. **登記改版時進行中的 run 怎麼辦**：B-302（`spec/base/identity-resources.md:15`）要求先排空再啟用新版。那進行中的 run 是暫停、失敗，還是換 UID 繼續？舊 UID 留下的檔案歸誰？都沒說。
4. **控制程序停機的時間要不要算進 max_elapsed_ms**（`spec/scheduling/llm.md:49`）：沒說清楚，重啟後可能一瞬間就判超時。
5. **維護 tick 由誰排、什麼時候觸發、要做什麼**：T-05、S-101 提到它，但沒有定義。

## 待裁定（10 條）

1. **（A 隊）任務途中的新訊息算哪一輪**（原文寫使用者尚未決定）：(a) 排到下一輪（spec 現在的預設）；(b) 併入目前這一輪的下一次 tick；(c) 交給 agent 判斷。**建議首版用 (a)**，並在 README 標明這是暫定。
2. **（A 隊）軟性原則和 spec 的硬規定要不要對齊**：使用者已經撤回「兩次 tick 之間不變」的硬保證，但 spec 仍有每輪固定版本（A-102）和登記改版先排空（B-302）兩條硬規定。(a) 維持硬規定，理由是可重現與恢復；(b) 一起放寬。**建議 (a)**，並在 between-ticks 筆記說明這兩件事是分開的。
3. **（A 隊）proto6 是新寫，還是在 proto5 上就地演進**：S-404 和 `plan/` 都假設要從 proto5 的 worker 後端遷移過來。(a) 新寫，S-404 的遷移段移到 plan；(b) 就地演進。**建議 (a)**，這也符合「舊 proto 另起、切開」的慣例。
4. **（A 隊）needs_attention 的出口**（見必修 1）：(a) resume 可以重新驗證非 unknown 的原因；(b) 一律取消、另開新輪。**建議 (a)**，否則連兩次壞回覆這種小事也得整輪重來。
5. **（B 隊）日常特權點是誰**：① 完整 root daemon 加 systemd 硬化加 MAC——本機 LSM 沒有 AppArmor／SELinux，要改 kernel 參數再重開機，被接管時波及面最大；② 極小的 root helper 服務，只做「查登記 → 建 leaf → 降權 → exec 固定 runner」，主 daemon 不是 root，用 SO_PEERCRED 認人，要寫的特權程式最少；③ systemd-run 經 polkit 開 transient unit——polkit 規則看不到 User=，daemon 可以要求以 root 開 unit，等於把 root 交出去；④ user namespace——日常不用宿主 root，但 project quota 仍要宿主 root 佈建，還多一層 UID 映射的維運。**建議預設②。**
6. **（B 隊）quota 逃脫怎麼處理**：用 seccomp 擋改 project ID，或接受 quota 只記帳。**建議 seccomp**，而且只在 launcher 裡裝一次。
7. **（B 隊）重啟語意**：work 分到獨立的 slice（控制端重啟不殺工作，但要能重新認領孤兒程序），或同一個 unit 接受重啟就殺光（簡單，但所有在途工作都變 unknown）。**建議先接受殺光**，把恢復測試改成「全部變 unknown」，第二版再分開。
8. **（B 隊）儲存 backend**：**建議 VM 裡用專用 XFS 卷**（pquota），ext4 之後再補。
9. **（astra）共享 LLM 排程要提供何種保證**：`notes/plan/llm-and-validation.md:29` 已提出兩路——① runner 持 key 直連，只管理遵循入口的呼叫；② broker 保管 aos 的 key 並代發，集中限制這些憑證的使用。**建議預設①**，先驗證受管路徑與等待理由；若要求工具不能繞過 aos 的帳戶預算，再選②。broker 仍不能保證攔住其他憑證的直連。
10. **（astra）多 agent 共寫同一外部 workspace，誰承擔衝突**：`notes/plan/linux-and-storage.md:70` 已分清容量歸屬，尚未定義並行寫入語意。選項是①由工具自行協調；②排程按宣告的 workspace 寫入範圍互斥；③每輪獨立副本，完成後合併。**建議預設①並明示不保證跨 agent 寫入一致性**；需要多人改同一專案時再採②或③，避免首版默默增加一套 workspace 交易系統。

## 機械檢查結果（C 隊）

C 隊對照 `notes/README.md`「完整來源對照」表宣稱的 15 份收錄與兩支位元組相同的探針程式，只讀檢查，六項全部通過或部分通過：

1. **忠實度（逐對 diff）：通過。** 15 對來源（13 份 Markdown＋2 支探針程式）逐一比對，扣掉「交接快照說明」「連結路徑改寫」「探針重跑路徑改寫」這三類必要調整後，**其他內容改動 0 處**——沒有任何字句、數字、結論被改寫或增刪。兩支探針程式 `notes/probes/run.py`、`notes/probes/landlock-canary.c` 與 proto5 原始檔案位元組相同。
2. **對照表完整性：通過。** 表格實際有 15 列，與宣稱一致；proto6/notes 下其餘非收錄檔案（`agent.md`、`base.md`、`concepts.md`、`scheduling.md`、`between-ticks-configuration.md`、`spec-gaps-review.md`、`spec-redundancy-review.md`、`investigations/README.md`）都是 proto6 自己的新草稿或索引，README 正文有點名連到，沒有誤標成收錄。proto5 與 wf 側的來源檔也沒有遺漏。
3. **連結：通過。** 全站掃描 `proto6/` 下 45 個 `.md` 檔的相對連結與錨點，0 個問題。`bash wf/tools/wf-lint.sh` 在 proto6 沒有任何壞連結，只有 3 條無害的風格提醒（條列內容建議轉資料檔，屬 AGENTS.md 鐵律 6 的候選，不是連結失效）：`notes/README.md:27-43`（來源對照表本身）、`notes/plan/README.md:13-18`、`notes/plan/llm-and-validation.md:69-74`。
4. **快照標頭：通過（15 份全部合格，2 份有無害的沿用瑕疵）。** 13 份收錄 Markdown 都有「交接快照／原始來源」說明並保留（重算過的）「←」導覽列。`notes/investigations/proto5-host-root-second-wall.md` 與 `notes/investigations/proto5-linux-wall-feasibility.md` 沒有「←」，但核對原始來源後確認這是沿用原本就沒有的結構，不是本次收錄新造成的缺漏。
5. **反向連結：部分通過，有一處措辭落差待確認。** `proto5/notes/README.md:7` 有交接說明連回 `proto6/notes/README.md`；`wf/INDEX.md:22` 也點名 `proto6/`。但 README 宣稱的「已收錄資料互連 proto6」，逐一檢查後發現 13 份被收錄的 proto5／wf 原始檔案本身，一份都沒有加回指向 proto6 的連結，只有上層的 `proto5/notes/README.md` 索引頁有連。這句話可能只是指「proto6 內部收錄檔彼此互連」（已驗證為真），也可能想講「proto5 原始檔案本身也連回 proto6」（未做到）。建議跟使用者確認這句話的原意。
6. **日期與名稱：通過。** 檔名日期與檔內標題、交接說明的日期一致；`spec/` 下 12 處連回 `../notes/...` 的連結目標檔案都存在。

## 機器查證結果（B 隊）

B 隊在本機（非 VM）做了唯讀探測，結果如下：

| 項目 | 結果 |
|---|---|
| kernel | 6.18.49-1-MANJARO，16 核，60 GiB |
| 根檔案系統 | `/dev/nvme0n1p5` ext4 `rw,relatime`，也就是 repo 所在；`/proc/fs/ext4` 顯示 `noquota` |
| quota 工具 | quota／quotaon／setquota 都沒裝；dumpe2fs 以非 root 執行被拒 |
| /tmp | tmpfs |
| cgroup | cgroup2，掛載選項有 nsdelegate、memory_recursiveprot；根控制器有 cpuset、cpu、io、memory、hugetlb、pids、rdma、misc、dmem |
| cgroup 委派 | user@1000.service 是 Delegate=yes，委派 cpu／memory／pids，目錄歸 lorkhan。非 root 可以在自己的 user manager 下建子 cgroup，但只管得到自己 UID 的程序，也沒有 io |
| LSM | capability、landlock、lockdown、yama、bpf（沒有 AppArmor／SELinux） |
| user namespace | unprivileged_userns_clone=1；subuid／subgid 為 lorkhan:100000:65536 |
| 探針 | `notes/probes/run.py` 退出 0，Landlock ABI=7，8 項全 PASS（denied 回 errno 13），runner 讀得到兩個 canary。跟 `notes/2026-09-28-linux-isolation-probes.md:24-33` 一致 |

**探針實際驗證了什麼**：只證明「非 root 程序能用 Landlock 擋新開檔的讀寫，fork 出來的子程序會繼承」。它沒有碰 UID、cgroup、quota 任何一軸，而計畫已經取消逐工具 bwrap，Landlock 只剩外牆候選 B 的一個零件。筆記自己也標了這個邊界。

**探針小瑕疵**：`notes/probes/run.py:28` 的 assert 如果失敗，JSON 不會印出來，失敗時看不到結果；筆記說「gcc 無警告」，但 run.py 沒有收集或檢查編譯輸出。

## 總評

**A 隊**：責任分區、spec 的契約，還有兩份既有審查（冗餘審查、遺漏審查），彼此大致一致，可以當首版實作的依據。但必修 1（needs_attention 出口）、以及「沒交代的邊緣狀況」裡的 tick 自我失敗、控制程序停機時間怎麼算、維護 tick 誰排，會讓實作者在「卡住以後怎麼恢復」和「怎麼重試」上被迫自己發明規則，應該先補。舊筆記的標示（必修 2、3、6）屬於閱讀誤導，順手修就行。

**B 隊**：方向和分工清楚，程式引用幾乎都查證屬實，也一再標明「未驗證」。最大的缺口在特權模型：日常切 UID 本身就要特權，project quota 擋不住擁有者，systemd 預設重啟會殺光工作，這三件讓第 2 階段現在無法定義完成。先裁定特權點，把第 2 階段拆成不含外牆和含外牆兩段，再統一階段編號，就可以動工。

**C 隊**：收錄忠實度、對照表完整性、連結、快照標頭、日期名稱五項全部通過，內容改動 0 處，壞連結 0 條。唯一值得使用者確認的落差是「已收錄資料互連 proto6」這句話的原意（proto6 內部互連 vs. proto5 原始檔案也連回來），這不是機械檢查能單獨判定對錯的問題。

**astra**：兩處必修（五分鐘到期時間、daemon 池式開檔描述）都是筆記對照程式碼時的用詞不夠精確，不影響先降權的結論。四條建議集中在巢狀委託、大 token 公平性、漏通知恢復指標（與 B 隊重複的 157 分鐘發現）、快照回退的副作用；兩條待裁定（LLM 直連 vs. broker、外部 workspace 並行寫入語意）都給了保守的首版建議，可以直接採用。

**綜合看**：四隊沒有發現互相矛盾的事實性錯誤，必修項目集中在兩類——spec 與筆記文字本身的內部矛盾（A 隊、astra 大半），以及計畫對 Linux 特權模型與資源邊界的樂觀假設（B 隊全部、astra 兩條）。C 隊確認了收錄工作本身沒有失真。建議在動工前先過一輪必修與待裁定，尤其是特權點與 needs_attention 出口這兩項會卡住其他設計。
