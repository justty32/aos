# node：資料夾、任務與一格 tick

← [共用約定](README.md)｜行為正本：[inst](../base/inst.md)、[tick](../tick.md)、[設定](../agent/configuration.md)｜[使用者裁定](../../notes/2026-09-29-verdicts.md)

## P-200．資料夾布局〔建議預設，未拍板〕

每個完整 node 是一個 git repo；根目錄的正規化絕對路徑就是 node id。以下名稱固定，其他內容按任務需要才建，不預建空表。kernel／agent 是裝了哪些任務的角色，不另設角色欄位。

| 路徑 | 用途／git |
|---|---|
| `.aos/inst.json`（或 `inst.json`） | 跑本 node 的 inst；追蹤；選檔順序依 P-010 |
| `.aos/tasks.json` | P-202 的任務註冊表；追蹤 |
| `config/` | 任務使用的正式設定；追蹤，領域格式由使用它的任務定義 |
| `state/` | 已消費收件、請求、結果與必要進度；追蹤，子結構由各協議篇定義 |
| `requests/`、`responses/` | node 根目錄的外部 JSON-RPC 請求／回應收件區；兩格都 ignore，各含發布用 `.tmp/`；細節由 messages 篇定義 |
| `work/` | 任務的暫存工作進度；ignore |
| `.aos/jobs/<id>/` | 替成員跑工具、打 LLM 的 once 工作；ignore |
| `.aos/attention/` | 本 node 的待處理事項，含 daemon 發現的 node 問題；ignore |
| `.aos/summary/` | 給上層讀的摘要；summary.json 追蹤、published.json ignore，見 P-307 |
| `.aos/outbox/` | 待 tick 投出的請求／回應；追蹤，見 P-206 |
| `.aos/alarms/` | 已投出、設了鬧鐘的待查紀錄；ignore，見 P-206 |
| `public/` | 可供其他 node 存取的共用空間；是否追蹤由內容決定 |
| `.gitignore` | 至少含 `/requests/`、`/responses/`、`/work/`、`/.aos/jobs/`、`/.aos/attention/`、`/.aos/alarms/`、`/.aos/summary/published.json`；追蹤 |

git 管理目錄以 `git rev-parse --absolute-git-dir` 找，不能假設 `.git` 一定是資料夾。其內 `aos/tick.lock` 是 P-203 的鎖；一般清理不得移除或替換這個鎖檔。待處理事項放 `.aos/attention/`，不隨 group 還原，見 [ops](ops.md)。

〔使用者方向 2026-09-29，裁定「收件分兩格」〕請求在被問者的 `requests/<id>.json`，回應在發問者的 `responses/<id>.json`。回應仍投回發問者家，不改成由發問者去對方家取。

〔使用者方向 2026-09-29〕依 [P-010](README.md)，登記資料夾時先找 `.aos/inst.json`，沒有再找 `inst.json`。資料夾目標的 base 仍是 node 根，不是 `.aos/`。`once` 可直接登記一份 inst 檔，檔案目標的 base 才是該檔所在資料夾；不跑 `aos-tick` 就不必有本節完整布局。

## P-201．inst 的格式與展開驗證〔使用者方向 2026-09-29〕

[node-inst.schema.json](schemas/node-inst.schema.json) 驗 [inst 正本](../base/inst.md) 的原始結構；引用內容、循環、選項值及展開後型別仍由 runner 驗證。`_metainfo` 沿第 1 版，不加 version；未知頂層／metainfo／選項額外鍵依 inst 忽略，是 P-002 的例外。

`user` 只准帳號或非負 UID，省略／空字串繼承，不吃指示詞。授權、切身分及整份 `$ref` 的身分核對依 [daemon P-108～110](daemon.md)；125／126／127 與 exit 的訊號編碼依正本，不改成 RPC 錯誤。

[正例](examples/node/inst.minimal.valid.json) 跑 aos-tick；[反例](examples/node/inst.user_directive.invalid.json) 的 user 指示詞不合法。

## P-202．任務註冊表〔建議預設，未拍板〕

