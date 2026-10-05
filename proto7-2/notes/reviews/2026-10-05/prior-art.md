proto7-2 已具備小型監督器與狀態調和迴圈的骨架；最值得借用成熟系統的，是身分、恢復、停止與證據保存的明確契約，並把重試政策、子監督樹及工作流語意維持在模組層。

# proto7-2 與成熟系統的唯讀比較報告

## 1. 審查範圍與證據強度

審查日期：2026-10-05。開始及結束時，repo HEAD 都是：

```text
6daebe2ef8227021745def649f4e3d86a3a8038c
```

先讀了 `AGENTS.md`、三軸狀態、工作流入口，以及指定的 `proto7-2/README.md`、`spec.md`、`modules/README.md`、`notes/problems.md`、`notes/play/README.md`，再定點核對核心與相關模組原始碼。另由六條平行審查線分別比較各系統、核驗保證邊界，最後做交叉檢查。

**全程沒有修改檔案、commit、push、執行測試、啟動 daemon 或執行故障探針。** 文中提到的測試都是閱讀既有程式，不能解讀成本輪重新測過。

比較以既有知識建立；容易混淆的外部機制，另以官方文件或官方原始碼做少量唯讀核對。以下分成：

- **已核對**：目前 repo 的規格、原始碼，或附連結的官方資料。
- **靜態推論**：由程式次序推導的情境，沒有動態重現。
- **記憶／版本未核對**：明確標示，不當成部署保證。

文中本地路徑皆位於 `/home/guanyu/projs/aos/`。歷史筆記保留了早期設計，判斷現況時以目前規格及程式為準；例如舊版核心 `retry_lost`、`ctl-seen` 的敘述，不能直接套到精簡後模組。

## 2. 先確定 proto7-2 現在承諾什麼

| 問題 | 現有設計與保證範圍 | 本地證據 |
|---|---|---|
| 雙開 | root 的 `daemon.lock` 擋第二個 daemon；node 的 `action.lock` 與 `gen` 協調 tick／tock；槽只有確定空或結束才起新 run。這三層保護各有對象。 | [aos7_daemon.py](../../../lib/aos7_daemon.py):558、[aos7_fs.py](../../../lib/aos7_fs.py):260、[spec.md](../../../spec.md):214 |
| 程序身分 | `PID＋starttime` 核對程序；`NODE＋TID＋RUN` 找同次執行的殘留；`slot#run` 區分可重用槽中的各次執行。 | [aos7_proc.py](../../../lib/aos7_proc.py):54、[aos7_proc.py](../../../lib/aos7_proc.py):122、[spec.md](../../../spec.md):209 |
| 崩潰後接回 | daemon 重起先收未關回合；活著的 runner 或任務繼續被認作活；tock 已提交總結時重播收尾。任務內部的工作進度由任務或 pack 保存。 | [spec.md](../../../spec.md):51、[aos7_task.py](../../../lib/aos7_task.py):93、[aos7_tock.py](../../../lib/aos7_tock.py):58 |
| 未知狀態 | 不存在與讀不到分開；不知道時保留現狀。依證據歸屬，停整個 node、單槽或單請求。 | [spec.md](../../../spec.md):9、[diag/README.md](../../../modules/diag/README.md):39 |
| 歷史保存 | 核心保留最近一次；history 是可能漏資料的取樣任務。工作包可另存自己的結果、帳與恢復證據。 | [spec.md](../../../spec.md):21、[modules/README.md](../../../modules/README.md):26、[budget/README.md](../../../packs/budget/README.md):16 |
| 子監督樹 | subd 管所有權、停止標記及重開前回收。父 kill 成功不代表子空間已空；新代啟動前才要求前代已收乾淨。 | [subd/README.md](../../../modules/subd/README.md):19、[subd/README.md](../../../modules/subd/README.md):75 |

這些保證以**合作式、本機檔案協議**為前提。換 uid、讓環境身分不可讀、故意脫離程序身分等，已有明確排除；本報告不把這些既定排除重新列為漏洞。[spec.md](../../../spec.md):279

另外，「恢復」至少有四種不同意思，後面的比較都依此區分：

1. 重起管理程序。
2. 重新辨認仍活著的工作。
3. 從已保存的工作進度繼續。
4. 查清外部效果是否已發生，避免重複執行。

proto7-2 核心主要處理前兩種，`step` 處理第三種，`budget` 的可查回假後端示範第四種。證據分別是 [aos7_task.py](../../../lib/aos7_task.py):73、[step/spec.md](../../../packs/step/spec.md):75、[budget/spec.md](../../../packs/budget/spec.md):55。

## 3. systemd：借執行身分、就緒與停止範圍

