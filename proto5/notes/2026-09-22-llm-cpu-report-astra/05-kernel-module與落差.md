← [llm cpu 調查報告（astra）](../2026-09-22-llm-cpu-report-astra.md)（分檔 5/5）｜[上一份](04-aos-agent交出與收回.md)

**4．proto4-3 kernel：module／syscall／101**

**4.1 module 登記與介面**

| 項目 | 實作 |
|---|---|
| 登記位置 | `K/config.json` 的 `"modules":["/abs/module.py",...]` |
| init 旗標 | 可重複 `--module PATH`；存入時轉絕對路徑 |
| 既有家 | init 不覆寫；後加 module 需修改 config |
| 載入 | importlib 從檔案載入；名稱使用路徑 SHA-256 前 16 字元 |
| 相依 import | 載入期間暫把 module 所在目錄放 sys.path 前方 |
| `NAME` | 必須非空字串，作為 kernel 子命令名 |
| `OPS` | 必須 tuple，每項非空字串；空 tuple 可通過 |
| hooks | 可以缺；存在時必須 callable |
| 重複 NAME／OPS | 沒有拒絕重複登記；按配置順序選擇 |
| 載入／tick 例外 | 捕捉 BaseException，記 note；不因此停止其他 module |
| 執行位置 | hook 在 kernel／kernel CLI 行程內直接呼叫，不是獨立服務 |

來源：[init:24](../../../proto4-3/aos_kernel_init.py)、[loader:16](../../../proto4-3/aos_kernel_module.py)。

| hook | 回傳／用途 |
|---|---|
| `handle(h,cfg,st,ticket)` | syscall handler；解包成 `(ok,msg)`，再轉 bool／str |
| `tick(h,cfg,st)` | 每回合一次；回 list 才逐項加進 notes |
| `status(h,cfg)` | kernel ls 使用；不是 None 就印 |
| `cli(h,cfg,argv)` | kernel module 子命令；回退出碼 |

`h` 是 `KHome`，含 `.dir`、`.syscalls`、`.syscalls_done`、`.procs`、`.cpus` 等路徑；cfg 是讀出的設定；st 是當回合 kernel state。[KHome:61](../../../proto4-3/aos_kernel.py)

CLI 的 K 判定實際掃 module argv 的**前兩個位置**，找「資料夾且含 config.json」的參數取出；所以可用：

```text
aos-kernel llm K req.json
aos-kernel llm ls K
aos-kernel llm rm K NAME
```

找不到則使用 cwd。[module CLI 分派:171](../../../proto4-3/aos_kernel.py)

**4.2 kernel tick 與 module 的順序**

| 順序 | 操作 |
|---:|---|
| 1 | 讀 K/state，補 cpu state 格 |
| 2 | 讀 daemon state，檢查／補登記普通 cpu |
| 3 | 載入 modules，收載入 notes |
| 4 | 處理 syscalls |
| 5 | 跑各 module.tick |
| 6 | 驗普通 procs queue |
| 7 | 普通 cpu 排程 |
| 8 | 保存 state、append kernel.log，正常回 0 |

LLM request 可在第 4 步排入、第 5 步同回合派工。即使 daemon 上普通 cpu 尚未 ready，module hook 仍會被執行。[tick:41](../../../proto4-3/aos_kernel_tick.py)

**4.3 syscall 請求／回音格式**

| 項目 | 實際格式／語意 |
|---|---|
| 投遞 | `K/syscalls/<自選名稱>.json` |
| 掃描 | 只收頂層 `.json` 普通檔，按檔名排序 |
| 請求頂層 | JSON object |
| 通用分派欄位 | `op` |
| 內建 rm | `{"op":"rm","pid":"行程名稱"}` |
| llm module | `{"op":"llm","id":"請求名稱","request":{...}}`；id 可 null，由 handler 產生 |
| 回音 | 同名 `K/syscalls/done/<名稱>.json` |
| 回音內容 | 固定 `{"ok":bool,"msg":string}` |
| 關聯方式 | 檔名相同；回音沒有另外帶 request／ticket ID 欄位 |
| 完成處理 | 先寫回音，再 unlink 原單 |
| 回音寫失敗 | 記 note；仍會嘗試刪原單，沒有 durable 重送回音機制 |
| 原單刪失敗 | 記 note；下一 tick 仍可能再讀同一張 |

