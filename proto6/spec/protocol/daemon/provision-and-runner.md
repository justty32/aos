# daemon 協議：佈建、私有通道與 runner

← [daemon 協議](README.md)｜[共用約定](../README.md)｜行為正本：[daemon](../../daemon.md)、[身分](../../base/identity-resources.md)、[inst](../../base/inst.md)｜[裁定](../../../notes/2026-09-29-verdicts.md)

## P-107．佈建固定動作〔建議預設，未拍板〕

`node.provision` params 為 `node_id` 與 `action`，其餘依下表；每次只做一件，不提供 shell、argv、任意 syscall 或任意 mount options。授權與允許 path 取**該 node 的登記**，執行端不信封包自報。成功 result 為 `{"node_id":"…"}`；做完並驗證才回，不能把已送 helper 當完成。

| `action` | 其他必填欄位 | 固定效果與範圍 |
|---|---|---|
| `account_create` | `user`：確切帳號名稱 | 名稱已在身分額度、尚未存在才建立非 root 帳號及同名主群組；無登入 shell、不建 home、不收密碼。已存在且符合先前綁定就核對後成功，不能接管同名不同 UID |
| `chown` | `path`、`user` | 單一路徑改為額度內既存帳號與其主 GID；不遞迴、不收任意 GID、不跟隨 symlink |
| `cgroup_create` | 無 | 在可信父資源子樹內建立本 node 的分支及執行 leaf；路徑由 daemon／helper 從登記推導，呼叫者不能給 cgroup 路徑 |
| `cgroup_limits` | `limits` | 非空 object，可有 `cpu_max:{quota_us,period_us}`、`memory_max_bytes`、`pids_max`，皆正整數；CPU 直接使用 cgroup 微秒，是 P-002 的明示例外，檢查 controller 範圍後原值寫入；只寫這些 controller，作用於 node 分支並含後代；不設該欄就不新增該項限制 |
| `quota` | `path`、`project_id`：正整數 | 只配置該路徑的 project **計量歸屬**；不設定磁碟硬上限或 soft limit。不支援或被設定 `disable` 關掉就報 `unsupported`，沒裝磁碟 module 不呼叫 |

〔使用者方向 2026-09-29 晚〕原有的 `mount`（helper 掛 tmpfs）首版拿掉，暫存就在磁碟。

路徑操作必須在被授 `provision.paths` 內（按元件判定，不用字串前綴）；helper 固定目錄 handle、拒絕 symlink 穿越及替換競態，逐步核對實體路徑。OS 現況已符合所要求設定就核對後成功，不同回 `conflict`，不覆蓋。quota 不搶走其他 node 的 project 歸屬。帳號不自動刪除或回收。

cgroup 的 node 分支承接父限制，執行 leaf 容納本 node 程序，子 node 分支留在同一父資源樹；框名（`daemon`、`n-<hash>`、其下 `tick`、`once-<hash>`）依 [B-605](../../daemon.md)〔第十六批〕；〔第十七批〕tick 的每個任務另在 node 框下開與 `tick` 並列的 `task-<序號>`，由 tick 用 node 帳號自建自清，所以 node 框的委派檔交給 node 的執行帳號、上限檔不交；module 決定哪些限制有值，daemon 不排資源。helper／收尾程序留在成員限額之外。〔使用者方向 2026-09-29 晚〕**上限設在 node 那層**：寫在 node 分支一次，之後每格沿用，不在每格重設。每個 tick 程序（含孫程序）都放進該 node 的框，once 放進其 parent 的框（[B-603](../../daemon.md)）；〔使用者方向 2026-09-29 晚〕node 還沒經 cgroup_create 建框時，daemon 開格前自己建（不寫上限）。**daemon 在交給它的 cgroup 子樹內（[B-605](../../daemon.md)）自己建框、寫限制及讀實際值，不經 systemd；無 helper 時用通用 user 做**，授權和父限制照舊。controller 不可用回 unsupported。只有建帳號、chown、quota 需要 helper，無 helper 回 helper_unavailable。

cgroup_limits 改值時，daemon 先關受影響子樹的啟動閘門，與 pending start／wake／週期派出互斥；執行端核對整個框及後代全空才套用，否則 busy。已是相同值可核對後成功，不重寫。helper 的 start／limits 也須按同一資源子樹串行；不能只靠呼叫者先查 node.show。kernel 先逐筆暫停受影響子樹、等全空再要求更新；node.pause 本身不遞迴，更新後也不代替呼叫者 resume。

首次建 node 前，可先用父 node 的佈建權在授權 path 建立必要權限／帳號，再登記成員。建立帳號不擴大額度。所有動作只保證單步完成後回覆，沒有跨步回滾；斷線或中途失敗須先核對 OS 事實，不能盲重送或自動「撤回」chown。

## P-108．daemon 與 helper 的私有通道〔建議預設，未拍板〕

