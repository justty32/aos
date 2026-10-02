> 封存 2026-10-02：09-30 審稿與第十八～二十批（含 cgroup／git）改寫計畫、交接、核對報告，批次已結束；結論已由 proto6/spec（settled/ 與 settled/deferred/）與裁定紀錄 proto6/notes/verdicts/09～11 吸收

← [審稿索引](README.md)

# proto6 notes 與 spec 審稿報告（第十七批之後）

審了什麼：`proto6/spec/` 全部（主規格 terms／daemon／tick／contracts／conformance／base／scheduling／agent／cli，協議篇 15 篇文字、57 份 schema、205 份範例）與 `proto6/notes/` 現行筆記（不含 archive），並拿 `proto6/proto/` 與 spec-gaps 當對照。

怎麼審：先跑兩支自動檢查——`spec/check_ids.py`（986 個條號引用，2 個找不到定義，都在 notes）、`examples/messages/validate.py`（57 schema、205 範例全過）。再開六隊平行審：裁定 07／08 逐條落實核對、裁定 01～06 被推翻後的殘留、主規格篇、協議篇、schema／範例／CLI 對文字、notes 過時，另一隊專審設計原則。最後由我逐條回原文核實行號、去重、彙整。所有相對連結與錨點都存在，沒有壞連結。

結論先講：第十六、十七批的每一條都找得到落點，落法跟裁定文字一致，舊說法（帳本、systemd 必要、「不管」、B1 分情況、ACL 等）在 spec 裡沒有殘留。問題集中在三處：(1) 「每任務一層 cgroup」和「取消工作」這兩條新裁定跟既有的權限／daemon 規則撞；(2) 幾個新機制只寫了一半（kernel 的 history 沒人讀得到、池 node 誰收件、取消沒有 CLI）；(3) 整體設計上有幾個沒考慮到的面向（投件被丟掉沒痕跡、萬級規模數字、版本演進、除錯線索散）。

總共 **79 條**：必修 9、設計問題 18、建議 37、要使用者裁定 15。行號都是 `proto6/` 起的相對路徑。設計問題與裁定裡，設-14～18 與裁-13～15 是照使用者 09-30 追加的兩個視角（「分配單位是一個表達式、必須符合規格、能被 Linux 管制；外部計算當外部函式庫」與「多層、多個 kernel」）拿 spec 去對的結果。

名詞先解釋一次：**cgroup**＝Linux 用來把一群程序框起來、限制資源、一次殺光的資料夾式機制；**委派**＝把 cgroup 資料夾和裡面幾個控制檔的擁有權交給另一個帳號，讓它能自己在底下開子框；**once**＝daemon 只跑一次就解除登記的工作程序（跑工具、打 LLM 都靠它）；**helper**＝sudo 開 daemon 時留下的 root 小程序，專做建帳號、chown 這類需要 root 的固定步驟；**多 UID 部署**＝有 helper、每個 node 用不同 Linux 帳號的部署。

---

## 一、必修（照 spec 實作會做錯或做不下去）

### 必-1．多 UID 部署下，「node 框委派給 node 帳號」做不到，而且委派後 daemon 自己也開不了子框、刪不了殘框

- 位置：`spec/daemon.md:80`（B-605：daemon 建 node 框時要把 `n-<h>` 資料夾及 `cgroup.procs`、`cgroup.subtree_control`、`cgroup.threads` 交給 node 的執行帳號）；`spec/daemon.md:78-79`（子 node 框 `n-<h2>`、once 框 `once-<h>` 都放在父 node 框底下）；`spec/protocol/daemon/provision-and-runner.md:21`（P-107：「只有建帳號、chown、quota 需要 helper」，cgroup 動作由 daemon 自己做）；`spec/protocol/daemon/startup-and-ipc.md:28`（P-101：`cgroup_root` 不是一般可寫路徑授權，所以 helper 的 chown 動作也管不到它）；`spec/base/identity-resources.md:35`（B-303：sudo 開時主程式永久降權）；`notes/verdicts/08-cancel-task-cgroup-and-gaps.md:31`（這句是落 spec 隊補的，不是使用者逐字裁定）。
- 問題：把資料夾 chown 給別的帳號要 root。sudo 模式下 daemon 已降權成通用帳號 D，成員 node 用帳號 N；P-107 說 cgroup 動作不經 helper，P-101 又說 helper 的 chown 只管一般路徑，所以沒有任何一條路能把 `n-<h>` 交給 N。就算交出去了，`n-<h>` 目錄歸 N 之後，D 沒有它的寫權，之後要在底下 mkdir 子 node 的 `n-<h2>`、once 的 `once-<h>`，或收尾後 rmdir 空掉的 `tick`／`task-*`／`once-*`（rmdir 需要父目錄寫權），全部會失敗。只有單帳號（無 helper）部署全同 UID 才沒事，但 spec 明說要支援 helper 模式。
- 情境：使用者用 sudo 開 daemon、給成員各自帳號，第一個成員 tick 一開就卡在建 `task-1`（或 daemon 一開始就 chown 失敗）。
- 建議（三選一，由使用者定）：(a) 新增 helper 固定動作（例如 `cgroup_delegate`），只 chown 三個委派檔、目錄改成 D 擁有＋共享群組可寫，讓 D 仍能 mkdir／rmdir；(b) 任務層改由 daemon 代建：tick 透過 IPC 向 daemon 要 `task-N`（多一個 method）；(c) 每任務一層 cgroup 只在單帳號部署啟用，多 UID 模式退回只有 `tick` 葉，並把這件事寫進 B-605 與 P-203。

### 必-2．人手 `aos node tick N`、或任何不在 daemon 框裡跑的 tick，「每任務開 `task-<序號>`」開不出來時怎麼辦沒寫

- 位置：`spec/protocol/node.md:78`（P-203：tick 本身在 node 框的 `tick` 葉，每個任務開並列的 `task-N`，開不出來沒說）；`spec/cli/commands.md:42`（第 17 列 `aos node tick N` 用目前帳號直接跑一格）；`spec/tick.md:11`（直接呼叫也須遵守鎖，暗示直接跑是正常用法）；`spec/protocol/agent-tasks.md:66`（手動整格用 `aos node tick`）。
- 問題：人在自己的 shell 跑 tick，程序在 shell 的 cgroup 裡，沒有 `n-<h>`、沒有委派；mkdir `task-1` 一定失敗。tick 該回 2／125 拒跑、略過任務層繼續、還是只在自己所在 cgroup 叫 `tick` 時才做，spec 沒選。原型的假 cgroup 也碰到同一問題。
- 建議：P-203 明寫「開不出任務層時的行為」；若選略過，收尾就退回 B-202 的 session／pgid 清法並在 stderr 註明一行。

### 必-3．取消在跑的工作靠 `node.unregister` 殺 once，但 `node.unregister` 在 daemon 篇與 kernel 篇都是「排空、不殺工作」

- 位置：`spec/protocol/work.md:88`（P-411：「請 daemon 對那個 once 做 `node.unregister`（daemon P-105：TERM、寬限、`cgroup.kill`、確認全空）」）；`spec/protocol/kernel-tasks.md:86`（P-806 同句）；`spec/protocol/daemon/registration.md:23`（P-105 `node.unregister`：「立即阻止目標及已登記子樹的新格，按 B-604 排空；確認所有後代全空後才刪登記」——沒有 TERM／kill）；`spec/daemon.md:55`（B-604：「daemon 阻止新啟動並排空既有程序，再解除登記」）；`spec/protocol/kernel-tasks.md:45`（P-802：「unregister 依 daemon 排空要求，busy 留待維護，**不自動殺工作**」）；`spec/cli/commands.md:36`（第 11 列 unregister：「排空目標與登記子樹，再解除」）。
- 問題：「排空」是等程序自己跑完，「殺」是主動 TERM／kill。P-411 括號裡把 P-105 描述成會殺，P-105、B-604、P-802 都說不殺。照 P-105 實作，取消在跑的工具等於「等它跑完」，永遠不會提前停；照 P-411 實作，`aos node unregister` 又會變成殺掉正在跑的成員格，跟 P-802「不自動殺工作」相反。只有 helper 模式的 `daemon.helper.stop`（`spec/protocol/daemon/provision-and-runner.md:36`）真的有「TERM、2 秒後 KILL」，但 P-105 沒說 unregister 會走它。
- 情境：kernel 收到 work.cancel，對 once 呼叫 unregister，daemon 一直等到工具的 `timeout_ms`（預設 60 秒）到期；使用者以為取消壞了。
- 建議（二選一）：(a) P-105 明寫 unregister 對 once（或帶一個 `kill:true` 參數）會 TERM、等 `shutdown_grace_ms`、`cgroup.kill`，並改 P-802／B-604／CLI 第 11 列的說法；(b) 另開一個 `node.kill` method 專給取消用，P-411／P-806 改指它。順帶：寬限時間三套（helper.stop 寫死 2 秒、daemon 用 `shutdown_grace_ms`、inst 逾時 2 秒），見建-9。

### 必-4．kernel 收 `agent.say` 寫進 `state/kernel/history/`，但 listen 只會讀 agent 的 history，kernel 也沒有序號檔

- 位置：`spec/protocol/kernel-tasks.md:53`（P-803：kernel 寫 `state/kernel/history/<id>.json`，「seq 在鎖內遞增」）；`spec/protocol/agent-tasks.md:164`（P-713 listen「從同一 commit 的 history 按 seq 查」，沒指路徑）、`:49`、`:59`（agent 的 history 在 `state/agent/history/`、序號在 `state/agent/sequence.json`）；`spec/cli/walkthrough.md:127`、`:212`（走查就靠 `aos agent listen --target top` 看 kernel 收到的話）；`spec/cli/commands.md:100`（「top 沒裝 agent 任務，收話只存 history」）。
- 問題：kernel 的序號檔位置、`source_path` 要填什麼（agent-history schema 必填）、listen 遇到沒有 agent 任務的 node 要改讀哪裡，都沒條文。照 P-713 實作，走查第 4、7 步對 top 跑 listen 找不到檔。
- 建議：P-713 補「target 沒有 agent 任務時讀 `state/kernel/history/`」（或統一兩者路徑）；P-803 補 kernel 序號檔（例如 `state/kernel/sequence.json`，形狀沿 agent-sequence）與 `source_path` 值（例如指向 `state/messages/requests/<id>.json`）。

### 必-5．`aos work cancel` 沒有 CLI 入口，第一層指令也沒有 `work`