分派規則：

1. `op=="rm"` 永遠走內建處理。
2. 其他 op 找第一個 `op in module.OPS` 的 module。
3. 找到且有 handle 才呼叫。
4. 第一個認領者若沒有 handle，**不繼續找後面的 module**，回不認得 op。
5. 無效 JSON／非物件／無 op／未知 op／handler 例外，都嘗試寫失敗回音。

來源：[handle_syscalls:72](../../../proto4-3/aos_kernel_syscall.py)、[回音／刪單:191](../../../proto4-3/aos_kernel_syscall.py)。

**4.4 一般 syscall 等待與 llm `--wait` 的關係**

| 路徑 | 等待行為 |
|---|---|
| `aos-kernel rm K NAME` | 寫 `<time_ns>-rm-<pid>.json`，每 50ms 等 done 回音 |
| rm 時限 | `max(3秒,3×interval)` |
| rm 收到回音 | 解析、刪回音、印 msg；ok 為真退 0，否則 1 |
| rm 逾時 | 退 1；**不撤掉原 syscall 單** |
| llm 收件階段 | 使用自己的 `_wait_reply()`，同一時限與輪詢頻率 |
| llm 收件逾時 | 另有刪原單的撤單分支 |
| llm `--wait` | 是 module 自己實作的第二段 result polling |
| kernel 通用介面 | 沒有一個通用 syscall `--wait result` 機制 |

來源：[rm CLI:18](../../../proto4-3/aos_kernel_syscall.py)、[llm 等回音:233](../../../proto4-5/llm_cpu_module.py)。

kernel 的普通 `rm` 與 `llm rm` 不同：

| 命令 | 動作 |
|---|---|
| `aos-kernel rm K agent` | 拿掉普通行程的下一次執行位置；cpu 上的 inst 換 idle；不殺正在執行的那一次 |
| `aos-kernel llm rm K request` | 直接查 LLM 家；running 時殺 worker process group，再刪單 |
| 拿掉 agent | 不會順帶取消它已送出的 LLM request |

**4.5 101 如何傳到 kernel**

| 階段 | 資料流 |
|---|---|
| agent | 無信／結果未到，退出 101 |
| aos-exec | 回 `(101,"child")` |
| aos-run | status-fd 發 `done #N exit=101 kind=child ...` |
| daemon | `Entry.feed()` 更新 runs、last_exit、last_kind；寫進 daemon state |
| kernel tick | 直接讀 daemon state，按 cpu inst 的 realpath 取得 entry |
| scheduler | 只有 `new_runs>0` 時觀察新的退出回報 |
| 判等待 | `last_kind=="child"` 且 `last_exit==cfg.wait_exit`；預設 wait_exit=101 |
| 記帳 | `waiting=true`，`wait_runs += new_runs` |
| 有人排隊 | 若目前行程至少跑過一次，立即換到隊尾，不必等滿 quantum |
| 沒人排隊 | 留在 cpu，aos-run 仍會繼續定期執行它 |
| 下一次非 wait 回報 | 清 waiting/wait_runs |
| bad streak | 101 不算一般非零錯誤，還會打斷 bad_runs 計數 |

來源：[aos-run 回報:85](../../../proto4-3/aos_run.py)、[daemon 解析:94](../../../proto4-3/aos_daemon_entry.py)、[kernel 讀狀態:62](../../../proto4-3/aos_kernel_tick.py)、[scheduler:40](../../../proto4-3/aos_kernel_schedule.py)。