檔案只用 `.aos/tasks.json`，schema：[node-tasks.schema.json](schemas/node-tasks.schema.json)。形狀為 `{"_metainfo":{"_type":"aos-tasks","_version":1},"tasks":[...]}`，順序只看 tasks 陣列位置。每項是 inst 加以下排程欄位，也可用整份 `$ref`；指示詞、串流、cwd、envs 依 inst 展開，base 是 node 根。展開前後皆不准 `user`。

| 欄位 | 約束 |
|---|---|
| `id` | 共用 `ID`；本表唯一 |
| `kind` | `system`、`kernel`、`agent`、`custom`；先 system，中段 kernel／agent 可交錯，最後 custom |
| `group` | 可省，共用 `ID`；相同名稱必須連續；省略是這一項自成一組，與任何具名組不同 |
| `needs` | 可省，預設空陣列；不重複的任務 ID，只能指向本表前項 |

`tasks` 可以是空陣列。tick 展開後檢查 inst、重名、前置存在與順序、連續 group、類別順序；錯誤整表拒載、不跑任何項，不退回舊表。任務表在開格時載入；各任務直接開檔讀自己的設定。

最小 [正例](examples/node/tasks.minimal.valid.json) 登記普通程式；[錯例](examples/node/tasks.user_override.invalid.json) 想在任務上加 `user`，不接受。

## P-203．aos-tick 與任意任務程式〔建議預設，未拍板〕

完整 argv：`aos-tick [--node <node_dir>]`。省略 `--node` 就用目前目錄；指定時必須是 P-002 的 node id，不向父目錄猜找 repo。以資料夾為執行目標時，inst 只需 `{"argv":["aos-tick"]}`，預設 cwd 正好是 node 根；若直接執行 `.aos/inst.json` 檔，base 不同，須明寫 `cwd:".."` 或 `--node`。tick 本身不找 inst。

| 介面 | 約定 |
|---|---|
| tick 的 stdin | 不讀；inst 預設 `/dev/null` |
| tick 的 stdout | 原樣轉送任務 stdout，不另混入成功 JSON |
| tick 的 stderr | 任務 stderr 原樣轉送；tick 自己另印 `code: 說明`，有需要附 task id、退出碼或 signal |
| 讀寫 | 讀 `.aos/tasks.json` 與 git；任務直接讀寫檔案；tick 負責提交、還原、投件、消費原件清理與鎖 |
| 身分 | 全部任務沿用 tick 的有效 UID、群組與資源範圍；tick 不切 UID，直接呼叫也不會替你取得 inst 的身分 |
| 任務 cwd／argv | 依本項 inst 展開後執行；cwd 未給時為 node 根 |
| 任務 stdin | 預設 `/dev/null`；可用本項 inst 的 stdin 重導向 |
| 任務 stdout／stderr | 依 inst 預設 `/dev/null`，可明寫 inherit 或重導向；tick 不解析文字當完成證據 |
| 任務環境 | 繼承 tick 環境，加 `AOS_NODE_DIR`（node id），再依 inst 套用 envs；不是授權證據 |

任務直接開檔讀設定；「tick 裡不改 config/」是軟性原則，不檢查、不阻擋，違反者自行承擔同格新舊設定混用。設定指令在 tick 外持同一把鎖更新；設定驗證依 [A-102](../agent/configuration.md)。

無設定需求的程式沒有必讀的環境變數或必寫的回應封套；`true`、腳本與既有程式都能直接當任務。key 不由 tick 放入 argv 或任務環境；daemon／runner 的環境來源照 [身分篇](../base/identity-resources.md)，inst 的 `envs` 沿正本。

tick 先對 P-200 鎖檔取非阻塞獨占 flock，全格持有。任務另繼承同一 open-file-description 的鎖 fd，號碼放 `AOS_TICK_LOCK_FD`；工具以 fstat 對上鎖檔並核對獨占鎖，判斷是否在 tick 內；無繼承鎖就自行持鎖，不能只信環境。任務不得解鎖，退出前關閉自身副本，後代全空後 tick 才釋鎖。這只是同帳號合作約定，不是授權。每項跑完、確認其後代清空後才往下；清不空就停止，不提早還原仍有人在寫的檔案。收尾沿 [B-202](../base/execution.md)。