- 位置：`spec/protocol/work.md:81`（P-411：「取消用檔案請求 `work.cancel`（`aos work cancel`）」）；`spec/protocol/README.md:44`（P-004：method 就是對應指令去掉 `aos`）；`spec/protocol/messages.md:63`、`:75`（展開後 argv 必須是收件 node 開放的命令）；`spec/cli/README.md:9`（第一層只有 daemon／node／kernel／agent／llm／attend／clean／inst）；`spec/cli/commands.md:7`（「共 53 條」，`grep cancel spec/cli/` 無任何結果）。
- 問題：協議說人和程式共用同一批指令，但人手要取消一件工作沒有任何指令可打；`aos work cancel` 帶什麼參數（目標 node、`--from-node R`、request_id）也沒定，CLI 實作會卡住。
- 建議：H-004 加一列（投件類，例如 `aos work cancel K --from-node R --request-id ID [--json]`，stdout `submitted ID`），cli/README 第一層加 `work`，總數改 54。若使用者想掛在 `aos kernel work cancel` 底下，method 就得跟著改成 `kernel.work.cancel`。

### 必-6．純池 node 誰接 `llm.chat` 沒定：P-405／P-408 說 aos-llm 自己收件，範本卻讓 pool 任務不宣告 methods、只讀 forward 接納的材料

- 位置：`spec/protocol/llm-work.md:13`（P-405：「池管理 node 的任務表加入 `aos-llm`…aos-llm 是短任務：收件、核對共享限制、派送、收結果」）；`spec/protocol/work.md:100`（P-408：aos-llm「直接讀 C、收件、池狀態」）；`spec/protocol/kernel-tasks.md:108`（P-809：「本池不投自己的收件區…pool 任務在後組讀已提交材料」）、`:168-169`（範本：forward 宣告 `llm.chat`，pool 宣告「無（讀 forward 已接納的材料）」）；`spec/protocol/node.md:52`、`spec/protocol/messages.md:63`（第十七批：沒任務宣告的 method 由 tick 回 -32601）；`spec/scheduling/llm.md:25`、`spec/protocol/kernel-tasks.md:143`（「kernel 不管」路線：agent 直接投池 node 的 requests/）。
- 問題：若池 node 只裝 aos-llm（照 P-405 的寫法），第十七批規則下 `llm.chat` 沒人宣告，tick 一律回 -32601；若池 node 必須同時裝 forward，P-814 沒說，P-405／P-408 的「aos-llm 收件」就是錯的。實作者不知道 aos-llm 要不要讀 requests/、methods 要不要寫 `llm.chat`。
- 建議（二選一寫死）：(a) 池 node 一律裝 forward 收件，把 P-405:13、P-408:100 的「收件」改掉，P-814 註明 pool 必須搭 forward；(b) aos-llm 自己宣告 `llm.chat`（同一 node 若同時有 forward 就撞「同 method 只能一項宣告」，要另定分工）。

### 必-7．LLM 的 unknown 請求：一邊說「占並行名額直到定期清理」，一邊說「本機連線關掉就可回收名額」

- 位置：`spec/scheduling/llm.md:57`（S-304：「本機 HTTP 已確定關閉，可回收本機並行名額；不明的遠端用量保持 unknown」）；`spec/protocol/resources.md:75`（P-505：active 與 unknown「合計占用份額；unknown 的估計占用隨 P-606 定期清理移除」）；`spec/protocol/kernel-tasks.md:110`（「未終局／unknown 各占一次」）、`:128`（「unknown 不重試，估計並行占用隨 P-606 清理」）；`spec/base/storage.md:37`（保留期預設 30 日）。
- 問題：池的 `concurrent_requests` 若是 3，三次送出後斷線（很常見）就把池鎖死到 30 天後清理；S-304 又說本機關閉就能回收。實作者不知道 unknown 到底占不占並行名額、占多久。
- 建議（使用者三選一）：(a) unknown 只占「用量統計」不占並行名額（S-304 現行說法）；(b) 占並行名額但另設短逾時（例如請求的 `timeout_ms` 到期或幾分鐘）就自動釋放，與 30 天資料保留脫鉤；(c) 維持占到清理為止，接受池會鎖死，並在 S-304 改口。

### 必-8．同一個 resume 流程呼叫的兩支 `--validate-only`，「設定不合法」一個回 2、一個回 1，而 agent 那邊的 2 又是「用法錯」

- 位置：`spec/protocol/kernel-tasks.md:74`（P-805 validate-only：0 合法、2 不合法、125 讀不到）；`spec/protocol/agent-tasks.md:149`（P-712 validate-only：0 有效、1 無效、2 用法錯、125）；`spec/protocol/node.md:155`（P-210 第 3 步在同一個 resume 裡兩種都呼叫，「兩種都有便都驗」）。
- 問題：寫 resume 的人拿到 2 分不出是「agent 設定壞」還是「我自己傳錯參數」；同時裝 kernel 與 agent 任務的 node 更亂。
- 建議：兩支 validate-only 統一同一組碼（用哪一組見裁-3）。

### 必-9．LLM 預留到底是旁檔 `kernel.json.llm`，還是 kernel.json 裡的 `llm` 欄位

- 位置：`spec/protocol/kernel-tasks.md:128`（P-811：「預留存 `state/work/<attempt>/kernel.json.llm`」）；`spec/protocol/schemas/kernel-work-state.schema.json:47-79`（`llm` 是 kernel.json 內的物件，必填 pool_id／quota_scope／reserved_tokens／reserved_at_ms／retry_at_ms）；`spec/protocol/kernel-tasks.md:86`（P-806 列 kernel.json 欄位時沒提 `llm`）。
- 問題：文字說是旁檔，schema 說是欄位；沒有 `kernel.json.llm` 的 schema 或範例。實作只能二選一，另一邊就對不上。
- 建議：擇一。若是欄位，改 :128 為「存在 kernel.json 的 `llm`」並在 :86 補列；若是旁檔，schema 拆出來並加範例。

---

## 二、設計問題（冗餘、沒考慮到的面向、設計弱點）

### 設-1．投件被丟掉只在 stderr 印一行，而那個檔每格覆寫；tick 因任務表壞掉回 2 也沒人寫待辦——agent 會無聲卡死

- 位置：`spec/protocol/node.md:111`（P-206：target_not_node／target_not_writable「tick 在 stderr 印一行…不寫待辦、不重試」）；`spec/protocol/daemon/provision-and-runner.md:53`、`spec/protocol/node.md:22`（runner stderr 收到 `.aos/runner-stderr.log`，每格**覆寫**）；範本任務都是 `stderr:{"$opt":"inherit"}`（`spec/protocol/examples/kernel-tasks/kernel-template.minimal.valid.json:14`）；`spec/protocol/agent-tasks.md:93`（alarm_ms 只是「可以設」，範本沒預設）、`:97`（只解讀已收結果）；`spec/protocol/node.md:84`（P-203 結束碼 2 沒說寫事項）、`spec/protocol/daemon/registration.md:30`（P-105 只把 3／125 當停格碼才寫 attention）、`spec/protocol/ops.md:83`（P-609 卻說「任務表壞到檢查任務跑不了時，由 tick／daemon 寫 node 事項」，沒人承接）。
- 情境：agent 的 `llm.chat` 因權限沒開被丟掉，唯一痕跡是 runner-stderr.log 的一行，下一格就被覆寫；agent 的 pending 永遠等不到回應、summary.ready=false，kernel 不再叫醒它，`aos attend ls` 什麼都沒有。人要查只能翻 git 歷史看到 outbox 檔曾存在，看不到原因。手改 tasks.json 寫錯，node 也只是「一直在跑」。
- 代價：第十五批「不寫待辦」是使用者裁的，但它跟「runner-stderr 每格覆寫」加起來就是零痕跡。
- 方向：(a) 維持不重試，但丟件寫一件 node attention（要使用者推翻「不寫待辦」）；(b) agent 範本預設對 LLM 請求設 alarm_ms；(c) runner-stderr.log 改追加＋簡單輪替；(d) P-203 明寫 2 時 tick 自己寫 `.aos/attention/open/`（reason 例如 tasks_invalid、同一問題沿用 ID）。

### 設-2．每條裁定落在三～四處重寫，不是正本＋引用，已經開始互相漂移

- 例一 cgroup 任務層：`spec/daemon.md:80`、`spec/protocol/node.md:78`、`spec/base/execution.md:19`、`spec/protocol/daemon/provision-and-runner.md:21` 四處各自完整敘述。
- 例二「任務不改 config 是軟性原則」：`spec/agent/configuration.md:17`、`spec/protocol/node.md:74`、`spec/protocol/agent-tasks.md:29`、`spec/protocol/kernel-tasks.md:78`。
- 例三投件失敗規則：`spec/protocol/node.md:111`、`spec/scheduling/llm.md:21`、`spec/protocol/messages.md:36`、`spec/protocol/agent-tasks.md:27`、`:93`、`spec/conformance.md:56`。
- 例四 in_reply_to 只記錄：`spec/agent/input.md:11`、`spec/protocol/agent-tasks.md:81`、`spec/protocol/messages.md:69`、`:77`、`spec/protocol/kernel-tasks.md:53`、`spec/cli/commands.md:98`。
- 例五 daemon 重啟／停機：`spec/daemon.md:37-45`、`:53` 與 `spec/protocol/daemon/shutdown.md:7-19`、`spec/protocol/daemon/startup-and-ipc.md:19`（`cgroup_root` 欄位說明又把搬程序規則講一遍）。
- 已經漂移的實例：沒人宣告的 method，`spec/protocol/messages.md:63` 說「丟掉原件」，`spec/protocol/node.md:52` 說「複製到 state/messages 再清原件」（見建-4）；unregister 一處說殺、三處說排空（必-3）。
- 代價：每批裁定要改 4～6 處，漏一處就是下一輪的「不一致」；P-001 宣稱「主規格是行為正本，協議篇只定編碼」，實際協議篇大量重述行為，讀者分不清哪句是正本。
- 方向：每條裁定只在正本寫全文，其他處只留一句＋條號連結；或反過來明定「協議篇是正本、主規格只留方向」。

### 設-3．node 帳號拿到 `n-<h>` 的委派後，可以自建 `tick`／`task-*` 以外的子框藏程序；daemon 收尾只看 `tick`＋`task-*`

- 位置：`spec/daemon.md:80`（委派三個控制檔給 node 帳號；「daemon 收尾 tick 時看的範圍是 `tick` 加所有 `task-*`」）；`spec/protocol/node.md:78`；`spec/base/execution.md:19`（後代清空才算結束）；`spec/tick.md:9`（舊 tick 清乾淨才開下一格）；`spec/daemon.md:45`（逃生口「以後再設計」）。
- 情境：任務 `mkdir n-<h>/keep`、把子程序寫進去、退出。tick 看 task-* 全空回 0；daemon 看 tick＋task-* 全空開下一格。程序活著、不在任何格裡；B-202 的「全空」保證形同虛設，第十七批等於順手把「逃生口」開放給每個 node。資源仍受 `n-<h>` 上限，但 unregister／B-604「確認所有後代全空」要看什麼框沒寫。
- 方向：(a) daemon／tick 判定「全空」改看整個 `n-<h>` 扣掉 `n-*`、`once-*` 子框；(b) 只委派一個 `n-<h>/tasks/` 分支給 node，tick 與 task-* 都放那底下（但要處理「有程序的層不能開 controller」）；(c) 接受，明寫這就是逃生口。

