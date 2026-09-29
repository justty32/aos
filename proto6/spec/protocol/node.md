# node：資料夾、任務與一格 tick

← [共用約定](README.md)｜行為正本：[inst](../base/inst.md)、[tick](../tick.md)、[設定](../agent/configuration.md)｜[裁定第一～十批](../../notes/2026-09-29-verdicts.md)

## P-200．資料夾布局〔建議預設，未拍板〕

每個完整 node 是一個 git repo；根目錄的正規化絕對路徑就是 node id。以下名稱固定，其他內容按任務需要才建，不預建空表。kernel／agent 是裝了哪些任務的角色，不另設角色欄位。

| 路徑 | 用途／git |
|---|---|
| `.aos/inst.json`（或 `inst.json`） | 跑本 node 的 inst；追蹤；選檔順序依 P-010 |
| `tasks.json` | P-202 的任務註冊表；追蹤 |
| `config/` | 任務使用的正式設定；追蹤，領域格式由使用它的任務定義 |
| `state/` | 已消費收件、請求、結果與必要進度；追蹤，子結構由各協議篇定義 |
| `inbox/` | 外部檔案 JSON-RPC；ignore，含發布用 `.tmp/`；內部分流由 messages 篇定義 |
| `work/` | 設定草稿、暫存與可丟工作材料；ignore，草稿不會自行生效 |
| `public/`（選用） | 已提交摘要的唯讀發布副本；ignore，見 messages P-307 |
| `.gitignore` | 至少含 `/inbox/`、`/work/`；使用 public 時也含 `/public/`；追蹤 |

git 管理目錄以 `git rev-parse --absolute-git-dir` 找，不能假設 `.git` 一定是資料夾。其內 `aos/tick.lock` 是 P-203 的鎖；一般清理不得移除或替換這個鎖檔。待處理事項依使用者指定的 `attention_dir` 發布，不放進會被本組還原的範圍。

〔使用者方向 2026-09-29〕依 [P-010](README.md)，登記資料夾時先找 `.aos/inst.json`，沒有再找 `inst.json`。資料夾目標的 base 仍是 node 根，不是 `.aos/`。`once` 可直接登記一份 inst 檔，檔案目標的 base 才是該檔所在資料夾；不跑 `aos-tick` 就不必有本節完整布局。

## P-201．inst 的格式與展開驗證〔使用者方向 2026-09-29〕

[node-inst.schema.json](schemas/node-inst.schema.json) 驗 [inst 正本](../base/inst.md) 的原始結構；引用內容、循環、選項值及展開後型別仍由 runner 驗證。`_metainfo` 沿第 1 版，不加 version；未知頂層／metainfo／選項額外鍵依 inst 忽略，是 P-002 的例外。

`user` 只准帳號或非負 UID，省略／空字串繼承，不吃指示詞。授權、切身分及整份 `$ref` 的身分核對依 [daemon P-108～110](daemon.md)；125／126／127 與 exit 的訊號編碼依正本，不改成 RPC 錯誤。

[正例](examples/node/inst.minimal.valid.json) 跑 aos-tick；[反例](examples/node/inst.user_directive.invalid.json) 的 user 指示詞不合法。

## P-202．任務註冊表〔建議預設，未拍板〕

檔案為 `tasks.json`，schema：[node-tasks.schema.json](schemas/node-tasks.schema.json)。形狀為 `{"version":1,"tasks":[...]}`，順序只看 tasks 陣列位置。

| 欄位 | 約束 |
|---|---|
| `id` | 共用 `ID`；本表唯一 |
| `argv` | 非空字串陣列，首項非空；直接 exec，不做指示詞展開 |
| `kind` | `system`、`kernel`、`agent`、`custom`；先 system，中段 kernel／agent 可交錯，最後 custom |
| `group` | 可省，共用 `ID`；相同名稱必須連續；省略是這一項自成一組，與任何具名組不同 |
| `needs` | 可省，預設空陣列；不重複的任務 ID，只能指向本表前項 |

`tasks` 可以是空陣列。未知欄位拒絕，沒有 `user`、UID、優先序或獨立 module 表。schema 檢查型別；tick 另外檢查重名、前置存在與順序、連續 group、類別順序。任一錯誤整表不載入，一項也不跑，不退回舊表。任務表及設定每格讀定一次，中途改檔下一格才採用。

最小 [正例](examples/node/tasks.minimal.valid.json) 登記普通程式；[錯例](examples/node/tasks.user_override.invalid.json) 想在任務上加 `user`，不接受。

## P-203．aos-tick 與任意任務程式〔建議預設，未拍板〕

完整 argv：`aos-tick [--node <node_dir>]`。省略 `--node` 就用目前目錄；指定時必須是 P-002 的 node id，不向父目錄猜找 repo。以資料夾為執行目標時，inst 只需 `{"argv":["aos-tick"]}`，預設 cwd 正好是 node 根；若直接執行 `.aos/inst.json` 檔，base 不同，須明寫 `cwd:".."` 或 `--node`。tick 本身不找 inst。

| 介面 | 約定 |
|---|---|
| tick 的 stdin | 不讀；inst 預設 `/dev/null` |
| tick 的 stdout | 原樣轉送任務 stdout，不另混入成功 JSON |
| tick 的 stderr | 任務 stderr 原樣轉送；tick 自己另印 `code: 說明`，有需要附 task id、退出碼或 signal |
| 讀寫 | 讀 inst 之外已選定的 node、`tasks.json`、本格設定及 git；任務自行讀寫一般檔案；tick 負責提交、還原與鎖 |
| 身分 | 全部任務沿用 tick 的有效 UID、群組與資源範圍；tick 不切 UID，直接呼叫也不會替你取得 inst 的身分 |
| 任務 cwd／argv | cwd 固定 node 根；依表中 argv 直接 exec；用 PATH 找程式，PATH 未設採系統預設路徑 |
| 任務 stdin | `/dev/null`，不塞協議 JSON；需要輸入檔、改 cwd 或重導向者可在 argv 明列普通 adapter／`sh -c` |
| 任務 stdout／stderr | 繼承 tick 對應串流；tick 不解析輸出、不把文字當成完成證據 |
| 任務環境 | 繼承 tick 環境，再設定 `AOS_NODE_DIR`（node id）、`AOS_TASK_ID`（本項 id）、`AOS_CONFIG_COMMIT`（格首恢復完成後的完整 commit OID）；皆不是授權、鎖或成功證據 |

