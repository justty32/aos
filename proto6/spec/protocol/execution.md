# 執行交接：固定工作、啟動與收尾

← [共用協議](README.md)｜[固定工作 B-101～B-103](../base/work.md)｜[執行器 B-201～B-204](../base/execution.md)｜[身分與資源 B-301～B-304](../base/identity-resources.md)｜[生命週期 B-602～B-604](../base/lifecycle.md)

本篇擁有 P-200～P-212 與七份 `execution-*.schema.json`。所有新增欄位、機器子命令、fd 配置與傳輸編碼均為〔建議預設，未拍板〕；使用者裁定的 helper、非 root daemon、重啟全殺、可選 quota 與工具自行協調共寫，沿 [09-29 裁定](../../notes/2026-09-29-verdicts.md)，不重新決定。這是規格草稿，尚非實作完成的宣告。

## P-200．邊界與七份資料契約〔主編補〕

控制 writer 是准入、attempt／claim 與結果的唯一權威；helper 只查可信登記、建 leaf、設限、降權並啟動固定 runner。supervisor 是留在控制資源域的可信角色，可以與 daemon 同程序，不要求另起常駐服務。runner 一次只執行一份固定工作，結束後不接下一單。工具 stdout、掛勾 stdout、PID 數字與 JSON 裡自報的 owner 都不構成授權。

| Schema | 根型別與公開片段 | 誰提供、誰讀 |
|---|---|---|
| [execution-template](schemas/execution-template.schema.json) | 根及 `#/$defs/ExecTemplate` | 工具 manifest 引用；非特權 adapter 讀 |
| [execution-work](schemas/execution-work.schema.json) | 根及 `#/$defs/FixedWork`；另有 `HookWork` | adapter 提候選，控制端固定，降權 runner 讀 |
| [execution-result](schemas/execution-result.schema.json) | 根及 `#/$defs/ExecResult` | supervisor 產生，控制端導入，agent 唯讀 |
| [execution-launch](schemas/execution-launch.schema.json) | `LaunchRequest/LaunchReply/LaunchRejected/GateRelease/GateRecord/ExecError/WaitStatus/ResultDelivery/ResultReceipt` 各在 `$defs` | 控制端、helper、runner 的可信交接 |
| [execution-observation](schemas/execution-observation.schema.json) | `ProcessIdentity/ProcessRecord/Cancellation/Cleanup/Recovery/Retirement/StopRecord` 各在 `$defs` | supervisor 觀測，控制 writer 保存 |
| [execution-profile](schemas/execution-profile.schema.json) | 根及 `#/$defs/Profile`、`ResourceLimits` | 管理者發布，daemon／helper 唯讀 |
| [execution-registry](schemas/execution-registry.schema.json) | 根及 `#/$defs/AgentRegistration`；另有 `#/$defs/LaunchSnapshot` | 管理者登記；daemon 匯出 launch 快照 |

launch／observation 根是明確種類的 union；`ProcessIdentity` 是嵌入片段，不單獨當持久紀錄。基本 ID、BlobRef、Error、Outcome 一律相對 `$ref` 到 `control-common.schema.json`，不另定第二套。所有範例在 [examples/execution/](examples/execution/)；標示的摘要除了 P-201 實算例外，均是形狀示意，不能用來宣稱 blob 已存在。

**Given** 工具印出一份合法 ExecResult；**When** 控制端讀 stdout；**Then** 只把它保存為不可信輸出，不接受其 state 或 owner；只有受信任回報通道能導入結果。

## P-201．ExecTemplate 變成一次固定工作〔建議預設，未拍板〕

依 [A-401／A-402](../agent/tools.md)。工具 manifest 的 `exec_ref` 指向 ExecTemplate；它只含 version、argv 及可省 cwd／env／timeout_ms／output_limit_bytes，不能夾 owner、stdin 路徑、UID、redirect 或 `$ref` 指示詞。adapter 驗 arguments 符合工具 input_schema 後，採 RFC 8785 UTF-8 編碼成唯一 stdin blob，不加換行；owner／run／job 從可信 claim 與已驗證 JobDraft 補上。cwd 缺省取本次固定 bundle；其餘缺省按 B-101：env={}、stdin_blob=null、timeout_ms=60000、output_limit_bytes=1048576。不在 argv 插值，不拆詞，也不隱式 shell。

最小 template、工具 arguments 與產生的工作如下；arguments `{}` 的兩個 UTF-8 bytes 及 SHA-256 是實值：

```json
{"version":1,"argv":["/usr/bin/true"]}
```

```json
{}
```

```json
{"version":1,"agent_id":"agent_a","run_id":"run_a","job_id":"job_a","argv":["/usr/bin/true"],"cwd":"/srv/aos/agents/agent_a","env":{},"stdin_blob":{"key":"args_a","sha256":"44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a","bytes":2},"timeout_ms":60000,"output_limit_bytes":1048576}
```

控制端驗描述原始 UTF-8 <=256 KiB、stdin <=16 MiB、字串無 NUL、owner 與 run 歸屬，再保存**這份確切描述 bytes**及摘要；後續不重新序列化來替代原摘要。上述三份分別由 execution-template、工具自己的 input_schema、execution-work 驗證。blob 導入與唯讀 fd 由 storage 篇負責，控制端不能用 agent 給的 path 請 root 代讀。排隊後改來源檔不影響既有 job；程式本身與 cwd 資料沒有自動快照。

同一 job 重送只能引用相同固定材料；異摘要衝突。是否另建 retry attempt 歸控制層，runner 不重跑；unknown 的外部副作用不能靠重新送 template 當成沒發生。

**Given** arguments 含空白、引號及 `$()`；**When** adapter 形成工作並執行；**Then** 它們只出現在 stdin JSON，argv 與 template 一致。**Given** 排隊後改 template 或 stdin 來源；**When** 放行；**Then** 仍讀已固定摘要；缺失／損毀拒絕啟動，不替換新檔。

## P-202．管理 profile、登記與唯讀 launch 快照〔建議預設，未拍板〕