### 設-4．一萬 node 與「60 秒一批、每批 64 個、kernel 每秒 tick、每格 9 個任務」的數字合不起來

- 位置：`spec/terms.md:40`（10,000 node）；`spec/scheduling/admission.md:17`、`spec/protocol/kernel-tasks.md:17`（補查每 60 秒 64 個）；`spec/protocol/kernel-tasks.md:176`（頂層 interval_ms=1000）、`:26`（子 kernel 建議 1000）、`:160`（範本 9 項任務）；`spec/protocol/node.md:78`（每任務一層 cgroup 建／殺／rmdir）。
- 情境：一個 kernel 帶 10,000 成員，漏掉通知的成員最慢要 10000÷64 分鐘≈2.6 小時才被補查到。改成樹狀（100 個 kernel × 100 成員）則每秒有 100 格 kernel tick，每格 9 個任務＝約 1,000 次 fork/exec＋900 次 cgroup 建刪／秒，機器閒置時也是這個負載。notes 說「idle 不頻繁 tick」只對 agent 成立。
- 方向：(a) kernel 也改事件驅動（門鈴＋較長間隔）；(b) 補查批量與間隔按成員數自動放大；(c) 承認一個 kernel 的成員上限並寫進規格；(d) 接受目前數字，把「萬級」改成「總數萬級、單樹活躍百級」。

### 設-5．沒有版本演進規則：`version` 只會拒絕，不能升級、不能新舊共存

- 位置：`spec/protocol/README.md:10`（未知版本拒絕；未知欄位預設拒絕）；`spec/contracts.md:11`；`spec/protocol/daemon/shutdown.md:15`（state.json version:1）；schema 幾乎全部 `additionalProperties:false`。
- 情境：出第 2 版格式時，舊 node 的 tasks.json／members.json／state.json 全被新程式拒絕，新程式寫的檔舊程式也拒絕；10,000 個 git repo 各自持有狀態檔，沒有「誰負責升級、升級失敗怎麼回退」，整棵樹只能一次全停、手動轉檔。
- 方向：至少寫下 (a) 讀舊版寫新版的升級責任在哪支程式；(b) 是否允許可選新增欄位（放寬 additionalProperties 或明列 ext）；(c) daemon 與 node 程式版本不一致時誰拒絕。

### 設-6．同一份 LLM／工具結果在 agent repo 存兩份、池端再一份、git 歷史再一份，而 git 歷史回收「先不管」

- 位置：`spec/protocol/agent-tasks.md:45`（`state/messages/responses/<id>.json` 完整原 bytes）與 `:55`（`state/work/<attempt_id>/response.json`）；`spec/protocol/work.md:42`（池端 jobs/result.json）；`spec/protocol/node.md:111`（outbox 刪了「原檔仍在 git 歷史裡」）；`spec/base/storage.md:39`、`spec/protocol/ops.md:63`（git 歷史回收先不管）。
- 代價：長期跑的 agent，每次 LLM 回覆在自己的 repo 寫兩份追蹤檔＋一次 outbox 增刪，repo 只增不減，git 越來越慢；清理（P-716）只搬日常檔，歷史不縮。
- 方向：state/work 的 response.json 改成引用 state/messages 那份；或明訂 repo 大小預期與 `git gc`／squash 的維護步驟。

### 設-7．git 2.35 預設不 fsync 鬆散物件，「commit 成功後才刪原件」在斷電時不成立

- 位置：`spec/daemon.md:63`（最低 git 2.35）；`spec/tick.md:53`（commit 成功才刪收件原件）；`spec/protocol/node.md:109`；`spec/base/storage.md:19`（自己寫的檔案有 fsync，但 git 提交沒提）。
- 情境：tick commit 回成功、刪掉 requests/ 原件，機器隨即斷電；git 2.35 的 `core.fsyncObjectFiles` 預設 false，物件可能還在記憶體快取，開機後 HEAD 指向壞物件，訊息連原件都沒了。spec 對自己寫的 JSON 檔都要求 fsync，唯獨最核心的 git 提交沒有。
- 方向：建 node 時設 `core.fsyncObjectFiles=true`（2.35 可用），或最低版本提到 2.36 並設 `core.fsync=all`；驗收加一條斷電模擬。

### 設-8．「哪裡出了事」散在六個地方，跨 node 追一件工作要對三套 ID

- 位置：node 事項 `.aos/attention/`（`spec/protocol/ops.md:11`）；daemon 事項 `state_dir/attention/`（`:13`）；once 旁檔 `<inst>.err`（`spec/protocol/daemon/provision-and-runner.md:70`，另一種 schema）；`.aos/runner-stderr.log`（`:53`）；git 目錄內擋板 `aos/tick-blocked`（`spec/protocol/node.md:101`）；`.aos/alarms/`（`:113`）；node.show 的 last_tick（`spec/protocol/daemon/registration.md:34`）。跨 node：agent 的 request_id → kernel forward 另配 forward_id（`spec/protocol/kernel-tasks.md:106`）→ 池的 attempt 目錄前綴（`spec/protocol/work.md:31`）。
- 代價：「這句話卡在哪」要先 `attend ls`，再看三個 node 的 state/、jobs/、runner-stderr.log 與 git log；`.err` 與 attention 是兩種格式做同一件事（「runner 沒啟動」）。
- 方向：(a) `.err` 內容直接用 ops-attention 形狀，工具只讀一種；(b) 沿路保留原 request_id 當關聯鍵，加一個 `aos work trace ID` 唯讀指令；(c) 接受，補一頁「除錯時看哪裡」的操作說明。

### 設-9．壞掉或投不回去的收件原件永遠留在 `requests/`，每格重掃、重報，沒有清理路徑

- 位置：`spec/protocol/messages.md:36`（P-303：無法回件「保留原件及本地錯誤供修正」）；`spec/protocol/node.md:52`（P-202：沒有合法 ID 或回址的「只留本地診斷」）；`spec/protocol/README.md:35`（P-004：壞件不產生 null.json）；`spec/base/storage.md:35`、`spec/protocol/ops.md:53`（未消費收件永遠保留，aos-clean 不碰）。
- 情境：任何有投件權的人丟一個壞 JSON 進來就永久留著；tick 每格首列一次 requests/（P-202），每格重印同一行錯誤；上萬 node 累積後掃描成本上升。
- 方向：(a) tick 診斷後改名成點開頭檔（`.rejected-<id>.json`，P-003 說點開頭不處理）留現場；(b) 過保留期後由 aos-clean 刪；(c) 永遠留著，但 attention 只寫一次。

### 設-10．daemon 當掉或 node 解除後留下的空 cgroup 目錄（`n-*`、`once-*`、`task-*`）誰移除，沒寫

- 位置：`spec/daemon.md:45`（重啟只殺程序）；`spec/protocol/work.md:51`、`spec/base/execution.md:21`（正常路徑「移除 leaf 前保存量測」）；`spec/protocol/node.md:78`（只清上一格的 `task-*`）；`spec/protocol/resources.md:48`（`usage_us` 是框存續期間累積，重建後不可接著取差值）。
- 代價：上萬 node、每次 once 一個框，長期運行累積空目錄；框重建後用量歸零。
- 方向：B-603 補「重啟後清空並 rmdir 沒有登記對應的框」，B-604 補「解除登記後 rmdir 該 node 框」。

### 設-11．沒有 project quota 時「定期掃資料夾」，誰掃、多久掃一次沒定

- 位置：`spec/base/identity-resources.md:47`、`spec/protocol/resources.md:85`（「定期掃資料夾量用量」）；`spec/protocol/kernel-tasks.md:59-65`（P-804 只說重測與量到的資料存哪）。
- 代價：對上萬 node 每格 du 一次不可行。
- 方向：放進 kernel.json 一個間隔或綁在 `usage_max_age_ms`，並註明只量直接成員。

### 設-12．tick 自己也在 node 的 `memory.max` 之內，「收尾程序不能困在成員自己的上限內」對任務層收尾不成立

- 位置：`spec/base/execution.md:37`（B-204：收尾程序不能困在成員自己的 memory.max 內）；`spec/protocol/node.md:78`、`spec/daemon.md:77-80`（tick 在 `n-<h>/tick`，上限寫在 `n-<h>`）。
- 情境：任務把記憶體吃滿，做 `cgroup.kill`／rmdir 的 tick 本身在同一上限裡，可能一起被 OOM 殺掉，殘留交回 daemon。
- 方向：(a) 接受（daemon 的 B-603 兜底）並改 B-204 說法；(b) `tick` 葉獨立於上限之外（要改框層級，tick 的用量就不算 node 的）。

### 設-13．多 UID 部署下三個檔案寫權沒交代：daemon 寫 `.aos/runner-stderr.log`、成員身分寫 kernel 的 `.aos/jobs/`、once 單檔的 runner 診斷落點

- 位置：`spec/protocol/daemon/provision-and-runner.md:53`、`spec/protocol/node.md:22`（daemon 每格覆寫 node 的 `.aos/runner-stderr.log`）對 `spec/protocol/node.md:133`（P-208 只授 daemon 對 `.aos/attention/` 的寫權）、`spec/protocol/agent-tasks.md:182` 與 `kernel-tasks.md:158`（`aos node new` 的產物清單沒有這個檔）；`spec/protocol/work.md:47`（外層 inst 的 `user` 是成員身分）、`:33-45`（stdout.bin／result.json 都寫在安排工作的 node 的 `.aos/jobs/` 下）對 `spec/protocol/node.md:131-139`（P-208 只講收件區權限）、`kernel-tasks.md:148`（只有 agent 自跑才提「jobs 路徑權限」）；P-109 只定義資料夾 node 的診斷落點，once 單檔沒說（原型 G-4 把它丟 /dev/null）。
- 情境：daemon（通用帳號）要在成員帳號擁有的 `.aos/` 裡建檔，每格開檔失敗；kernel 帳號建的 jobs 目錄，成員 UID 的 aos-work 寫不進 result.json，工作一律 start_failed。
- 方向：P-208 補 daemon 對 runner-stderr.log 的寫權（或改由 runner 以目標身分開檔）與 jobs 目錄給成員帳號／共享群組寫權；P-109 補 once 的落點（`<inst>.runner-stderr` 旁檔或 /dev/null，擇一寫明）。

### 追加視角一：「資源分配的單位是一個表達式＝任意計算，但必須符合特定規格、能被 Linux 管制；外部計算當外部函式庫」

### 設-14．spec 沒有一個統一的「可排程計算」定義：五種被排程／被限制的東西各自一套啟動、逾時、取消、暫停、限制與結果

