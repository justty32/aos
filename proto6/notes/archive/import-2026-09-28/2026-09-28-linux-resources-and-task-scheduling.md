> 封存 2026-09-29：09-28 從 proto5 收錄的交接快照，是 proto6 的起點；09-29 起架構改為 node／kernel 樹，spec 已重寫。現行看 [spec](../../../spec/README.md) 與 [kernel 樹](../../../notes/2026-09-29-kernel-tree.md)。

# Linux 資源、任務排程與通訊：後續討論紀錄

> 2026-09-28 交接快照；[原始來源](../../../../proto5/notes/2026-09-28-linux-resources-and-task-scheduling.md)保留於原位置。本文的現行行為與實測均指當時 proto5／環境，非 proto6 已實作；僅調整導航與探針重跑路徑。

← [筆記索引](../../README.md)｜前文：[身分與工具繼承權限](2026-09-28-employee-identity.md)｜[使用建議](../../../../proto5/advice.md)

2026-09-28。記錄工具繼承權限決定之後的討論，未修改產品。本篇以「使用者已接受」「構想」「助理提出的邊界」「現行事實」區分狀態；不是已完成的規範或實作。

## agent 的本體與三種資源

**使用者已接受：先把正式員工／工具的組織分類放一邊，考慮一個 agent 對應一個 Linux 使用者。** agent 的資料夾是持久本體，tick 是推進其狀態的執行步驟；agent 不必等同於永遠存活的一個程序。

權限、執行資源與自有容量分開管理：Linux UID／group／DAC 決定能存取什麼；cgroup v2 管執行時 CPU、記憶體、程序數等資源；project quota 管 agent 自有資料的容量。這三個方向已獲使用者接受，數值、目錄配置與具體啟動接法未定。

工具沿用委託 agent 的權限與資源歸屬，包括工具內部 LLM 與再次呼叫工具。它們代表 agent 做事，不能因另啟程序就脫離資源限制。控制用的 daemon／kernel 不因此搬進某個 agent 的資源域。