| 問題 | systemd 怎麼處理 |
|---|---|
| 雙開 | 同一 manager 內，同一 unit 由狀態機協調啟停；不同 unit 或 template instance 仍可跑同一個 executable。因此單例範圍是 unit。重起另外受 `Restart=`、間隔及啟動頻率限制控制。[unit 實作](https://raw.githubusercontent.com/systemd/systemd/main/src/core/unit.c)、[unit 設定](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.unit.xml) |
| 程序身分 | unit 名、每次執行的 invocation ID、主 PID、所屬 cgroup 分別回答不同問題。近期實作也會在核心支援時使用 pidfd。cgroup 提供程序集合，不能簡化成一份 pidfile。[PidRef](https://raw.githubusercontent.com/systemd/systemd/main/src/basic/pidref.h)、[journal 身分欄位](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.journal-fields.xml) |
| 崩潰後接回 | `daemon-reexec` 有先序列化、重新執行、再還原的交接流程。這個機制不能直接證明任意管理者崩潰後都能重建原來的等待關係與退出結果。[systemctl 定義](https://raw.githubusercontent.com/systemd/systemd/main/man/systemctl.xml) |
| 未知狀態 | 分開載入狀態、活動狀態、細部狀態與結果；設定讀取失敗不等於舊服務已死。主 PID 推測也有能力限制。它沒有一份可直接等同 proto7-2「所有讀不到都保留現狀」的通用契約。[D-Bus 狀態](https://raw.githubusercontent.com/systemd/systemd/main/man/org.freedesktop.systemd1.xml)、[service 定義](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.service.xml) |
| 歷史保存 | journald 可用暫存或持久儲存，並提供輪替、容量及速率限制。它是觀測日誌；保存設定與丟棄政策仍影響完整性。[journald 設定](https://raw.githubusercontent.com/systemd/systemd/main/man/journald.conf.xml) |
| 子監督樹 | cgroup、`KillMode=` 及 delegation 定義程序集合與管理權。停止整個集合的能力強於只對一個 PID 送訊號；具體保證仍取決於設定與程序是否留在受管範圍。[KillMode](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.kill.xml)、[cgroup delegation](https://systemd.io/CGROUP_DELEGATION/) |

**適合借的做法**

最直接的是區分「已啟動」「還活著」「已就緒」。systemd 的 `Type=exec` 只確認執行程式成功，`Type=notify` 才等待應用宣告 `READY=1`。proto7-2 的 `LIVE` 也可能只代表 runner 尚活、剛起或身分暫時讀不到，不能當成服務已可接單。[service type](https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.service.xml)、[aos7_task.py](../../../lib/aos7_task.py):93

若上層需要 readiness，可由任務保存帶**本次 run 身分**的 JSON 就緒證據，讓依賴者或工具讀取。要帶 run，因為任務自己的檔案會跨槽重用保留，舊的就緒檔可能還在。[spec.md](../../../spec.md):195

另一個可借重點是：回條說清楚完成範圍。daemon 接受 stop、主程序消失、受管程序集合清空，應各有不同證據。proto7-2 已部分做到，值得維持。[component-contracts.md](../../component-contracts.md):97、[subd/README.md](../../../modules/subd/README.md):22

**不適合直接搬入**

PID1、完整 unit 相依引擎、D-Bus job 管理與 cgroup 管理權，會明顯擴大核心責任。JSON／文字介面並不排斥底下使用 OS 原語，但目前 cgroup 已在範圍外；若日後需要更強程序收容，應把它視為有不同前置條件的選用後端。[spec.md](../../../spec.md):290

## 4. supervisord：借簡明生命週期與有界重試

| 問題 | supervisord 怎麼處理 |
|---|---|
| 雙開 | 對同一個受管 process 項目，以記憶體狀態拒絕重複 start；`numprocs` 也可明確多開。這不構成同一 executable 的全域互斥。[RPC 實作](https://raw.githubusercontent.com/Supervisor/supervisor/main/supervisor/rpcinterface.py)、[設定](https://supervisord.org/configuration.html) |
| 程序身分 | 直接建立子程序，保存 PID 與 process 物件的關聯，用 `SIGCHLD`／`waitpid` 得到結果；受管程式應留在前景。[Subprocesses](https://supervisord.org/subprocess.html) |
| 崩潰後接回 | 正常 HUP 會停止受管程序、重讀設定再啟動。新 daemon 的 process 表重新建立。**靜態推論**：硬死後沒有 proto7-2 這種持久證據重新認領流程；若外層未清孤兒，舊程序可能與新 autostart 重疊。[signals](https://supervisord.org/running.html#signals)、[supervisord.py](https://raw.githubusercontent.com/Supervisor/supervisor/main/supervisor/supervisord.py) |
| 未知狀態 | `STARTING`、`RUNNING`、`BACKOFF`、`FATAL` 等是生命週期狀態。其 `UNKNOWN` 官方定義為程式錯誤，與 proto7-2 的「資訊不足」不同；`startsecs` 也只代表存活一段時間。[Process States](https://supervisord.org/subprocess.html#process-states) |
| 歷史保存 | activity log 與 stdout／stderr log 可輪替；eventlistener 有確認與重送流程，但緩衝區滿了可以丟事件，不能當持久事件帳。[Logging](https://supervisord.org/logging.html)、[Events](https://supervisord.org/events.html) |
| 子監督樹 | group 提供管理群組；`stopasgroup`／`killasgroup` 可作用於 Unix process group。它不等同遞迴程序收容或完整子監督器恢復樹。[設定](https://supervisord.org/configuration.html) |

**適合借的做法**

把「起不來」「起來後很快死掉」「跑一段時間後死掉」「重試太多而停手」分開呈現。對 LLM 而言，這比只看到連續的非零退出码更容易判斷下一步。

proto7-2 的 `keep` 現在補空槽，restart policy 尚列為之後再說；若需求出現，有界重試與退避適合放在包裝器或政策模組。[spec.md](../../../spec.md):137、[spec.md](../../../spec.md):294

但要收窄保證：**包裝器能限制它放行的實際工作，不能阻止核心繼續啟動包裝器本身。** 若只由取樣任務讀最近一回合來計失敗次數，又可能漏算。需要精確額度時，必須由放行工作的一方保存自己的證據；先記額度再啟動，也要接受中斷時「記了一次、實際尚未啟動」的窗口。[aos7_tick.py](../../../lib/aos7_tick.py):184、[modules/README.md](../../../modules/README.md):30

**不適合直接搬入**

不能用 supervisord 的直接父子程序模型取代 proto7-2 的跨 daemon 重啟證據鏈，也不能把其 `UNKNOWN` 名稱移來便宣稱具有相同三態語意。

## 5. runit／s6：借小程序分工與服務存活期的排他

兩者很接近 proto7-2 的「小組件、資料夾、工具組合」方向，但機制不能混為一談。

| 問題 | runit | s6 |
|---|---|---|
| 雙開 | 同一 service directory 拒絕第二個 `runsv`。[runsv](https://smarden.org/runit/runsv.8) | 同一 service 拒絕第二個 supervisor；現行文件另有可選 `lock-fd`，讓舊服務仍活時，新服務等待鎖。[service directory](https://skarnet.org/software/s6/servicedir.html) |
| 程序身分 | service directory 是邏輯名稱，`runsv` 直接管理自己起的程序。 | service directory 是名稱，supervisor 以父子關係掌握程序；控制端不必自行猜 pidfile。[overview](https://skarnet.org/software/s6/overview.html) |
| 崩潰後接回 | `runsvdir` 重起死掉的 `runsv`。手冊未承諾重新領養活孤兒；舊服務可能重疊是依模型的推論。[runsvdir](https://smarden.org/runit/runsvdir.8) | `s6-svscan` 重起 supervisor；`lock-fd` 能擋新副本，但不等於接回舊服務的等待及退出碼關係。[svscan](https://skarnet.org/software/s6/s6-svscan.html)、[lock-fd](https://skarnet.org/software/s6/servicedir.html) |
| 未知狀態 | 查詢或控制失敗、等待逾時，不能一律當成服務已死。[sv](https://smarden.org/runit/sv.8) | 查詢會區分 supervisor 不在與系統呼叫失敗，也分 up／ready。[svstat](https://skarnet.org/software/s6/s6-svstat.html) |
| 歷史保存 | 現況由 supervision status 表示；輸出可交獨立 `svlogd` 保存輪替。[svlogd](https://smarden.org/runit/svlogd.8) | 有界 death tally 與 `s6-log` 各負責死亡資訊及輸出歷史，不是完整業務帳。[svdt](https://skarnet.org/software/s6/s6-svdt.html)、[s6-log](https://skarnet.org/software/s6/s6-log.html) |
| 子監督樹 | 可組巢狀 `runsvdir`，但訊號與收尾需明確安排；TERM 與 HUP 的行為不同。[runsvdir](https://smarden.org/runit/runsvdir.8) | svscan 可作根或分支，正常停止有服務與 logger 的協調；強殺後殘留仍是另一個問題。s6 與 s6-rc 的相依管理也需區分。[svscan](https://skarnet.org/software/s6/s6-svscan.html) |

**適合借的做法**

s6 的 `lock-fd` 提醒了一件重要的事：**排他證據最好能活得跟真正工作一樣久。** 如果只是外層 wrapper 持鎖，wrapper 死了、工作還活著，鎖便無法防止重疊。因此不能把「加一層 flock 包裝」直接寫成完成解法。

proto7-2 的 runner 已是小型監督者，負責等待任務、寫 exit；外層 tick 不等待。這種分工值得保留。[aos7_run.py](../../../lib/aos7_run.py):75、[spec.md](../../../spec.md):161

但 runner 若死掉，不能靠再起一個程序補回原本的 `wait()` 結果。現有的 lost／unknown 正是在誠實表達這個邊界。[aos7_task.py](../../../lib/aos7_task.py):118

**不適合直接搬入**

runit／s6 的二進位 status、FIFO 控制字元，不適合直接成為 LLM 的主要操作協議。可借其責任切分，對外仍維持 JSON／文字。

**版本注意**：s6 `lock-fd` 已核對現行官方文件，但首次引入版本未核對；不能假定舊版都有。runit 的孤兒重疊敘述是架構推論，未實跑特定發行版。

## 6. Erlang／OTP supervisor：借失敗範圍與重啟預算

| 問題 | OTP 怎麼處理 |
|---|---|
| 雙開 | 同一 supervisor 的 child ID 識別子項；登記名稱另有其唯一性範圍。這不是任意 VM 或 OS 程式的全域單例。[supervisor](https://www.erlang.org/doc/apps/stdlib/supervisor.html) |
| 程序身分 | child ID 是子項規格身分，BEAM PID 是這次程序實例。BEAM process 與 Linux process 是不同層次。[supervisor](https://www.erlang.org/doc/apps/stdlib/supervisor.html) |
| 崩潰後接回 | 通常依 child spec 重建程序。應用工作狀態仍需自行恢復；supervisor 重建也不會自動保留先前動態加入的全部 child specs。[監督原則](https://www.erlang.org/doc/system/sup_princ.html) |
| 未知狀態 | 同一 BEAM 的 link／monitor 有執行期提供的終止資訊；跨 node 的 `noconnection` 只證明連線失去，不能證明遠端程序死亡。[Processes](https://www.erlang.org/doc/system/ref_man_processes.html) |
| 歷史保存 | child 表與 restart 計數是監督狀態；完整業務歷史不由 supervisor 自動提供。Logger 的保存取決於 handler。[Logger](https://www.erlang.org/docs/26/man/logger.html) |
| 子監督樹 | 原生支援 supervisor 的孩子也是 supervisor；`one_for_one`、`one_for_all`、`rest_for_one` 明示故障影響範圍，restart intensity 避免無限重啟。[監督原則](https://www.erlang.org/doc/system/sup_princ.html) |

**最直接對上 proto7-2 的教訓，是子樹停止時間。**

OTP 官方特別警告：子 supervisor 若只有有限 shutdown timeout，可能在尚未收完孩子時被強制終止。這與 proto7-2 的父 kill 一秒寬限、子 daemon 需要逐槽收尾，屬於同類問題。[supervisor shutdown](https://www.erlang.org/doc/apps/stdlib/supervisor.html)、[subd/README.md](../../../modules/subd/README.md):49

proto7-2 已採取明確折衷：正常停止先嘗試收；未收完的，在下次啟動 subd 包前回收。父不再啟動該包時，殘留可以繼續存在。這是既定契約，不能省略。[subd/README.md](../../../modules/subd/README.md):53、[subd/README.md](../../../modules/subd/README.md):75

**適合借的做法**

- 明示「哪個失敗只重起自己，哪個失敗需要連帶重起一組」。
- 為重起保存有界預算、退避原因與停止條件。
- 父結束時，明確選擇保留孩子、要求孩子停止，或等待確認清空。

這些都是上層政策，適合由 subd 或任務包描述。現有核心不必知道「團隊」「服務群組」等應用概念。[modules/README.md](../../../modules/README.md):5

**不適合直接搬入**

不能把所有 node 強制改成 OTP 的連帶重啟樹，也不宜直接把 shutdown 改成無限等待。前者改變故障範圍，後者可能讓整個停止流程永久等候。

另外，OTP 管外部 OS 程式時仍有邊界：port 關閉後，外部程式是否退出，取決於它如何處理通道關閉。BEAM 監督樹的保證不能直接外推成全部 OS 子孫都被收掉。[Ports](https://www.erlang.org/doc/system/ports.html)

## 7. Kubernetes controller／reconcile：借重新觀測與版本分工

「調和」的意思是：反覆比較希望的狀態與實際觀測，逐步把差距補上。

| 問題 | Kubernetes 怎麼處理 |
|---|---|
| 雙開 | controller 可用 Lease 選主，但 client-go 明說選主本身不保證 fencing，也就是不能保證舊主控已停止造成效果。Job 即使設定只要一份工作，程式仍可能啟動兩次。[leader election](https://raw.githubusercontent.com/kubernetes/client-go/master/tools/leaderelection/leaderelection.go)、[Job 失敗處理](https://kubernetes.io/docs/concepts/workloads/controllers/job/#handling-pod-and-container-failures) |
| 程序身分 | UID 識別某次建立的 API 物件；同名重建有新 UID。Pod UID、container 的一次執行與 Linux PID 也不是同一件事。[UID](https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#uids)、[Pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) |
| 崩潰後接回 | controller 重起後重新讀取 desired state 與目前狀態，繼續調和；通常不需要逐一重演漏掉的所有變動。[Controllers](https://kubernetes.io/docs/concepts/architecture/controller/) |
| 未知狀態 | Conditions 可表達 True／False／Unknown；`observedGeneration` 表示觀測過哪代意圖，仍需另看結果是否達成。[Condition 定義](https://raw.githubusercontent.com/kubernetes/apimachinery/master/pkg/apis/meta/v1/types.go) |
| 歷史保存 | watch 有有限保留窗口；版本太舊時需重新 list／watch。這是恢復現況觀測的機制，並非永久事件歷史。[API watch](https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-changes) |
| 子監督樹 | ownerReference 與 GC 管 API 物件的所有權、刪除關係。物件刪除順序不等於父程序死後所有子程序立即消失。[Owners](https://kubernetes.io/docs/concepts/overview/working-with-objects/owners-dependents/)、[GC](https://kubernetes.io/docs/concepts/architecture/garbage-collection/) |

**最值得借的是把四種身分與版本分開。**

| 概念 | 回答的問題 | proto7-2 的對照 |
|---|---|---|
| 物件 UID | 是不是同一次建立的對象？ | 目前 node 路徑沒有持久的建立代次身分。 |
| 內容版本 | 我修改時所根據的內容是否仍是目前版本？ | `tasks.json.lock` 負責互斥；`tasks_rev` 只是內容 hash。 |
| 意圖世代 | 希望的設定是哪一版？ | 沒有直接等價欄位；daemon `gen` 不是這個意思。 |
| 觀測版本 | 這份結果看過哪一版意圖？ | `tasks_rev` 有部分對照用途，但不代表活任務已採用設定。 |

Kubernetes 欄位的官方定義見 [ObjectMeta](https://raw.githubusercontent.com/kubernetes/apimachinery/master/pkg/apis/meta/v1/types.go) 與 [條件更新](https://kubernetes.io/docs/reference/using-api/api-concepts/#updates-to-existing-resources)。

**具體發現：表改了，不代表活著的 keep 已換設定。**

假設 keep 正在跑 argv A，使用者把表改成 argv B。下回合可以讀到新的 `tasks_rev`，但槽仍活著，因此不會換成 B。另一方面，daemon 重起會增加 `gen`，即使任務設定完全未改。

這是現有行為，不是自動 rollout 缺陷；需要確認設定生效的上層，應比對本次 birth／自己的生效證據。[aos7_tick.py](../../../lib/aos7_tick.py):25、[aos7_tick.py](../../../lib/aos7_tick.py):184、[aos7_daemon.py](../../../lib/aos7_daemon.py):578

**另一個可借點：同址重建要有辦法辨認。**

靜態推論：外部 history 已記某來源到 round 100；來源在同一路徑重建並從 1 開始。現有 history 以 node id 記 `seen`，會略過所有 `round <= 100` 的資料，到 101 才繼續。這是目前去重身分的限制，未動態重現。[history.py](../../../modules/history.py):64

若上層需要辨認這種重建，可由發布者協議保存建立代次身分，再以「來源代次＋序號」判斷。代次應在真正重建時更換，普通 daemon 重起則沿用。

**不適合直接搬入**

API server、etcd、跨機選主、完整 ownerReference／finalizer 圖，都超出目前單機最小核心。可借「重新觀測現況」，但必須逐筆處理的付款、交付意圖，不能合併成最新值。

## 8. cron／anacron：借日曆排程與漏期政策

本節具體實作以 Cronie 為核對對象；其他 cron 的校時、DST、補跑行為可能不同。

| 問題 | cron | anacron |
|---|---|---|
| 雙開 | daemon 有自身排他；一般 job 沒有跨排程時刻的執行互斥，上一份沒結束仍可能派下一份。[cron.c](https://raw.githubusercontent.com/cronie-crond/cronie/master/src/cron.c)、[job.c](https://raw.githubusercontent.com/cronie-crond/cronie/master/src/job.c) | 同 spool／job identifier 的 active job 有鎖，避免正常運行中的多個 anacron 同時執行它。[anacron.8](https://raw.githubusercontent.com/cronie-crond/cronie/master/man/anacron.8) |
| 程序身分 | 排程項目與當次 child PID。 | job identifier 對應日期紀錄；當次另追 child PID。[runjob.c](https://raw.githubusercontent.com/cronie-crond/cronie/master/anacron/runjob.c) |
| 崩潰後接回 | 重讀排程繼續匹配時間；一般不恢復舊工作的內部進度。 | 看最近日期，逾期補做一次；漏 N 天不代表重播 N 份工作。[anacron.8](https://raw.githubusercontent.com/cronie-crond/cronie/master/man/anacron.8) |
| 未知狀態 | 沒有持久的「效果可能已發生，等查證」工作協議。 | 日期與啟動錯誤不能回答業務是否已完成；不是 proto7-2 的三態仲裁。[lock.c](https://raw.githubusercontent.com/cronie-crond/cronie/master/anacron/lock.c) |
| 歷史保存 | 輸出郵件、syslog 等交給外部保存。 | 最近執行日期加上日誌，不是成功結果史。[cron.8](https://github.com/cronie-crond/cronie/blob/master/man/cron.8)、[anacron.8](https://raw.githubusercontent.com/cronie-crond/cronie/master/man/anacron.8) |
| 子監督樹 | 啟動程式，沒有服務重啟監督樹。 | 串行選項管工作順序，不構成子監督樹。 |

**適合借的做法**

把三個問題分開：

- 現在是否到了應執行的期間？
- 上次漏掉的期間要跳過、合併補一次，還是逐期補做？
- 某一期工作是否真正完成？

如果未來需要每天結算或每週備份，可由排程任務保存期間識別及完成證據，再透過 once 派工。日曆與時區規則留在該任務，不必進 tick。

**proto7-2 的回合數不是日曆時間。**

`each` 沒空槽時只留下 `skipped`，沒有待補佇列。因此「不丟回合」不表示每一回合都會執行一份 each 工作。[aos7_tick.py](../../../lib/aos7_tick.py):184

同理，step 的 patience 用本 node 回合；adapt 的 `max_age` 用來源回合。來源 pause 時，來源年齡不增加；需要偵測來源停住時，可看 adapt 的 `stall`，不能直接把 `max_age` 當成秒數。[step/spec.md](../../../packs/step/spec.md):83、[adapt/spec.md](../../../packs/adapt/spec.md):48

**不適合直接搬入**

anacron 的「本期已跑」不等於成功。Cronie 的實作在 job 結束時先更新 timestamp，再處理退出狀態；非零退出仍會更新日期。這適合其排程角色，不能拿來當 step 的成功回條。[runjob.c](https://raw.githubusercontent.com/cronie-crond/cronie/master/anacron/runjob.c)

另有一處文字需精確化：`spec.md:30` 說 tick 之後等滿 interval，但實作在 tick 前取 `t0`，等待到 `t0＋interval`。tick 本身會消耗這段間隔。這是靜態讀碼差異，未實跑，不在本輪直接定為 bug。[spec.md](../../../spec.md):30、[aos7_daemon_timeline.py](../../../lib/aos7_daemon_timeline.py):215

## 9. Temporal／durable workflow：借流程、嘗試與效果的分離

| 問題 | Temporal 怎麼處理 |
|---|---|
| 雙開 | 同 Namespace、Workflow ID 同時只有一個 open 邏輯執行；Activity 仍可能重試或重複造成效果。邏輯工作單例不等於每段程式只執行一次。[Workflow ID](https://docs.temporal.io/workflow-execution/workflowid-runid)、[Activity 冪等性](https://docs.temporal.io/activity-definition#idempotency) |
| 程序身分 | Workflow ID、Run ID、Activity ID、Task Token 分別識別不同層級；worker PID 不是業務身分。[識別](https://docs.temporal.io/workflow-execution/workflowid-runid)、[Activity execution](https://docs.temporal.io/activity-execution) |
| 崩潰後接回 | Workflow worker 由已保存事件重播確定性程式；已記錄的 Activity 結果可直接恢復。未回報完成的 Activity 可能重新執行。[Tasks](https://docs.temporal.io/tasks) |
| 未知狀態 | timeout 只表示期限內未取得完成證據；效果可能已發生、回報卻遺失。外部 API 的去重仍需應用處理。[Activity 冪等性](https://docs.temporal.io/activity-definition#idempotency) |
| 歷史保存 | Event History 是恢復來源；完成的執行另受保存期管理。Continue-As-New 可帶必要狀態，以新 Run ID 開新歷史。[Event History](https://docs.temporal.io/encyclopedia/event-history)、[Continue-As-New](https://docs.temporal.io/workflow-execution/continue-as-new)、[Retention](https://docs.temporal.io/temporal-service/temporal-server#what-is-a-retention-period) |
| 子監督樹 | Child Workflow 是邏輯父子關係；父關閉政策可要求 terminate、cancel 或 abandon。worker 死亡不等於父 Workflow 關閉，也不等於 OS 子程序樹清空。[Parent Close Policy](https://docs.temporal.io/parent-close-policy)、[Activity cancellation](https://docs.temporal.io/activity-execution#cancellation) |

**proto7-2 已有值得維持的對應。**

`step` 分開：

- `inst`：這次工作。
- `request`：這次邏輯操作，重送時沿用。
- `attempt`：第幾次派工。
- `slot#run`：實際執行它的核心程序代次。

`budget` 再以 `K = (budget, holder, request)` 去重，沒有把 attempt 或 run 當成新扣款。這是很重要的分工。[step/spec.md](../../../packs/step/spec.md):56、[budget/README.md](../../../packs/budget/README.md):42

`step` 的接續方式是**明示 checkpoint**：保存 frame，讀取槽外結果，依證據續走。它不需要實作完整的確定性程式重播，也因此比較符合 JSON／文字可讀的目標。[step/spec.md](../../../packs/step/spec.md):75

**適合借的做法**

意圖先記、重送沿用業務身分、效果與去重證據由效果擁有者一起提交、取消與完成分開、證據保存期涵蓋重送期。

其中 `budget` 已做出示範：假後端把 K 的效果與受理計數同次提交，因此回條遺失後仍可查回。這份保證只適用於該可查回、按 K 去重的後端。[budget/spec.md](../../../packs/budget/spec.md):68、[budget/README.md](../../../packs/budget/README.md):39

**不適合直接搬入**

完整 Event History、SDK replay、工作流程式版本演進與服務端調度，是另一套系統責任。現在的 checkpoint 若能满足需求，就沒有必要為了名稱上的 durable workflow 把它們搬入核心。

也不能把 `idempotent: true` 當成系統自動提供的能力；它是作者對工作行為的承諾。接真實 API 時，穩定 request 必須能傳到效果端，並有相應去重或查詢契約。[step/spec.md](../../../packs/step/spec.md):84、[budget/README.md](../../../packs/budget/README.md):40

## 10. Make 類增量建置：借產物有效性與明示相依

| 問題 | GNU Make 怎麼處理 |
|---|---|
| 雙開 | 一次 make 推導內共用一般 target 的建置結果；`-j` 管並行量。**記憶、高信心但未逐版核對**：兩個獨立 make 不提供通用的輸出目錄全域互斥。[Parallel](https://www.gnu.org/software/make/manual/html_node/Parallel.html) |
| 程序身分 | 核心識別是 target／檔案路徑，PID 只是當次 recipe 的執行狀態。它沒有 proto7-2 的持久 run 認領協議。 |
| 崩潰後接回 | 重新執行時重算相依與新舊，重建需要的產物；不是接回原程序。SIGKILL 等仍可能留下時間較新卻不完整的 target。[Interrupts](https://www.gnu.org/software/make/manual/html_node/Interrupts.html) |
| 未知狀態 | recipe 失敗會影響 build 結果；但產物存在且 mtime 較新，未必代表內容正確。沒有通用的持久 unknown 仲裁層。[Errors](https://www.gnu.org/software/make/manual/html_node/Errors.html) |
| 歷史保存 | 一般保存的是目前產物及必要建置資訊，不是每次執行的完整歷史。此為架構層級比較。 |
| 子監督樹 | recursive make／jobserver 管子建置與並行額度；相依圖描述推導順序，不是常駐程序重啟樹。[Parallel](https://www.gnu.org/software/make/manual/html_node/Parallel.html) |

**適合借的做法**

對有限、可重建的成果，明示「哪些輸入變了就要重做」，並在完成後才發布產物。這可由 task 呼叫既有建置工具，或放成小型 JSON 產物包。GNU Make 預設主要依檔案時間與相依關係；若另加輸入／工具／配方雜湊，那是額外設計，不能說 GNU Make 原本就全都有。[How Make Works](https://www.gnu.org/software/make/manual/html_node/How-Make-Works.html)、[Interrupts](https://www.gnu.org/software/make/manual/html_node/Interrupts.html)

**具體發現：step 的 receipt 不等於增量失效判斷。**

例如輸入 CSV 已改，舊報表仍在；若 receipt 只問 `exists`，step 會接受舊報表。現有 `num` 條件可以比較 JSON 數字版本與常數，但不會自動計算輸入相依或比較任意 hash。[aos7_step.py](../../../packs/step/aos7_step.py):417

結果包裝器會記錄 `expect` 輸出檔的 SHA-256，但這本身沒有建立輸入相依圖，也沒有變成完整的快取有效性檢查。[aos7_step_result.py](../../../packs/step/aos7_step_result.py):69

**不適合直接搬入**

mtime、檔案存在或建置成功，不能取代外部副作用的 request／結果證據。付款、寄信、非決定性模型呼叫等，也不能只因舊輸出檔還在，就套用一般可重建產物的語意。

## 11. 跨系統最重要的七項發現

### 11.1 「不雙開」必須附上範圍

systemd 的 unit、runit／s6 的 service directory、OTP 的 child ID、Temporal 的 Workflow ID，都各有其命名與管理範圍。

proto7-2 的範圍是 root／node／slot 與合作任務。同一 argv 放在不同槽，本來就可並行；外部 API 的效果也不受槽鎖直接保護。

**判斷：既有設計合理，應維持精確措辭。**

證據：[spec.md](../../../spec.md):138、[spec.md](../../../spec.md):233、[spec.md](../../../spec.md):290。

### 11.2 程序接回不會補出遺失的成功結果

runner 死掉而任務主程序還活著時，proto7-2 可以繼續把它認作 LIVE。等主程序也結束，若沒有 `exit.json`，它不能從「現在不存在」推回原退出碼，更不能推回業務成功。

**判斷：lost／unknown 是必要資訊，不能為了看起來自動恢復而改成成功或直接重跑。**

證據：[aos7_task.py](../../../lib/aos7_task.py):93、[aos7_task.py](../../../lib/aos7_task.py):118、[aos7_run.py](../../../lib/aos7_run.py):89。

### 11.3 `never_started` 與「至少一次」都需要限定

`never_started` 檢查的是：沒有記到 runner、沒有 pid、out.log 不存在或空。它沒有查證外部效果。

靜態可推導的窗口是：tick 已起 runner 但未補 birth；runner 已起真命令但未寫 pid；此時管理程序中斷，靜默的真命令仍可能完成效果。這次未動態重現，也沒有量測其機率。

`once_retry` 還有取樣前提：要及時看到那筆 lost，相關槽證據仍在。漏取樣、模組重起遺失記憶體待辦或槽已刪除，都會削弱補派能力。它也只補特定 lost，不是所有失敗。

**較準確的說法是「及時觀測到特定 lost 時可補派，容許重複」，不能無條件宣稱至少成功執行一次。**

證據：[aos7_task.py](../../../lib/aos7_task.py):148、[aos7_task.py](../../../lib/aos7_task.py):315、[aos7_run.py](../../../lib/aos7_run.py):75、[once_retry/README.md](../../../modules/once_retry/README.md):18。

`budget` 已明文不拿 `never_started`、逾時或 step 失敗當成未支用證明，這個規則應保留。[budget/README.md](../../../packs/budget/README.md):34

### 11.4 觀測歷史、恢復證據與去重帳不能共用同一保存假設

| 資料用途 | 合理的保存依據 |
|---|---|
| 給人看的觀測歷史 | 可接受取樣、輪替，但需揭露缺漏。 |
| 恢復目前工作 | 保留足以恢復的 checkpoint 與未完成交接證據。 |
| 防止重送造成重複效果 | 去重證據必須活過可能重送的期間。 |
| 稽核完整事件序列 | 需要在事件發生或提交時可靠保存，事後取樣不足。 |

proto7-2 已有不同例子：

- history 是取樣；
- step 保存 frame 與槽外結果；
- control 的 `req_id` 證據會隨後續換 run 消失；
- budget 的證據保存到預算退役。

**因此「核心只留上一次」可以與可恢復工作並存，但上層不能把所有資料都照最新值清掉。**

證據：[modules/README.md](../../../modules/README.md):30、[step/spec.md](../../../packs/step/spec.md):42、[control/README.md](../../../modules/control/README.md):22、[budget/spec.md](../../../packs/budget/spec.md):102。

### 11.5 `log.on` 也不是完整、必達的事件來源

它能避免只輪詢 `last_event` 所造成的一部分漏取樣，但實作在追加失敗時會忽略 `OSError`；事件追加也沒有與業務動作或所有狀態更新形成同一筆提交。

所以不能把開啟 `log.on` 寫成「完整事件保存已解決」。

證據：[aos7_daemon.py](../../../lib/aos7_daemon.py):79、[aos7_fs.py](../../../lib/aos7_fs.py):163。

這裡還有資訊上的硬界線：如果兩段不同歷史最後都留下相同的 `last-round.json`，事後讀取者沒有足夠資料分辨它們。序號可以揭露漏了幾筆，不能還原漏掉的內容。

**若要求某类資料不漏，保存者必須預先參與該類資料的產生或提交；純事後觀測模組做不到。** 這項結論不代表要把同步歷史鉤子放回核心；目前文件已說明拒絕同步鉤子的理由。[modules/README.md](../../../modules/README.md):32

### 11.6 子樹清理需要活著的執行者

subd 已保證「新代啟動前，前代先清乾淨」。它没有保證「父 kill 後，即使永遠不再啟動也會清乾淨」。

如果將來需要後一種保證，就必須有仍會執行的清理者，以及不隨父程序死亡消失的清理意圖。單靠已死亡的 wrapper 或 owner 檔案無法完成。

**這是新增契約的成本，不能把它包裝成只是多一個設定。**

證據：[subd/README.md](../../../modules/subd/README.md):23、[subd/README.md](../../../modules/subd/README.md):55、[subd/README.md](../../../modules/subd/README.md):75。

另一個已接受的邊界是 `allowed_stop` 以 `at >= since` 判斷停止回條所屬代次，因此要求牆鐘不倒退。若日後要解除此前提，可考慮讓停止證據綁明確代次／請求身分；本輪不列為新 bug。[subd/README.md](../../../modules/subd/README.md):48

### 11.7 程序中斷恢復、跨開機身分與斷電耐久需要分開

核心 `write_json` 與 runner `write_at` 使用暫存檔加 replace，沒有檔案與目錄 fsync。tock 讀回成功可以確認當時讀得到，不能推成斷電後一定存在。Linux 也明確區分檔案同步與目錄項目同步。[fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)

這已是專案明文排除的範圍，**不是本輪新判定的 bug**。[component-contracts.md](../../component-contracts.md):51、[aos7_fs.py](../../../lib/aos7_fs.py):119、[aos7_run.py](../../../lib/aos7_run.py):102

也不能泛稱整個 repo 都沒有 fsync：搬入的 aos-exec 對特定 exit 檔及父目錄有 fsync；step 的結果發布也有檔案 fsync。這些局部措施不會自動涵蓋全部核心狀態。[aos_exec_run.py](../../../lib/aos_exec_run.py):212、[aos7_step_result.py](../../../packs/step/aos7_step_result.py):28

身分方面，Linux starttime 是本次開機後的時間；目前 PID＋starttime 沒有額外 boot identity。daemon gen 防舊動作，也不是 node 重建身分。**跨開機或重建後的實際碰撞未重現，只能說目前沒有編碼足以區分這些沿革的維度。** [proc_pid_stat(5)](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html)、[aos7_proc.py](../../../lib/aos7_proc.py):54、[aos7_fs.py](../../../lib/aos7_fs.py):260

## 12. 符合最小核心原則的借用順序

以下是比較得到的候選落點，不是本輪新增工作或已實作功能。

| 可借做法 | 合適落點 | 必須保留的限制 |
|---|---|---|
| alive／ready／完成分開 | 任務自有狀態、工具或 pack | readiness 綁本次 run，不能只看舊檔存在。 |
| 有界重試、退避與停手原因 | 包裝器或政策模組 | 精確限制放行額度與精確計算實際啟動次數不同；取樣計數可能漏。 |
| 父結束後孩子的處置政策 | subd 或上層任務包 | 要保證最終清空，須有持續執行的清理者。 |
| 意圖版本與已觀測／已生效版本 | 需要設定確認的模組 | `tasks_rev`、daemon gen 不可直接代替生效證明。 |
| 穩定 request、attempt 與效果帳分離 | 延續 step／budget 的分工 | 後端要能履行去重或查回；作者宣告不會自動產生此能力。 |
| 日曆排程與漏期補做 | 排程任務／工具 | 期間、漏期政策、業務完成分開記錄。 |
| 產物相依與失效判定 | 產物 pack 或既有建置工具 | 僅適用於契約明確的可重建成果。 |
| 來源重建身分 | 發布者與觀測模組協議 | 普通重啟沿用，真正重建才換；不補回漏掉的歷史。 |

這些落點符合現有 A 任務、B argv 包裝、C 工具三種接面。[spec.md](../../../spec.md):271

但三接面有能力邊界：A 是取樣者，B 只涵蓋經過它的工作，C 只有被呼叫才會執行。它們不是任意時點都能攔截核心的鉤子。因此，可靠保存全部核心事件、跨外部系統原子提交、全面斷電耐久等要求，需要另外定義契約，不能只說「以後加模組就好」。[component-contracts.md](../../component-contracts.md):105

## 13. 記憶、版本與未驗證事項

以下保留為不確定範圍：

- **systemd、supervisord**：核對了現行官方文件／原始碼，未測本機安裝版；任意管理者硬死後的完整行為仍受啟動方式與外層管理者影響。
- **runit**：監督者死後與活孤兒重疊的情境是依啟動模型推論，未驗證特定發行版修補或服務自帶鎖。
- **s6**：`lock-fd` 已核對現行文件，首次引入版本未核對；不假定所有舊版都有。
- **OTP**：本文使用長期存在的監督與 port 邊界；各版新增旗標與細節沒有逐版比較。
- **Kubernetes**：未釘 release；各資源如何增加 generation、watch/cache 細節、feature gate 與 Lease 預設值，沒有靠記憶補成保證。
- **cron**：DST、校時與停機補跑依實作不同；不能籠統寫成所有 cron 都完全不補跑。
- **Temporal**：各 SDK 的取消、heartbeat checkpoint、服務端交易及跨區故障切換細節未完整核對，本文未據此增加保證。
- **Make**：獨立 make 之間缺乏通用全域排他的敘述屬高信心架構記憶；未遍查所有版本與外部包裝。
- **proto7-2**：所有新情境都是靜態推導；沒有執行程序碰撞、斷電、I/O 注入或長跑驗證。

## 14. 唯讀核驗入口

以下指令只讀取原始碼；它們可核對本文證據，**不會重現故障情境，也不代表測試通過**。

```sh
cd /home/guanyu/projs/aos

git --no-optional-locks rev-parse HEAD

# 排他、程序身分與 lost 判定
nl -ba proto7-2/lib/aos7_fs.py | sed -n '244,314p'
nl -ba proto7-2/lib/aos7_proc.py | sed -n '54,62p'
nl -ba proto7-2/lib/aos7_task.py | sed -n '73,155p'

# 寫入持久性與事件出口
nl -ba proto7-2/lib/aos7_fs.py | sed -n '119,172p'
nl -ba proto7-2/lib/aos7_run.py | sed -n '102,113p'
nl -ba proto7-2/lib/aos7_daemon.py | sed -n '79,88p'

# 歷史、補派與子樹停止邊界
nl -ba proto7-2/modules/history.py | sed -n '57,91p'
nl -ba proto7-2/modules/once_retry/README.md | sed -n '15,35p'
nl -ba proto7-2/modules/subd/README.md | sed -n '15,77p'

# 工作身分、checkpoint 與效果帳
nl -ba proto7-2/packs/step/spec.md | sed -n '42,84p'
nl -ba proto7-2/packs/budget/README.md | sed -n '30,42p'
```

可供後續另行驗證的既有測試位置：

- daemon 死後接回原 run：[test_daemon.py](../../../tests/core/test_daemon.py):396。
- birth 已寫、once 實際零次而報 lost：[test_once_threestate.py](../../../tests/core/test_once_threestate.py):51。
- 子空間前代殘留與重開前回收：[test_subd_recover.py](../../../modules/subd/tests/test_subd_recover.py):90。
- step 各交接中斷點：[test_step.py](../../../packs/step/tests/test_step.py):389。

本輪僅閱讀上述證據，未執行這些測試。