- 位置（每種單位的正本）：tick 格——`spec/protocol/daemon/registration.md:13`（interval／wake）、`:25`（pause 只擋下一格）；tick 任務——`spec/protocol/node.md:60-78`（P-203）、`:93`（P-204 只看退出碼）；once／工具 attempt——`spec/protocol/work.md:22`（timeout_ms）、`:49`（先提交、下格 register＋wake）、`:57-67`（work-result）、`:79-93`（work.cancel）；LLM attempt——`spec/protocol/llm-work.md:13`、`:28`（timeout_ms）、`:42-48`（llm-result）；agent 一輪（一則 input）——`spec/protocol/agent-tasks.md:81`、`:89`、`:110`（agent-reply）；run——`spec/scheduling/runs.md:5`（軟性分組，非排程單位）。
- 對照表（「無」＝spec 沒寫）：

| 單位 | 怎麼啟動 | 逾時 | 取消 | 暫停 | Linux 框 | 結果形狀 | 事前成本 |
|---|---|---|---|---|---|---|---|
| tick 格 | daemon 到期／wake | 無 | 無（只能 unregister 排空） | node.pause 擋下一格 | `n-<h>/tick` | 退出碼＋summary | 無 |
| tick 任務 | tick 依序 exec | **無** | **無** | 無 | `task-N` | 退出碼，無結果檔 | 無 |
| 工具 once | 先提交、下格 register＋wake | timeout_ms 60 s | work.cancel（只 kernel work 任務） | 無 | `once-<h>` 在 parent 框 | work-result | 無（只有並行數） |
| LLM attempt | 池 tick 建 once | timeout_ms | 不支援（裁-5） | 無 | once 框只管本機程序 | llm-result 塞在 work-result 的 stdout | token 用 bytes 估（P-811） |
| agent 一輪 | 收件觸發 | 無 | 無（裁-10） | 無 | 不是單位，只透過 node 框 | agent-reply | 無 |

- 問題：使用者說的「表達式」在 spec 裡沒有名字；「計算必須符合的規格」散在 inst（怎麼啟動）、B-103／C-03（結果）、B-203（取消）、P-401（逾時）、B-605（限制框），而且每種單位只覆蓋一部分。最明顯的洞：**tick 任務沒有逾時也沒有取消**——一個卡住的任務讓 node 永遠 running、下一格永遠開不了（B-602 不重疊），除了 daemon 重啟沒有任何辦法；agent 一輪沒有任何限制；「成本事先不知道怎麼辦」只有 LLM 有答案（估 token、占並行、事後 usage），工具完全沒有事前成本概念，admission 只看並行數（`spec/protocol/resources.md:75`）。
- 方向：(a) 在 terms 或 contracts 加一條「可排程計算」的最小契約（名字、啟動、逾時、取消、暫停、限制框、結果形狀、成本估計），把五種單位對上去、缺的補；(b) 把 tick 任務也做成 once 的形狀（每任務一份 inst＋result），把「tick 任務」與「once」合成一種單位；(c) 維持各自一套，但至少補 tick 任務的逾時與取消。

### 設-15．外部計算（Linux 管不到的部分）spec 只管 LLM chat 一種，而且是寫死的特例；任何工具打遠端 API 的成本、限流、取消完全沒有掛勾

- 位置：`spec/scheduling/llm.md:23`、`:37`（只有 LLM 池有共享限制與 unknown 規則）；`spec/protocol/kernel-tasks.md:124-128`（token 估算與窗口）；`spec/protocol/resources.md:85`（網路首版只記用量、不限速）；`spec/protocol/agent-tasks.md:33-35`（工具是任意 argv，只驗參數 schema）；`spec/protocol/work.md:91`（取消不撤銷外部效果）；`spec/tick.md:49`（API／寄信等不可逆後果不還原）；`spec/protocol/llm-work.md:30-38`（LLM 格式寫死 OpenAI Chat Completions 子集）。
- 問題：使用者的方向是「外部計算（例如量子計算）當外部函式庫管」；spec 裡唯一有「外部成本」概念的是 LLM 池（token 估、窗口、usage、429、unknown 占用），而它是用 `llm.chat`／`aos-llm-call`／OpenAI 子集寫死的。第二種外部計算（另一種 API、量子後端）要從頭再寫一套 method、程式、schema、池狀態。工具呼叫遠端 API 時：事前成本不管、並行不管、限流不管、取消只殺本機程序、遠端結果不明就 unknown 放 30 天。agent 直連檔更是「aos 完全不管」。
- 方向：(a) 把 LLM 池抽成通用「外部資源池」（請求檔、池 node、窗口／並行、usage、unknown 占用），LLM 只是第一個實例，第二個外部函式庫只需換 adapter；(b) 接受首版只有 LLM 是受管外部計算，其他遠端呼叫算工具、不管，並在 README 原則段明寫；(c) 在工具定義（P-702）加可選的「外部成本／所屬池」宣告，讓 kernel 用同一套 admission。

### 追加視角二：「現有 OS 都是單一 kernel，我要做多層、多個 kernel」

### 設-16．中間某層 kernel 卡住時，它底下整棵子樹會靜靜停擺；上層只看得到一個可能過時的摘要，沒有接手、告警或失聯逾時的規則

- 位置：`spec/protocol/node.md:101`（擋板只停本 node）；`spec/protocol/daemon/registration.md:30`（P-105 停格只針對那個 node）；`spec/protocol/kernel-tasks.md:55`（成員只由自己的 kernel 叫醒）、`:26`（agent 省略 interval）；`spec/protocol/messages.md:85`、`:87`（summary 的 needs_attention；「過時／缺失不等於 idle」但沒說要怎麼辦）；`spec/scheduling/admission.md:7`（上層只看下層摘要）；`spec/daemon.md:41`（只有 daemon 重啟才逐層重建）、`:55`（停用 kernel 時才處理其子樹）。
- 情境：kernel B 的 tick 因 commit 故障寫了擋板，daemon 停 B 的格。B 的成員仍在 daemon 登記，但 agent 沒有 interval、靠 B 叫醒→全部停擺；經 B 轉交的 LLM 請求也停；B 的 summary 不再更新，父 A 看到的是過時摘要。沒有「A 代 B 叫醒孫輩」（P-103 祖先 owner 其實有 wake 權）、「A 自動 pause B 的子樹」、「摘要多久沒更新算失聯」的規則。多層 kernel 的核心承諾——一層壞了不拖垮別隊——只做到「別隊不受影響」，沒做到「這隊有人接」。
- 方向：(a) 父 kernel 對子 kernel 設「摘要過期上限」，超過就寫事項並可選擇代管（直接叫醒孫輩或代轉交）；(b) 只寫事項，人處理；(c) 接受，明寫「一層卡住＝整棵子樹停到人修好」。

### 設-17．跨分支（兄弟子樹）投件在多 UID 部署下沒有可佈建的路：helper 只會建帳號與同名主群組，沒有任何「共享群組」動作

- 位置：`spec/base/transport.md:13`（第九批：跨隊有權限就直投，不經上層轉送）；`spec/protocol/node.md:133`（P-208 首版只用共享群組、可配 setgid 目錄）；`spec/protocol/daemon/provision-and-runner.md:11-15`（P-107 五種動作：account_create 只建同名主群組、chown「不收任意 GID」、沒有建群組／加成員／chgrp）；`spec/protocol/kernel-tasks.md:150`（「其他群組由有權建立者配置」）。
- 情境：A 隊 agent 要投 B 隊 agent 的 requests/，兩者不同 UID，需要一個兩邊都在的群組並把目錄設 setgid；aos 的固定動作做不到，「由有權建立者配置」＝管理員手動 root 操作，每一對跨隊關係做一次。LLM 池若在別的分支，同一條路也要手動開。上萬 node 時跨隊協作等於不可用。
- 方向：(a) helper 加 `group_create`／`group_add`／`chgrp` 固定動作並納入 provision 授權；(b) 首版明寫跨分支投件只在單帳號部署支援；(c) 跨分支一律經共同祖先轉交（與第九批相衝，要使用者裁）。

### 設-18．層數變深時每一跳至少一個 tick 間隔，來回要約 2×層數秒；所有中間 kernel 都得每秒常駐 tick

- 位置：`spec/protocol/kernel-tasks.md:26`（子 kernel 建議 1000 ms）、`:55`（wake 要先看見收件）；`:104-109`（P-809 轉交每跳一格＋commit，回件再一格）；`spec/protocol/node.md:109`（先 commit 再投）；`spec/daemon.md:11`（kernel 本格結束就退出）；`spec/protocol/agent-tasks.md:75`（同格回件等下格）。
- 情境：agent → 自己 kernel（轉交）→ 上層 kernel → 池：請求 3 跳、回應 3 跳，每跳等對方下一格（≤1 秒）＋commit；最少 6 秒才回到 agent，還沒算 LLM 本身，每多一層 +2 秒。同時所有 kernel 每秒 tick（設-4 的負載）。「多層」的代價沒有被量化或列進驗收。
- 方向：(a) 接受並寫進 V-04 當量測項（端到端喚醒延遲已提到，轉交鏈沒有）；(b) 轉交改成 kernel 只做授權（allowed_origins），請求直投池（P-208 已允許直投）；(c) 用門鈴（收件通知→IPC wake）縮短每跳延遲。

---

## 三、建議

### 建-1．systemd 服務範例的註解跟 B-303「服務啟動的 root 必須在設定寫 common_user」對不上

- 位置：`spec/daemon.md:103`（註解：「以 root 開＝sudo 模式（有 helper）；要單帳號模式就加 User=，並在設定寫 common_user」，ExecStart 直接以 root 跑）；`spec/base/identity-resources.md:37`（「直接用 root 或由服務啟動時必須在設定檔明寫一個非 root 帳號，否則拒絕啟動」）。
- 問題：systemd 以 root 啟動沒有 `SUDO_UID`，設定沒寫 `common_user` 就拒絕啟動；但註解讀起來像只有單帳號模式才要寫。照範例抄的人第一次啟動就被拒。
- 建議：註解改成「以 root 開＝sudo 模式，但服務啟動沒有 SUDO_UID，設定檔一定要寫 common_user；單帳號模式另加 User=」。

### 建-2．「首版 LLM 只有並行份額」與 P-811 必填 `tokens_per_window` 的關係沒說清

- 位置：`spec/scheduling/llm.md:39`（S-302：「token 預算先不做：首版 LLM 只有並行份額（P-505）」）；`spec/protocol/kernel-tasks.md:124-126`（每 scope 必填 `tokens_per_window`，每次 HTTP 用 bytes 估算 token 預留窗口）；`spec/protocol/schemas/kernel-llm-limits.schema.json`（required）。
- 問題：一個是 kernel 份額（只有 concurrent_requests），一個是池端 provider 限流窗口。兩者可以並存，但 S-302 讀起來像整個首版沒有任何 token 計量，實作者會不確定 `tokens_per_window` 是不是「先不做」的那部分。
- 建議：S-302 或 P-811 補一句「token 預算（花費上限）先不做；P-811 的 tokens_per_window 是 provider 限流窗口，不是預算」，並讓使用者確認它首版要不要做、要不要改可省。