| 容易混淆的點 | 程式事實 |
|---|---|
| kernel 是否知道結果路徑 | 不知道；退出碼沒有附帶 path |
| 是否等待檔案事件喚醒 | 沒有；等待者仍在普通 FIFO／cpu 循環中重新執行 |
| waiting 是否表示 OS process 被 suspend | 不是；本次 agent 已退出 |
| `wait_runs` 是否等於 agent.checks | 不是；一個來自 daemon runs 差值，一個由 agent 每次查不到 result 自增 |
| kernel 是否看到每一次退出 | 不保證；它讀最新 snapshot，中間的退出碼可能看不到 |
| `new_runs>1` 時 | 以最新 last_exit 配合差值加計 wait_runs/bad_runs |
| 被換下時 | wait_runs 存到 kernel state 的 `waiting[pid]`；再次上 cpu 時還原 |

101 讓出的是**後續 cpu 執行機會**，不是將一個仍阻塞在模型呼叫中的 agent 行程移走。[換人／還原 waiting:94](../../../proto4-3/aos_kernel_schedule.py)

---

**5．文件與程式對不上的地方**

下表將明確落差與表述過度保證分開寫；時序推導不當作已跑過的故障測試。

| # | 文件／註解說法 | 程式事實 | 位置 |
|---:|---|---|---|
| 1 | proto5 aos-agent「程式還沒寫」 | 工作樹已有 lib/CLI；think 直接同步 call | [README:16](../../README.md)；[aos_agent:215](../../lib/aos_agent.py) |
| 2 | proto5 lib 列「五支模組」，llm_ask 說 agent「之後」import | 已有第六支 aos_agent，且正在 import／使用 | [lib README:1](../../lib/README.md)、[244](../../lib/README.md)；[aos_agent:18](../../lib/aos_agent.py) |
| 3 | proto4-5「沒有取消」 | 已有 `aos-kernel llm rm`，可殺 running worker 並刪單；另有收件逾時撤 syscall | [README:181](../../../proto4-5/README.md)；[manage:85](../../../proto4-5/llm_cpu_manage.py) |
| 4 | 「每一發另 append usage.jsonl」 | 只有 worker 寫 usage；scheduler 退件、spawn、worker_died、hard timeout 不寫 | [README:157](../../../proto4-5/README.md)；[worker:55](../../../proto4-5/llm_cpu_worker.py)、[tick:35](../../../proto4-5/llm_cpu_tick.py) |
| 5 | result 說明把 notes 列為通用欄位 | scheduler 自產錯誤 result 沒有 notes | [README:66](../../../proto4-5/README.md)；[tick:23](../../../proto4-5/llm_cpu_tick.py) |
| 6 | 「連線及逾時會標 retryable:true」 | 第一層 HTTP timeout 是 true；scheduler hard timeout 使用預設 false | [README:177](../../../proto4-5/README.md)；[tick:15](../../../proto4-5/llm_cpu_tick.py)、[104](../../../proto4-5/llm_cpu_tick.py) |
| 7 | syscall 還在就可說「沒送出去」 | 原單沒有先 rename claim；kernel 可能已讀入但未 unlink，CLI 刪單成功不能證明未送出 | [README:120](../../../proto4-5/README.md)；[module:154](../../../proto4-5/llm_cpu_module.py)、[syscall:86](../../../proto4-3/aos_kernel_syscall.py) |
| 8 | kernel 沒活著就撤掉、不排隊 | CLI 沒有直接判 kernel 存活；它靠等回音逾時推斷。同名同內容分支甚至不投 syscall，也不撤已有單 | [README:118](../../../proto4-5/README.md)；[module:137](../../../proto4-5/llm_cpu_module.py) |
| 9 | `call()` docstring：「永遠以 v1 result 回報成敗」 | 畸形 usage detail 可拋 AttributeError；直接 CLI 未總括捕捉，worker 才包 internal | [aos_llm:89](../../../proto4-5/aos_llm.py)、[11](../../../proto4-5/aos_llm.py)；[worker:50](../../../proto4-5/llm_cpu_worker.py) |
| 10 | 失敗 stderr「一行」 | msg 可直接包含 HTTP body 的換行，print 前沒有壓成單行 | [README:62](../../../proto4-5/README.md)；[aos_llm:156](../../../proto4-5/aos_llm.py)、[CLI:119](../../../proto4-5/aos_llm_cli.py) |
| 11 | agent「連錯五次」stuck | errors 在成功模型／工具輪不清零；實際是同一題期間累計到 5，未要求連續失敗 | [README:27](../../../proto4-7/README.md)；[state_machine:78](../../../proto4-7/state_machine.py)、[195](../../../proto4-7/state_machine.py) |
| 12 | 「每題格數」上限 | step 只在 ask 自增；idle/wait/act 不加，故是 ask 次數上限 | [README:8](../../../proto4-7/README.md)、[26](../../../proto4-7/README.md)；[state_machine:119](../../../proto4-7/state_machine.py) |
| 13 | 收「最舊」的一封信 | 實際按檔名排序，不看 mtime／信件 time；aos-user 的 timestamp 檔名使一般情況看起來是時間序 | [README:25](../../../proto4-7/README.md)；[mailbox:43](../../../proto4-7/mailbox.py) |
| 14 | 工具名對不上就算模型錯誤 | 只適用文字修復；正式 tool_call 的未知工具變成 tool content「沒有這個工具」，不加 errors | [README:91](../../../proto4-7/README.md)；[tools:86](../../../proto4-7/agent_tools.py)、[110](../../../proto4-7/agent_tools.py) |
| 15 | 所有改寫 JSON 都先 tmp/rename | agent 自己主要檔案如此；ask 呼叫的 helper `<name>.req.json` 是直接 write_text | [README:19](../../../proto4-7/README.md)；[aos_py:155](../../../proto4-6/aos_py.py) |
| 16 | 工具程式註解稱 parameters 一定 object、有 properties | 只補缺省；已有 `type:"array"` 或非 dict properties 不會被改掉 | [tools:29](../../../proto4-7/agent_tools.py) |
| 17 | module CLI 第一個參數符合才當 K | 實作掃前兩個參數，支援 action 後接 K | [kernel 文件:84](../../../proto4-3/docs/kernel.md)；[kernel:175](../../../proto4-3/aos_kernel.py) |
| 18 | module 載入失敗會留 note | tick／ls 會處理 notes；module CLI 丟掉 loader.notes，可能只顯示「不認得子命令」 | [kernel 文件:65](../../../proto4-3/docs/kernel.md)；[kernel:186](../../../proto4-3/aos_kernel.py) |
| 19 | kernel tick 退出碼「一律 0；不是家=1」 | 帶參數明確退 2；主 tick 也沒有捕捉所有自身 I/O 例外的總括邊界 | [kernel 文件:57](../../../proto4-3/docs/kernel.md)；[tick:140](../../../proto4-3/aos_kernel_tick.py)、[41](../../../proto4-3/aos_kernel_tick.py) |
| 20 | 排程段括號仍寫「v1 的行程不會自己結束」 | 已有 done_exit，預設 100，搬入 procs/done | [kernel 文件:127](../../../proto4-3/docs/kernel.md)；[schedule:42](../../../proto4-3/aos_kernel_schedule.py) |