掛進來的外部 workspace 不計入 agent 的「自有容量」；這是資料歸屬政策，落地時要把自有資料和外部檔案的 project quota 歸屬分清楚，不能只看路徑是否長在 agent 目錄下。外部檔案的讀寫仍可能產生 RAM／page cache 用量，依 cgroup 記帳歸屬計入；磁碟容量與記憶體用量不是同一本帳。機制背景見 [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) 與 [XFS project quota](https://man7.org/linux/man-pages/man8/xfs_quota.8.html)。

## tmpfs 的容量邊界

**討論中的機制事實：** tmpfs 的 `size` 限制整個 tmpfs 實例，包含其普通子目錄與更深層檔案的合計，不是替任意子目錄自動各設一個限額。如果在其中掛入另一個檔案系統，後者的檔案由它自己的檔案系統計容量，不會因掛載位置而算成該 tmpfs 的檔案頁面。

**一個 agent 一個 tmpfs 是候選，尚未拍板。** tmpfs 不是持久儲存；卸載或重啟後不能用它承擔 agent 本體的持久性。它可能使用 swap，因此不等於資料永遠只在實體 RAM；是否允許 swap 要另定。容量上限之外還有 inode 數量限制，很多小檔案可能先碰到另一種上限。若使用 tmpfs，也仍要和 cgroup 記憶體限制一起考慮。來源：[Linux tmpfs 文件](https://docs.kernel.org/filesystems/tmpfs.html)。

## Docker 與 FUSE 的位置

**使用者方向：基本架構不需要先引入 Docker 或 FUSE。** Linux 帳號、cgroup 與 quota 各自能承擔上述責任。FUSE 未來會做，但現在延後，不是這輪架構成立的前提。

討論中也修正了「一千個容器一定不行」的概括：不能只憑容器數量判斷。空閒容器與同時進行編譯、模型呼叫或大量 I/O 的容器不是同一種負載；若未來採用，應量測實際同時活躍的工作與管理成本。本輪沒有進行千容器效能測試。

## CPU worker 可以取消，但執行責任仍在

**使用者提出「其實不用」CPU worker 的方向，尚未實作。** Linux 已經排程真正的程序；aos 不必為了模仿 CPU 再維持一層常駐 worker。這是對前文「固定 tick worker」的後續重新思考，不應把兩者同時當成不可變更的要求。

拿掉 worker 不等於拿掉 `aos-exec`。啟動程序、等待結束、取消／終止、取得退出結果與回報等責任仍需有人承擔。worker 專用資料夾和交接檔可望精簡，但持久任務、結果與故障恢復資訊不能因程序改由 Linux 直接排程就一併刪掉。

**kernel 的新構想是往「一輪任務」層次提升：** 從接受工作、經過多次 tick 推進，到回到 idle，作為較高層的排程與觀察單位。kernel 可處理任務策略、LLM 工作優先次序與 token 資源，以及較粗的執行資源安排；目標是讓行為可理解、可預測。是否把這些責任分散給多個部分，尚未定案。這不是把 LLM token 當成 Linux CPU 時間。

## 資源域必須跟著可信派工走

**現行事實：** agent tick 把 LLM／工具工作交給 kernel，再由 kernel 派給 worker 執行；工具通常不是該次 tick 直接 fork 出來的子程序。因此不能只把 tick 放進某個 cgroup，就宣稱它委託的所有工作會自然繼承該資源域。現行接線可見 [`aos_agent_batch.py`](../../../../proto5/lib/aos_agent_batch.py) 與 [`aos_kernel_engine.py`](../../../../proto5/lib/aos_kernel_engine.py)。

**後續設計需要：** 可信派工資料攜帶委託 agent 的身分與資源歸屬，在工作開始執行之前就讓它進入正確 cgroup；不能讓工具自行填寫任意別人的資源域。這套接法適用於一般 exec 工作，不只 Python 或某一個工具包。具體採何種啟動方式尚未選定；daemon／kernel 自己維持控制層的資源歸屬。

## 即時性、通知與串流

**使用者偏好：即時性優先序較後，約 0.5 秒的反應可以接受。** 不為了更快一點就立即增加整套常駐服務。`--immediately`（使用者原拼 `--immediatly`）是討論中的候選介面，尚未成為指令契約；可由 daemon 承擔即時通知的角色。

使用者曾考慮每個 agent 各有一個 tick-daemon，隨即自行撤回，**不列為待辦**。未來若與 FUSE 整合，讓 agent／tick 在同一個常駐程序中運行，並與 daemon 鬆耦合，仍只是後續構想，不是現在的部署前提。

**現行喚醒鏈：** `say` 先存輸入，再往 kernel 的 requests 放 `wake`；daemon 查看 kernel requests，可提前開一格 kernel tick；kernel 派工作時按 worker 的門鈴。daemon 的 `poll_ms` 預設是 20 ms，這不是端到端延遲保證，也不是每個 agent 每 20 ms 必定推進。排隊、正在執行的 tick、啟動及其他負載都會影響體感。參考 [`aos_agent_say.py`](../../../../proto5/lib/aos_agent_say.py)、[`aos_agent_wake.py`](../../../../proto5/lib/aos_agent_wake.py)、[`aos_daemon.py`](../../../../proto5/lib/aos_daemon.py) 與 [`aos_kernel_engine.py`](../../../../proto5/lib/aos_kernel_engine.py)。

串流是另一件事：提早喚醒與開始執行，不等於模型輸出會逐字送到使用者。先前 `say`／`listen` 的串流需求仍未實作，不能用新的即時通知構想宣稱已解決。

## JSON-RPC 不要求常駐 socket server

**討論確認：JSON-RPC 與傳輸方式無關，檔案可以作為傳輸媒介。** server 是處理請求並產生回應的角色；某次 tick 讀取檔案、執行處理、寫回結果，就可以履行這個角色，不必因此建立永久常駐的網路服務。來源：[JSON-RPC 2.0 規範](https://www.jsonrpc.org/specification)。

**助理提出的後續協定邊界：** 要分清楚「收到請求」「建立任務」「任務完成的回應」，以及重送、去重、結果保留與串流如何表達。JSON-RPC 的 `id` 負責請求與回應對應，本身不保證副作用只發生一次；串流也需另定協定，不是多寫幾個相同 id 的完成回應就自然成立。

任務進行中收到新訊息，究竟歸入目前這輪、下一輪，或形成另一個任務，也是助理提出的語意邊界，**使用者尚未決定**。上述問題留在此作為日後設計背景，不以本篇紀錄替使用者裁決。

## 後續補充：家用機上的一萬個 agent

**使用者明確的工作負載前提：** 一台家用機目標承載 10,000 個 agent，共用十幾個廠商的雲端 LLM endpoint；Claude／GPT 的推論不在本機進行。一小時內活躍的 agent 不到 100 個，其餘保持不動。

「一小時活躍不到 100 個」不是同時併發上限，而且單一 agent 仍可能同時派出多個工具或 LLM 工作。因此不能直接用 agent 數量推導程序數或請求併發。雲端 endpoint 數量也不等於吞吐量；實際額度與任務量決定排隊情況。

**對應的工程方向：** idle agent 沒有常駐程序，不頻繁 tick、不載入 history，收到事件或到期才喚醒。調度成本應主要隨 active／ready 工作增加，而不是每輪掃過一萬個 agent。執行資源同時受全局併發控制、共同父 cgroup 與每 agent cgroup 約束；project quota 是容量上限，不是替每個 agent 預先保留等量磁碟空間。具體併發值與容量數值尚未定案。

在這個稀疏活躍、模型推論在雲端的前提下，一萬個 agent 是合理的工程目標，**不是現版已通過萬 agent 驗證的結論**。目前不需要為這個數量預先引入分散式 kernel、Docker 或 FUSE；是否增加機制，應由實際負載與量測結果決定。

後續使用者要求具體規劃「要改什麼、引入什麼」，見[萬 agent 改動計畫](plan/README.md)：分基線、idle 索引、Linux 執行邊界、LLM 配額與萬級驗收逐步落地，仍未實作。
