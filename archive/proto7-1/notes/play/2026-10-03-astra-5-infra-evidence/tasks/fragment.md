# Tasks／Q3 子報告

## I-04／I-05 回歸

| 原編號 | 本輪判定 | 重現、數據與證據 |
|---|---|---|
| I-04 | **部分修復：原腳本 task kill 通過；stop 自己仍漏收。** | astra-4 `tasks/probe.py` 只改 `/tmp/astra5-tasks-` 前綴。`fork.json`、`forksetsid.json` 都回 `already ended; 1 leftover process(es) killed`、孫程序不活、stop 無殘留。但移除 task kill 步驟後，`fork-stop-only.json`／`forksetsid-stop-only.json` 各殘留 1 孫程序，daemon 已 exit 0 且 stopped:true/live:[]。普通 fork 同 PGID、原 AOS7 環境仍在，已足以證明 Q1(a) 保證範圍內的 stop 缺口。 |
| I-05 | **本轮承諾的壞 birth／tock 隔離已修；刪 taskdir 仍可重現，但屬 Q1(a) 已接受例外。** | `birtharray.json`／`birthsyntax.json` 四輪正常 tick/tock，只保留 r1 活實例，無連起；`tockdirpeer.json` 每輪記單任務 `phase:tock.json/IsADirectoryError`，健康 `zzhealthy-r1/tock.json` 到 r4，summary 正常，stop 全收。`deletekeep.json` 仍連起 r1/r2/r3 三對 task/runner，stop 後 6 個活；全部由 finally 收掉。`delete.json` 仍留 2 個。需求 Q1(a) 明列刪 taskdir 自負，不把這兩案當新增違約／待決策。 |

其餘舊腳本 default 案例 `short`、`ignore`、`cpu`、`output`、`chdir`、`tocksyntax`、`tockdir` 均已重跑；除了明示刪目錄者，正常 stop 後無殘留。所有輸出保留在本目錄。`stop_only.py` 是原腳本的對照版，只拿掉 fork／forksetsid 的 task kill 步驟，檔名加 `-stop-only`。

## 新問題 A：stop 掃 live_tasks，主程序已結束的同群組後代仍漏收〔bug〕

**重現**：`python .../tasks/stop_only.py fork forksetsid`。fork 案主程序正常結束，不改環境、不刪 taskdir、不 setsid；睡 12 秒的孫程序仍在同 PGID。等 650 ms 後直接 SIGTERM daemon。對照是舊腳本先寫該任務 ctl kill 再 stop。

**看到**：普通 fork 的孫 PID 2340656、PGID 2340655 在 daemon 正常 exit 0 後仍活；status `stopped:true,kill_on_stop:true,nodes.n.live:[]`。setsid 對照也留 1 個。task ctl kill 對照均成功。這是判斷主程序 ended 後，stop 沒進修好的 kill_task 清殘留分支；`aos7_daemon_timeline.py:191` 只掃 `live_tasks`，不是 kill_group 本身能力不足。Q1(a) 已允諾程序群組／相符環境，普通 fork 不屬故意脫離例外，無須重問資源域決策。

**最簡單對策〔技術選型〕**：stop 在每個已接管 node 做一次和 Q4 同範圍的程序／環境收尾（要避開 daemon 自己與祖先），不能只從 live_tasks 取得入口；或逐一掃含已結束的任務，但還要涵蓋已搬到 tasks-old 的普通後代。不要求 subreaper/cgroup。停機回條不能把 direct-task live=[] 当整個保證範圍已清空。

**S-**：S-03、S-06、S-10、S-17；N-09、N-25。證據 `fork-stop-only.json`、`forksetsid-stop-only.json`；對照 `fork.json`、`forksetsid.json`。

## 新問題 B：Q3 rename 與讀者沒有協定，前任狀態／用量可以瞬間被讀成不存在〔bug〕

**重現**：`python .../tasks/archive_probe.py`。fixture 建一個已結束 worker-r1，ended round=1、usage=1234、agent state=act/r2/steps9/pc4、kernel-state 有 sentinel；r3、keep_ended_rounds=0，另有 worker-r3。只對 reader 的 read_json 開檔前加入一次 barrier，呼叫**獨立程序的原版 aos7-tock**完成真實 rename，再放行原讀取；無替換回傳值、無改產品。分別在 agent state、kernel state、kernel usage 的舊路徑開檔前觸發。這是固定住允許的並行順序，不是實測自然發生率；kernel／agent 僅作通用檔案讀者探針，沒有呼叫 LLM。

