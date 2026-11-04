← [daemon／kernel 調查報告（astra）](../2026-09-22-daemon-kernel-report-astra.md)（分檔 6/6）｜[上一份](05-aos-kernel-llm檔案到測試.md)

**4. 文件與程式碼的落差，以及 proto5 相容性**

**4.1 proto4-3 文件直接不符或描述過強**

| 文件說法與位置 | 程式現在做什麼 | 程式位置 |
|---|---|---|
| README 說 add 多寫欄位「會被擋」。[README:67](../../../../proto4-3/README.md) | 普通未知頂層 key 已忽略；docs/kernel 已改成忽略 | [aos_inst.py:92](../../../../proto4-3/aos_inst.py)、[docs/kernel.md:93](../../../../proto4-3/docs/kernel.md) |
| README 說 aos-run 整合 daemon 是之後的事。[README:112](../../../../proto4-3/README.md) | daemon 已直接啟動 aos-run 並讀 status pipe | [aos_daemon.py:66](../../../../proto4-3/aos_daemon.py) |
| README 說 exit 父目錄不會 mkdir。[README:117](../../../../proto4-3/README.md) | exit 支援 `$opt:"mkdir"`；只有未開選項才不建 | [aos_exec.py:121](../../../../proto4-3/aos_exec.py) |
| README 範例 add `my-proc.json` 沒指定名，下一行 rm `my-proc`。[README:54](../../../../proto4-3/README.md) | 自動名是數字，首次通常1，不是來源 stem | [aos_kernel_add.py:106](../../../../proto4-3/aos_kernel_add.py) |
| README 測試數寫243。[README:31](../../../../proto4-3/README.md) | 本輪靜態數 `test_*.py` 有322個 `test_*` 函式定義；不是本輪通過數 | `proto4-3/test/` AST 靜態統計 |
| daemon 文件說主迴圈不等人。[daemon.md:62](../../../../proto4-3/docs/daemon.md) | reap 對每筆兩 thread 各 join 最多1秒；檔案操作也是同步 | [aos_daemon.py:195](../../../../proto4-3/aos_daemon.py)、[aos_daemon_entry.py:172](../../../../proto4-3/aos_daemon_entry.py) |
| state「每0.5秒」，ls 最多看到0.5秒前。[daemon.md:133](../../../../proto4-3/docs/daemon.md)、[daemon.md:170](../../../../proto4-3/docs/daemon.md) | 0.5是每輪後的存檔門檻；輪間另睡0.2，工作時間也會延遲；沒有0.5秒最大陳舊保證 | [aos_daemon_lifecycle.py:29](../../../../proto4-3/aos_daemon_lifecycle.py) |
| request 處理後「搬到 done」。[daemon.md:103](../../../../proto4-3/docs/daemon.md) | 先 remove 原單，再另寫回應；存在失單窗口 | [aos_daemon_req.py:75](../../../../proto4-3/aos_daemon_req.py) |
| ctl 等 rm/restart/pause 到位「才印結果」。[daemon.md:174](../../../../proto4-3/docs/daemon.md) | 先印原始 ok/result，再等到位，之後另印完成文字 | [aos_daemon_ctl.py:133](../../../../proto4-3/aos_daemon_ctl.py) |
| daemon 收工／五秒強殺的文字容易涵蓋整個工作樹。[daemon.md:57](../../../../proto4-3/docs/daemon.md)、[daemon.md:121](../../../../proto4-3/docs/daemon.md) | KILL 的是 aos-run group；inst 在另一 session/group，不能據此保證整棵子孫清掉 | [aos_daemon_entry.py:166](../../../../proto4-3/aos_daemon_entry.py)、[aos_exec.py:190](../../../../proto4-3/aos_exec.py) |
| run 文件把 time-limit 稱硬時限。[run.md:81](../../../../proto4-3/docs/run.md) | 透過縮短 subprocess timeout，未涵蓋所有同步前置處理時間，且有TERM grace | [aos_run.py:126](../../../../proto4-3/aos_run.py)、[aos_exec.py:201](../../../../proto4-3/aos_exec.py) |
| kernel tick「一律0」。[kernel.md:57](../../../../proto4-3/docs/kernel.md) | 有參數2、非家1；未捕捉例外也可異常退出 | [aos_kernel_tick.py:140](../../../../proto4-3/aos_kernel_tick.py) |
| queue 的 cwd「一定要寫死」，理由是搬到 CPU 不可改中心。[kernel.md:111](../../../../proto4-3/docs/kernel.md) | 只驗 key 存在且 raw 是字串，接受相對 cwd；搬移後 base 可由 procs 變 cpus | [aos_kernel_tick.py:115](../../../../proto4-3/aos_kernel_tick.py) |
| 完成後換 idle，再看 quantum。[kernel.md:115](../../../../proto4-3/docs/kernel.md) | `_finish()` 後立即 return，當輪不再排該 CPU | [aos_kernel_schedule.py:42](../../../../proto4-3/aos_kernel_schedule.py) |
| 「v1 的行程不會自己結束」。[kernel.md:127](../../../../proto4-3/docs/kernel.md) | 現在已有 done_exit 與 bad 退件 | [aos_kernel_schedule.py:42](../../../../proto4-3/aos_kernel_schedule.py) |
| module CLI 只有第一個參數會當 K。[kernel.md:84](../../../../proto4-3/docs/kernel.md) | 搜尋前兩個參數，所以可 `llm ls K`、`llm rm K NAME` | [aos_kernel.py:175](../../../../proto4-3/aos_kernel.py) |
| config 的 ncpu 至少1等條件列為欄位限制。[files.md:43](../../../../proto4-3/docs/files.md) | 這些限制只在 init CLI；直接讀 config 不重驗範圍，bool也接受 | [aos_kernel.py:93](../../../../proto4-3/aos_kernel.py) |

