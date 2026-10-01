← [審稿索引](README.md)

本輪先分工獨立審閱 `proto6/notes/`（排除 archive）與 `proto6/spec/`，按後批優先核對裁定、文字、schema 與範例；完成獨立發現後才讀 Fable 報告，再逐條回查原文、去重。第一段驗證 **79 條**；第二段列 **8 條新發現：必修 4、設計問題 1、建議 1、要使用者裁定 2**。我認為最嚴重的三條是：**Fable 裁-1 的借權執行與 key 隔離承諾衝突、新必-1 的資源故障連取消與收結果都擋住、新必-3 的兩個 daemon 可能互相清殺工作**。全程未修改 repo、未 commit。

自動檢查方面：57 份 schema、205 份正反範例全部通過；這只證明格式驗證符合目前 schema，不代表跨篇語意一致。`spec/check_ids.py` 檢查 986 個引用、193 個定義，找到兩個不存在的條號：`notes/between-ticks-configuration.md:5` 的 B-305，以及 `notes/verdicts/01-notes-review-1-10.md:44` 的 P-011。

## 一、對 Fable 報告的逐條驗證

下表沿用 Fable 編號。「部分成立」表示確有問題，但原報告的推論、影響範圍或修改建議需要縮小；不代表整條都應照單修改。

### 必修：9 條

| 編號 | 判定 | 理由 |
|---|---|---|
| 必-1 | 成立 | 多 UID 的 cgroup 委派流程確實缺一段：`proto6/spec/daemon.md:80` 要交給 node 帳號，`proto6/spec/base/identity-resources.md:35` 要 daemon 永久降權，`proto6/spec/protocol/daemon/provision-and-runner.md:21` 又規定由 daemon 自己建框、寫限制。沒有定如何跨 UID 委派並保留管理權；但不能進一步斷言所有群組權限配置都做不到。 |
| 必-2 | 成立 | `proto6/spec/cli/commands.md:42` 支援直接執行 tick；`proto6/spec/protocol/node.md:78` 卻以已有 node 框及委派權為前提。人手呼叫如何進框、核對既有框，或在哪個條件下拒跑，沒有接上。 |
| 必-3 | 部分成立 | `proto6/spec/protocol/kernel-tasks.md:45` 的「不自動殺工作」需要釐清，但 unregister 並非明定只能等、不准殺：`proto6/spec/protocol/daemon/registration.md:23` 引用的收尾規則，在 `proto6/spec/daemon.md:53` 有 TERM、寬限及 kill；`proto6/spec/protocol/work.md:88` 更明定取消使用 unregister。問題是呼叫政策與底層能力混寫。 |
| 必-4 | 成立 | `proto6/spec/protocol/kernel-tasks.md:53` 新增 kernel history 與遞增序號，但 `proto6/spec/protocol/agent-tasks.md:49`、`:59`、`:164` 的序號及 listen 契約仍以 agent 路徑為主。kernel 如何供 listen 讀取、兼具兩類任務時如何選取及保存序號，沒有完整定義。 |
| 必-5 | 成立 | `proto6/spec/protocol/work.md:81` 已有 `aos work cancel`，但 `proto6/spec/cli/README.md:9` 的命令入口及 CLI 表沒有 work，也未定取消目標、原請求 ID 等完整參數。 |
| 必-6 | 部分成立 | `proto6/spec/protocol/llm-work.md:13` 與 `proto6/spec/protocol/kernel-tasks.md:108` 對收件者的分工不一致；但後者 `:168`、`:169` 的完整範本已讓 forward 宣告 `llm.chat`、pool 讀其材料。因此是獨立池部署契約不清，不能說現有完整範本必然回 -32601。 |
| 必-7 | 部分成立 | `proto6/spec/scheduling/llm.md:57` 說回收「本機」名額，`proto6/spec/protocol/resources.md:75` 保留的是 unknown 的份額，可能是不同計數。需要明定兩者關係，以及 unknown 長期占滿池的處置；目前不足以判定兩句必然矛盾。 |
| 必-8 | 不成立 | `proto6/spec/protocol/kernel-tasks.md:74` 與 `proto6/spec/protocol/agent-tasks.md:149` 各自明定退出碼，呼叫者知道自己執行哪支程式。`proto6/spec/protocol/node.md:155`、`:156` 只要求檢查失敗就維持暫停，不要求所有 validator 共用相同錯誤碼，並不妨礙實作。 |
| 必-9 | 部分成立 | `proto6/spec/protocol/kernel-tasks.md:128` 的 `kernel.json.llm` 寫法有歧義，但也可以表示 JSON 欄位；`proto6/spec/protocol/schemas/kernel-work-state.schema.json:47` 已定義 `llm` 欄位。宜明寫「kernel.json 的 llm 欄位」，不能認定正文已另規定一個旁檔。 |

### 設計問題：18 條