另有幾項屬於**文件未完整交代，而非直接相反**：

| 主題 | 程式中的補充事實 | 來源 |
|---|---|---|
| 第一／第二層 endpoint 不同要求 | 第一層可省 timeout/max_concurrent；第二層兩個都必填 | [第一層:58](../../../proto4-5/aos_llm.py)、[第二層:135](../../../proto4-5/llm_cpu_tick.py) |
| 第一層 params 的覆蓋能力 | 只強制保護 model/stream；messages 可被 params 覆蓋 | [body 組裝:140](../../../proto4-5/aos_llm.py) |
| `--wait --json` stdout | 完整 JSON之外另有結果路徑文字行 | [wait_result:184](../../../proto4-5/llm_cpu_module.py) |
| module 衝突 | 不拒絕重名／重疊 OPS，分派取前者 | [CLI:187](../../../proto4-3/aos_kernel.py)、[syscall:105](../../../proto4-3/aos_kernel_syscall.py) |
| syscall wire schema | 實作為同名檔案關聯、固定 `{ok,msg}`，不是包含完整結果的通用回覆 | [syscall:191](../../../proto4-3/aos_kernel_syscall.py) |
| agent 的 101 | kernel 不讀結果檔；只讓位、再輪到時重新跑 agent | [schedule:68](../../../proto4-3/aos_kernel_schedule.py) |