### 建-3．取消流程有三個窗口沒定結果

- 位置：`spec/protocol/work.md:87-88`（P-411 只分「還沒建 marker」與「已建 marker＝在跑」）；`spec/protocol/kernel-tasks.md:90`（P-807：marker 先建、再 register／wake；「沒有可信結果、在途或從未執行證據就是 unknown，不因登記消失…」）；`spec/protocol/daemon/registration.md:28`（不存在目標回 not_registered）；`spec/base/execution.md:29`（B-203：尚無結果而先處理取消，收尾後即使 exit 0 也記 canceled）；`spec/protocol/work.md:88`（「已有完整結果檔就照原結果回，不改成 canceled」）。
- 三個窗口：(a) marker 建好、register 前當機或被拒時取消到了：unregister 回 not_registered、沒結果檔，P-411 只說「確認不了全空就 unknown」，但這種其實明確沒跑。(b) 「記 canceling」與「呼叫 unregister」是同格還是先提交再下格做沒說；同格做且 commit 失敗（P-205 還原），下格重處理時 daemon 說 not_registered、無 result.json，依 P-807 只能記 unknown 而不是 canceled。(c) daemon 殺 once 時 aos-work 不知道這是取消：它若來得及在 TERM 時寫 result.json（reason `signal`），P-411 就「照原結果回」，變成 failed/signal 而不是 canceled——結果隨競速而變。
- 建議：P-411 補 (a)「daemon 回 not_registered 且 P-807 可信證據證明從未開始，就當排隊中拿掉、回 canceled」；(b) 比照 register「先提交、下格才動」：本格只記 canceling 並提交，下格再 unregister，或明寫 phase=canceling＋not_registered＋無結果檔判 canceled；(c) 明寫 phase=canceling 時忽略 wrapper 寫出的 signal 結果、一律回 canceled（B-203 的精神）。

### 建-4．沒人宣告的 method：P-306 說「丟掉原件」，P-202 說「複製到 state/messages 再清原件」

- 位置：`spec/protocol/messages.md:63` 對 `spec/protocol/node.md:52`。
- 問題：一個留消費副本、一個直接丟；去重（P-304 靠已提交原件）會受影響。
- 建議：P-306 改成引用 P-202 的做法。

### 建-5．tick 篇與 CLI 篇的任務表欄位表沒跟上 `methods`，布局清單漏兩檔，tick 自己的 `aos-tick unclaimed` 提交沒進主規格與 P-205

- 位置：`spec/tick.md:17-26`（只列 id／kind／group／needs）、`spec/tick.md:43`（「每組成功便 commit」）；`spec/cli/commands.md:46`（「每項 inst 加 id/kind/group/needs、無 user」；布局列 `.aos/{inst.json,tasks.json,jobs/,summary/,outbox/,attention/}`）對 `spec/protocol/node.md:50`（`methods` 欄）、`:21-22`（`.aos/alarms/`、`.aos/runner-stderr.log`）、`:52`（tick 開格前自己回 -32601 並以 `aos-tick unclaimed` 提交）、`:99`（commit 訊息只定義 `aos-tick group …`）；`spec/cli/commands.md:43`（`aos node log` 預設只列 `aos-tick group`，`--all` 才含維護提交）。
- 問題：照 tick.md 或 CLI 篇手寫任務表會漏 methods，node 收任何請求都被回 -32601。主規格說「每組一 commit」，協議篇多一個組外 commit，讀主規格的人不會知道；`aos node log` 預設也會把它濾掉。
- 建議：tick.md、commands.md:46 各補 `methods` 與兩個檔；tick.md 補一行「開格前 tick 自己處理沒人宣告的請求並提交一次」；P-205 補 `aos-tick unclaimed` 的訊息格式並明說 log 預設列不列。

### 建-6．daemon 範例的 once 位置與 parent_id 對不上

- 位置：`spec/protocol/examples/daemon/list_result.minimal.valid.json:8-9`、`get_result.launch_failed.valid.json:5-6`（job 在 `/srv/aos/team/member/.aos/jobs/…`，parent_id 卻是 `/srv/aos/team`）；`spec/protocol/work.md:33`、`:49`（job 資料夾建在「安排工作的 node」；agent 自跑時 parent_id 是自己）。
- 問題：job 目錄在成員樹裡＝成員自跑，parent_id 應是 `/srv/aos/team/member`；由 kernel 代跑則目錄應在 `/srv/aos/team/.aos/jobs/`。前綴雜湊本身是對的（`640b231841e0290f`＝sha256("/srv/aos/team/member") 前 16 hex，我算過）。
- 建議：把 parent_id 改成 `/srv/aos/team/member`，或把路徑改到 team 的 `.aos/jobs/`。

### 建-7．B-605 驗收沒涵蓋第十七批「有寫 cgroup_root 也搬程序」

- 位置：`spec/daemon.md:90`（驗收只寫「省略 cgroup_root 時原層只剩子層」）對 `:67`（第十七批：有寫也比照）。
- 建議：驗收句改成「省略、或該層有程序時，原層只剩子層」。

### 建-8．B-202 殘留「跨重啟再核對 boot ID、PID、starttime」，跟 B2「不要求跨重啟保存程序表、用 cgroup 清」相牴觸

- 位置：`spec/base/execution.md:17` 對 `spec/daemon.md:45`（「不要求跨重啟保存程序表」）、`notes/verdicts/05-dependencies.md:100-103`。
- 建議：括號那句改成「重啟後的清法依 B-603，用 cgroup」。

### 建-9．寬限時間三套：helper.stop 寫死 2 秒，daemon 用可設定的 `shutdown_grace_ms`，inst 逾時 2 秒

- 位置：`spec/protocol/daemon/provision-and-runner.md:36`（helper.stop「TERM、2 秒後 KILL」）；`spec/daemon.md:45`、`:53`、`spec/protocol/daemon/startup-and-ipc.md:18`、`spec/protocol/daemon/shutdown.md:7`（`shutdown_grace_ms` 預設 2000、可設）；`spec/base/inst.md:73`、`spec/base/execution.md:19`（2 秒）。
- 問題：部署把 `shutdown_grace_ms` 設 10000 時，有 helper 的停法仍 2 秒就 KILL，沒 helper 則等 10 秒；同一個動作兩種行為。另外 kernel work 任務同步呼叫 unregister 會在 tick 內等到全空，P-800:11 又說「不在任務中等工具」，沒說這個等允許、上限多少。
- 建議：helper.stop 改成寬限由 daemon 帶入；P-411／P-806 註明取消時允許同步等到全空、等不到回 cleanup_failed 記 unknown。

### 建-10．任務結束後的殘留程序：B-202 說先 TERM 再 2 秒 KILL，P-203 說直接 `cgroup.kill`

- 位置：`spec/base/execution.md:19`（「需要清理時先 TERM，再按 inst 的 2 秒寬限 KILL」）對 `spec/protocol/node.md:78`（「還有程序就寫 cgroup.kill，等 populated 變 0 再 rmdir」）。
- 建議：二選一寫清楚（配合裁-4 一起定）。

### 建-11．S-301「沒裝任務、沒被 tick，請求就堆著」在第十七批後只剩一半成立

- 位置：`spec/scheduling/llm.md:21`、`:29`（驗收：「投給沒人處理的 node，請求留在對方收件區」）對 `spec/protocol/node.md:52`（有 tick 但沒任務宣告 `llm.chat` 的 node 會在開格時回 -32601 並清原件）、`:113`（鬧鐘只看「原件還在不在」，被 -32601 取走就算處理了、不響）。
- 建議：S-301 改寫成「沒被 tick 才堆著；有 tick 但沒人宣告就收到 -32601」，驗收跟著改。

### 建-12．B-501 仍寫「指令未對發件者開放就回 -32601」，第十七批後「開放」只看收件 node 的任務表，跟發件者無關

- 位置：`spec/base/transport.md:9` 對 `spec/protocol/messages.md:63`、`spec/protocol/node.md:52`；發件者授權相關的拒絕是 -32000 `work_not_authorized`（`spec/protocol/kernel-tasks.md:98`）。
- 建議：把「對發件者」拿掉。

### 建-13．B-203「取消指定 attempt」，P-411 是以原請求 RPC id（一件工作、可能多次 attempt）取消

- 位置：`spec/base/execution.md:27` 對 `spec/protocol/work.md:81`（材料是 `{request_id}`）。
- 建議：B-203 改成「取消指定工作（原請求）」，免得實作以為要逐 attempt 取消。

### 建-14．A-101、A-401 兩處過時引用

- `spec/agent/configuration.md:9`（agent 設定格式「見協議 node」）→ 實際在 `spec/protocol/agent-tasks.md:11-37`（P-701／702）。
- `spec/agent/tools.md:9`（工具 JSON 與 adapter「留協議篇下一輪定義」）→ P-702 已定義。
- 建議：改成引用 P-701／P-702。

### 建-15．P-804 說父配額「依 P-503 發布到 `public/quotas/<id>.json`」，P-503 沒有這件事，期望配額有兩個落點

- 位置：`spec/protocol/kernel-tasks.md:61` 對 `spec/protocol/resources.md:38-50`（P-503 只講 cgroup 對應）、`spec/protocol/resources.md:13`（P-501：父 kernel 存在自己 repo 的 `state/resources/`）、`kernel-tasks.md:30`（`state/resources/<id>.quota.json`）。
- 問題：`public/quotas/` 只在 P-804 出現一次，子 kernel 的 `quota_file` 該指哪份、誰同步兩份沒定。
- 建議：指向 P-501，並明寫 `public/quotas/` 是 `state/resources/` 的發布副本、何時發布。

### 建-16．inst 篇留了一句「100＝做完等產品退出碼約定也另定」，全 spec 沒有定

- 位置：`spec/base/inst.md:5`；全 spec 找不到「100」的約定（P-713 只有 101）。
- 建議：刪掉或標「未定」。

### 建-17．本地動作類指令（agent.say／recheck／quota.set／work.cancel）的 stdout `{"accepted":true}` 要變成檔案給 work-result 的 `stdout.path` 引用，落點沒定；範例乾脆填 null

- 位置：`spec/protocol/messages.md:32`（P-302：業務 JSON 是該指令的 stdout）、`:69-75`（各命令 stdout）；`spec/protocol/work.md:57`、`:67`（P-403 stdout 是 `{path,bytes,truncated}`，path 絕對路徑）；`spec/protocol/kernel-tasks.md:84`；`spec/protocol/examples/messages/command-result.minimal.valid.json:12`（stdout:null）。
- 問題：任務在程序內處理請求，沒有真的 exec 一支指令，「stdout」得由任務自己寫成檔案再填路徑；P-703／P-800 沒列這個落點。範例填 null 等於「沒有輸出證據」，跟 P-306 要求的 accepted 矛盾；發件者依 P-208 預設讀不到對方 repo，實際只能看 status。
- 建議：定一個落點（例如追蹤的 `state/messages/stdout/<id>.json`，隨清理遍歷一起清），或裁定「本地動作類命令 stdout 允許 null、只看 status」並改 P-306 表格。