**看到**：

| 讀者 | 搬家前／後控制組 | 搬家穿插讀取時 |
|---|---|---|
| agent.load_state | 都接到 worker-r1，act/r2/steps9/pc4 | 回 fresh idle/r0/steps0/from:null |
| kernel.load_state | 都接到 worker-r1、sentinel=inherited-state | 回 empty_state，usage／paused／issued 全空 |
| snapshot_node | usage_total=1234、worker-r1 alive:false | usage_total=0、已結束 worker-r1 反而 alive:true；下一次讀回 1234 |

原因是 `task_dirs_of` 回傳兩處的**路徑清單**，不是讀取快照；之後 tock 在 `aos7_tock.py:58` rename，持有舊 pathname 的 reader 遇 ENOENT，就當無狀態／零用量。兩處都找只解決搬完後的靜態查詢，沒有解決讀到一半搬家。用量下降再回升可能干擾 cap/budget 決策，這屬程式路徑推論；本探針直接量到的是 1234→0→1234 與活性誤判，未宣稱跑出實際調度命令。

**對策〔技術選型〕**：給歷史任務穩定的讀取協定，例如開 directory fd 後用 openat 讀整個任務，或遇舊路徑消失按 tid 在兩處重新定位並重讀整個快照／明示 unknown。只再呼叫 find_task_dir 仍有第二次 rename 的 TOCTOU，要配合 retry／目錄 fd。snapshot 可有版本並重試，不能把搬家中缺檔無條件折算成零。archive 不必改成保留原地，也不要求改核心語意。

**正面對照**：已先 open 的 state.json fd 在 rename 後仍可正常讀出 act/r2/steps9/pc4 (`already-open-fd-archive.json`)；不是檔案資料被刪除。

**S-**：S-01、S-06、S-17、S-19（後兩者為探針顯示後果，不把 kernel/agent 重寫列為目標）。N-40 應從「已做」改為「部分：搬移與縮工作集已做，讀者一致性未做」；補需求「由基礎設施搬移歷史任務時，持有 tid 的正常讀者不會把存在的資料誤判為沒有；能定位／重試或明示不完整」。證據 `agent-archive.json`、`kernel-archive.json`、`usage-archive.json`、`archive_probe.py`。

## tasks-old 撞號：正常分配通過；異常匯入不覆蓋

`archive_probe.py` 的 collision 案先把 worker-r1 正常歸檔，再呼叫原版 new_tid(node,"worker",1)，得到 `worker-r1-2`，證明 allocation 同查 tasks 與 tasks-old。另手動把同 tid 匯回 tasks 製造非正常 restore 衝突（舊 usage1234、新 usage5678），tock 回 errors `phase:scan,OSError(39,'Directory not empty')`，兩份 usage 都還在，健康 worker-r3 收到 tock，沒有覆寫／連坐；此案沒有正常 tick 自己造出同號的證據。原衝突留在 active，後續會重試；若未來支援匯入／restore，再補衝突修復工具屬技術選型，不列目前核心語意未決。證據 `archive-collision-archive.json`。

## 需求清單建議

- N-40 改「部分」，追加穩定歷史讀取／搬家一致性驗收；必要優先度維持，因常態 tock 自己觸發會影響上層狀態接續與用量。
- N-25 已接受 Q1(a) 不重開資源域決策；但把「stop 對主程序已 ended 的普通後代也履行保證範圍」列必要驗收。不是新增全子孫保證。N-09 維持必要且部分，stopped/live=[] 仍不能證實範圍內全收乾淨。
- N-21 在原 I-05 birtharray/birthsyntax/tockdirpeer 驗收中通過；不要因已明示接受的 deletekeep 例外而把這部分重新判 bug。

所有 live probe 都自建 subreaper，只收自己的 AOS7_ROOT；finally SIGKILL own 殘留、reap 再刪 /tmp/astra5-tasks-*，不碰其他工作程序。archive probe 無長駐程序，toсk subprocess 有 5 秒上限並 wait。最終清理核對另見 cleanup.json。
