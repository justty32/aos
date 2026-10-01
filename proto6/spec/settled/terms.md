# 整理區名詞：tick 核心、四類程式與 daemon 核心

← [整理區](README.md)｜[通用 tick](tick.md)｜[daemon](daemon/README.md)｜[慣例](conventions.md)｜其餘名詞：[名詞與責任](../terms.md)｜暫緩的名詞：[T-09](deferred/terms.md)

本篇收 tick 與 daemon 核心用到的名詞（T-07、T-10、T-11）；其餘名詞（來源標記、node 與角色、工作識別、投件權等）仍在[名詞與責任](../terms.md)。這裡只講詞義，規則以各詞後面連的正本為準。

T-09（收尾、排空停機、熱重載、逃生口）全是舊 daemon 的用語，2026-10-01 整條搬到[暫緩區](deferred/terms.md)，條號不變。表裡連到 `deferred/` 的詞也屬暫緩區的設計，現行程式沒有。

## T-07．tick 核心

**tick 是一個定期被執行的程式**（`aos-tick`）。誰來跑都行：daemon、cron、人手；人手或 cron 直接跑的風險自己承擔。它本質上是加了一些功能的 aos-exec（跑一份 [inst](../base/inst.md)）。

| 詞 | 一句話 | 正本 |
|---|---|---|
| tick 核心 | 只做三件事：簡單互斥鎖、照表跑、每項結束碼紀錄；照表跑時另外只認停格檔與擋板檔；任務沒有 `user`（寫了照陌生鍵）。不靠 daemon、git、cgroup、helper，也不靠任何系統級任務。上下層判定已搬暫緩區（[B-628](deferred/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)） | [B-626](tick.md)、[B-620](tick.md) |
| 工作資料夾 | 這一格 `aos-tick` 跑的資料夾（它的 cwd），由命令列的目標決定（`aos-tick [<目標>]`）；任務拿到的 `AOS_TICK_CWD` 就是它的絕對路徑。tick 這層只講工作資料夾（英文 `tick dir`〔使用者 2026-10-01〕）；node 是之後 node 模組才出場的詞 | [B-620](tick.md)、[P-203](protocol/tick.md) |
| 拆出去的 | 原本算在 tick 裡的其餘事，成了系統級任務或普通程式（T-10）；舊設計裡一格結束後殺殘留歸 daemon，那套在暫緩區、現行 daemon 不做〔astra 報告必修 1〕 | [B-626](tick.md)、[B-601](deferred/daemon/runtime.md) |
| 衡量基準 | 整個 aos 以格計：「花十格」算安排它的上層的格；排程本身也是任務表上每格跑一次的程式；反應速度就是一格，只有通道急件例外 | [C-01](../contracts.md)、[B-614](deferred/daemon/messaging.md) |
| 唯一逃生口 | tick–daemon 通道；通道外的事都要在某一格裡做，不准有背景程序或常駐服務繞過 tick。通道是舊 daemon 的設計，在暫緩區 | [B-612](deferred/daemon/channel.md) |
| tick 外的寫入者 | CLI 或工具在 tick 之外自己取鎖改檔，當外部世界，aos 不管 | [B-602](tick.md) |

tick 不跟其他計算單位（once、LLM 嘗試、agent 一輪等）放進同一個外殼；那些的外殼、逾時與取消延後（P-008）。

依據：第十八批（外殼）；第十九批（定期被執行的程式）；第二十批（衡量基準、系統級任務與普通程式）、疑點裁定 1（停格靠檔案）、8（tick 外的寫入者）；使用者 2026-10-01（核心縮成三件事、不判上下層、撤回 `user`、工作資料夾）。

## T-10．tick 核心、系統級任務、普通程式與其他任務

**管轄區**：tick 執行時的目前目錄（cwd）就是它的管轄區。

- aos 體系裡的慣例是兩個 tick 的管轄區**不重疊、但可以包含**；真的重疊了風險自負。被包含的那個從屬於包含它的（上下層），但上下層怎麼算已搬暫緩區（[B-628](deferred/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)），核心現在不判。
- tick 對管轄區內的東西有最高裁量權。這是 aos 體系裡的約定，**不是 tick 運作的前提**（[B-626](tick.md)）。

### 四類

取代第十九批的「核心／標準配備／其他掛載」三層。