管理者經 P-011 第 2 項的本機發布 adapter 發布 profile／registry；這裡不新增公開管理 RPC。profile 明列 backend、UID/GID 分配與保留範圍、cgroup/data/control 根、每個可寫位置的容量歸屬、全局 work 限制、控制域保留資源及 probe_revision。registry 依 C-02 再帶 agent 合計 resource_limits；quota 啟用才需要 project 與 quota_bytes／quota_inodes。完整最小 JSON 見 [profile.minimal](examples/execution/profile.minimal.valid.json) 與 [registry.minimal](examples/execution/registry.minimal.valid.json)。

`uid_mapping` 的數字是該部署有效 Linux ID；實際 host 映射須由 backend probe 核對。範例的 backend 名稱與額度只是示意，不代表外牆已選定。profile 必須通過 B-302 的隔離／fork／cgroup／可選 quota 實測；有效 UID 不得與 root、daemon、kernel、管理及控制服務重合，live agent 不得共 UID；groups 只能取管理者核准集合。全局與 agent 合計上限在建 leaf 前生效，leaf memory.oom.group=1、swap=0，控制域不受 agent memory.max 限制。

依 P-011 第 6 項，daemon 從已准入的帳本與管理登記產生不可變 `LaunchSnapshot`。快照放在管理者指定、只有控制 writer 能發布且 agent 不可寫的 `<launch_registry_root>/<snapshot_revision>.json`；同 filesystem 暫存、fsync、不可覆蓋 rename、父目錄 fsync 依 P-004。helper 只在這個可信根讀命名快照，不讀 SQLite、不接任意路徑、不接受 agent 自送快照。部署者保護父目錄、profile 與固定 aos 程式，daemon 負責內容與 revision 綁定；只有 daemon 的可信派出意圖能產生 launch 快照。

快照另含管理者指定的 `runtime_home/runtime_tmpdir` 絕對路徑，runner 用它們建立 HOME／TMPDIR；一般執行 runtime_home 必須等於登記 home，scratch 先佈建且屬 profile 核准可寫範圍。helper 不開這兩條路徑。快照含 `attempt_id/agent_id/registry_revision/profile_id/probe_revision/execution_kind`、work／stdin 摘要、固定登記及掛勾關係，**沒有 argv、cwd、arguments 或憑證**。一般執行 service 欄位為 null；系統掛勾 registration=null，改用管理者指定非 root 的 service_uid/service_gid/resource_domain/service_limits。完整例子見 [registry.launch](examples/execution/registry.launch.valid.json) 與 [registry.system-hook](examples/execution/registry.system-hook.valid.json)，型別為 execution-registry 的 `LaunchSnapshot`，不是根 AgentRegistration。

helper 核對請求與快照的 tuple、摘要綁定存在、probe／登記版本已核准及身分白名單，不解析 work fd。runner 才核對實際工作／stdin 摘要。快照 filename 是查詢鍵，不是授權。登記改版可採排空或 attempt 邊界切換；已準備／放行的執行持有舊版到收尾，新准入才用新版，絕不在同一次執行中換 UID／cgroup。快照保留到相關執行與恢復證據不再需要，由正常留存清理，不能更新同名檔來換身分。

quota_backend=none 合法且 project=null；TMPDIR 不是牆。磁碟暫存算檔案系統政策，tmpfs 算 cgroup 記憶體與掛載容量，外部 workspace 的共寫由工具協調。profile schema 通過不能宣稱 quota 是安全邊界或已測過 Windows 權限。

**Given** fake snapshot、舊 revision、新登記改成 UID 0 或缺一項 probe；**When** launch；**Then** fail closed，不以 daemon UID 降級執行。**Given** 新版登記已發布而舊 attempt 尚在；**When** 收尾；**Then** 證據仍記原 registry_revision。

## P-203．機器程序、argv 與環境〔建議預設，未拍板〕

以下 fd 數字是**由父程序實際繼承的本機位置**，不是 JSON 授權；缺少必填選項、多餘選項或 fd 型別不符均拒絕。範例部署路徑不可由工作覆寫。沒有自訂 `AOS_*` 環境輸入，沒有用 env 選 owner、socket 或 revision 的捷徑。

| 角色／完整 argv 範例 | 身分、stdin/stdout/stderr 與其他 fd | 退出語意 |
|---|---|---|
| `["/usr/bin/aos","exec-helper","--listen-fd","3","--registry-root","/var/lib/aos/launch","--profile-fd","4","--control-uid","900"]` | systemd 啟動 root helper；3 是受保護 Unix 監聽 socket，4 是管理 profile 唯讀普通檔；0 關閉、1 接 /dev/null、2 有界服務診斷。所有選項必填。 | 正常停 0；初始配置錯 2；自身 I/O 等失敗 125；單一請求被拒不令服務退出。 |
| `["/usr/bin/aos","exec-runner","--work-fd","3","--stdin-fd","4","--gate-fd","5","--exec-error-fd","6","--launch-fd","7"]` | helper 固定程式與固定 argv；已降至核准 UID。3 工作唯讀檔、4 已核准 stdin 唯讀檔或 EOF pipe、5 放行 pipe 讀端、6 CLOEXEC 錯誤 pipe 寫端、7 可信快照唯讀檔；0 暫接空輸入，1/2 為輸出捕獲 pipe。所列選項必填；另可帶 `--extra-fd-count N`（預設 0），指從 fd8 起真正繼承的受限角色 fd。 | runner 成功時直接 exec 目標，之後 wait 狀態是工具原狀態；exec 前失敗另送 ExecError 並退 125，初始協議錯可退 2。必須看錯誤通道，不從 125 猜是誰失敗。 |
| supervisor（daemon 內可信角色） | 不另定 argv；持有 pidfd、放行寫端、錯誤讀端、輸出讀端及控制 writer 內部連接，留在控制域。 | 不借工具 exit 當自身 exit；若實作成單次包裝角色，約定回報持久完成後 0，發布失敗 125，設定錯 2，沿 P-008。 |
| 工具／agent 掛勾／系統掛勾 | argv 是已固定的工作或掛勾 argv；stdin 分別為 arguments／agent-hook-input；stdout/stderr 只進捕獲 pipe。 | 子程式 exit 0..255 與 signal 獨立保存，不轉成 shell 的 128+signal。 |