### 建-18．P-304 說同 ID 重送要「補投原回應」，但待送回應投出後即刪、只留在 git 歷史，沒說去哪拿

- 位置：`spec/protocol/messages.md:46`（「已有已提交回應就補投原回應」）；`spec/protocol/node.md:115`（成功投件後移除待送檔）、`:111`（原檔仍在 git 歷史裡）；`spec/protocol/agent-tasks.md:85`（收件確認只更新 meta，沒存回應）。
- 建議：規定回應同時保存一份追蹤副本（例如 `state/messages/sent/<id>.json`，隨保留期清），或明寫「補投只在 state/work 有 response.json 的工作類命令適用，其餘回應不補」。

### 建-19．乾淨停機「接回尚未啟動的 once」，但發起者要「同 boot 登記」才能第一次 wake——重開後 boot_id 必變

- 位置：`spec/protocol/daemon/shutdown.md:21`（P-116：乾淨停機可接回尚未啟動的 once）；`spec/protocol/kernel-tasks.md:90`（P-807：marker 存在時「先核對同 boot 登記…可信登記證明從未開始才可第一次 wake」）；`spec/protocol/agent-tasks.md:120`（P-709 同句）。
- 問題：daemon 說接回可用，發起者字面上要求 boot 相同；實作可能一邊保留登記、一邊永遠不 wake，once 變孤兒。
- 建議：P-807／P-709 改成「daemon 目前登記且 last_tick:null」即算從未開始；或 P-116 改成乾淨停機也不接回 once。

### 建-20．`aos-llm --config`：P-405 說絕對路徑，範本給相對 `config/llm-pools.json`；aos-llm-call 的設定是不是派出時凍結的副本也沒定

- 位置：`spec/protocol/llm-work.md:13`（「`aos-llm --config <絕對設定路徑>`」「`aos-llm-call…--config <絕對設定路徑>`」）；`spec/protocol/kernel-tasks.md:169`（範本 `aos-llm --config config/llm-pools.json`）；`spec/protocol/work.md:100-101`（P-408 「C 含本次派出時固定的必要設定」）；`spec/protocol/llm-work.md:24`（「派出時只固定該次工作需要的設定值及憑證引用」）。
- 問題：相對路徑基準沒像 P-605 那樣寫明；aos-llm-call 若讀同一份池設定，派出後改 endpoint 會影響在途嘗試，跟「派出時固定」矛盾。
- 建議：明寫相對路徑基準（node 根），並規定 aos-llm 派出時把固定值寫進 W/（例如 `W/config.json`），aos-llm-call 只讀那份。

### 建-21．agent-context 範例的工作目錄還是沒加發件者前綴

- 位置：`spec/protocol/examples/agent-tasks/agent-context.minimal.valid.json:5`、`agent-context.negative-estimate.invalid.json:5`（`state/work/attempt-1/request.json`）對 `spec/protocol/work.md:31`（P-402：`state/work/<attempt_id>/` 一律指 `<前綴>-<attempt_id>`）；第十六批第 6 條只改了 kernel-work-state 與 daemon 範例（`notes/verdicts/07-review-fixes-and-proto-gaps.md:17`）。
- 建議：兩份改成 `state/work/d38275629dba15f1-attempt-1/request.json`（`/srv/aos/a` 的 sha256 前 16 hex，我算過）。

### 建-22．node.show 範例的 cgroup 路徑不是 B-605 的命名

- 位置：`spec/protocol/examples/daemon/get_result.minimal.valid.json:17`（`"path":"/sys/fs/cgroup/aos/team"`，node 是 `/srv/aos/team/member`）對 `spec/daemon.md:78`、`spec/protocol/daemon/provision-and-runner.md:21`。
- 問題：範例暗示 cgroup 用人類可讀路徑，而且是父 node 的路徑；照 B-605 應是 `<子樹>/n-d20539a311399b5e/n-640b231841e0290f`。schema 驗不出來，只有範例在教錯。
- 建議：改範例路徑；順便在 P-106 說清楚 `cgroup.path` 回的是 node 分支（`n-<h>`）還是 `tick` 葉。

### 建-23．`signal` 的合法範圍三個 schema 各寫各的

- 位置：`spec/protocol/schemas/daemon-rpc.schema.json:372-378`（LastTick 1～64，文字 `spec/protocol/daemon/registration.md:46` 同）、`daemon-runner-report.schema.json:53-56`（1～127）、`work-result.schema.json:56-66`（1～2^53）。
- 問題：同一個 wait 訊號值沿 runner 回報 → daemon last_tick → work-result 傳遞，範圍越傳越不同。
- 建議：統一成 1～64（Linux 實際上限），或全部只寫 ≥1。

### 建-24．llm-result 每個 attempt 可帶 `retry_at_ms`，P-407 文字沒有這欄，且和 kernel-work-state 重複存

- 位置：`spec/protocol/schemas/llm-result.schema.json:101`、`:209` 對 `spec/protocol/llm-work.md:42`（attempt 欄位列表沒有它）、`:48`（「池 tick 保存 retry_at_ms」）、`spec/protocol/schemas/kernel-work-state.schema.json:63`（`llm.retry_at_ms`）。
- 建議：P-407 補列這欄並說明用途，或從 llm-result 刪掉、只留 kernel-work-state。

### 建-25．走查前置條件的理由已被第十七批取代

- 位置：`spec/cli/walkthrough.md:7`（要先把終端 A 的 shell 放進 `$CG/shell` 葉框，「不放子樹根，免得擋住 daemon 開 controller」）對 `spec/daemon.md:67`、`spec/protocol/daemon/startup-and-ipc.md:19`（第十七批：那層有程序，daemon 自己開 `daemon` 子層搬進去）。
- 建議：前置改成「shell 可留在子樹根，daemon 啟動會把它搬進 `daemon` 葉」，或註明保留舊做法只是為了不驗這一段。

### 建-26．P-202 的兩份 methods 範例沒在正文說明，反例驗的不是正文說的那種錯

- 位置：`spec/protocol/node.md:52`（「兩項任務宣告同一 method 算任務表錯」）、`:56`（正文只連 minimal／user_override 兩例）對 `spec/protocol/examples/tick/tasks.methods-duplicate.invalid.json:18-21`（同一任務內寫兩次 `agent.say`，由 schema `uniqueItems` 擋）、`schemas/tick-tasks.schema.json:85`（跨項唯一性「由 tick 驗」）。
- 建議：P-202 補一句連結兩份範例，並註明「跨任務重複 schema 驗不到，由 tick 驗」（P-007 要求每個反例在正文說明）。

### 建-27．`aos agent config recheck` 的結束碼 1 一碼兩義

- 位置：`spec/protocol/agent-tasks.md:151`（recheck：「鎖忙 75、保存失敗 1、提交／還原故障 3」，沒寫無效回幾）對 `spec/cli/commands.md:95`、`spec/cli/walkthrough.md:172`（「仍無效回 1」）。
- 建議：P-712 明寫；配合裁-3 一起定。

### 建-28．notes：kernel-tree.md 掛在「現行方向」下且自稱「以本篇為準」，但多處已被後批推翻沒標

- 位置：`notes/README.md:11`；`notes/2026-09-29-kernel-tree.md:5`（「以本篇為準」）；`:27`（「daemon…不存狀態」，對 `spec/daemon.md:39` 的 state.json）；`:42`（「key…agent 與工具讀不到」，對第八批沒 helper 不受保護、直連 key 必須 agent 讀得到，`spec/scheduling/llm.md:17`、`:25`）；`:48`（「交給帳本」沒劃掉，對 `spec/tick.md:43`）；`:102-103`（待定 2、3 仍列待定，但 `spec/protocol/daemon/registration.md:9`、`:15` 已定）。
- 建議：頁首加「09-29 晚起以 spec 為準，本篇為架構背景」，改掉「以本篇為準」；四處加「已被第 N 批取代／已定於 P-104」。

### 建-29．notes：llm-scheduler-options.md 三處跟第十五批相反，仍用已改名的「不管」

- 位置：`notes/2026-09-29-llm-scheduler-options.md:14`（交給 endpoint「照 429 等」，對第十五批只轉發、不重試，`spec/scheduling/llm.md:12`）；`:19`（「預算首版只算 token」，對「token 預算先不做」，`llm.md:39`）；`:28`（「不管」檔由 agent 開 aos-llm-call，對直連 aos 完全不管，`llm.md:13`、`:17`）；`:13`、`:17`、`:28` 用「不管」沒註明改名；`:3` 連結寫 S-301～S-306 但 S-306 已刪。
- 建議：改成現行說法或加「已被第十五批取代」；「不管」旁加「（現名直連）」。

### 建-30．notes：verdicts/05 第十四批第 2、3 條沒標被同份「追加 1」取代

- 位置：`notes/verdicts/05-dependencies.md:14`（「quota、systemd 都是可選項：有就用」）、`:21-22`（「沒有 systemd 的 Linux 也要能跑…改成降級執行」）對同檔 `:67`（追加 1「初版不使用 systemd」）、`spec/daemon.md:63`。
- 建議：三處加「（已被追加 1 取代）」。

### 建-31．notes：verdicts/01 殘留「控制帳本」「控制側」「A-506」「P-011」等已被推翻或不存在的說法

- 位置：`notes/verdicts/01-notes-review-1-10.md:27`（「控制帳本配發的序號…C-03 加 seq／ready_seq」，對 `spec/scheduling/admission.md:37`；contracts.md 沒有 ready_seq）；`:23`（「控制側代發服務」，對第九批用池 kernel node 帳號）；`:41`（A-506 已刪，`spec/agent/README.md:42`）；`:44`（「協議篇 P-011」不存在，check_ids 報錯；內容現在對應 `spec/agent/configuration.md:13-17` A-102 與 `spec/protocol/README.md:59` P-008）。
- 建議：各處加取代註記；:44 改指 A-102／P-008。

### 建-32．notes：between-ticks-configuration.md 引用已刪的 B-305 與舊條文標題，讓 `check_ids.py` 永遠回 1

- 位置：`notes/between-ticks-configuration.md:5`（「對應 B-305」，全 spec 無定義）；`:11`（「A-102『每輪固定版本』與 B-302『登記改版先排空』改為建議預設」，對現行 `spec/agent/configuration.md:13` A-102 標題與 `spec/base/identity-resources.md:17-25` B-302 內容都不是這樣）。
- 問題：加上建-31 的 P-011，`check_ids.py` 跑完永遠「找不到 2 個」、結束碼 1，`spec/protocol/README.md:75` 列它為驗證工具卻不能當「全過」用。
- 建議：寫成「原 B-305（已刪）」；:11 改述為現行內容。

### 建-33．notes：base.md 兩句以「spec 目前」「09-29 裁定」口吻描述已改掉的東西