| 類 | 一句話 | 正本 |
|---|---|---|
| tick 核心 | `aos-tick` 本身（T-07） | [B-626](tick.md) |
| 系統級任務 | 從核心拆出、掛在任務表上的獨立程式，`kind:"system"` 標記，寫在表上才跑：系統訊息佇列 `aos-mq get`／`aos-mq post`、清理、git 開格／存檔點／收尾 `aos-git` | [B-626](tick.md)、[B-629](tick/template.md) |
| 普通程式 | 任務會用到的工具：要的任務自己在 argv 包的 `aos-as`、`aos-cg`；自己占一項的 `aos-tick-check-task` | [B-303](deferred/helper.md)、[B-621](tick/check-task.md)、[B-634](tick/cg.md) |
| 其他任務 | kernel、agent、clock、檔案收件與投件程式、自訂任務 | [B-623](tick/mq.md)、[scheduling](../scheduling/README.md)、[agent](../agent/README.md) |

daemon 不在任務表上。現行 daemon 核心只定期叫 `aos-exec`（T-11）；舊設計裡 daemon 跟 tick 之間的通道、node 框與資源上限（[B-601](deferred/daemon/runtime.md)、[B-607](deferred/daemon/registration.md)、[B-605](deferred/daemon/cgroup.md)）都在暫緩區。範本只是預設，拿掉哪一項就沒有那一項的保證（[B-629](tick/template.md)、[T-01](../terms.md)）。

### 幾個詞

詞義如下；檔名、欄位與碼值以正本為準。

| 詞 | 意思 | 正本 |
|---|---|---|
| 掛載 | 把一個程式寫進任務表，讓 tick 每格跑它 | [B-620](tick.md) |
| 標準任務表範本 | 預設的一組系統級任務加原本的 kernel／agent 任務；分沒有 git、有 git 兩版 | [B-629](tick/template.md) |
| aos 範圍 | 有 git 時 aos 提交與還原的東西：`.aos/`、任務表、系統級任務動到的檔；使用者任務改的檔不在內。`AOS_DIRNAME` 是空字串時例外：整個工作資料夾都算，使用者的檔也會被提交、還原〔使用者 2026-10-01〕 | [B-630](tick/git.md) |
| 存檔點 | 任務表上的 `aos-git mark` 項；相鄰兩個之間的項是一組，組裡有失敗就當場還原那組改的 aos 範圍 | [B-630](tick/git.md) |
| 每項結束碼紀錄 | 核心每格寫的一份紀錄，記本格跑了幾項、哪幾項結束碼不是 0，後面的任務讀得到；取代第十九批的日誌。〔使用者 2026-10-01 第九批〕一格是一個資料夾（`tick/current/`，上一格 `tick/last/`）：不常改的欄位在 `record.json`，常改的 `ran`、`tasks`、`hooks` 各自一個檔，由 `record.json` 用 `$ref` 指過去 | [B-633](tick.md)、[B-632](tick/git.md) |
| 格數 | 本工作資料夾第幾格〔使用者 2026-10-01 改名〕，記在結束碼紀錄裡；aos 內部的時長與起算點都用它數 | [B-633](tick.md)、[C-01](../contracts.md) |
| 停格檔 | 任務建它，核心跑完那一項就不開本格後面的項；只管本格，daemon 不看它 | [B-620](tick.md) |
| 擋板檔 | 擋住之後的格：有它時 daemon 照常叫，由 tick 自己擋——核心取鎖後看到它就一項不跑、回 0；只由人手刪。〔astra 報告必修 1〕舊 daemon「有擋板就不開格」在暫緩區（[B-607](deferred/daemon/registration.md)） | [B-620](tick.md) |
| 掛點（hooks） | 任務表頂層鍵 `hooks`（跟 `tasks` 同層，不是模組）：讓使用者在 tick 的某個時機插一串 inst，寫法比照 `tasks`；目前只開 `after_all`：照表跑完（含被停格檔停下）之後跑，碼記進紀錄 `hooks.after_all`，不影響 tick 的結束碼 | [B-635](tick/hooks.md) |
| 任務環境變數 | 整格共用的叫 `AOS_TICK_*`，這一項專屬的叫 `AOS_TASK_*`，hook 專屬的叫 `AOS_HOOK_*`（`AOS_HOOK_POINT`、`AOS_HOOK_INDEX`、`AOS_HOOK_ID`；hook 不給 `AOS_TASK_*`） | [B-620](tick.md)、[P-203](protocol/tick.md)、[B-635](tick/hooks.md) |
| 包裝 | 先做一件事、再跑原指令、照原指令的結果結束的普通程式，例如 `aos-cg -- 原指令` | [B-634](tick/cg.md)、[B-303](deferred/helper.md) |
| 有效上層 | （暫緩）有登記覆蓋就是覆蓋指定的那個，否則是資料夾推得的上層；覆蓋只改管理關係 | [B-628](deferred/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)、[B-606](deferred/daemon/registration.md) |
| 通道 | （暫緩）舊 daemon 開的 tick 跟 daemon 之間的 IPC，也是唯一逃生口；不是 daemon 開的 tick 沒有通道 | [B-612](deferred/daemon/channel.md) |
| 系統訊息佇列 | aos 的系統級 IPC：tick 之間經通道互送請求與回應，daemon 暫存；`aos-mq post` 送、`aos-mq get` 取 | [B-614](deferred/daemon/messaging.md)、[B-623](tick/mq.md)、[B-624](tick/mq.md) |
| 憑證 | （暫緩）舊 daemon 開 tick 時發的一次性憑證，證明通道上的請求來自哪一格；每格一張 | [B-612](deferred/daemon/channel.md) |
| 急件 | （暫緩）送進佇列時要叫醒收件 tick 的訊息 | [B-614](deferred/daemon/messaging.md) |
| 以指定帳號開程序 | （暫緩）任務在 argv 包 `aos-as <帳號> -- 原指令`，由 helper 用那個帳號開；核心不切帳號 | [B-303](deferred/helper.md)、[B-609](deferred/daemon/helper-actions.md) |