helper 自己的環境由服務管理者建乾淨集合，不繼承 agent env。固定 runner 啟動前不套用描述 env；放行及降權驗證後才建工作環境：PATH=/usr/bin:/bin、HOME=登記 home、TMPDIR=可信 scratch、LANG=C.UTF-8，再套允許的描述 env，HOME／TMPDIR 禁覆寫。scratch 必須屬 profile 已聲明的容量範圍。系統掛勾的 HOME／TMPDIR 由管理服務設定提供，不拿 agent home 當服務家目錄。繼承憑證、loader env、管理 socket 及未核准 fd 均清掉；工具自己的一般合法 env key 沿 B-101，不把合法自訂 key 一律禁掉。

精確 loader 變數排除集合尚未在正本定義，見 P-212；固定 runner 的 loader 環境無論如何不能受工作 env 影響。LLM 收件通道若交給工具，僅是 llm 篇綁定原 attempt 的受限通道，不能把此 helper socket 或代發 key 傳下去。

**Given** 工作含 `env.HOME` 或多傳控制 fd；**When** 啟動；**Then** 拒絕覆寫或關閉非核准 fd。**Given** 工具正常 exit 125；**When** 錯誤 pipe 已在成功 exec 關閉；**Then** 保存 failed/exit、exit_code=125，不當作 runner 故障。

## P-204．控制端到 helper：可信 socket 與 fd 交付〔建議預設，未拍板〕

helper socket 只接受 `SO_PEERCRED` 的 UID 等於已登記控制 daemon UID 的連線，先認證才讀 launch 資料，agent 或其他 UID 一律拒絕。可信內部協議採 Unix `SOCK_SEQPACKET`，一 packet 一份 UTF-8 JSON，<=256 KiB；有 fd 時使用同一次 sendmsg 的 SCM_RIGHTS。截斷 packet／ancillary、未列 fd、數量不符、可寫或非普通工作檔都拒絕，並關閉已收到的 fd。這不是 P-005 公開 JSON-RPC，不加 method，也不套 RPC file envelope。

最小請求（無 stdin blob）與準備完成回覆：

```json
{"version":1,"kind":"launch","attempt_id":"attempt_a","registry_revision":1,"snapshot_revision":"snap_a","execution_kind":"tool","hook_run_id":null,"fd_roles":["work"]}
```

```json
{"version":1,"kind":"prepared","attempt_id":"attempt_a","hook_run_id":null,"snapshot_revision":"snap_a","identity":{"boot_id":"00000000-0000-0000-0000-000000000001","pid":3001,"starttime_ticks":12000,"cgroup_relative_path":"agents/agent_a/attempt_a"},"fd_roles":["pidfd","gate_write","exec_error_read","stdout_read","stderr_read"]}
```

請求的 fd 順序固定：work，stdin（僅有 blob 時才有第二個）；daemon／非特權內容 adapter 先開好、核對唯讀快照，root 不碰 agent 路徑。回覆的 fd 順序如上：pidfd 指那個程序實體、gate_write 只給可信 supervisor、exec_error_read 與 stdout/stderr 讀端分開；pidfd 的可用性按核心介面驗證，不把它當一般檔。helper 只持有準備／交付所需副本，交付完成關閉多餘副本；固定 child 只保留 P-203 的 fd，成功 exec 前關閉 3/5/7，4 複製到 0 後關閉，6 設 CLOEXEC，最終工作只拿 0/1/2 與該角色另有明文授權的內容 fd。

上述 fd 關閉表是普通工具路徑；tick／系統掛勾另依可信 execution_kind 使用固定白名單，不能由 payload 要求任意保留 fd：

| execution_kind | SCM_RIGHTS 的 fd_roles 順序 | runner 到目標程序的配置 |
|---|---|---|
| tool | work，stdin 可省 | 只留 0/1/2；stdin 可省則為 EOF |
| tick | work、tick_input、tick_commit、blob，接零或多個 tick_content | runner 的額外 fd8 起依序接這些受限角色；exec 前搬成 input=3、commit=4、blob=5、content=6 起，stdin=EOF，沿 agent-state P-301 |
| agent_hook | work、stdin | 只留 0/1/2，不能拿 commit socket |
| system_hook | work、stdin；僅已登記 clean 角色可再加 clean_channel | clean_channel 暫在 runner fd8，exec 前搬成目標 fd3，供 storage P-507 的 `aos clean --mode system-post --channel-fd 3`；其他掛勾只留 0/1/2 |

helper 把額外 fd 的數量放 `--extra-fd-count N`，不能指定任意目的 fd；它只驗角色數量、類型與可信用途，內容由降權 runner 檢查。tick_input/tick_content 是唯讀普通快照，tick_commit/blob/clean_channel 是已連線、由控制入口限定 claim／owner／清理用途的 socket。tick_input 內的 content_fds 對應**搬移後**的 6 起位置，ref/role/摘要由 agent-state 契約核對；commit 不是全權管理 socket。runner 搬移前把錯誤 pipe 暫存到不衝突的 CLOEXEC fd，關閉工作／gate／launch 材料，安全 dup 各目標 fd、關閉所有來源副本，避免把 fd6 的 exec 錯誤端覆蓋成內容。tick 的固定 argv 必須是 agent-state P-301 的機器形狀；其他執行種類不能冒用 tick fd 角色。完整請求見 [launch.tick](examples/execution/launch.tick.valid.json)、[launch.system-hook](examples/execution/launch.system-hook.valid.json)。

helper 是固定 child 的真正父程序，負責 wait/reap；pidfd 就緒只是通知，supervisor 不能憑它猜退出碼。helper 收到主程序 wait 狀態後，透過原先已認證 socket 發 `WaitStatus`，不寫帳本、不解讀 stdout：

```json
{"version":1,"kind":"wait_status","attempt_id":"attempt_a","hook_run_id":null,"snapshot_revision":"snap_a","identity":{"boot_id":"00000000-0000-0000-0000-000000000001","pid":3001,"starttime_ticks":12000,"cgroup_relative_path":"agents/agent_a/attempt_a"},"exit_code":7,"signal":null}
```