fork 前建 Unix SOCK_SEQPACKET socketpair，只供 daemon／helper；每包一個 JSON-RPC、最多 256 KiB、無 LF。必要 fd 以 SCM_RIGHTS 同包傳，數量不符即拒；runner／子程序不繼承通道。method 對應 `aos daemon helper <動作>` 內部子命令，只接這條既有私有通道與 fd，不成為公開 IPC 入口。

| method | params／fd | 效果 |
|---|---|---|
| daemon.helper.bind | registration、owner_uid；1 個密封 inst 快照 fd | 以啟動根額度、可信父鏈、原始 user 及路徑重驗；頂層 registration 用 P-101 形狀，只能是設定已有 roots |
| daemon.helper.unbind | node_id；無 fd | 全空且無已登記子節點才移除鏡像，子到父依序解除 |
| daemon.helper.start | node_id、target_uid；inst 快照與回報 pipe 共 2 fd | 重驗 UID、安置已配置資源、fork／降權／exec 固定 aos-runner；不收自訂 argv／env／輸出路徑 |
| daemon.helper.stop | node_id；無 fd | 只停登記範圍，TERM、2 秒後 KILL、確認後代全空；不收任意 PID／訊號 |
| daemon.helper.provision | P-107 params；無 fd | 重驗授權與固定動作後執行 |

成功 result 都為 `{node_id}`。start 要等 runner 結束、wait 回收與後代全空才回；daemon 從送出起就記 running。通道按 id 配對多筆在途，不能因等一格堵住其他 node／stop。全空但業務失敗仍可完成 start；無法全空回 cleanup_failed，保留阻擋及占用。

helper 用安全程序 handle 追蹤、wait 自己的孩子並跨 UID 收尾；daemon 不 wait helper 的孩子、不信裸 PID。helper 失聯時 daemon 只做自身權限可做的收尾，其他 UID 未確認全空就阻擋，斷線不代表退出，也不能重送不明 start。

快照是 daemon 取原始 user 的同份不可變 bytes。helper 不以 root 展開引用；runner 切身分後重新確認原來源可讀且 bytes 相同，才解析快照，base 仍依 P-010，不以快照位置計算。helper 以 OS handle 核對實體路徑，不能只信正規化字串。

鏡像只在記憶體。helper 存活時 bind／更新先通過它才公開；無 helper 時通用 user、無佈建權的登記可本地核對；只授 cgroup 動作時另核對它落在交給 daemon 的子樹內。其他 UID／三種特權動作（建帳號、chown、quota）的新登記回 helper_unavailable。既有通用 user 仍可執行。

## P-109．runner argv 與解析〔建議預設，未拍板〕

固定 argv：`aos-runner --inst-fd N --target /absolute/target --authorized-uid UID --status-fd N [--stderr /absolute/path] [--timeout-ms N]`。fd 已由父層打開；target 按 P-010 定原來源與 base，不改尋找規則。timeout 為正整數，省略不另加；authorized-uid 只是核對，不授予直接呼叫者切 UID 的能力。

啟動時已降權、設好群組與資源；依 P-108 驗 UID／來源，再按 [inst 正本](../../base/inst.md) 的順序展開與開檔。整份引用不得換已授權身分。

runner 初始 stdin／stdout 為 /dev/null，stderr 由 daemon 收集為 node 診斷，不直通 daemon stderr；〔使用者方向 2026-09-29，第十七批〕資料夾 node 暫定寫 `.aos/runner-stderr.log`（覆寫、ignored，[node P-200](../node.md)），輪替與留存以後再定；inst 可重導向子程序串流。--stderr 由目標身分以覆寫方式開檔、不自建父目錄，蓋過 inst 的 stderr 選項；runner 診斷仍走自身 stderr。status-fd 只供 runner，子程序 exec 前關閉。

環境依 [B-303](../../base/identity-resources.md)，不注入 AOS_* 或帶管理 fd／key；$env 先讀該環境，再套 inst.envs。所有檔案、mkdir、exit 皆用目標帳號。

## P-110．runner 結束與 125〔建議預設，未拍板〕

回報 pipe 一行 JSON、LF 結尾，無 version（非持久檔）；[schema](../schemas/daemon-runner-report.schema.json)。每次完整收尾只回報一次：

- 前置失敗：`{"started":false,"exit_code":125,"error":{"code":"UserNotGranted","message":"身分不在額度內"}}`。`error.code` 沿 inst 的 PascalCase 代號；CLI 用法錯則 exit_code 2。父層尚未 exec runner 的拒絕由父層合成相同回報。**不寫 inst exit**。
- 已越過執行前檢查／放行：`{"started":true,"exit_code":125}` 也合法，表示子程式自己退出 125；正常結束回原碼，找不到程式 127、不能執行 126 都屬此分支並寫 exit。子程式被 signal 結束時另帶 `signal`，exit_code 依 inst 為 128+N。runner 自己被殺則父程序讀 wait 狀態，不能從 128+N 猜。