| 編號 | 判定 | 理由 |
|---|---|---|
| 設-1 | 部分成立 | `proto6/spec/protocol/node.md:111` 的丟件診斷與 `proto6/spec/protocol/daemon/provision-and-runner.md:53` 的覆寫確有證據流失風險；但 `proto6/spec/protocol/ops.md:83` 已要求壞任務表由 tick／daemon 記事項，並非一概沒人報。`proto6/spec/protocol/node.md:113` 的鬧鐘也不能補救未成功投出的件。 |
| 設-2 | 成立 | 任務 cgroup 規則在 `proto6/spec/daemon.md:80`、`proto6/spec/protocol/node.md:78`、`proto6/spec/base/execution.md:19`、`proto6/spec/protocol/daemon/provision-and-runner.md:21` 多次重述，確實增加裁定同步成本。但其中「丟原件」和「先存副本再清原件」不是有效的矛盾例子。 |
| 設-3 | 成立 | `proto6/spec/daemon.md:80` 委派整個 node 分支，正常 tick 收尾卻只看 tick 與 task-*。同 UID 任務若把後代搬到自建的其他葉端，`proto6/spec/protocol/node.md:78` 的 task 框可能已空，卻未滿足 `proto6/spec/tick.md:9` 的後代清空保證。 |
| 設-4 | 部分成立 | `proto6/spec/protocol/kernel-tasks.md:17`、`:26`、`:160` 的預設確有補查延遲及空轉成本；但這些數字可調，`proto6/spec/conformance.md:68`、`:70` 已要求萬級與多層量測。可要求量測及配置指引，不能未量就斷言萬級目標不成立。 |
| 設-5 | 部分成立 | `proto6/spec/protocol/README.md:19`、`:20` 沒有完整的資料遷移、回退及混版部署契約，這是缺口；但拒絕「未知版本」不代表新程式不能同時認得舊版與新版，不能推出必然無法升級或共存。 |
| 設-6 | 部分成立 | `proto6/spec/protocol/agent-tasks.md:45`、`:55` 有多層保存，`proto6/spec/base/storage.md:39` 又暫不回收 git 歷史，長期成長值得處理；但外層 RPC 與內層結果未必相同，Git 也會共用相同內容的物件，不能按檔案位置直接算成四倍輸出。 |
| 設-7 | 成立 | `proto6/spec/tick.md:53`、`proto6/spec/protocol/node.md:109` 把 commit 成功當成刪原件的邊界，卻未定斷電耐久條件。Git 的檔案同步另有設定，不能把 commit 成功直接視為資料已安全落盤；修正也不能只加一個物件同步選項就宣稱全部解決。參見 [Git 2.35 官方文件](https://git-scm.com/docs/git-config/2.35.0)。 |
| 設-8 | 部分成立 | 診斷確實分散，但 `proto6/spec/protocol/kernel-tasks.md:106` 已要求保存轉交前後的 ID 對照；`proto6/spec/protocol/ops.md:11` 的待辦和 `proto6/spec/protocol/daemon/provision-and-runner.md:70` 的啟動失敗證據也不是同一用途。較準確的缺口是缺少統一串查入口，不能直接把這些檔案當冗餘合併。 |
| 設-9 | 部分成立 | `proto6/spec/protocol/messages.md:36`、`proto6/spec/base/storage.md:35` 會保留未接納原件，缺自動隔離壞件的流程；但不代表人不能修理或清除，也未要求每格重新報一次。`proto6/spec/protocol/ops.md:83` 還要求同一問題沿用事項 ID。 |
| 設-10 | 部分成立 | `proto6/spec/daemon.md:45` 未完整定義重啟後空 node／once 框的回收；但 `proto6/spec/protocol/node.md:78` 已要求清理 task-*，`proto6/spec/protocol/work.md:51` 也提到移除 leaf。缺口應限縮，不能說所有空框都沒人刪。 |
| 設-11 | 部分成立 | 掃描頻率及大量資料時的成本控制未定；但誰量測已有規則：`proto6/spec/protocol/resources.md:7`、`:9` 將量測交給 module，`proto6/spec/protocol/kernel-tasks.md:61`、`:65` 定義資源任務。`proto6/spec/base/identity-resources.md:47` 的問題主要是掃描節奏不完整。 |
| 設-12 | 部分成立 | tick 受同一 node 記憶體上限，確實可能無法自行收尾；但 `proto6/spec/daemon.md:80` 已要求 daemon 收尾 tick 與 task-*，`proto6/spec/protocol/daemon/provision-and-runner.md:21` 也讓外層收尾程序留在成員額度之外。應驗證交接，不是只能靠重啟兜底。 |
| 設-13 | 成立 | `proto6/spec/protocol/node.md:133` 只明授 daemon 寫 attention，未完整接上 `proto6/spec/protocol/daemon/provision-and-runner.md:53` 的診斷檔；`proto6/spec/protocol/work.md:33`、`:47` 的跨 UID jobs 輸出權限與 once 診斷落點也不完整。但寫結果失敗可能是 unknown，不能一概當 start_failed。 |
| 設-14 | 部分成立 | 對照使用者的「表達式」視角，確實缺一份共同計算契約；但已有 inst、node 資源框及工作結果等共用部分。卡住也不只剩重啟：`proto6/spec/protocol/daemon/registration.md:23` 可 unregister，`proto6/spec/daemon.md:53` 有收尾規則。不能把五條路線描述成完全沒有共同控制。 |
| 設-15 | 部分成立 | `proto6/spec/protocol/llm-work.md:28`、`:38` 的外部計算契約偏向 LLM，通用遠端成本與取消介面未定；但 `proto6/spec/protocol/resources.md:7` 允許普通資源任務，`proto6/spec/protocol/work.md:75`、`:91` 也有外部效果不明及取消界線。應裁定是否抽出共用介面，不是完全沒有擴充位置。 |
| 設-16 | 部分成立 | 中間 kernel 停格會卡住由它叫醒、轉交的工作，但不必然停掉整棵子樹：`proto6/spec/protocol/daemon/registration.md:25` 明定 pause 不遞迴，已有週期的下層 kernel 可繼續。`:30` 有 attention，`proto6/spec/protocol/kernel-tasks.md:49` 也讀 node.show；成立的是接手與失聯處置未定。 |
| 設-17 | 部分成立 | `proto6/spec/protocol/daemon/provision-and-runner.md:11` 沒有共享群組管理動作，但 `proto6/spec/protocol/kernel-tasks.md:150` 明定其他群組由有權建立者配置。因此不是沒有可佈建的路，也不必每對 node 建一組；缺的是自動建立隔離 node 時的完整配置流程。 |
| 設-18 | 部分成立 | 多跳提交與程序啟動的成本成立，但 `proto6/spec/protocol/kernel-tasks.md:26` 的一秒是建議值，`proto6/spec/protocol/daemon/registration.md:13` 及 `proto6/spec/protocol/messages.md:59` 有通知／wake。不能推出每跳至少一秒、三跳來回最少六秒，或所有 kernel 都必須每秒空跑。 |

### 建議：37 條

| 編號 | 判定 | 理由 |
|---|---|---|
| 建-1 | 部分成立 | `proto6/spec/daemon.md:103` 的範例註解漏提醒 root 服務模式也須填 common_user，但未明說只有單帳號才需要。正式要求已在 `proto6/spec/base/identity-resources.md:37`，屬範例提醒不足。 |
| 建-2 | 不成立 | `proto6/spec/protocol/resources.md:73`、`:77` 已區分成員並行份額與池端共享窗口；`proto6/spec/scheduling/llm.md:39` 延後的是另一種預算，不會取消 `proto6/spec/protocol/kernel-tasks.md:124` 的 provider 窗口。 |
| 建-3 | 部分成立 | `proto6/spec/protocol/work.md:88` 與 `proto6/spec/base/execution.md:29` 間確實欠取消、程序結束、結果發布的先後交接；但 `proto6/spec/protocol/kernel-tasks.md:90` 規定無可信證據就 unknown，不能只憑 canceling 加 not_registered 改判 canceled。 |
| 建-4 | 不成立 | `proto6/spec/protocol/messages.md:63` 的丟原件直接引用 P-202，而 `proto6/spec/protocol/node.md:52` 要先複製、提交、回覆再清原件。保存副本與刪原件可以同時遵守，沒有矛盾。 |
| 建-5 | 部分成立 | `proto6/spec/cli/commands.md:46` 摘要漏 methods，`:43` 的 log 篩選也漏新提交名稱；但 `proto6/spec/tick.md:26` 已指定 P-202 為詳細正本，`proto6/spec/protocol/node.md:52` 也明定組外提交，不能說該行為沒有規格。 |
| 建-6 | 不成立 | `proto6/spec/protocol/work.md:49` 明定 parent_id 與工作目錄 W 的位置無關，`proto6/spec/protocol/resources.md:71` 再次禁止由路徑推资源歸屬。因此不能憑 `proto6/spec/protocol/examples/daemon/get_result.launch_failed.valid.json:5` 的位置判定 parent_id 錯誤。 |
| 建-7 | 成立 | `proto6/spec/daemon.md:67` 已要求明寫 cgroup_root 的情形也搬程序，但 `:90` 驗收只列省略設定的情形。應補驗第十七批新增分支。 |
| 建-8 | 不成立 | `proto6/spec/base/execution.md:17` 以「例如」說明安全核對 PID，沒有要求持久保存程序表；`proto6/spec/daemon.md:45` 不要求跨重啟程序表，也沒有禁止清理時安全核對當前程序。 |
| 建-9 | 部分成立 | `proto6/spec/protocol/daemon/provision-and-runner.md:36` 的 helper.stop 固定兩秒，與 `proto6/spec/protocol/daemon/shutdown.md:7` 的可配置停機寬限如何銜接確實不明；但 `proto6/spec/base/execution.md:19` 的 inst 逾時是另一種操作，不是第三套互相衝突的停機設定。 |
| 建-10 | 部分成立 | `proto6/spec/base/execution.md:19` 同段混放一般 TERM 寬限與第十七批 task 殘留直接清殺，適用邊界宜明寫；但 `proto6/spec/protocol/node.md:78` 已有後批專則，不需把已裁定事項重新交使用者二選一。 |
| 建-11 | 成立 | `proto6/spec/scheduling/llm.md:21`、`:29` 概括成沒人處理就留件；但依 `proto6/spec/protocol/node.md:52`，有正常 tick、無任務宣告 llm.chat 時會回 -32601 並消費原件。應區分沒開 tick 與沒宣告方法。 |
| 建-12 | 部分成立 | `proto6/spec/base/transport.md:9` 把「未對發件者開放」歸入 -32601，與方法不存在、來源未授權容易混淆；但 `proto6/spec/protocol/kernel-tasks.md:98` 仍明定來源授權及 work_not_authorized，不能說開放與授權全部都和發件者無關。 |
| 建-13 | 部分成立 | `proto6/spec/base/execution.md:27` 寫取消指定 attempt，`proto6/spec/protocol/work.md:81` 卻以原請求 ID 定位；對 `proto6/spec/protocol/llm-work.md:42` 的多次 HTTP 嘗試需釐清涵蓋範圍。但目前公開取消參數並沒有兩種競爭格式。 |
| 建-14 | 成立 | `proto6/spec/agent/configuration.md:9` 的導引不準，`proto6/spec/agent/tools.md:9` 仍稱 adapter 下一輪才定；實際設定及 adapter 契約已在 `proto6/spec/protocol/agent-tasks.md:13`、`:33`。 |
| 建-15 | 部分成立 | `proto6/spec/protocol/kernel-tasks.md:61` 所引 P-503 實際是 `proto6/spec/protocol/resources.md:38` 的 cgroup 規則，公開副本的同步時點也不清；但 kernel 同一行已明定父任務發布、子 quota_file 指公開檔，並非完全不知道誰寫、讀哪份。 |
| 建-16 | 不成立 | `proto6/spec/base/inst.md:5` 明說產品退出碼另定，沒有規定某條 proto6 命令須回 100。找不到 100 的產品契約不構成矛盾，也不妨礙依各命令已列出的碼實作。 |
| 建-17 | 部分成立 | `proto6/spec/protocol/messages.md:69`、`:75` 與 `proto6/spec/protocol/work.md:67` 間可補清 accepted 輸出的落點及留存；但 `proto6/spec/protocol/examples/messages/command-result.minimal.valid.json:13` 是通用範例，未宣稱它是 agent.say 回件，stdout:null 不能據此判錯。 |
| 建-18 | 部分成立 | `proto6/spec/protocol/messages.md:46` 要补投原回應，`proto6/spec/protocol/node.md:115` 會刪已送 outbox，確需明定查找與保留方式；但 `:111` 已指出原檔仍在 git 歷史，不能說沒有保存來源，也不必然要再存一份。 |
| 建-19 | 部分成立 | `proto6/spec/protocol/kernel-tasks.md:90` 的同 boot 核對應接上 `proto6/spec/protocol/daemon/shutdown.md:21` 的乾淨恢復例外；但 `proto6/spec/protocol/agent-tasks.md:120` 沒有 Fable 所稱的同 boot 限制，正文也允許可信的從未啟動證據，不足以斷言必然永久睡死。 |
| 建-20 | 部分成立 | `proto6/spec/protocol/llm-work.md:13` 要絕對設定路徑，`proto6/spec/protocol/kernel-tasks.md:169` 範本卻用相對路徑，這點成立；「是否固定設定沒定」則被 `proto6/spec/protocol/work.md:101` 和 `proto6/spec/protocol/llm-work.md:24` 的派出時固定必要設定直接推翻。 |
| 建-21 | 成立 | `proto6/spec/protocol/examples/agent-tasks/agent-context.minimal.valid.json:5` 及 `proto6/spec/protocol/examples/agent-tasks/agent-context.negative-estimate.invalid.json:5` 仍用無前綴目錄，與 `proto6/spec/protocol/work.md:31` 明定的統一展開規則不符。 |
| 建-22 | 成立 | `proto6/spec/protocol/examples/daemon/get_result.minimal.valid.json:17` 的 cgroup 路徑不符合 `proto6/spec/daemon.md:78` 的 n-\<hash\> 層級命名。這類跨欄位語意錯誤不會由目前格式驗證抓到。 |
| 建-23 | 成立 | `proto6/spec/protocol/schemas/daemon-rpc.schema.json:372`、`proto6/spec/protocol/schemas/daemon-runner-report.schema.json:53`、`proto6/spec/protocol/schemas/work-result.schema.json:56` 分別允許 signal 到 64、127、9007199254740991；`proto6/spec/protocol/daemon/registration.md:46` 則寫 1～64。範圍應統一，但不能因此斷言正常 wait 結果必然轉換失敗。 |
| 建-24 | 部分成立 | `proto6/spec/protocol/schemas/llm-result.schema.json:101` 有 retry_at_ms，`proto6/spec/protocol/llm-work.md:42` 卻未解釋；`:48` 又定池保存重試時間。欄位語意缺漏成立，但結果中的歷史證據與排程中的下次時間未必冗餘，不宜未釐清就刪。 |
| 建-25 | 部分成立 | `proto6/spec/cli/walkthrough.md:7` 將預先搬 shell 說成必要前置，理由已被 `proto6/spec/daemon.md:67` 的自動搬移縮小；但原走查仍能工作，而且保留手動準備是合理部署方式，不必改成一定由 daemon 搬。 |
| 建-26 | 部分成立 | `proto6/spec/protocol/node.md:56` 漏說明新增 methods 反例，不符合 `proto6/spec/protocol/README.md:52` 的範例說明要求；但 `proto6/spec/protocol/examples/tick/tasks.methods-duplicate.invalid.json:18` 的同任務重複確實違規，`proto6/spec/protocol/schemas/tick-tasks.schema.json:85` 也已說跨任務唯一性另由 tick 驗。 |
| 建-27 | 不成立 | `proto6/spec/protocol/agent-tasks.md:149` 已定設定無效回 1，`:151` 另定保存失敗也回 1；與 `proto6/spec/cli/commands.md:95` 一致，且有 stdout／stderr 診斷。spec 沒要求每種失敗必須獨占退出碼，這不是妨礙實作的歧義。 |
| 建-28 | 部分成立 | `proto6/notes/2026-09-29-kernel-tree.md:5` 自稱正本，`:27`、`:42`、`:102`、`:103` 又有已過時內容，應整理；但帳本在同篇 `:51` 已明標被第五批 git 規則取代，不能說全部未標註。現行狀態保存見 `proto6/spec/daemon.md:39`。 |
| 建-29 | 成立 | `proto6/notes/2026-09-29-llm-scheduler-options.md:14`、`:19`、`:28` 的 endpoint 429、token 預算與直連程式說法，落後於 `proto6/notes/verdicts/06-cgroup-direct-delivery.md:19`、`:25`、`:31`。但 S-306 在 `proto6/spec/scheduling/llm.md:71` 仍有刪除去向，不是不存​​在的條號。 |
| 建-30 | 部分成立 | `proto6/notes/verdicts/05-dependencies.md:14` 的 systemd「有就用」可補上 `:67` 的首版延後標記；但 `:22`「沒有 systemd 也能跑」沒有被推翻，同篇也已交代追加裁定，不能把整段視為現行矛盾。 |
| 建-31 | 部分成立 | `proto6/notes/verdicts/01-notes-review-1-10.md:44` 的 P-011 確實不存在，`:27` 的帳本及欄位指引也過時；但該篇 `:5` 已說後批優先，`proto6/spec/agent/README.md:42` 仍保留 A-506 的刪除／合併去向，不能把所有歷史用語都算錯。 |
| 建-32 | 部分成立 | `proto6/notes/between-ticks-configuration.md:5` 確使條號檢查失敗；但原文已寫「已移除」，Fable 建議改成「原 B-305（已刪）」仍會被掃到。另 `:11` 硬稱同格不換設定版本，與 `proto6/spec/agent/configuration.md:17` 允許自行承擔同格混用風險相反，這部分應一併修正。 |
| 建-33 | 不成立 | `proto6/notes/base.md:3` 已明標歷史概念稿、現行以 spec 為準，符合本次排除已註明過時內容的條件；而 `proto6/spec/base/identity-resources.md:33`、`:35` 仍要求主 daemon 非 root、sudo 啟動後永久降權，並未推翻這點。 |
| 建-34 | 部分成立 | `proto6/notes/verdicts/04-late-day-directions.md:47`、`:87` 的待改標記與 `proto6/notes/verdicts/README.md:11` 宣稱已落實不一致；但前者 `:41` 的「不是 node 報錯」不直接反對後來的可選鬧鐘，不能把整段都算被推翻。 |
| 建-35 | 部分成立 | `proto6/notes/2026-09-29-wsl-machine-check.md:28`、`:38` 的現行連結指向已重寫內容，補明「引用當時版本」有幫助；但該篇 `:5` 已標為查證紀錄，`proto6/notes/verdicts/01-notes-review-1-10.md:11` 更要求保留作背景，不應要求把歷史實測全文改成現行規範。 |
| 建-36 | 部分成立 | `proto6/notes/probes/README.md:16` 漏列後增的每任務 cgroup 探針，快照說明也未更新；但 `proto6/notes/probes/systemd-run-latency.md:5` 是帶日期的條件式實測，不宣稱現行 daemon 使用 systemd-run，`:3` 連裁定索引也不是壞連結。 |
| 建-37 | 部分成立 | `proto6/notes/verdicts/07-review-fixes-and-proto-gaps.md:27` 確實漏標被 `proto6/notes/verdicts/08-cancel-task-cgroup-and-gaps.md:23` 推翻；Fable 引的後者行號差一行。另 proto6 頂層 README 過時可作入口附註，但不在本次指定的 notes／spec 審稿範圍。 |

### 要使用者裁定：15 條

| 編號 | 判定 | 理由 |
|---|---|---|
| 裁-1 | 成立 | `proto6/spec/protocol/messages.md:63` 明准完整 inst 並承認借權執行風險，`proto6/spec/base/inst.md:48` 又用覆蓋後 PATH 找 aos，因此換程式讀池憑證的情境成立；與 `proto6/spec/scheduling/llm.md:29` 的 key 隔離驗收需協調。但完整 inst 是已接受方向，應裁清保護承諾，不能擅自加白名單推翻它。 |
| 裁-2 | 成立 | `proto6/spec/protocol/agent-tasks.md:104` 不主動叫醒，`:75` 等結果可 ready=false、due=null，`proto6/spec/protocol/kernel-tasks.md:26` 又建議 agent 不設週期。這個組合確實可一直等不到收結果的下一格；是最新裁定與預設組合的代價，不是裁定漏落。 |
| 裁-3 | 部分成立 | `proto6/spec/protocol/kernel-tasks.md:74` 與 `proto6/spec/protocol/agent-tasks.md:149` 的一般 check 行為確實不同，可討論統一；但第十七批只指定 kernel，兩套已明定介面不構成違反裁定，也不使 resume 無法實作。統一是設計選擇，並非必修。 |
| 裁-4 | 不成立 | `proto6/spec/base/execution.md:21` 已明定強制清理後代時記失敗，不以主程序 exit 0 冒稱成功；`proto6/spec/protocol/node.md:78` 直接引用該收尾規則。已有答案，不需重新裁定。 |
| 裁-5 | 部分成立 | forward／agent 取消流程未完整定義屬實，但 `proto6/notes/verdicts/08-cancel-task-cgroup-and-gaps.md:42` 已列下一輪，`proto6/spec/protocol/work.md:91` 也明標範圍。完整 kernel 的 `proto6/spec/protocol/kernel-tasks.md:167` 已宣告 work.cancel，故未必回 -32601，也可能是 work_not_found。 |
| 裁-6 | 不成立 | `proto6/spec/protocol/messages.md:36` 已明分接納前與接納後：接納前可以拒絕副作用、保留原件；執行後才發現投不回去，不能撤銷已完成工作，只丟待送回應。這是兩階段處置，不是同一情境矛盾。 |
| 裁-7 | 成立 | `proto6/spec/protocol/work.md:83` 用 node 根目錄 UID 核權；`proto6/spec/protocol/daemon/startup-and-ipc.md:42` 的 IPC owner 卻依授權執行身分更新，`proto6/spec/protocol/node.md:133` 也只要求可讀寫、未要求擁有目錄。两種 owner 確實可能不同，應確認權限後果。 |
| 裁-8 | 部分成立 | 未预授身分的擴容確需改啟動設定；但 `proto6/spec/protocol/daemon/registration.md:9`、`proto6/spec/protocol/daemon/provision-and-runner.md:25` 允許先授予尚不存在的確切帳號，日後建帳號不用重開。不是每新增隔離帳號都必須全殺。 |
| 裁-9 | 部分成立 | 缺整機「停新派工、等待自然完成」模式的代價成立；但 `proto6/spec/protocol/daemon/startup-and-ipc.md:18` 的兩秒是可配置預設，`proto6/spec/protocol/work.md:53`、`proto6/spec/daemon.md:47` 也保留可信完整結果，不是所有在途工作都必然 unknown。 |
| 裁-10 | 部分成立 | 標準人工修復流程不足，但 `proto6/spec/protocol/agent-tasks.md:110` 允許 unknown 的 final，`:114` 允許有終局回話後把 input 記 done，並非必然永久卡住。`proto6/spec/protocol/ops.md:37` 也允許人手修理；不能直接把工作 unknown 改寫成 failed 再重做。 |
| 裁-11 | 部分成立 | `proto6/spec/protocol/daemon/provision-and-runner.md:23` 確要求整個子樹全空，修改上層限制需要維護窗口；但該條與 `proto6/spec/protocol/resources.md:58` 已給暫停、等空、更新、恢復的路，不是沒有可行方式。 |
| 裁-12 | 成立 | `proto6/spec/protocol/agent-tasks.md:81` 明定回話只記錄、不觸發 LLM，`:89` 又不混其他 input，答案不會自動推進提問者。這是已接受防循環規則的協作代價；標題宜縮成「回話不自動推進既有委託」，不是只能問一次。 |
| 裁-13 | 部分成立 | `proto6/spec/scheduling/llm.md:23` 的父份額承諾，與直投／自有池的事前扣額鏈之間有缺口；但 `proto6/spec/protocol/resources.md:28`、`:32` 和 `proto6/spec/protocol/kernel-tasks.md:114` 已有用量收集，不能說根本量不到。要裁清的是如何事前限制，而非有沒有事後觀測。 |
| 裁-14 | 部分成立 | `proto6/spec/protocol/daemon/registration.md:7` 的 roots 變更需重開，但一般 node 不能原地換父，不等於重組必須重開：`:23` 可解除，`proto6/spec/protocol/kernel-tasks.md:41`、`:45` 可調成員後由新父註冊。成立的是重掛流程與維護成本，不是全面強制重啟。 |
| 裁-15 | 部分成立 | `proto6/spec/protocol/README.md:71` 的同 provider scope 集中同池確有單點成本；但 `proto6/spec/protocol/daemon/startup-and-ipc.md:15`、`:16`、`:19` 是每實例設定，未限定一機一 daemon。`proto6/spec/protocol/messages.md:59` 也有通知，不只定期補查；跨 daemon 邊界仍值得明定。 |

## 二、Fable 漏掉的新發現

以下只列獨立審查時找到、且未被 Fable 同一問題涵蓋的項目。

### 必修

#### 新必-1．拿掉 check 的依賴還不夠：resources 失敗仍會擋住收結果與取消

**引用位置：**

- `proto6/spec/protocol/kernel-tasks.md:76`、`:166`、`:167`、`:168`、`:169`
- `proto6/spec/protocol/resources.md:9`、`:93`
- `proto6/spec/tick.md:32`、`:38`、`:39`

**問題與情境：**  
正文要求壞設定只停新工作，既有結果、取消與收尾仍能處理。第十六批因此拿掉對 check 的 `needs`——也就是「前置任務成功才准執行」的依賴。

但完整範本仍讓 work、forward 依賴 resources，pool 再依賴 forward。resources 因父配額檔壞掉、讀取失敗或必要量測不可用而非零退出時，後面三項依規則全部跳過。即使工具已完成、結果檔完好，或使用者送來取消，也無法處理。設定故障因此反過來阻止解除資源占用。

**建議怎麼改：**  
把「允不允許新派工」和「任務能不能執行收件、收尾」分開。可以移除這些整項依賴，由各任務讀已提交資源狀態，只擋新啟動；或明定資源故障保存後如何讓收尾路徑繼續。補一個驗收：工作在途時弄壞父配額，仍須能收結果、接受取消，且不得開新工作。

#### 新必-2．排程要辨認「新的一格已完成」，卻只留下不能當格次用的時間

**引用位置：**

- `proto6/spec/protocol/kernel-tasks.md:55`
- `proto6/spec/protocol/schemas/kernel-schedule-state.schema.json:55`、`:66`、`:84`
- `proto6/spec/protocol/daemon/registration.md:38`、`:42`、`:49`
- `proto6/spec/tick.md:71`

**問題與情境：**  
schedule 要記下 wake 時的 last_tick，等新格完成後才重新採用摘要，避免拿舊 ready 一直叫醒。但持久狀態只提供 `summary_commit` 和 `wake_after_end_ms`，沒有可辨識格次的欄位；schema 也不允許任意補欄位。

daemon 明說 UTC 時間可能校正，不准據此排序格數；沒變動的成功 tick 又不產生新 commit。若子 node 在父兩次查詢間完成新格、摘要沒有變，且時鐘倒退或時間值重複，父層就缺少可靠證據區分新舊。用「結束時間更大」會卡住，用「時間不同」也沒有完整的識別保證。

**建議怎麼改：**  
明定一個不靠牆鐘的格次識別，例如本次登記內遞增序號，連同 boot／登記識別一起回傳並保存。也可採其他能證明完成了指定新格的契約，但需要同步補正文、IPC schema、schedule-state 與重啟行為。

#### 新必-3．兩個 daemon 使用不同 socket，就可能同時管理並清殺同一棵資源樹

**引用位置：**

- `proto6/spec/protocol/daemon/startup-and-ipc.md:15`、`:16`、`:19`、`:30`
- `proto6/spec/daemon.md:37`、`:45`
- `proto6/spec/protocol/daemon/shutdown.md:19`

**問題與情境：**  
目前排他鎖放在 socket 所在目錄，但 socket、state_dir、cgroup_root 是分別設定的，沒有要求後兩者也排他。

例如兩份設定使用不同 socket 目錄，卻指向同一 cgroup_root。兩個 daemon 都能拿到自己的鎖；後啟動者再按恢復規則清理既有程序，可能把前者仍在管理的有效工作當殘留殺掉。共用 state_dir 時，還可能互相覆寫恢復檔與 PID 提示檔。

這與 Fable 裁-15 的集中瓶頸不同：即使允許多 daemon，仍須防止它們誤管同一資源。

**建議怎麼改：**  
在任何恢復、清殺或寫狀態之前，對實際 state_dir 與受管 cgroup 子樹取得排他所有權；相同或重疊受管範圍應有明確拒絕規則。路徑別名也須視為同一資源，不能只比較設定字串或 socket 名稱。

#### 新必-4．只記錄、不建立 input 的回話，沒有可套用的清理終局

**引用位置：**

- `proto6/spec/protocol/agent-tasks.md:81`、`:114`、`:186`、`:188`
- `proto6/spec/protocol/kernel-tasks.md:53`、`:178`
- `proto6/spec/protocol/ops.md:53`、`:57`

**問題與情境：**  
帶 `in_reply_to` 的回話只進 history，不建立待處理 input；kernel 收一般回話也不建 input。但 agent 的清理是從 input 出發，要求它已 done；一般保留期則從工作終局起算。這種只有記錄的訊息，沒有被指定哪個終局、哪個時間可以套用。

例如 A 用 say 向 B 發問，B 持續回報進度與最後答案。A 保存回話，卻沒有對應的本地 input 能變成 done。長期下來，清理程式只能因缺證據而一直保留，或自行發明另一套資格。kernel history 也有同樣問題。

**建議怎麼改：**  
補上「只記錄訊息」的清理單元、完成證據及保留期起點。可以從接件確認提交起算，或明確歸到原發問紀錄及其終局；同時定義尚有引用時如何保留。不需要為了清理而重新建立會觸發 LLM 的 input。

### 設計問題

#### 新設-1．完成的 once 診斷可以無限累積，規定的清除方式卻會中斷其他工作

**引用位置：**

- `proto6/spec/protocol/daemon/registration.md:53`
- `proto6/spec/protocol/work.md:31`、`:33`
- `proto6/spec/daemon.md:37`、`:45`

**問題與代價：**  
once 是只執行一次的登記。完成後，其診斷留在 daemon 記憶體，沒有時間或容量淘汰；正文建議長期大量 once 可安排重啟清掉。

但每次 attempt 應使用新路徑，因此同 node_id 重新登記取代舊記錄，不是正常的回收方式。只要父層持續存在，工具與 LLM 嘗試愈多，診斷記錄就持續增加。另一方面，重啟又會終止其他在途計算：單純回收診斷記憶體，竟要付出整棵受管樹中斷的代價。

**建議方向：**  
把「供人查詢的完成診斷」和「工作不能丟失的結果證據」分清，再選擇容量上限、保留期、確認後清除或手動清除介面。若仍採不淘汰，也應定義可接受的規模及不影響其他工作的維護方式。這不需要改動 unknown 不自動重做的原則。

### 建議

#### 新建-1．LLM 重試由池配置新 attempt ID，工作目錄前綴卻把配置者等同原發起 node

**引用位置：**

- `proto6/spec/protocol/work.md:31`
- `proto6/spec/protocol/llm-work.md:28`、`:42`、`:48`

**問題與情境：**  
目錄前綴定義為「配出 attempt_id 的 node」，括號又說就是工作材料的 node_id。一般請求兩者相同，但 LLM 轉交保留原 node_id，後續重試 ID 卻由池 tick 配置。

例如 A 發起、P 池重試：依「配置者」會雜湊 P，依「材料 node_id」會雜湊 A。不同實作者可能算出不同目錄，讓恢復或結果查找失敗。這不是 Fable 建-21 的範例漏前綴，而是前綴來源本身有例外未說明。

**建議怎麼改：**  
明確指定重試仍以原材料 node_id 計算，或另定配置者識別；不要繼續把兩者寫成永遠相等。同步加一個跨 node、含第二次 attempt 的路徑例子。

### 要使用者裁定

#### 新裁-1．頂層 kernel 的本地額度，第一次由誰套成 Linux 限制沒有定義

**引用位置：**

- `proto6/spec/protocol/kernel-tasks.md:17`、`:30`、`:61`、`:63`
- `proto6/spec/protocol/schemas/kernel-resource-state.schema.json:9`、`:14`
- `proto6/spec/protocol/daemon/provision-and-runner.md:21`、`:23`
- `proto6/spec/daemon.md:41`

**問題與情境：**  
顶層可用本地 quota_file 提供額度，但 resources 的套用流程及 applied 狀態都以 members 為對象，沒有自身額度。daemon 自動建框時不寫上限，啟動後又立即跑頂層 tick。

因此，頂層設定 2 GiB 記憶體額度時，正文只接上「拿這份額度分給下層」，未接上「誰先把頂層框設為 2 GiB」。也不能簡單叫頂層資源任務設定自己：它執行時框內已有程序，而改限制要求整個子樹全空。

這不是 Fable 裁-11 的修改既有上限成本，而是**第一次套用**的責任與時序缺口。部署者事先設好限制當然可行，但目前沒有把它寫成必要步驟。

**可選方向：**

- 由部署者或外部授權程序在首格之前建立、套用並驗證頂層限制，規格明列此前置。
- 提供啟動階段的頂層限制設定，在首次 tick 前完成；需明確維持 daemon 不負責分配政策的界線。
- 本地 quota_file 只代表分配政策，不承諾頂層硬限制；另外明定真正的 Linux 上限由哪一層提供。

需要使用者先選清楚，才能決定哪些設定與啟動驗收是必要的。

#### 新裁-2．agent 收到 RPC 拒收時，等待中的工作與使用者輸入要如何收尾未定

**引用位置：**

- `proto6/spec/protocol/messages.md:30`、`:32`、`:79`
- `proto6/spec/protocol/agent-tasks.md:83`、`:99`、`:106`、`:124`
- `proto6/spec/protocol/schemas/agent-input.schema.json:23`、`:36`
- `proto6/spec/protocol/schemas/agent-usage.schema.json:29`

**問題與情境：**  
RPC 是請求與回應的外層封套；它可以直接回 error，例如 work_not_authorized、pool_not_found，而沒有承載工作結果的 stdout。

agent 收結果段落主要描述從 stdout 解讀工具／LLM 結果，套用後再移除 pending——也就是等待中的請求。用量格式雖有 rejected，卻沒有完整說明外層拒收如何變成工具結果、何時解除等待，以及 input 接下來轉去哪個狀態。

例如一批兩個工具，一個成功，一個被 kernel 拒收。agent 要等「整批全回」才繼續，但拒收究竟算一筆可交給模型的未執行結果，還是整個 input 應停住，沒有明文。這裡不是完全沒有拒收格式，而是缺狀態轉換。

**可選方向：**

- 把確定拒收記成「未派出」的工具結果，解除該 pending；整批齊後交模型判斷。
- 拒收立即阻擋該 input、進入 needs_attention，等待修復；另定修復後是否及如何再派。
- 某些拒收直接產生 failed 終局，其他保留人工處理，並明列分類。

無論選哪種，都應定義 LLM 請求與工具請求的處置、工具呼叫配對，以及哪些錯誤足以證明尚未發生副作用。