helper 暫存同鍵 wait 狀態供同一控制端重取，writer 保存後才算耐久證據。wait 回報丟失且 helper 崩潰時不得由 pidfd／空域推測 exit 0，按恢復 unknown；收到 wait 狀態仍須排空後代與輸出。helper 做必要 wait/reap 不代表取得結果提交權，ExecResult 仍只由 supervisor 結合全部證據產生。

去重鍵為 `(attempt_id, hook_run_id)`；一般 tool／tick 的 hook_run_id=null，掛勾則是獨立 hook_run_id。相同鍵及相同 snapshot 重送回同一次準備狀態，允許重送同一組 fd 的副本但不另建 leaf／child；已有 supervisor 接管時不得讓兩個讀者同時消費 pipe。若同鍵同 snapshot 已 reap，原 LaunchRequest 重送改回原 WaitStatus，這就是 wait 證據的重取入口，不另建 child；若沒有可重交的 prepared fd、也沒有可回傳的 wait 證據，才以 conflict 表示不能重新準備，控制端從自己帳本及持久證據查狀態。重送用 [launch.replay](examples/execution/launch.replay.valid.json)，它與原請求相同。

```json
{"version":1,"kind":"rejected","attempt_id":"attempt_a","hook_run_id":null,"error":{"code":"conflict","message":"此執行已準備或已結束，請核對原證據","retryable":false}}
```

helper 不持有耐久帳本；去重不能只靠它的記憶體 map。控制 writer 先持久派出意圖，helper 以受控唯一 leaf 與存活 child 核對；helper 重啟或 fd 遺失時暫停相關准入，先由控制端恢復對帳，不能因 map 空了再開同鍵 child。socket 斷線本身不證明未啟動；未放行 child 等不到有效 gate 就退出。

**Given** agent 冒稱 attempt_a、fd_roles 對不上或同鍵換 snapshot；**When** 接收；**Then** 分別在認證／fd／衝突檢查拒絕且不建第二 leaf。**Given** prepared 回覆遺失後重送；**When** helper 尚持有該準備狀態；**Then** 仍是原 pidfd 與程序；無法重交時先對帳。

## P-205．先記準備證據，再放行與 exec〔建議預設，未拍板〕

依 B-201、B-303。控制交易先 reserved＋派出意圖；helper 查快照，先設全局／agent 域及唯一 leaf 上限、記 memory.events 基線，再讓固定 child 進 leaf。child 清原附加群組、僅設核准 groups，設 GID／UID、清 capabilities、no_new_privs、關閉其他 fd，核對實際 UID/GID/groups/cgroup；任一步失敗都不能讀工作描述。prepared 回覆只在這些保證完成後送出；supervisor 保存 ProcessRecord 與 GateRecord，writer 耐久完成才可放行。

```json
{"version":1,"kind":"gate","gate_record_id":"gate_a","attempt_id":"attempt_a","hook_run_id":null,"snapshot_revision":"snap_a","recorded_at_ms":1000,"phase":"release_intent","identity":{"boot_id":"00000000-0000-0000-0000-000000000001","pid":3001,"starttime_ticks":12000,"cgroup_relative_path":"agents/agent_a/attempt_a"}}
```

```json
{"version":1,"kind":"release","attempt_id":"attempt_a","hook_run_id":null,"snapshot_revision":"snap_a","gate_record_id":"gate_a"}
```

gate pipe 是一次性、<=256 KiB 的單份 JSON 至 EOF；supervisor 寫完立即關閉，runner 必須等 EOF 才驗完整物件及全部識別。半份／壞資料／只有 EOF 均不執行描述。資料不由工作 stdin 傳；argv 複雜資料不放 env。runner 核對 work bytes 摘要、stdin 摘要／大小及 owner 後，降權進 cwd、按 argv[0]（無 slash 時走工作 PATH）找程式，再 exec。摘要檢查用 pread，或在交付前明確 seek 至 offset=0；給工作的 stdin 與內容檔使用獨立 open-file-description，其他讀者不能推進它的 offset。root 從未開這些路徑。正常工具 timeout 從放行起算；tick／掛勾的共享預算另見 P-209。

`GateRecord.phase` 是證據事件：prepared、release_intent、release_observed、never_released；不是 attempt state，也不是保證每個 phase 必然存在。已持久 release_intent 而未保存放行觀測，視為不確定，不能猜沒有寫入 pipe。只有可驗證的未放行關閉／拒絕及已清空程序證據，才能保存 never_released；「沒找到 running」不夠。放行後控制端記 running，DB 與放行不是原子操作。

錯誤通道一樣讀至 EOF、一份 <=256 KiB JSON。固定 runner 在 exec 前失敗寫 ExecError；成功 exec 因 CLOEXEC 關閉該端。EOF 本身仍須結合 gate 與 wait 證據，不能排除 runner 在 exec 前被殺。最小失敗：

```json
{"version":1,"kind":"exec_error","attempt_id":"attempt_a","hook_run_id":null,"stage":"exec","errno":2,"error":{"code":"invalid_record","message":"降權後找不到程式","retryable":false}}
```

prepared 前的早期失敗由 helper 讀取 ExecError，透過 LaunchRejected 的 error.details 保存 `stage/errno` 與可信診斷；它先清空 child／leaf，控制端再記 failed/spawn_error。prepared 成功後才把錯誤讀端交 supervisor，helper 關自己的副本，避免兩個讀者搶管線。若甚至無法清空，保留證據及占用而不是宣稱啟動失敗已收尾。stage 分資源、群組、GID/UID、capabilities、no_new_privs、fd、身分、gate、描述解碼、stdin、cwd、exec；保留真實 errno，沒有 errno 就 null，不創造虛構數碼。EAGAIN／ENOMEM／ENOENT／EACCES 的 exec 前錯誤皆以 spawn_error 收尾；清空域後才回名額。一般 Error code 用 C-04 既有值，細部 errno 與 stage 才是系統原因。

**Given** 在 reserved、prepared、release_intent、實際放行與 running 之間逐點殺控制端；**When** 恢復；**Then** 至多一個執行範圍，未知窗口不重送 gate／重開同 attempt。**Given** setuid 或移入 cgroup 失敗；**When** 檢查；**Then** 目標 argv 從未被讀取執行。