有正式設定需求的任務或 adapter 從 `AOS_CONFIG_COMMIT` 讀取本格設定（例如 `git show <oid>:config/...`），不重新讀被前項任務改過的工作檔。各領域按 A-102 驗證，無效更新回退其保存的上一有效 commit／內容；格首 HEAD 不保證設定有效，缺舊有效值就停止依賴它的新工作。這是合作介面，不承諾把任意程式直接 open 工作檔變成快照讀取。

無設定需求的程式沒有必讀的環境變數或必寫的回應封套；`true`、腳本與既有程式都能直接當任務。key 不由 tick 放入 argv 或任務環境；daemon／runner 的環境來源照 [身分篇](../base/identity-resources.md)，inst 的 `envs` 沿正本。

tick 先對 P-200 鎖檔取非阻塞獨占 flock，全格持有。任務另繼承同一 open-file-description 的鎖 fd，號碼放 `AOS_TICK_LOCK_FD`；`--in-tick` 工具須 fstat 對上鎖檔並以該 fd 核對獨占鎖，不能只信環境或旗標。任務不得解鎖，退出前關閉自身副本，後代全空後 tick 才釋鎖。這只是同帳號合作約定，不是授權。每項跑完、確認其後代清空後才往下；清不空就停止，不提早還原仍有人在寫的檔案。收尾沿 [B-202](../base/execution.md)。

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

commit／還原／清理故障保存基線與收件，停後續組，在 git 管理目錄 `aos/tick-blocked` 寫 UTF-8 原因。格首看到就回 125、不碰工作樹；本格故障回 3。即使擋板寫不出，仍由 [daemon P-105](daemon.md) 依可信退出證據停格並報 attention／stderr。直接呼叫者同樣須修復後才能再跑；修復者暫停、持鎖、核對 repo 後移除擋板。

合併 commit 須暫停、持鎖，保留現版本及仍被請求／設定引用的 commit 或內容；不得延後對外派送前的提交。submodule 各自提交、父只管 gitlink，無跨 repo 原子保證；歷史空間依 [B-404](../base/storage.md)。

## P-206．收件與派送的提交邊界〔使用者方向 2026-09-29〕

依 [Q1／Q2](../tick.md)，收件任務先複製原件到追蹤區，後組清理任務 `needs` 收件組，確認提交後才刪相符原件。派送也拆成產生／提交與後組送出，不新增 commit callback。

通用訊息以 `state/messages/requests/<id>.json`、`responses/<id>.json` 保存原件；工作與 LLM 以 `state/work/<attempt_id>/` 保存請求、結果與固定材料依據；資源、ops 路徑各見所屬篇。只在需要時建。原件與原請求目標留在同一領域狀態供配對，不再複製通用帳本。分流／去重／unknown 重投界線只見 [messages P-301～305](messages.md)。

## P-207．加入普通設定與重要設定手改〔建議預設，未拍板〕

argv：`aos-config-add --node <node_dir> --from <source> --to <target>`。source 是 node/work/ 內檔案，target 是 node/config/ 內檔案；相對 node，不准 ..／symlink 逃出。安裝整份設定、保留來源；刪清單項目也是先改草稿再匯入。

用呼叫者帳號，無自訂環境；stdin 不讀，stdout 成功印 target＋LF，stderr 印 code: 說明。讀來源及 repo，寫目標與 git。取同一非阻塞鎖、拒 dirty 或故障擋板；JSON 草稿先驗 P-002，領域設定下一格依 [A-102](../agent/configuration.md) 驗證。

目標旁 .tmp/ 完整寫入、fsync、rename 替換、fsync 目錄；只 stage 目標，訊息 `aos-config-add <target>`，無變動不 commit。它自行持鎖／提交，不能在同 node tick 內呼叫；一般任務改 config 隨 group 提交、下一格採用。

退出：0 已提交／無變動；2 參數／路徑／JSON 不合；75 busy；125 前置失敗（上述皆未寫目標）；1 寫入失敗且已還原；3 commit／還原故障，依 P-205 擋新格。

重要設定（inst 身分、tasks）不用此工具；依 [A-102](../agent/configuration.md) 及 [daemon P-105](daemon.md) 暫停、等全空、持鎖修改驗證並 commit 後才 resume，保留已派工作所需的舊內容。

## P-208．收件區權限〔建議預設，未拍板〕

node 帳號須可遍歷根路徑、讀寫 repo、清理收件；投件者只授必要父目錄 traverse 與 requests／responses 及 .tmp/ 的寫入／遍歷權。用共享群組或 ACL 保證 node 可讀、消費提交後可 unlink，不依賴投件者 umask，不一律 world-writable。

投件權不含 repo／config／key 讀權，也不保證投件者間不能改檔；不覆蓋與內容核對見 P-003，可信來源及同 UID 界線見 [messages P-303](messages.md)。權限配置由上層 kernel 用自己的帳號做，固定特權步驟經 daemon；key 隔離見 [work P-405](work.md)。

## P-209．待決與跨篇

見 [README P-008](README.md#p-008)。