**6．測試證據與本次驗證範圍**

本次沒有執行會建立暫存家、啟動 server／worker、寫檔或殺行程的測試，也沒有跑 build/ctest。因此以下是**閱讀測試碼確認的涵蓋範圍**，不是本次宣告測試全綠。

| proto4-5 測試檔 | 方法數 | 涵蓋內容 |
|---|---:|---|
| [test_aos_llm.py:15](../../../proto4-5/test/test_aos_llm.py) | 16 | endpoint 三種選法、result 全欄位、tools/tool_choice、HTTP500、禁止 model、stdin/stdout、missing key、timeout 覆寫、strict 預檢／fallback |
| [test_home.py:11](../../../proto4-5/test/test_home.py) | 12 | 建家、submit、撞名、壞 request、process 拒絕、壞 endpoints tick 仍 0、ls、aos-exec 一次一 tick |
| [test_worker.py:8](../../../proto4-5/test/test_worker.py) | 9 | success/usage、HTTP500、壞 JSON、model mismatch、alias、missing key、connection refused、固定 model |
| [test_schedule.py:10](../../../proto4-5/test/test_schedule.py) | 7 | priority、mtime、容量、跨 endpoint、worker 死亡、HTTP timeout、hard timeout |
| [test_module.py:19](../../../proto4-5/test/test_module.py) | 14 | 首 tick 建家、syscall 收件、wait/plain/json、两種收件逾時分支、結果逾時、同名同內容冪等／撞名 |
| [test_module_manage.py:19](../../../proto4-5/test/test_module_manage.py) | 6 | init 提示、placeholder 警告、ls、rm、殺 running worker、無 PID 拒絕 |
| 合計 | **64** | 使用假 OpenAI server、CLI 與暫存家 |

`_fake_openai.py` 提供 `/models`、echo、延遲、500、壞 JSON、model mismatch 等情境；`_util.py` 管理 fake server、暫存家、CLI、結果輪詢與清理。[fake server:9](../../../proto4-5/test/_fake_openai.py)、[共用 fixture:19](../../../proto4-5/test/_util.py)

| proto4-7 測試檔 | 方法數 | 涵蓋內容 |
|---|---:|---|
| [test_agent.py:18](../../../proto4-7/test/test_agent.py) | 16 | 四格、req 組裝、一信一題、陣列信、壞信、step 上限、精確 600 次、第五次錯誤、epoch、20 次重試、stuck 清除、退出碼、submit 失敗 |
| [test_tools.py:17](../../../proto4-7/test/test_tools.py) | 9 | schema 補預設、正式／文字 call、普通文字、救回失敗、缺工具／壞參數、非零退出、截斷 |
| [test_user.py:18](../../../proto4-7/test/test_user.py) | 6 | new、內建工具、say、listen、status、talk、reset |
| 合計 | **31** | 假 kernel、人工寫 result、本機 shell 工具 |

proto4-7 的 fake kernel 是把 helper request 複製到假 `K/llm/requests/`，測試再自行寫 result；這組測試**不是實際 kernel module→worker→HTTP 的整條端到端測試**。[fake kernel:26](../../../proto4-7/test/test_agent.py)

kernel 的相關測試明確涵蓋「101 無競爭時留 cpu」「有人排隊時讓位」「waiting 在 ls 顯示」「101 不累計一般錯誤」。[退出碼政策測試:18](../../../proto4-3/test/test_kernel_exit.py)

本次額外執行的唯讀驗證僅有：以 AST 統計上述測試方法，以及以純記憶體 HTTP 替身確認 `params.messages` 覆蓋與畸形 usage 的 `AttributeError`。崩潰窗口、撤單競態、首 tick 前提交等情況，均依原碼順序報告，未聲稱已做故障注入。
