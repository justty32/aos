# Linux 正式員工制度：實作可行性與複雜度

> 2026-09-28 交接快照；[原始來源](../../proto5/notes/2026-09-28-linux-employee-implementation.md)保留於原位置。本文的現行行為與實測均指當時 proto5／環境，非 proto6 已實作；僅調整導航與探針重跑路徑。
>
> 後續註記（2026-09-29，依 [notes 審查](notes-review.md) 必修 2、14）：本文「正式員工」分類與專屬 tick worker（含「專屬 tick worker 可以復用多少 cpu」整節）已被[資源與任務排程](2026-09-28-linux-resources-and-task-scheduling.md)取代——分類已放下，CPU worker 改為取消方向，只是演進脈絡。另外「`_execute_inst` 先建 cwd、開 stdin／stdout／stderr」一句混寫了一般 exec 與 daemon 池式路徑：daemon 池式啟動時 `spawn_target` 會拒絕 inst 寫 stdin／stdout（由控制 pipe 接管），帶 launcher 時 `_execute_inst` 也不開這兩個檔；前面仍有讀 target、解析指示詞、條件式建目錄與開 stderr，所以「必須先降權」的結論不變。

← [設計草案](2026-09-28-host-root-design.md)｜[第二道牆](investigations/proto5-host-root-second-wall.md)

> 同日後續決定：工具通常繼承委託員工的 UID／群組權限，包含內部 LLM 與再次呼叫工具；不需逐工具 bwrap，保留整套 aos／daemon 的外牆。見[已定方向](2026-09-28-employee-identity.md)。下文「同 UID 候選未定」、逐工具隔離與工具權限 group 是決定前的歷史比較，不再是必要設計；其餘接法仍為候選，現行程式未變更。

2026-09-28，Linux 限定的調查與候選設計。本線只讀程式，未啟動 root daemon、建立宿主帳號或改動產品；隔離子程序 UID 實驗另見 [Linux 外牆可行性](investigations/proto5-linux-wall-feasibility.md)。所有方案均未替使用者拍板。

## 問題、方法與結論

問題是：在 proto5 上把正式員工做成 Linux UID＋專屬 tick worker，實際要改哪裡、比現行架構多承擔什麼？方法是唯讀追蹤 daemon 啟動、cpu 收件、kernel 派工、agent 回音查詢與檔案交接；Linux／Python 行為另核對官方文件。本文行號以本輪工作樹為準。

**可行，但不是在 access 加 user 欄位即可完成。** 切換 UID 的系統能力現成；主要缺口是把原本「同一使用者、共用資料夾」的內部協定變成「不同員工、可互不信任」的邊界。最小合理原型仍需要受限啟動入口、身分化投件、跨 UID 檔案交接與故障回收。只考慮 Linux 可以省掉跨平台分支，省不掉這四件事。

沿用上一輪結論：root daemon 管程序；員工 UID 做工作；名冊／程式由管理者持有；外包同 UID 是起步候選；固定 tick worker 不被工具佔用；外部牆連 daemon 一起限制；帳號預建以避免開放寫 `/etc`。完整第二道牆選項仍見上方連結。後續無特權 namespace 的多 UID 映射、no_new_privs 與永久降權小實驗見 [Linux 外牆可行性](investigations/proto5-linux-wall-feasibility.md)；這不等於已驗證宿主 root daemon 的完整部署。

## 目前在哪裡啟動，以及最小降權位置

現行池式路徑是 daemon → `spawn_child()` → `spawn_target()` → `_execute_inst()` → `Popen()`。`spawn_target` 先讀 target／解析指示詞，`_execute_inst` 先建 cwd、開 stdin／stdout／stderr，再執行。因此不能只替最末端 Popen 加 user；那會把讀寫窗口留在 root。

另一條 kernel tick 路徑直接 Popen `[ticker.cli, tick, --target, home]`，也沒有降權參數。這條也要收緊成管理者認可的固定 kernel 程式與服務 UID，不能只修 cpu 啟動線。