## P-206．可信結果、輸出與持久收據〔建議預設，未拍板〕

supervisor 持有控制域的輸出讀端與 pidfd；工具的 stdout/stderr 只保存內容，不解析為控制回報。各自到 output_limit_bytes 即停止保存超額 bytes、持續排空並丟棄、提交 output_limit 取消意圖，不能塞住子程序或無限寫碟。B-103 的 bytes 記實際讀到的 bytes（含丟棄部分），BlobRef.bytes 記有保存的 bytes；這個計數解釋為本篇建議編碼，計數不減少、不得溢出 C-01 整數上限，飽和時須留受限診斷。

最小成功 ExecResult：

```json
{"version":1,"attempt_id":"attempt_a","job_id":"job_a","agent_id":"agent_a","state":"succeeded","reason":"exit","exit_code":0,"signal":null,"started_at_ms":1000,"finished_at_ms":1002,"stdout_blob":null,"stderr_blob":null,"stdout_bytes":0,"stderr_bytes":0,"truncated":false}
```

null blob 表示沒有保存的引用，不能冒充「已保存空字串」。需要證明完整空輸出時導入 bytes=0 的 blob。失敗／unknown／截斷的完整例子見 P-211。正常成功要主程序 exit 0、無先提交取消、pipes 排空、結果持久且 cgroup populated=0；強制清掉後代即 failed/signal，即使主程序 exit_code=0。JSON 工具回傳是否合法由 A-403 的 OutcomeAdapter 判，不能改寫底座程序事實。

ExecResult 導入受管 blob 後，Outcome.result_ref 指它；Outcome.status 必須與 ExecResult.state 一致，非成功附 Error。可信 ResultDelivery 使用 execution-launch schema：

```json
{"version":1,"kind":"result","report_id":"report_a","attempt_id":"attempt_a","outcome":{"status":"succeeded","result_ref":{"key":"blob_result","sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","bytes":400},"error":null},"cleanup_ref":{"key":"blob_cleanup","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","bytes":640}}
```

```json
{"version":1,"kind":"result_receipt","report_id":"report_a","attempt_id":"attempt_a","disposition":"recorded","error":null}
```

同程序 supervisor 直接交控制 writer；跨程序時用 P-004 管理者綁定 supervisor 服務 UID／principal 的用途專屬檔案通道認證；若經 socket 導入，入口另做 SO_PEERCRED。沿 P-003／P-004 的 requests/responses 同 delivery_id 持久檔交換，內容直接是上述 versioned record，不用 RPC 包裝。stdout 沒有這個入口。sender 先持久結果與 cleanup，writer 驗 owner、原 attempt、blob 摘要及觀測證據；確定成功／失敗／取消的收尾須清空，unknown 可連同 populated=true/null 的 Cleanup 入帳而保留名額及 claim。再以單次交易保存結果、計量及收據，最後發布回覆。沒收據就以同 report_id／同內容重送，可換 delivery_id；disposition=duplicate 回原已登記事實，不再計量／釋放名額。同確定終局異內容回 conflict＋Error，保留原結果。unknown 依 C-03 可由可信證據單調補全，用新 report_id 保留舊 unknown 事件，不能覆寫較新 attempt 的選定結果。

結果持久化或回覆丟失不是工具失敗碼，包裝器可退 125；上層必須查原收據。沒有可信結果時走 unknown，不能拿子程序 exit 0 或 wrapper 0 補成功；工作也不因送結果失敗而自動重跑。

**Given** 主程序 exit 7、無限輸出、工具偽造 result JSON 及回覆遺失各一例；**When** 控制端導入；**Then** 分別為 failed/exit/7、failed/output_limit/truncated、只保存不可信 stdout、同 ID 回原收據，沒有雙重結算。

## P-207．取消、清理與觀測證據〔建議預設，未拍板〕

公開 `attempt.cancel/get` 歸 control-rpc；此處只接已授權且已持久的控制意圖。Cancellation 是控制 writer 到 supervisor 的可信紀錄，intent_id 為原意圖，不以新送達次數再算取消：

```json
{"version":1,"kind":"cancel","observation_id":"obs_cancel","attempt_id":"attempt_a","hook_run_id":null,"intent_id":"cancel_a","committed_at_ms":1001,"cause":"canceled","term_grace_ms":5000}
```

未放行先阻止 gate；已放行先保存 canceling，再對可識別受管程序 SIGTERM，預設 5000 ms 後 cgroup.kill。不能只殺主 PID 或 process group。取消／timeout／output_limit 的競態由控制交易提交順序裁定：取消先則後續 exit 0 仍 canceled，timeout 先則 failed/timeout；已確定終局再取消只回已終止。不重設 monotonic deadline，也不因重送增加寬限。清空不明時 unknown、保留名額及 claim，不能假清理完成。

Cleanup 是 supervisor 到 writer 的證據；完整例子：

```json
{"version":1,"kind":"cleanup","observation_id":"obs_cleanup","attempt_id":"attempt_a","hook_run_id":null,"observed_at_ms":1002,"identity":{"boot_id":"00000000-0000-0000-0000-000000000001","pid":3001,"starttime_ticks":12000,"cgroup_relative_path":"agents/agent_a/attempt_a"},"term_sent":true,"kill_sent":false,"descendants_forced":false,"populated":false,"pipes_drained":true,"home_lock_available":null,"resource_usage_saved":true,"memory_events_delta":{"oom":0,"oom_kill":0},"parent_oom_evidence_ref":null,"controlled_io_errno":null,"error":null}
```

`populated=null` 表示未能核實，不能等同 false；tick／掛勾收尾須另外核對 home 鎖，普通工具此欄 null。lock 觀測只是證據，下一個 claim 的取得仍必須原子核對並持鎖，不能拿舊的 true 通行。identity=null 只適用 child 尚未建立或無可信程序識別，需其他閘門證據配合。resource_usage_saved=true 要對應帳本已保存的實際計量，才可刪空 cgroup。observation_id 去重；同 ID 異內容拒絕，後續觀測使用新 ID，writer 不接受較舊觀測推翻已確定結果。