- 位置：`notes/base.md:35`（「spec 目前把收件的 server 角色交給控制接入口（B-501／B-502），tick 只是發出 checkpoint.commit 的一方」，對 `spec/base/transport.md:15` B-502 已刪、`spec/base/storage.md:25-27` B-403 已刪）；`:25`（「09-29 裁定為極小 root helper：主 daemon 不是 root」，對第八批 sudo 開 daemon 再 fork helper，`spec/base/identity-resources.md:31-33`）。
- 建議：兩句加「（後續已改：現見 B-501／tick、B-303 sudo 模式）」。

### 建-34．notes：verdicts/04 三處「之後要改／待釐清」已落實或被取代沒標

- 位置：`notes/verdicts/04-late-day-directions.md:38-41`（沒標被第十五批第 5 條取代，同檔 :80 同題有標）；`:47-52`、`:87`（「spec 之後要改…只列、不改」「之後只需補：串流、轉發任務、target_node 可為 null、schedule 兩欄位」——全部已落實，`spec/scheduling/llm.md:7-13`、`:61-69`）。
- 建議：加「已於第十五批落實」或劃掉。

### 建-35．notes：wsl-machine-check.md 引用的是重寫前 spec 的條文內容

- 位置：`notes/2026-09-29-wsl-machine-check.md:28`（「B-303 要求 swap 設 0」）、`:34`（「B-302 啟動 probe 加三項檢查」）、`:38`（「B-604 的 30000 ms」）、`:40`（`quota_backend`）、`:45`（SQLite 索引、LLM 門票）；現行 spec 沒有 swap、`quota_backend`、SQLite（`spec/tick.md:43` 明說不用），B-604 寬限現為 `shutdown_grace_ms` 預設 2000。頁首只說「不代表建議已採納」，`spec/README.md:37` 把它當現行背景連結。
- 建議：頁首加一句「條號引用為 09-29 重寫前的 spec；swap 上限、probe、quota_backend 現行 spec 未規定」。

### 建-36．notes：probes/README.md 漏列 per-task-cgroup-cost 且自稱 09-28 快照；systemd-run-latency 的回連與前提過時

- 位置：`notes/probes/README.md:3`、`:16`（只列 systemd-run-latency；`per-task-cgroup-cost.md` 被 `spec/daemon.md:80` 與 verdicts/08 引用卻沒列）；`notes/probes/systemd-run-latency.md:3`（連到 verdicts 索引頁，內容實際在 `notes/verdicts/04-late-day-directions.md:13-17`）、`:5`（「daemon 若每次工具呼叫都用 systemd-run」是第十四批前的前提）。
- 建議：README 補一列、首句含 09-29；systemd-run-latency 連結改指 verdicts/04，:5 加「（初版不用 systemd，此數字僅供日後可選增強參考）」。

### 建-37．notes：verdicts/07 落 spec 補充仍留「有寫 cgroup_root 照舊」，已被第十七批 C2 取代；proto6/README 說「沒有新增 CLI、daemon」也過時

- 位置：`notes/verdicts/07-review-fixes-and-proto-gaps.md:27`（「只在省略 cgroup_root 時做，有寫 cgroup_root 的情況照舊」）對 `notes/verdicts/08-cancel-task-cgroup-and-gaps.md:24`；`proto6/README.md:3`、`:5`（「沒有新增 CLI、daemon…現行程式仍在 proto5」）對 `proto6/proto/README.md:1-3`（已有可跑的第一段原型）。
- 建議：07:27 加「已被第十七批 C2 取代」；proto6/README 入口同時指到 proto/。

---

## 四、要使用者裁定

### 裁-1．「檔案請求的 params 是完整 inst」＝有投件權就能以對方身分跑任意程式，UID 隔離、key 保護、取消核權都被這一條架空

- 位置：`spec/protocol/messages.md:63`（「envs、指示詞與 stdin 路徑照 inst，借權讀檔或換程式的風險由使用者承擔」）；`spec/base/transport.md:9` 同句；`spec/base/inst.md:48`（`argv[0]` 用 envs 疊完的 PATH 找）；`spec/protocol/node.md:137`（agent 必須能投進 kernel 與池的 requests/）；`spec/scheduling/llm.md:25`、`spec/protocol/llm-work.md:9`（有 helper 配合帳號隔離就能保護 key）；`spec/base/identity-resources.md:7`。
- 情境：agent A 投一封 `llm.chat`，params 的 envs 設 `PATH=/tmp/x`，裡面放自己寫的 `aos`。池 node 展開後 argv 仍是 `aos llm chat`、method 對得上，於是用池 node 的帳號、在池 node 的 cgroup 裡執行 A 的程式：讀 key_ref、改 kernel 設定、用 kernel 的額度。使用者已裁「風險自負」，但 spec 別處同時承諾「有 helper 就能保護 key」「工作 leaf 必須放在父框內」——這兩個承諾對所有有投件權的關係（每個 agent 對其 kernel 與池）都不成立。
- 選項：(a) 接受，但把 S-301／P-405 的 key 保護說法改成「只對沒有投件權的人有效」；(b) 檔案 RPC 執行時固定用絕對路徑的 `aos`、envs 只准白名單或忽略、不展開指示詞——method 仍是指令，不改大方向；(c) 只對「同帳號」關係開放完整 inst，跨帳號只准 stdin 材料。

### 裁-2．agent 自己開的 once 做完不叫醒，但等結果時 ready=false、due=null，逐次放行的 agent 又沒有 interval——結果永遠沒人來收

- 位置：`spec/protocol/agent-tasks.md:104`（P-707 第十七批：「由 agent 自己（下次被叫醒或定期 tick 時）去看」）、`:75`（P-704：只等結果則 ready=false，無到期事務時 due_ms=null）；`spec/protocol/kernel-tasks.md:55`（P-803 只在有收件、ready、due 到期或 bootstrap 才叫醒）、`:26`（逐次放行的 agent 省略 interval_ms）；`spec/agent/README.md:33`、`spec/daemon.md:11`（agent 通常不設定期）。
- 情境：`tools.target_node=null` 的 agent 派工具後結束本格，工具 10 秒做完，agent 要等到下一則外來訊息才會發現。裁定只說 aos 不主動叫醒，沒說 agent 靠什麼機制看。
- 選項：(a) agent 在等自跑 once 時把 `due_ms` 設成輪詢時間（例如 timeout_ms 或固定短間隔），讓 P-803 到期叫醒——等於 aos 還是會因到期叫醒，只是不因 once 完成叫醒，且每次多開一格；(b) 這類 agent 必須設 `interval_ms`；(c) daemon 在 once 收尾後對 parent 做一次 wake（推翻第十七批第 3 條）；(d) 維持現狀，在 P-707 明寫這是接受的行為。

### 裁-3．agent 的設定檢查要不要跟 kernel 一樣「跑完就回 0」（同時決定必-8 的 validate-only 用哪組碼）

- 位置：`spec/protocol/kernel-tasks.md:74`（第十七批：一般 check 寫好紀錄就回 0）、`spec/cli/commands.md:67` 對 `spec/protocol/agent-tasks.md:149-151`（agent check／recheck 無效回 1）、`commands.md:94-95`、`walkthrough.md:172`；`spec/protocol/ops.md:81`（P-609 把兩者寫成同一套流程）；裁定來源 `notes/verdicts/08-cancel-task-cgroup-and-gaps.md:30`（C1 只點名 kernel P-805 與第 31 列）。
- 問題：同名「設定檢查」，一個把「設定壞」當 0、一個當 1。agent 的 check 不在任務表裡、不會拖垮 group，維持 1 有道理；但腳本或 agent 依結束碼判斷會被兩套規則坑。
- 選項：(a) agent 也改成「跑完寫紀錄就回 0」，統一；(b) 維持現狀，在 P-609 或 P-712 明寫「agent check 不是 tick 任務，所以無效回 1」；(c) 只統一 validate-only（必-8）為同一組碼（0／2 或 0／1），一般 check 各自保留。

### 裁-4．任務主程序 exit 0 但留下後代被 tick 殺掉，這項任務算成功還是失敗

- 位置：`spec/protocol/node.md:78`（任務結束有剩就 cgroup.kill、等空再 rmdir；前句「清不空就停止」）；`node.md:93`（P-204 以 wait 正常退出 0 判成功）；`spec/base/execution.md:21`（B-202 對 attempt：強制清理後代時記失敗）。
- 問題：group 要不要還原？B-202 對 attempt 說「記失敗」，P-204 對 tick 任務只看退出碼，兩種讀法都合理。
- 選項：(a) 算成功，只在 stderr 記 `descendants_killed`；(b) 算失敗、group 還原（與 B-202 一致）；(c) 算成功但寫一件待處理事項。

### 裁-5．LLM 請求與 agent 自跑 once 的取消：本輪明寫「暫不支援」，還是現在補欄位

- 位置：`spec/protocol/work.md:91`（「LLM 請求與 agent 自跑的 once 由持有它的 node 照同一規則處理；範本目前只有 kernel 的 work 任務宣告 work.cancel」）、`:83`（核權要靠接件時記下的擁有 UID）；`spec/protocol/kernel-tasks.md:169`（pool 任務 methods「無」）、`spec/protocol/agent-tasks.md:70`（agent 範本 methods 只有 agent.say）；`spec/protocol/schemas/kernel-forward-state.schema.json`、`agent-request.schema.json`（都沒有 `submitter_uid`、phase 沒有 `canceling`）；`notes/verdicts/08-cancel-task-cgroup-and-gaps.md:38`（「留下一輪」只寫「由誰宣告」，沒提欄位缺口）。
- 問題：投 work.cancel 給池 node 或 agent 現在會被 tick 回 -32601；原請求檔消費後就刪了，forward／agent 沒記 UID 就永遠核不了權，「同一規則」做不到。
- 選項：(a) 本輪明寫「LLM 與自跑 once 的取消暫不支援，投了會 -32601」；(b) 現在就讓 forward／pool 與 agent 任務宣告 work.cancel，並在 forward-state、`kernel.json` 的 llm、agent 的 work meta 加 `submitter_uid` 與 `canceling`。

### 裁-6．P-303 前段「接件前核對回址、回不了就不接納、保留原件」和第十六批「回應投不出去就報一次錯、丟掉」是同一件事的兩種處置

- 位置：`spec/protocol/messages.md:36` 同一段前半與後半；`notes/verdicts/07-review-fixes-and-proto-gaps.md:12`（第十六批第 2 條）。
- 問題：接件前發現回不了→原件永遠卡在收件區（連到設-9）；接件後才發現→做了工作、回應丟掉。兩階段不同處置沒說理由。
- 選項：(a) 接件前也照第十六批：報一次錯、消費掉原件、不執行；(b) 保留兩階段，明寫為何不同（接件前可以不做工，接件後不能重來）；(c) 拿掉接件前核對，一律做完再投、投不出就丟。

### 裁-7．「node 的擁有者」取根目錄 owner UID，可能跟 node 實際執行身分（inst user）不是同一人