候選最小接法：在 daemon 決定「要開哪個員工／哪類受允許工作」後，走新的受限啟動入口，從名冊取得數字 UID／GID／群組；直接啟動固定、管理者擁有的 runner，設定乾淨 env、固定安全 cwd、明確 fd。runner 已是員工身分後，才讀員工的 inst 和工具設定、開工作輸出。

Python `Popen` 已有 `user`、`group`、`extra_groups`、`umask` 等 POSIX 參數，可作降權基礎，不必自行在多執行緒父程序裡呼叫 setuid，也不宜塞複雜 `preexec_fn`。但 capabilities、no_new_privs、外部政策與完整後代回收並不因此自動完成，需由固定 launcher 或服務配置落實並驗證。[Python subprocess](https://docs.python.org/3/library/subprocess.html)

root 側不得把員工 target 先丟進通用指示詞解析器；只能接收固定形狀的工作識別與允許動作。通用 inst 能保留，位置移到降權後。root 若需要記 stderr，用自己的固定管理 log／管線，不能接受工作單指定任意宿主輸出路徑。

程式證據：`aos_daemon_pools.py:292`（Popen）、`:305`（spawn_target）；`aos_exec_spawn.py:50` 起（讀取目標）；`aos_exec_run.py:26` 起（mkdir／open）；`aos_daemon_ticks.py:222`（kernel tick Popen）。

## 專屬 tick worker 可以復用多少 cpu

可以復用 `aos_exec_cpu` 的控制 pipe、go、輪詢、單件執行、回音先落檔、重啟對帳等機制。先用「每員工一個只有一顆 cpu 的專屬池」也能沿用現有 kernel 排程，不必先發明新的常駐迴圈。

但專屬池名稱不是安全邊界，需要新增契約：池綁定名冊的員工與用途；kernel 只派該員工的 tick；worker 的實際 UID 必須吻合；固定 tick 入口不能被工作參數換成任意管理命令；一般工具不能把 `_pool` 指到別人的 tick 池；員工不得 scale／kill 他人。這些限制是提案，不是現有 cpu 已具備的能力。

`aos_exec_cpu._params()` 現在接受任意 target、dir_target、args、stderr 等欄位，`_execute()` 直接交給通用執行器。tick 專用模式可以把輸入收斂成「推進既定 agent 一格」，不需要暴露完整 aos-exec 介面。

worker 一次 tick 完就再次等訊息。LLM／工具另排短命工作；共享的應是併行名額，而不是一顆永遠以 root 解員工 inst 的通用 cpu。若已降成 A 的長命 cpu，要服務 B 就不能自己換 UID；可以用每 UID 工具池，或共用名額、每件由受限入口開正確 UID 的短命 runner。前者多常駐程序，後者多啟停與對帳；初版不必兩種都做。

程式證據：`aos_exec_cpu.py:128` 起（參數）、`:208` 起（run）、`:239` 起（loop）；`aos_kernel_engine.py:180`（工作信封）、`:186`（按池取 free）；`aos_agent_batch.py:253`（LLM／工具選池）、`:261`（送完停車等叫醒）。

## 最容易低估的地方：檔案可以原子寫，不代表別的 UID 能讀

`aos_home._write_temp()` 用 NamedTemporaryFile，在目的目錄建立暫存檔。`write_json()` 用 replace，`post_request()` 用 link 發布。暫存檔預設只允許建立者讀寫，發布後不會自然變成另一 UID 可讀。只把 queue 目錄 chmod 成群組可寫，不能解決檔案仍是 0600 的問題。[Python tempfile](https://docs.python.org/3/library/tempfile.html)

另外，Doorbell 明確以 0600 建 FIFO；agent 的 `.tick.lock` 由執行 tick 的使用者建立；agent 查工作是否已送過，會直接開 kernel 的 SQLite 帳本。這些都依賴原本同一身分的假設。

候選資料分工：

| 資料 | 主要寫入者 | 員工看到的範圍 |
|---|---|---|
| 安裝程式、名冊、外部限制政策 | 管理者 | 必要唯讀，不能替換上層目錄或 symlink |
| daemon 控制與程序紀錄 | daemon | 經查詢介面給自己的摘要 |
| kernel 帳本與私有工作副本 | kernel 服務 UID | 不直接打開整份 SQLite |
| 每員工投件口 | 該員工，kernel 可收取 | A 無法替 B 投件 |
| 每員工結果口 | kernel，該員工唯讀 | ack 另投，員工不直接刪 kernel 的結果 |
| agent 記憶、workspace | 員工 UID | 預設私有，需要共享才加 group／ACL |

這張表是權責建議，不是已完成的 chmod 配方。每個跨 UID 目錄都要明定建立者、刪除者、檔 mode、default ACL 與 group，並在發布前用已開啟 fd 設定權限；不要發布後才補 chmod，留下讀不到或過度開放的窗口。replace 會換 inode，新檔必須重新套對的權限，不能以為舊檔 ACL 自動保留。

rename 需同一檔案系統，跨 mount 可能 EXDEV；不能為了搬單把一個跨檔案系統 rename 當成原子交接。若需跨區域搬入 kernel 私有 spool，讀取受限大小的完整內容、驗證、在目的區域建立新檔／交易，然後記錄接收與去重。[Linux rename](https://man7.org/linux/man-pages/man2/rename.2.html)

flock 是合作鎖，不是對惡意同 UID 程序的保護。鎖路徑的目錄若可被工具替換，兩個程序可能鎖住不同 inode。保留 agent 自己的 tick 鎖可防正常重入；專屬性與啟動世代還需管理端保證，不可把這把鎖當完整授權機制。

程式證據：`aos_home.py:106`（temp）、`:122`（replace）、`:136`（link）、`:324`（FIFO 0600）；`aos_agent_runtime.py:40`（tick lock）、`:80`（直接讀 kernel proc）、`:90`（knows）；`aos_kernel_store.py:57`（SQLite 開啟）。

## 投件身分：兩條 Linux 路線

**每員工隔離目錄**最貼近目前架構。kernel 從 A 的受保護入口讀到的單，就標為 A；JSON 不得覆寫這個 owner。A 不能改入口本身或接觸 B 的入口。接收後把有效資料存入 kernel 自己的帳本／spool，避免事後工作單被改。

難點是讀到 symlink／非普通檔案、同時改寫、過大輸入、半張單及假 ack。需要安全開檔、大小上限、固定路徑解析和至少一次投件的去重。即使 A 把自己的單改壞，也只能損害 A 的工作，不能讓 parser 變成 root 讀檔代理。這類掃描在普通 kernel UID 下做。

**Unix socket＋SO_PEERCRED**可直接取得連線對端的 PID／UID／GID，再查名冊；JSON 自報的名字不作驗證。這能省去「從哪個共享目錄認人」，但增加連線生命週期、消息 framing、背壓、重連、回覆遺失與重放設計。SO_PEERCRED 反映連線建立時的憑證，不是每筆 JSON 都重新辨識送件程序。[Linux unix socket](https://man7.org/linux/man-pages/man7/unix.7.html)

兩者都能保留目前 durable ledger：socket 接收驗身分後仍落盤、提交成功才答收件；重連帶相同 job ID 查結果，不用把所有工作狀態搬進 socket 記憶體。目錄方案則保留檔案郵箱，但加入口與 owner分區。初版選一條即可，不必同時維護兩套。

**兩條路都不能用同一 UID 區分 tick 與外包。** 若外包以 A 執行，就應預期它能以 A 的身分送工作／查自己結果。可把操作分三類：員工可提交及查詢自己的工作；管理者才可新增員工、改身分／quota／外牆、停別人；需保護的 worker 控制走 daemon 已持有的專用 pipe。若要求工具連 A 的投件能力都沒有，必須另隔離 socket／控制 fd 的可見性與程序存取，或採不同身分／強制安全域；SO_PEERCRED 本身不解決。

## 同 UID 外包、檔案歸屬與帳號生命週期

同 UID 外包省掉成果 chown 和跨身分交接，工具生成的新檔自然歸員工；Linux 權限模型也較直覺。但員工目錄必須實際設定私有，例如 home 0700、合適 umask，否則不同 UID 仍可能讀到 world-readable 資料。共享用明確 group／ACL；不要把所有員工放進能寫控制目錄的共用群組。

同 UID 是「代表員工辦事」，不是「工具天然不能傷到員工」。若員工可以自改 prompts／記憶，工具又同 UID，需把這種授權一致性講清楚；不要宣稱單靠帳號已做到工具最小權限。

初版建議預建專用帳號，禁止 UID 0 和宿主現有管理帳號，並核對數字 UID／GID。登記同時有穩定 employee ID 和入職世代；程序重啟只換程序世代，不變成新員工。移除員工先拒新單、處理在途工作、終止後代與撤回入口，再由管理者處理帳號和資料。

UID 被重用時，新帳號可能繼承舊數字 UID 留下的檔案權限。因此不要刪帳號後立即把 UID 分給新人；先保留／隔離舊資料、關掉存活程序和舊憑證入口，確認無殘留再考慮回收。employee ID 世代能防協定舊單混入，不能自動修復檔案系統的數字 ownership。

daemon 自行 useradd 要寫帳號資料庫、處理鎖與部分失敗、home 權限及 UID 衝突，還會與「外牆禁止改 /etc」矛盾。可以讓外部人事管理動作獨立完成，但不必在首版加入。

目前 `/tmp/haha` 是同一使用者試驗家，不能直接 sudo 接著跑當成升級：可能留下 root-owned state、lock、temp 或 log，使普通使用者之後無法修改。建議新建獨立測試佈局，遷移另做明確步驟；本輪沒有碰 haha。

## 取消、重啟與何時算完成

現行 daemon 記 kid gen，先記錄再 go，並使用程序／process group 的 stop→TERM→KILL；這些可沿用思路。但會另開 session 或留下孫程序的工具，不能只靠原始 worker PID 判斷工作已結束。

Linux 候選是每個員工、每件短命工作都放可識別的 cgroup，管理者掌握其生命週期；細節與外牆交由第二線調查。停止員工不等於殺掉所有同 UID 程序，否則會誤殺管理者自己以該 UID 做的維護。需清理本系統建立的工作範圍。

重啟時對帳需同時看 employee ID／入職世代、工作 ID、worker 世代、實際受管理程序。不要僅把舊檔案中的 PID 拿來發 signal。取消要區分已排隊取消、已執行且正在停止、後代確實清空；ack 只是消費回音，不能取代回收確認。副作用已發生卻沒寫回結果，仍然不是 exactly-once，不能盲目重跑外部寫入。

程式證據：`aos_daemon_loop.py:255`（記錄 pid／gen）、`:286`（TERM）、`:290`（kill group）；`aos_exec_cpu.py:274` 起（結果先寫，再刪 request）；`aos_kernel_engine.py:135` 起（收回音與補派）。

## 必要改動、可延後與維護成本

必要改動是：受限啟動與完整降權；名冊／入職世代；kernel 的 owner 授權；專屬 tick 綁定；一種跨 UID 投件與結果協定；控制檔 ownership；帳本查詢介面；受管理工作範圍的取消／重啟；外部第二道牆的部署驗證。

可延後的是：daemon 自建帳號、UID 自動回收、不同 UID 外包、工具權限 group 的完整產品介面、跨機 worker、Windows／macOS、同時支援目錄與 socket、可在執行中切換員工身分。這些是控制初版範圍的建議。

成本不是「多幾個 setuid 呼叫」，主要增加四類責任：

- **新協定**：身份、授權、重連／重放、owner 與工作世代，既有直接讀檔捷徑需要收斂。
- **部署安裝**：預建帳號、程式不可寫、目錄 ownership／ACL、外牆政策；安裝與升級也要驗證。
- **身分生命週期**：入職、停用、換群組、撤權、保留資料、UID 不誤重用。
- **恢復測試**：每個交接點的崩潰＋跨 UID 權限失敗＋工具後代未退出，比目前單 UID happy path 多維度。

測試至少分為不需特權的協定與模擬測試，以及可丟棄 Linux 環境內的真雙 UID／外牆驗收。後者要包含冒名與假 ack、0600／ACL 與原子發布、替換 symlink／lock、daemon 在降權前拒絕讀工作檔、取消後無後代、重啟不誤殺／不重複執行、舊 UID 世代拒收，以及 root daemon 即使嘗試寫外牆之外也失敗。這些尚未執行，不把設計可行等同於已驗證安全。