ProcessRecord 在放行前保存 boot ID、PID、starttime_ticks、相對 cgroup 路徑、登記版本及 leaf memory.events 基線；pidfd 不序列化。OOM 必須有 leaf oom_kill 增量且工作失敗；父域 OOM 另附 parent_oom_evidence_ref，不能單憑 SIGKILL 猜 OOM。EDQUOT 只有受控 I/O errno 或可信診斷能支持 quota，工具忽略 EDQUOT 再 exit 0 不代表業務資料完整。EAGAIN／ENOMEM 保留在 ExecError，不偷換成 OOM。

**Given** 工具 fork＋setsid、主程序 exit 0；**When** 收尾；**Then** 停止後代、確認 populated=0、保存 failed/signal 與 descendants_forced=true 後才歸還名額。**Given** SIGKILL 無 OOM 計數增量；**When** 結果分類；**Then** 不標 oom。

## P-208．重啟、停機、停用與退役〔使用者方向 2026-09-29；編碼為建議預設，未拍板〕

原生 Linux 與 WSL 都由 systemd 啟動，control/work 同 unit 的首版預設 KillMode=control-group；重啟全殺，不認領孤兒。控制 writer 取得排他鎖後暫停派工，按帳本、launch／gate／process 證據、可信已發布結果與受管 cgroup 對帳。boot 不同只證明舊程序已死，不證明未曾產生外部副作用；boot 相同也不能只看 PID。

Recovery 完整最小 unknown 例：

```json
{"version":1,"kind":"recovery","observation_id":"obs_recovery","attempt_id":"attempt_a","hook_run_id":null,"observed_at_ms":1003,"old_identity":{"boot_id":"00000000-0000-0000-0000-000000000001","pid":3001,"starttime_ticks":12000,"cgroup_relative_path":"agents/agent_a/attempt_a"},"current_boot_id":"00000000-0000-0000-0000-000000000001","gate_evidence":"release_uncertain","published_result_ref":null,"cleanup_ref":{"key":"blob_cleanup","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","bytes":640},"proposal_receipt_ref":null,"decision":"unknown","side_effects_unknown":true}
```

恢復決策只有四種：有可信結果且清空就 import_result；確切 never_released 且清空才 spawn_error；可能放行而沒可信結果就 unknown；無法清空就 await_cleanup，保留占用。不存在 result 檔不證明工具未執行，不重新給 timeout。tick 的 C-05 提案收據另以 proposal_receipt_ref 核對：已提交 checkpoint/final 不因程序 unknown 撤銷，清空前仍不放 claim；無提案收據才以新 tick job／generation 推進，不能因此重做未知工具／LLM。hook_run_id 非 null 的恢復只記掛勾結果，不補跑該次掛勾、不產生工具 Outcome。

正常 stop 先停新准入、保留 queued／ready，按 control-config 的 stop_grace_ms 等待，未完走取消。StopRecord 保存未清空 attempt／hook 名單、結果與計量是否已耐久；逾時或 kill 失敗非零退出，不能刪 cgroup 或假釋放名額。8000 ms WSL、30000 ms 原生 Linux 僅是正本建議值，不是新的硬保證。來不及收尾遭 VM 終止者下次照 unknown。

停用先 status=disabled，再排空，保留排隊工作。Retirement 由管理者明示處置、控制 writer 記錄；只有無活程序、無 held claim、核對未結結果與 quota／檔案 ownership 清單後才能 retired。清單使用受管 BlobRef，內容是管理者已核對的盤點證據，不能把其任意路徑拿來要求 root 清檔。首版留住 UID/GID/project/home，不自動回收或刪除。完整 JSON 見 [observation.stop](examples/execution/observation.stop.valid.json)、[observation.retirement](examples/execution/observation.retirement.valid.json)。未結結果不應被遺忘；盤點完且按既有處置結清才能把 unresolved 清單清空。

**Given** daemon crash、WSL 消失、PID 重用各一次；**When** 恢復；**Then** 不錯殺非受管程序，無可信結果的在途工作 unknown，已有提交不撤銷。**Given** UID 還擁有舊檔或域未清空；**When** 退役；**Then** 留盤點，未清空者不能 retired，數字身分不分給新 agent。

## P-209．掛勾實際執行與 claim 收尾〔建議預設，未拍板；沿 P-011 暫定 7〕

掛勾登記、stdin 與結果語意分別引用 `agent-hook-registration.schema.json`、`agent-hook-input.schema.json`、`agent-hook-result.schema.json`，由 agent-state 篇唯一持有。本篇只定程序及 fd，不重造掛勾結果、tool Outcome 或 Proposal。system hooks 容器在 control-config；agent hooks 在固定 bundle。各自按 order 再 name 排序。系統與 agent 清單之間同值的排序尚待整合，見 P-212；不能靠目錄列舉順序猜。

取得 claim 後控制端替**每一次**掛勾分配獨立 hook_run_id，與父 claim 的 attempt_id/generation 綁定於 LaunchSnapshot。launch.attempt_id 是父 tick attempt_id，hook_run_id 才區分多個 pre／post 執行；不新增 C-03 kind=hook、不虛構可被工具結果消費的 attempt。agent 掛勾以登記 UID、agent 合計域內的獨立受控 leaf 執行；一般 leaf 用 attempt_id，掛勾 leaf 用 hook_run_id 作獨立鍵，不能與父 tick 共用同一 leaf 名稱；系統掛勾以管理配置的非 root 控制服務 UID、控制側另設限的服務域執行，不能借 root helper 身分跑掛勾正文。準備／gate／fd 同 P-203～P-205；system_hook 的身分只來自管理快照，agent 不能提交這個執行種類。掛勾 fd3 使用 execution-work 的 `#/$defs/HookWork`，不使用必含 job_id 的 FixedWork：`{version:1,kind:"hook_work",template:ExecTemplate,stdin_blob:BlobRef}`。控制端把登記 argv、有效 timeout、output limit 與 cwd 明填進 template；agent hook cwd 取本次 bundle.cwd，system hook cwd 取管理服務 runtime_home。stdin_blob 必指本次 agent-hook-input，摘要與快照 stdin_sha256 相同；整份 HookWork 摘要等於 work_sha256，runner 依可信 execution_kind 選型。完整例見 [hook-work.minimal](examples/execution/hook-work.minimal.valid.json)。