| tick 結束碼 | 意思 |
|---|---|
| `0` | 所有組成功（含沒有工作／沒有變動）；只表示本格完成 |
| `1` | 至少一組任務失敗或跳過；需要的還原成功，後續獨立組已照表處理 |
| `2` | argv、任務表或啟動所需設定不合法；尚未開任務 |
| `3` | 開始處理後發生提交／還原／後代清理等故障；停止後續組，依 P-205 阻止新格 |
| `75` | 鎖被占用；本次沒有開任務，也不在程式內重試 |
| `125` | tick 自己無法開始，例如 repo 讀不到或無初始 commit；沒有開任務 |

父程序以 wait 狀態辨識 tick 被訊號結束，不把 `128+N` 當訊號證據。inst 的文字 `exit` 編碼仍依 P-201。

## P-204．成敗、group 與 needs〔使用者方向 2026-09-29〕

group／needs 的順序、提交與失敗跳過完全依 [tick 正本](../tick.md#group-與-needs)。tick 以可信 wait 的正常退出 0 判定任務成功；exec 失敗、非零或訊號皆失敗，不能把普通程式的 125 猜成沒跑。「沒事做」可不改檔回 0；在途工作存領域狀態，不用特殊退出碼當排程訊號。

## P-205．git 提交與恢復〔建議預設，未拍板〕

git 基線、範圍及還原語意依 [tick 正本](../tick.md)。實作以基線 commit 的 ignore 規則管理這組修改／新增／刪除與 index；不採失敗工作樹的新 ignore、不用全樹 git clean -x、不遍歷 git 管理目錄或子 repo。已追蹤檔不因新增 ignore 脫管，新規則從下一組開始算。

commit 訊息為 `aos-tick group <first_task_id>..<last_task_id>`，單項兩端相同；作者用 repo 設定，不互動、不執行 git hooks。無 diff 不 commit。任務自行換 HEAD／分支、後代未清空時保留現場，不盲目還原。

commit／還原／清理故障保存基線與收件，停後續組，在 git 管理目錄 `aos/tick-blocked` 寫 UTF-8 原因。格首看到就回 125、不碰工作樹；本格故障回 3。即使擋板寫不出，仍由 [daemon P-105](daemon.md) 依可信退出證據停格，寫 node 的 `.aos/attention/`；寫不進去只在 daemon stdout 警告。直接呼叫者同樣須修復後才能再跑；修復者暫停、持鎖、核對 repo 後移除擋板。

合併 commit 須暫停、持鎖，保留現版本及仍被請求／設定引用的 commit 或內容；不得延後對外派送前的提交。submodule 各自提交、父只管 gitlink，無跨 repo 原子保證。

## P-206．收件與派送的提交邊界〔使用者方向 2026-09-29〕

每個 module 只需一項任務：收件原件逐 byte 複製到追蹤的 `state/messages/{requests,responses}/<id>.json`；待送檔放 `.aos/outbox/{requests,responses}/<id>.json`，內容為 `{"version":1,"target_node":"/目標","message":{...}}`，可加鬧鐘 `alarm_ms`（見下），message 是完整 JSON-RPC，ID 須與檔名相同。領域狀態引用這份原件，不另做通用收據。

每組成功 commit 後，tick 才從該 commit 發布 `.aos/summary/published.json`、投出待送 message、刪除與已提交消費副本 bytes 相同的收件原件。組歸屬由 commit 邊界決定，無須另寫 task／group 欄位。原件不同就報衝突並保留；送出遇到暫時性錯誤時留待送檔，「目標不是 node」與「沒有寫入權限」兩種依下文報一次錯就丟掉。新格恢復後也補做發布與投件，只使用已提交內容。

〔使用者方向 2026-09-29 晚，第十五批〕**投件只查一件事：目標是不是一個 node**。「是 node」照找 inst 的規則（[P-010](README.md)）：`target_node` 是資料夾，且有 `.aos/inst.json` 或 `inst.json`。不是就在投件那一步報錯：tick 在 stderr 印 `target_not_node: <node> <id>`，這封不投、不重試，待送檔跟成功投件一樣移除（原檔仍在 git 歷史裡），不寫待辦、不改投別處。是 node 就投進去，之後 aos 都不管：對方有沒有裝任務、有沒有被 tick、多久才處理，都不過問。投件時沒有寫入權限，跟「目標不是 node」一樣處理：tick 在 stderr 印一行 `target_not_writable: <node> <id>`，就把待送檔丟掉，不每格重試、不寫待辦；權限補上之後要再送，由投件者重新產生待送檔。

〔使用者方向 2026-09-29 晚，第十五批〕**鬧鐘（可選）**：投件者可在待送封套加 `alarm_ms`（正整數毫秒，從投出那一刻算）。投出成功後，tick 在自己的 `.aos/alarms/<id>.json`（ignore，不隨 group 還原）記下目標、投出的檔案路徑與到期時間。到期後本 node 的下一格去看：那封原件還在對方收件區（`requests/<id>.json` 或 `responses/<id>.json`），就算沒被處理，tick 在 stderr 印 `request_not_handled: <node> <id>`；不寫待辦、不重投、不取消。原件已被取走就算處理了，不印。看完不管結果都刪掉這筆鬧鐘。aos 不為鬧鐘另外叫醒 node，要準時就讓這個 node 有定期 tick。沒設 `alarm_ms` 就完全不等、不逾時。範例：[設了鬧鐘的封套](examples/messages/outbox.alarm.valid.json)、[反例：`alarm_ms` 為 0](examples/messages/outbox.alarm-zero.invalid.json)。

成功投件後移除待送檔，於下一組或格末提交這些刪除；刪除本身就是變動，不造空 commit。提交前當機可再投相同 bytes，接收方依 [P-304](messages.md) 去重。這只是補投同一封檔案，不是重做 unknown 外部工作。once 的 register／wake 仍由該 module 在後續格核對已提交材料後執行，不往待送區塞 IPC。

工作與 LLM 的固定材料依據留 `state/work/<attempt_id>/`；其餘領域路徑見所屬篇。tick 不等遠端結果，不重做 unknown。

## P-207．加入普通設定與重要設定手改〔建議預設，未拍板〕

argv：`aos-config-add [--node <node_dir>] --from <source> --to <target>`；省略 node 用 cwd。source 是任意可讀路徑，相對呼叫 cwd；target 是 node/config/ 內檔案，相對 node、不准 ..／symlink 逃出。安裝整份設定、保留來源。

用呼叫者帳號，無自訂環境；stdin 不讀，stdout 成功印 target＋LF，stderr 印 code: 說明。讀來源及 repo，寫目標與 git。取同一非阻塞鎖、拒 dirty 或故障擋板；JSON 草稿先驗 P-002，領域設定下一格依 [A-102](../agent/configuration.md) 驗證。

目標旁 .tmp/ 完整寫入、fsync、rename 替換、fsync 目錄；只 stage 目標，訊息 `aos-config-add <target>`，無變動不 commit。它自行持鎖／提交，不能在同 node tick 內呼叫；任務直接讀目前設定。

退出：0 已提交／無變動；2 參數／路徑／JSON 不合；75 busy；125 前置失敗（上述皆未寫目標）；1 寫入失敗且已還原；3 commit／還原故障，依 P-205 擋新格。

重要設定（inst 身分、tasks）不用此工具；依 [A-102](../agent/configuration.md) 及 [daemon P-105](daemon.md) 暫停、等全空、持鎖修改驗證並 commit 後才 resume，保留已派工作所需的舊內容。

## P-208．收件區權限〔建議預設，未拍板〕

建 node 時須開 daemon 對 `.aos/attention/` 的寫權。node 帳號須可遍歷根路徑、讀寫 repo、清理收件；投件者只授必要父目錄 traverse 與 requests／responses 及 .tmp/ 的寫入／遍歷權。〔使用者方向 2026-09-29 晚〕首版只用共享群組（可配 setgid 目錄）、不用 ACL，保證 node 可讀、消費提交後可 unlink，不依賴投件者 umask，不一律 world-writable。

投件權不含 repo／config／key 讀權，也不保證投件者間不能改檔；不覆蓋與內容核對見 P-003，可信來源及同 UID 界線見 [messages P-303](messages.md)。權限配置由上層 kernel 用自己的帳號做，固定特權步驟經 daemon；key 隔離見 [llm-work P-405](llm-work.md)。

〔使用者方向 2026-09-29，裁定「LLM 請求送去哪」〕建立 agent 時，LLM 路線與權限一起核對：經自己的 kernel 轉交，須能從 agent 投進該 kernel 的 requests，kernel 能回投 agent 的 responses；轉交下一站時再配 kernel 到下一站、下一站回 kernel 的兩個方向。agent 直接投 LLM kernel，則開 agent→LLM kernel requests、LLM kernel→agent responses，不要求自己的 kernel 代投。工具路線同樣由 `tools.target_node` 決定：有位址就開往該 kernel 的請求／回件權；null 則准 agent 以自己為 parent_id 登記 once、自己記用量。每個寫入方向都含該區的 `.tmp/`；正式副本由接件帳號可讀、提交後可清除。回址不是授權證明，仍依 P-303 核對。

〔建議預設，未拍板〕自己的 kernel 另外取得成員 `requests/`、`responses/` 的必要列目錄權及摘要讀權，供收件／到期喚醒；只做這項觀察時可以用 [messages P-307](messages.md) 的唯讀摘要。用量收集路線另需 repo 讀權，固定 commit 讀 [agent P-703](agent-tasks.md) 的 `state/agent/usage/<request_id>.json`；只有摘要讀權不夠。若部署不願開 repo 讀權，就不能宣稱已啟用這條收集路線；仍不授寫設定或讀池 key 的額外權限。持久成員、路由及完整建立範本見 [kernel 任務篇](kernel-tasks.md)。

**驗收：**兩種路線都能送請求並收結果；刻意拿掉回件寫權時拒絕接納新副作用；只有摘要讀權的父層不能讀成員其他追蹤檔。

## P-209．待決與跨篇

見 [README P-008](README.md#p-008)。

## P-210．預設範本與恢復前驗證〔主編補；依 A-102、CLI H-036 第 2、3、5、6 步〕

`aos node new N --template kernel` 的完整 `.aos/tasks.json`、設定與頂層建立順序由 [kernel 任務篇](kernel-tasks.md) 定；agent 範本由 [agent P-715](agent-tasks.md) 定。範本只安裝普通任務，不寫角色旗標。先驗證產物、有初始 commit，才報建好；建立本身不授身分、不登記、不叫醒。頂層額度仍須放 daemon roots，成員保存及同步沿 kernel 篇。

`aos node resume N` 在 daemon 已暫停且程序全空後，持 P-203 同把鎖，依序檢查目前手改的內容：

1. 按 P-010 選 inst，驗 P-201 原始結構與身分宣告；daemon 在 resume／開格時仍須另驗可信額度、身分與展開，不以本地檢查代替授權。
2. 驗 tasks 的 schema，以及 P-202 的重名、needs、group 連續與 kind 順序。
3. 有 kernel 預設任務就執行 `aos-kernel-check --node N --validate-only`；有 agent 預設任務則復用 [agent P-712](agent-tasks.md) 的檢查規則，對**目前候選工作樹**的 agent 設定、工具及引用驗證，檢查程式直接讀檔。兩種都有便都驗。自訂普通程式沒有 aos 領域設定契約，不因其未提供 validator 就拒收合法任務表；其執行失敗仍由 group 管。
4. 任何檢查失敗保持暫停、保留手改、stderr 指出檔案與欄位；通過後才照 CLI 的確認流程提交手改，再送 daemon node.resume。後續任務直接讀設定，不重做已派工作。

唯讀驗證檢查目前工作樹；由外層持鎖，不另取鎖，不寫追蹤／ignored 檔、不發事項、不自行 commit。它只證明設定可採用，不證明外部 endpoint 可達。日常檢查與待辦標完成依 [ops P-609](ops.md)。

**驗收：**把 tasks 的 needs 指到不存在項目或寫壞 kernel 路由，resume 都不開閘、不抹手改；修好後先提交再恢復；新增 `true` custom 任務不需要虛構領域 validator。