依據：第十九批（管轄區）；第二十批（四類與詞義）；astra 審整理區建-2（名詞只留定義與連結）與同日定案（系統訊息佇列）；aos-git 分工（aos 範圍、存檔點）。

## T-11．daemon 核心與模組

〔使用者方向 2026-10-01〕現行的 daemon 只是「一個定期叫 `aos-exec` 的 cron」，其餘功能做成可掛的模組。

| 詞 | 意思 | 正本 |
|---|---|---|
| daemon 核心 | `aos-daemon` 本身：定期叫 `aos-exec` 跑設定檔 `insts` 裡的每一項，等它結束、印一行結果。不認得工作資料夾與 node、不讀任務表、不碰鎖與擋板 | [B-640](daemon/core.md) |
| 項（inst 字面值） | `insts` 的一個鍵就是一項，鍵就是交給 `aos-exec` 的 inst 字面值（資料夾或檔）。核心沒有 id，一項就是它的字面值 | [B-640](daemon/core.md) |
| 跑 tick 的項 | 就是一份 `argv` 開頭是 `aos-tick` 的 inst；把它加進 `insts`，daemon 就會定期跑那個工作資料夾的 tick。daemon 不認得工作資料夾；node 這個詞留給之後的 node 模組〔使用者 2026-10-01 改名〕 | [B-640](daemon/core.md)、[B-620](tick.md) |
| 模組 | 設定檔頂層 `modules` 底下，一個鍵一個模組；寫了才掛上。核心只認得 `modules` 這個鍵，不解讀別的模組的內容 | [B-640](daemon/core.md) |
| 控制模組 | 模組 `control`：開一個 Unix socket，收 `wake`、`pause`、`resume`、`status` 四種指令，每個指令只對一項；送指令的小工具是 `aos-ctl` | [B-641](daemon/control.md) |
| 重讀設定模組 | 模組 `reload`：收到 SIGHUP 重讀同一份設定檔，加減項、改週期免重開；`cwd`、`modules` 改了只印警告 | [B-642](daemon/reload.md) |
| 記住狀態模組 | 模組 `state`：設定寫成 `{"$ref": "<狀態檔>"}`，把每項的暫停、已停記進那個檔，重開時讀回 | [B-643](daemon/state.md) |

- 「daemon 管 node」（自動找 node、上下層、叫醒往上傳）之後另做成 node 模組，還沒排程（[node 模組方向](../../notes/verdicts/11-tick-as-unit.md#node-模組方向2026-10-01記錄用未排程)）。
- 舊 daemon 的登記、通道、收尾等用語在暫緩區（[T-09](deferred/terms.md)、[舊 daemon](deferred/daemon/README.md)）。

依據：第二十批篇末「2026-10-01：最核心 daemon」（daemon 只叫 `aos-exec`、核心沒有 id、`modules`、`insts` 物件、控制模組）。