stdin 沿 agent-state 的 agent-hook-input，含它已定義的 hook_run_id；不把這個欄位塞進工具 arguments。識別同時由可信 launch 快照核對，即使 hook stdin 的 attempt_id 可為 null，仍不能遺失與 claim 的關係。

```json
{"version":1,"hook_run_id":"hook_pre_a","agent_id":"agent_a","run_id":"run_a","when":"pre","attempt_id":"tick_a","tick_outcome":null}
```

```json
{"version":1,"hook_run_id":"hook_post_a","agent_id":"agent_a","run_id":"run_a","when":"post","attempt_id":"tick_a","tick_outcome":"committed"}
```

pre 在 tick 前依序跑；post 在提案交易完成或 tick 被收尾後、claim 釋放前跑。每項 timeout_ms 預設 30000；agent pre／tick／agent post 共用本次 tick 的剩餘執行預算，從取得 claim 起計，不在每個 hook 放行時重設一整份 tick timeout。post 只能用剩餘時間，預算用完就不再開 agent hook，記未執行原因。系統掛勾另計自身有界 timeout，不消耗 agent tick 時間；兩個正本對「總 deadline」的算式仍需 P-212 的整合說明，不能暗中新增無界 claim 延期。

pre 失敗且 on_failure=skip_tick，先清空已啟動掛勾、記原因，不啟動 tick、不判 run failed；核對鎖與證據後釋放 claim。依 P-011 暫定由控制排程做有界退避或等新事件；例如 60 秒倍增、最多 15 分鐘只是可採預設。writer 必須保存等待原因及到期／事件條件，不立即因 ready 還在就重跑。skip_tick 時 post 是否執行與對應 tick_outcome 正本未定，本篇列待決，不虛構 skipped enum。

首版 supervisor 與控制 writer 同程序交接掛勾結果：傳 agent-hook-result 根物件及 Cleanup 引用，writer 從快照核對 hook_run_id、父 claim、scope、generation，交易保存掛勾結果與收尾證據；沒有工具 Outcome，也不使用只含 attempt_id 的 ResultReceipt。同 hook_run_id 與相同結果重送只回原內部提交收據，異內容拒絕；unknown 只可由同次執行的可信晚到證據補全，不重跑掛勾。若將此角色拆成跨程序服務，需沿 P-206 可信通道補專屬掛勾收據，不冒用公開 RPC。完整最小結果見 [hook-result.minimal](examples/execution/hook-result.minimal.valid.json)，按 agent-hook-result.schema.json 驗。一般掛勾失敗只記觀測，不改已提交 tick 結果。掛勾 stdout/stderr 受相同有界捕獲與清理，輸出 blob 只作診斷，不進 history、不提交 Proposal；需通知 agent 就走正常 input。hook 程序全清空、tick 提案收據與掛勾結果已核對、home 鎖可取得後才釋放 claim；deadline 到不代表程序已死。重啟一起殺且不補跑，未知掛勾不冒充成功，也不倒改已提交 run。

系統 post 的 aos-clean 由管理者登記的固定 `aos` 機器 argv 啟動；確切子命令與 request/candidates/result 交接歸 storage 篇，stdout 不能代替 writer 收據。clean 只能以登記服務 UID 走該內部通道，按候選引用驗證並回報，不直接成為第二個 SQLite writer。aos-attend 由 control-rpc 篇負責，這裡不新增任何公開 method 或人用操作流程。

**Given** agent pre、tick、system post clean；**When** 提案提交；**Then** 可由 hook_run_id 查到 pre→tick→post，post 收 committed，clean 用控制服務 UID。**Given** pre skip_tick 或 post 中途重啟；**When** 收尾；**Then** 前者有等待依據且不忙迴圈，後者不補跑、不撤銷已提交 checkpoint，清空前仍 held claim。

## P-210．沿用 proto5 的部分與必要差異〔主編補〕

[inst-posix](../../../proto5/spec/inst-posix/README.md) 的直接 argv、明示 shell 與 [aos-exec](../../../proto5/spec/aos-exec/README.md) 的自身錯誤區分可沿用；[cpu](../../../proto5/spec/cpu/messages.md) 的 requests/responses 配對與 [kernel](../../../proto5/spec/kernel/no-overlap.md) 的先記意圖／單寫者也保留其原則。

這裡明確改掉：inst 的 envs 疊加、redirect、`$ref`／`$opt` 不搬來，改為 B-101 固定 env 與 blob；root 不代開程式及路徑。舊 process group＋2 秒等待改 B-202 cgroup 清空及建議 5 秒，因 setsid 後代仍須受管。舊「找不到程式算 child 127」改獨立 exec 錯誤通道的 spawn_error；signal 不折成 128+signal，125 不再與工具原碼混用。cpu 的常駐 worker、notification ack 與 link 發布不搬來：B-601 按需執行、C-05 交易消費與 P-004 rename/fsync 負責持久交接。proto5 的 go pipe 啟發 gate，但現在必須先完成降權／資源安置與耐久識別，再讓 child 讀描述；重啟不靠重新送 go 接續孤兒。

**Given** 用 proto5 工具 wrapper 當候選；**When** 接進 proto6；**Then** wrapper 仍可用固定 argv 讀 stdin，所有 owner、輸出、取消、結果提交按本篇重新接線，不宣稱舊 wire 直接相容。

## P-211．範例與三層驗證〔主編補〕

所有完整訊息例放 [examples/execution](examples/execution/)。hook-input／hook-result 前綴分別按 agent-hook-input／agent-hook-result 根驗；hook-work 按 execution-work 的 `#/$defs/HookWork` 驗。JSON 檔前綴 work/template/result 對應同名前綴 schema；launch、observation 對應各自 union。profile 對應 Profile；registry 登記例對應 AgentRegistration，`registry.launch*`、`registry.system-hook*`、`registry.hook-*` 對應 LaunchSnapshot。檔名 valid 只表示 JSON/schema 可接受，仍須做授權與狀態驗證。