- 位置：`spec/protocol/work.md:83`（P-411 擁有者＝node 根目錄的擁有 UID）；`spec/base/identity-resources.md:9`（身分「不由 node 資料夾位置決定」）；`spec/protocol/node.md:133`（P-208 只要求 node 帳號可讀寫 repo，不要求擁有）；`notes/verdicts/08-cancel-task-cgroup-and-gaps.md:37`（落 spec 隊自認的取法）。
- 情境：kernel 用自己帳號建成員資料夾、沒 chown，根目錄 owner 是 kernel；成員 node 自己跑的 tick 反而不算「擁有者」，取消自己持有的工作只能靠請求檔 UID 相同。
- 選項：(a) 維持根目錄 owner；(b) 改成「該 node inst 的 user」；(c) 兩者皆可。

### 裁-8．新增一個隔離帳號＝改 daemon 設定＋重開 daemon＝全殺在途工作

- 位置：`spec/base/identity-resources.md:11`（最頂層額度在 daemon 設定檔）；`spec/protocol/daemon/registration.md:9`（預授尚未存在的帳號名「只能由設定往下傳」，不支援萬用名稱）；`spec/protocol/daemon/startup-and-ipc.md:30`（設定於啟動讀定，修改後重開）；`spec/daemon.md:37`（重啟全殺）；`spec/terms.md:40`（目標一萬個 node）。
- 情境：要多開一個有自己 Linux 帳號的 agent，頂層 identity_grant 必須加這個名字 → 改 daemon.json → 重開 daemon → 所有在途 tick／once／LLM 呼叫被殺、變 unknown、不自動重做。上萬 agent 的部署每天都在加帳號。
- 選項：(a) 設定熱重載（只擴大 roots 額度、不動程序）；(b) 頂層額度允許範圍或前綴（例如 `aos-*`、UID 區間），與第十一批「不支援萬用名稱」相衝；(c) 接受，把「加帳號要重開」寫進部署說明。

### 裁-9．daemon 重開（升級、當掉）的寬限只有 2 秒，所有在途 LLM／工具全變 unknown 且永不自動重做，沒有「先排空再停」的模式

- 位置：`spec/protocol/daemon/startup-and-ipc.md:18`（shutdown_grace_ms 預設 2000）；`spec/daemon.md:53`、`spec/protocol/daemon/shutdown.md:7`（正常 Ctrl-C 也是 TERM→寬限→cgroup.kill）；`spec/scheduling/operations.md:9`（unknown 不自動重做）；`spec/protocol/agent-tasks.md:106`（unknown 停新副作用）；`spec/cli/walkthrough.md:90`（LLM timeout 例子 30 秒）。
- 情境：升級版本按 Ctrl-C，所有正在等 HTTP 的 `aos-llm-call` 2 秒後被 kill；每個對應的使用者輸入變 unknown，卡到人工處理或 30 天清掉。
- 選項：(a) 加 drain 模式：停新格、等在途 once 跑到自己的 timeout 再收尾；(b) shutdown_grace_ms 預設拉到與 LLM timeout 同量級；(c) 接受。

### 裁-10．人工介入只有 `attend done`；卡在 unknown 的使用者輸入沒有「當作失敗、繼續」的出口

- 位置：`spec/protocol/agent-tasks.md:90`（略過等待／阻擋的 input）、`:106`（unknown 停新副作用、記事項、不因改設定重跑）、`:189`（unknown 到期連同卡住的 input 整組清）；`spec/scheduling/operations.md:41`（done 只標完成）；`spec/cli/commands.md:122`（try-solve 以後再做）；`spec/protocol/messages.md:49`（不能換 ID 重送繞過 unknown）。
- 情境：使用者一句話觸發的 LLM 呼叫因 daemon 重開變 unknown。人看到事項、標 done，但 input 仍是「有 unknown pending」的阻擋狀態，agent 永遠跳過它，30 天後被清理。唯一出口是重講一次。
- 選項：(a) `attend done` 對 unknown 事項＝把那次嘗試記成 failed，讓 agent 對該 input 繼續；(b) 新增 `aos agent input cancel N ID`，把 input 標 canceled 並回一句 final；(c) 接受「重講一次」為唯一出口，但寫明。

### 裁-11．改一個 kernel 的 cgroup 上限要整棵子樹全空，頂層 kernel 幾乎永遠改不了

- 位置：`spec/protocol/daemon/provision-and-runner.md:23`（「核對整個框及後代全空才套用，否則 busy」）；`spec/protocol/resources.md:58`（逐筆暫停受影響子樹、清空後才套新值，「不能直接寫較低 memory.max 逼出 OOM」）。
- 問題：cgroup v2 的 `memory.max`／`cpu.max` 本來可以熱改；只有調低記憶體才有 OOM 疑慮。
- 選項：(a) 維持全空才改（接受頂層幾乎不能調）；(b) 允許熱改但只准調高、調低才要全空；(c) 允許熱改，OOM 風險由設定者承擔。

### 裁-12．agent 對 agent 的問答只能問一次：帶 `in_reply_to` 的回話只記 history，問的那方永遠不會因為收到答案而思考

- 位置：`spec/protocol/agent-tasks.md:81`（回話不建 queued input、不觸發 LLM）；`spec/agent/input.md:11`；`notes/verdicts/07-review-fixes-and-proto-gaps.md:15`（第十六批第 5 條）。
- 情境：agent A 用 agent.say 請 agent B 幫忙，B 的 final 回到 A 只被記錄；A 除非又被別的訊息叫醒，否則不會處理 B 的答案，委託鏈斷掉。這是第十六批「免得互回無限循環」的直接後果。
- 選項：(a) 維持，agent 間協作只能靠人或工具讀 history；(b) 回話「記錄且標 ready」但不自動回話（只叫醒、不再 say，一樣避免無限循環）；(c) 只有帶 `in_reply_to` 且對方也是回話時才靜音。

### 追加視角二（多層 kernel）要裁定的

### 裁-13．下層 kernel 自己的 LLM 池不受上層 LLM 份額約束；上層份額只在「經上層轉交」時生效，跟「下層不能超過上層」對不上

- 位置：`spec/scheduling/llm.md:23`（「頂層或下層 kernel 都可以有自己的池…上層分配與池端限制仍有效」）；`spec/protocol/kernel-tasks.md:110`（P-809：直接成員扣自己份額，只在轉交路線）；`spec/protocol/resources.md:75`（P-505 LLM 並行份額是每個 kernel 自己記）；`spec/protocol/kernel-tasks.md:143`（「kernel 不管」：agent 直投池）；`spec/protocol/messages.md:85`（上層只讀摘要 usage）。
- 問題：cgroup 是階層的，下層不可能超過上層；LLM 份額不是。kernel B 裝自己的池（自己的 key）時，A 對 B 的 LLM 份額根本量不到 B 的用量，「上層分配仍有效」在這條路線上沒有機制。
- 選項：(a) 明寫 LLM 份額只管經本 kernel 轉交的請求，自有池由該 kernel 自己負責（接受非階層）；(b) 要求下層池的用量彙整進摘要，上層以摘要事後扣、超額就停派；(c) 禁止下層自建池，池只能在頂層或明授節點。

### 裁-14．樹形寫死在 daemon 登記與 cgroup 路徑裡：不能換父、頂層只能從 daemon 設定改；重組樹＝重開 daemon＋全殺

- 位置：`spec/protocol/daemon/registration.md:9`（不得成環或換父）、`:7`（頂層只從設定載入，更新須改設定重開）；`spec/daemon.md:37`（重啟全殺）、`:78`（cgroup 框放在父 node 框下）；`spec/protocol/kernel-tasks.md:44-45`（members 清單改了只同步差異）。
- 情境：把 agent X 從 kernel B 搬到 kernel C：B rm、等 X 全空、unregister、C add、重登（cgroup 框要 rmdir 再在 C 底下重建、限制重設）。把一棵子樹升成頂層、或新增一棵頂層樹，必須改 daemon 設定重開（全殺）。「多個 kernel」的樹一旦建好就很難動。
- 選項：(a) 接受，寫一頁「搬 node／子樹的操作步驟」；(b) 允許 unregister 後帶新 parent 重登、cgroup 框跟著重建，spec 明定順序；(c) roots 允許由 daemon 帳號經 IPC 增刪，不重開。

### 裁-15．幾處其實還是偷偷假設「一台機器一個 daemon、一個瓶頸點」

- 一機一 daemon：一個 socket、一個 state.json、一棵 cgroup 子樹、一個 boot_id（`spec/protocol/daemon/startup-and-ipc.md:7-31`、`spec/protocol/daemon/registration.md:59-61`、`spec/daemon.md:65`）。兩個 daemon 各管一棵樹沒禁止，但 helper、委派各一份，跨 daemon 投件的叫醒不能走 IPC，只能靠 60 秒補查（`spec/protocol/messages.md:59`）。
- 帳號預授只能從頂層設定往下傳（`spec/protocol/daemon/registration.md:9`）→ 見裁-8。
- 「相同 provider 限制交同一池管理 node，不能靠同名 scope 跨 node 同步」（`spec/protocol/README.md:71`）→ 共用一把 key 的所有分支都得經過同一個 node，形成全樹瓶頸與單點。
- 資源只能由上往下給：`kernel.quota.set` 只准父配置權（`spec/protocol/messages.md:71`），兄弟子樹之間不能借，公平只在一個 kernel 之內（`spec/scheduling/admission.md:39`），沒有任何跨層優先權表達（上層無法說「這個子樹的互動任務優先」）。
- 選項：本輪只需決定要不要在 spec 明寫「一機一 daemon、一 daemon 多棵頂層樹、樹之間只靠檔案投件」這條邊界，並把池單點與帳號預授列為已知代價；或者把其中一兩項（例如 roots 可經 IPC 增刪、池可分片）列進下一輪。

---

## 附：自動檢查結果與沒問題的部分

- `python3 proto6/spec/check_ids.py`：986 個引用、193 個定義，找不到 2 個（都在 notes，見建-31、建-32），結束碼 1。spec 內全過。
- `validate.py`（用 `uv run --with jsonschema --with referencing`）：57 schema、205 範例全 PASS。
- 相對連結與錨點（spec 與 notes，含 proto5、archive、probes 交叉連結）全部存在。
- 第十六批 10 條、第十七批 A1～5、B、C1～3 與落 spec 補充：全部在裁定書所指位置找得到，且落法一致；attempt 前綴雜湊（`94a18415f07a8c0d`、`640b231841e0290f`、`910ff19802dbbc63`）都對。
- 裁定 01～06 被後批推翻的舊說法（帳本／總帳／控制側／單一控制寫入者／SQLite／systemd 必要／LiteLLM 進標準／「不管」／B1 分情況／ACL／AOS_TASK_ID／resolve／attention.put／舊 method 名／launch-error.json／inbox／非串流／每格重試）：spec 內都沒有殘留。