「七個動作」是七個 table 方法；加上 `stop` 後，**外部請求 op 有八個**。若寫請求協議，不能只列七種。

**4.2 文件有提到，但不足以直接當精確協議的地方**

| 文件概述 | 必須一併記錄的程式事實 | 位置 |
|---|---|---|
| 連續非零 N 次退件 | 不同非零碼仍累加；差額 runs 全算成最新碼；swap 會丟失一般連敗計數 | [schedule.py:75](../../../../proto4-3/aos_kernel_schedule.py)、[schedule.py:133](../../../../proto4-3/aos_kernel_schedule.py) |
| 連續125退件 | 指 kind=aos 的連續 tick 觀察；預設下 child 125 不退件；同快照可計兩次 | [schedule.py:51](../../../../proto4-3/aos_kernel_schedule.py) |
| CPU 在 daemon 表上即可使用 | 未檢 entry.state、alive、ready；stopping/paused/陳舊快照也可被排程 | [tick.py:81](../../../../proto4-3/aos_kernel_tick.py) |
| CPU 缺少會補 add | add 成功當輪仍不排，下一 tick 才重新觀察 | [tick.py:85](../../../../proto4-3/aos_kernel_tick.py) |
| boot 重複無害 | 只對快照 state=running/paused 直接成功；pause_pending/stopping/restarting 不在此分支 | [boot.py:31](../../../../proto4-3/aos_kernel_boot.py) |
| 原子換 CPU 檔 | 只保證單檔替換，不保證 invocation 歸屬、行程不重疊或跨檔 crash recovery | [schedule.py:111](../../../../proto4-3/aos_kernel_schedule.py) |
| rm 等 kernel 回覆 | CLI 超時不撤單，之後仍可能刪除 | [syscall.py:53](../../../../proto4-3/aos_kernel_syscall.py) |
| module 錯誤隔離 | 同 process 捕捉例外，沒有副作用回滾或資源隔離 | [module.py:16](../../../../proto4-3/aos_kernel_module.py) |

proto4-5 相鄰文件還有兩處與 kernel 接口有關的落差：

| 文件 | 實作 |
|---|---|
| [README:118](../../../../proto4-5/README.md) 說 kernel 沒活著就撤單、不排隊 | CLI 沒有直接活性檢查；先投單並等回音，超時才依原檔是否存在嘗試撤單。[module.py:148](../../../../proto4-5/llm_cpu_module.py) |
| [README:116](../../../../proto4-5/README.md)／CLI 文字說「下一回合處理」 | syscall handle 與 module.tick 在同一 kernel tick 順序執行，新接受請求可在**同格**被 dispatch。[kernel_tick.py:50](../../../../proto4-3/aos_kernel_tick.py) |
| [README:181](../../../../proto4-5/README.md) 說沒有取消 | 已有 `llm rm` 直接終止 running worker 並刪四處資料；但沒有通用取消 syscall／交易式取消。[manage.py:107](../../../../proto4-5/llm_cpu_manage.py) |