主要正例索引如下（同目錄亦包含完整最小 profile／registry／hook-work）：

| 情境 | 完整範例 |
|---|---|
| 工具成功及原 ID 重送 | [result.minimal](examples/execution/result.minimal.valid.json)、[result.same-attempt-redelivery](examples/execution/result.same-attempt-redelivery.valid.json) |
| 程式失敗、啟動失敗 | [result.exit7](examples/execution/result.exit7.valid.json)、[result.spawn-error](examples/execution/result.spawn-error.valid.json) |
| 未知、截斷、取消、後代清理 | [result.unknown](examples/execution/result.unknown.valid.json)、[result.truncated](examples/execution/result.truncated.valid.json)、[result.canceled](examples/execution/result.canceled.valid.json)、[result.descendant-cleanup](examples/execution/result.descendant-cleanup.valid.json) |
| 準備前的程序識別與 OOM 基線 | [observation.process](examples/execution/observation.process.valid.json) |
| 掛勾 stdin 與結果 | [hook-input.pre](examples/execution/hook-input.pre.valid.json)、[hook-input.post](examples/execution/hook-input.post.valid.json)、[hook-result.minimal](examples/execution/hook-result.minimal.valid.json) |
| 原啟動請求重送／結果重送收據 | [launch.replay](examples/execution/launch.replay.valid.json)、[launch.receipt-replay](examples/execution/launch.receipt-replay.valid.json) |

第一層先按 P-002 驗原始 bytes、重複 key、UTF-8、整數 token、無尾隨值，再做 2020-12 schema。第二層核對所有 ref 的真實 bytes／摘要、owner／run、revision、服務 principal、fd 權限、狀態與跨欄位條件。第三層在「準備→記識別→記放行意圖→放行→exec→排空→發布結果→提交→回覆」每個邊界注入崩潰，確認不重啟同 attempt、不丟已提交資料、不早放名額。靜態範例不能代替 Linux 真程序與持久性測試。

invalid 檔是預期被拒的測試向量，精確名稱與理由如下：

| 檔名（皆以 `.invalid.json` 結尾） | 拒絕原因 |
|---|---|
| `work.owner-field`、`launch.uid` | 偷塞 uid 未知欄位 |
| `work.home-env` | env 覆寫 HOME |
| `template.owner` | template 夾 agent_id |
| `template.empty-program` | argv 首項為空 |
| `result.exit7-success` | exit 7 卻報 succeeded |
| `result.limit-unmarked` | output_limit 未標 truncated |
| `result.embedded-diagnostic` | ExecResult 偷加 errno，診斷應走 ExecError／observation |
| `profile.unknown-field` | profile 偷加 root 欄位 |
| `registry.root-uid` | uid=0 |
| `registry.hook-missing-claim` | 掛勾缺 claim_attempt_id |
| `observation.retirement-live` | retired 卻未清空域 |

schema 無法判跨 owner、假摘要、錯誤 fd 或 populated 證據過期，這些是另外的語意拒絕，不把它們偽裝成 schema 能驗。

**Given** 所有 valid 通過、所有 invalid 被拒；**When** 做完整驗收；**Then** 還須通過 P-201～P-209 的 owner／程序及崩潰案例，不能由 schema 全綠宣稱實作合規。

## P-212．待決、整合修改與現況〔建議預設，未拍板〕

1. **deadline 的精確計時式**：P-011 暫定 7 的「總 deadline 從取得 claim 起算」與 A-506 的「系統掛勾另計、不占 agent tick 時間」需整合者回寫 B-101／B-602／A-506。建議以 claim 起點計 agent elapsed，扣除明確記錄的系統掛勾區間，agent post 只用餘額；系統掛勾各受自己的 timeout，全部已登記掛勾的有界總時間另限制 claim 收尾。若「總 deadline」其實是包含系統時間的硬牆鐘，須明示優先級，不能兩種同時保證。正文沒有擅定額外全局 timeout。
2. **掛勾跨清單順序與 skip_tick 的 post**：各清單內 order/name 已定，但 system/agent 同名同序如何比較、pre skip_tick 後 post 要不要跑與 tick_outcome 用什麼，正本與暫定都未明說。建議跨清單以 scope 作最後 tie-break、skip_tick 不補 post；交整合者確認後回寫 A-506 及 agent-hook schema，不自行加 enum。
3. **loader env 的精確集合**：B-102/P-007 要求排除 loader env，但完整 key 清單與工作明示設定是否也拒絕未定。建議部署 adapter 按支援平台發布固定排除表，固定 runner 永不受這些值影響；對工具明示值的拒絕規則需補回 B-102，不能各實作默默不同。這不阻止清掉全部繼承環境與憑證。
4. **README 與來源同步**：README P-012 可從第一階段「尚未建立正文/schema」改為實際導覽；可列上述公開 `$defs`、機器子命令與內部 SOCK_SEQPACKET。B-103 建議補 stdout_bytes/stderr_bytes 是讀到量、BlobRef.bytes 是保存量的說明。B-302/C-02 建議列 profile 的 global_work_limits/control_reserve_limits、registry.resource_limits 與 LaunchSnapshot 的編碼落點。這些只在本篇提出，沒有改 README 或正本。
5. **其他四份交界假設**：control-rpc 持有 common 型別、准入與公開 cancel/get，認證完才交本篇；agent-state 用本篇 template/result，持有 hook stdin／結果與 Proposal，掛勾不取得提交權；llm 的代發 key 與服務程序不走工具 runner，工具只拿受限投件通道；storage 提供不可變 blob／唯讀 fd 及 clean 內部交接，不能由 helper 代開路徑或把 clean 當 writer。跨檔只引用約定檔名，沒有建立或修改別人的 schema。

現況：本次只交規格、schema 與靜態範例；沒有 runner/helper 實作、Linux 故障注入或 quota probe 結果。以上未決細節不可被當成已可上線的保證。依使用者範圍不 commit、不 push、不寫其他四人的檔。

**Given** 整合者合併五份；**When** 核對待決與引用；**Then** 能找到上述未決點及每份唯一 owner，沒有因本篇範例而新增產品決定。