runner 用法錯（含資料夾兩處皆無 inst）回 2；前置解析、開檔、身分失敗回 125，stderr 印 `代號: 白話`；其餘碼照 inst。signal、126／127 是 inst 執行規則對 [P-006](../README.md) 的特例。前置檢查可能已建立目錄或截斷輸出，125 不是「沒有任何檔案副作用」。

若已放行卻在寫 exit／收尾／發布回報時自己失敗，程序回 125，回報若仍可寫則 `started:true, exit_code:125, error:{code:"FinalizeFailed",message:"…"}`；不能把它當子程序已確定退出 125。沒有完整可信回報則結果不明，不能從 runner 碼推定從未執行。工作篇的結果檔保留這個區別與已取得的 wait 證據，這條 pipe 回報不是另一份持久工作結果。

後代清空、捕獲排空及取消競態依 [B-202／203](../../base/execution.md)。最終成功需要該範圍全空；收尾失敗可回 FinalizeFailed，但不能因此釋放尚在用的名額或開下一格。所有失敗不自動重跑 unknown。

〔使用者方向 2026-09-29，第十一批與後續旁檔改名裁定〕**once 單檔未啟動的最小旁檔**：當 daemon／helper 拒絕啟動 runner，或可信 runner 回報 `started:false`，daemon 在本次選定的 inst 旁發布 `<inst 檔名>.err`（例如 `job.json.err`），格式為 `{version:1,node_id,error}`，見 [schema](../schemas/daemon-launch-error.schema.json)。error 使用 P-005；私有 PascalCase 必須映成 `user_not_granted`、`user_mismatch`、`source_changed` 或 `start_failed` 等小寫代碼，不直接抄 runner error。每個 attempt 用新 inst 路徑；不覆蓋既有旁檔。

daemon 以已授權目標的目錄 handle 按 P-003 發布；不可信／無權註冊不能藉此任意寫檔。旁檔衝突或寫不出就 stdout 印一行警告，不另存 daemon 事項；發起者沒證據仍保留 unknown。資料夾 node 的啟動失敗寫自己的 `.aos/attention/`，不寫 inst 旁檔。

runner 已放行後不寫這份「未啟動」旁檔；wrapper 自己的 125、exec 126／127 或結果遺失依 work 篇處理。daemon 的暫存 wait 證據可供診斷，但不是另一份持久工作結果。

## P-111．錯誤〔建議預設，未拍板〕

RPC error 沿 P-005；`data` 必填 `code`、`retryable`。解析／請求／method／參數／內部錯誤分別用保留碼，其他用 -32000。下列是本篇的業務 code：

| code | 意思；預設 retryable |
|---|---|
| `forbidden`、`user_not_granted` | peer 無權／超出身分額度；false |
| `user_invalid`、`user_mismatch` | 帳號不能解析／前後身分不合；false |
| `source_changed` | 〔第十七批〕授權後 inst 原來源的內容與快照不同（不一定是身分改了）；false |
| `not_registered`、`registration_conflict` | 目標或父不存在／搶登記、換父、成環；false |
| `busy` | 活程序、維護狀態不合；true，等全空後先查狀態 |
| `stopping`、`cleanup_failed` | 正在停／無法確認後代清空；false |
| `helper_unavailable`、`unsupported` | helper 不在／部署不支援所選固定動作；false |
| `path_not_granted`、`conflict` | 超路徑範圍／OS 現況不符所要求設定；false |
| `resource_observation_failed` | cgroup 實際配置無法讀取；false |
| `response_too_large` | 一筆查詢結果就超過封包上限；false |
| `provision_failed`、`start_failed` | 固定動作或啟動失敗；false，先核對是否已有副作用 |

標準碼的 data.code 依序為 parse_error、invalid_request、method_not_found、invalid_params、internal_error，retryable=false。取不到合法 ID 的解析／請求錯誤依 P-004 回 `id:null`；超長行回一次 invalid_request 後關連線，避免無界讀取。可辨識合法 ID 就沿用，不造新 ID。

## P-112．schema 與最小範例〔建議預設，未拍板〕

[common](../schemas/common.schema.json) 只放共用型別；[daemon-rpc](../schemas/daemon-rpc.schema.json) 驗公開 IPC，[registration](../schemas/daemon-registration.schema.json) 與 [provision](../schemas/daemon-provision.schema.json) 驗其參數，[helper](../schemas/daemon-helper.schema.json) 驗私有通道。

[examples/daemon/](../examples/daemon/) 檔名首段對應 schema：config、state、runner_report、launch-error 驗同名 schema，helper_* 驗 helper，其餘驗 rpc。正反例涵蓋必填、未知欄位、版本、once 週期、查詢分頁及結果矛盾；解析、授權與 OS 事實仍須依正文驗收。