**4.3 proto4-3 與 proto5 `exec.md`／`inst-posix.md` 的實質差異**

先保留文件自身的成熟度：proto5 的 [README:13](../../../README.md) 將 inst-posix 標為定稿；[exec.md:7](../../../spec/aos-exec/README.md) 明寫命令列尚未逐條拍板。因此下表區分「定稿格式差異」與「目前 exec 文件差異」。

| 項目 | proto5 文件 | proto4-3 現碼 | 影響／來源 |
|---|---|---|---|
| 省略 aos-exec 目標 | `xxx` 省略＝`.`。[exec.md:22](../../../spec/aos-exec/usage.md) | `aos-exec` 的 xxx 必填；缺少退出2 | [aos_exec.py:270](../../../../proto4-3/aos_exec.py)。這是 exec CLI 文件差異；不代表 aos-run 也應省略目標 |
| `_metainfo:null` | 有寫時必須是物件。[inst-posix.md:36](../../../spec/inst-posix/metainfo.md) | `obj.get()` 取得 None，再直接套 posix v1 預設 | [aos_inst.py:100](../../../../proto4-3/aos_inst.py)、[aos_inst.py:142](../../../../proto4-3/aos_inst.py)。本輪記憶體檢查確認接受 |
| `$ref` 字串內 `#位置` | inst 文件明示 `#` 前空＝本文件，完整語法交 directives。[inst-posix.md:179](../../../spec/inst-posix/directives.md) | 整個 `$ref` 字串都當檔名，`#` 不切開 | [aos_inst_resolve.py:231](../../../../proto4-3/aos_inst_resolve.py)。`x.json#/a` 會找檔名含 `#` 的路徑 |
| 外部 `$ref` 的相對位置 | proto5 以被引檔根作目前位置，允許 `./a`。[directives.md:128](../../../spec/directives/ref.md) | 只有 `$ref:""` 才准相對 `$at`；指外部檔的 `./a` 拒絕 | [aos_inst_resolve.py:248](../../../../proto4-3/aos_inst_resolve.py)、[aos_inst_resolve.py:281](../../../../proto4-3/aos_inst_resolve.py) |
| `$at:null` | 有寫必須字串，否則 DirectiveValueTypeMismatch。[directives.md:124](../../../spec/directives/ref.md) | `.get("$at")` 得 None，當省略，取整份 | [aos_inst_resolve.py:103](../../../../proto4-3/aos_inst_resolve.py)、[aos_inst_resolve.py:274](../../../../proto4-3/aos_inst_resolve.py) |
| `$fmt` 內位置 | 原始 JSON 實體路徑，含 `$fmt` 這層。[inst-posix.md:181](../../../spec/inst-posix/directives.md) | 變數用 `ctx.down(name)`，模板用 `ctx.down("$val")`，少 `$fmt` 層 | [aos_inst_resolve.py:202](../../../../proto4-3/aos_inst_resolve.py)。本輪確認 fmt 兄弟變數相對 ref 可因此 PointerInvalid |
| cwd mkdir 時序 | 先建 cwd，再以它為中心解其他欄位。[inst-posix.md:231](../../../spec/inst-posix/exec.md) | `aos_inst.load()` 先解全部欄位，回到 `_run_inst()` 才 makedirs | [aos_inst.py:102](../../../../proto4-3/aos_inst.py)、[aos_exec.py:116](../../../../proto4-3/aos_exec.py)。讀／驗失敗時 cwd 尚未建立 |
| `kind=aos` 一律等於沒跑 | proto5 exec 說 aos 是根本沒跑，125不寫exit。[exec.md:59](../../../spec/aos-exec/exit.md)、[exec.md:63](../../../spec/aos-exec/exit.md) | child 已完成後，exit 寫入或 fsync 失敗仍轉 `(1,"aos")`→125 | [aos_exec.py:226](../../../../proto4-3/aos_exec.py)。125不能絕對推論沒有子程式副作用；exit也可能已部分寫入 |
| timeout 收整個 group | 規範要求先TERM、2秒後必要時KILL整群。[inst-posix.md:246](../../../spec/inst-posix/exec.md) | KILL 時用 `os.getpgid(p.pid)`；若直接 child 已被 wait 回收，可能取不到原 pgid | [aos_exec.py:203](../../../../proto4-3/aos_exec.py)、[aos_exec.py:218](../../../../proto4-3/aos_exec.py)。不能把最後補 KILL 的程式碼當作對仍活孫程序的完整保證；本輪為靜態判讀 |

其中 `$ref #位置` 與 `$fmt` 實體位置，正是 proto4-3 README 所說未跟上的 K／L，**不是 README 錯報已凍結的範圍**。

**4.4 合法 proto5 inst 不一定能直接交給 proto4-3 kernel**

這是 kernel 的**輸入子集差異**；不能全部算作 aos-exec 本身違反 inst 規範。

| proto5 合法格式／執行語意 | proto4-3 kernel 限制 | 位置 |
|---|---|---|
| 頂層整份可為 `$ref` 等指示詞 | add raw 檢查要直接有可用 argv；queue raw 也要 argv/cwd，尚未解就拒絕 | [aos_kernel_add.py:83](../../../../proto4-3/aos_kernel_add.py)、[aos_kernel_tick.py:113](../../../../proto4-3/aos_kernel_tick.py) |
| cwd 可為指示詞 | add／queue 要 raw 字串 | [aos_kernel_add.py:87](../../../../proto4-3/aos_kernel_add.py)、[aos_kernel_tick.py:119](../../../../proto4-3/aos_kernel_tick.py) |
| cwd 可為 `$opt:mkdir`，允許目錄尚不存在 | add 先因非字串拒絕；字串不存在也拒絕；手放 queue 同樣不接受 cwd 選項物件 | [aos_kernel_add.py:88](../../../../proto4-3/aos_kernel_add.py) |
| argv 整包可由 `$ref` 得到 | add 要 raw list | [aos_kernel_add.py:96](../../../../proto4-3/aos_kernel_add.py) |
| argv[0] 可由 `$env/$fmt/$ref` 得到 | add 要 raw argv[0] 是字串 | 同上 |
| 缺 cwd 使用 inst base | add 會補絕對 cwd；手放 procs 缺 cwd 直接退件 | [aos_kernel_add.py:86](../../../../proto4-3/aos_kernel_add.py)、[aos_kernel_tick.py:117](../../../../proto4-3/aos_kernel_tick.py) |
| `argv[0]` 指不存在路徑，在執行時成 child127 | add 對含 `/` 的不存在 argv[0] 事先拒絕，根本不進 queue | [aos_kernel_add.py:103](../../../../proto4-3/aos_kernel_add.py) |
| 普通檔案是 aos-exec 合法目標 | daemon add 只收 `.json`；kernel add 讀的是 JSON 內容 | [aos_daemon_entry.py:50](../../../../proto4-3/aos_daemon_entry.py) |

proto5 的依據為 [inst-posix.md:79](../../../spec/inst-posix/fields.md)、[inst-posix.md:176](../../../spec/inst-posix/directives.md)、[inst-posix.md:244](../../../spec/inst-posix/exec.md)。

**4.5 不構成衝突的邊界**

| 項目 | 事實 |
|---|---|
| 100＝完成、101＝等待 | proto5 明確把它們留給 kernel／程式約定，不屬 inst 格式。[inst-posix.md:253](../../../spec/inst-posix/README.md) |
| 126／127 算 child，kernel 可累計一般失敗 | 與 proto5 的執行器語意相容 |
| daemon／kernel 的 config、state、request JSON 不解指示詞 | 它們目前只是直接 `json.load()`；不能把 inst 的指示詞允許位置直接外推成所有控制 JSON 的既有能力 |
| daemon `ok/result` 與 kernel `ok/msg` | 是兩套現在不同的檔案協議，不是同一 schema 的別名 |
| daemon done、kernel syscall done、LLM request done、LLM result | 四者含義不同：daemon 動作受理回應、kernel handler 回應、LLM 原請求歸檔、模型／排程結果 |
| 原子 rename | 各 writer 的單檔發佈方式；目前不存在橫跨上述檔案的統一交易、exactly-once 或崩潰對帳協議 |
