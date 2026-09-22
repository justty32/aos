你的觀察大致成立：**proto5 沒有「aos-agent 走一格」的整體限時，也沒有工具限時、等待期限或引擎連敗上限。**但要補兩個區別：

- `think` 裡的 HTTP **已有預設 120 秒的 socket timeout**，只是它不等於整次思考的牆鐘上限。
- `waits` 可以永遠等不到，但每次檢查完會退 **101**；它不是在同一次 aos-agent 呼叫裡一直阻塞。

本報告依調查時的工作樹，HEAD 為 `9c45f06`。**README 說 aos-agent 尚未實作，但工作樹已有未追蹤的 `aos_agent.py`／CLI，以及尚未提交的 exec／inst 修改**，以下有區分。全程唯讀，沒有改檔，也沒有執行會寫檔的測試；清理風險標為源碼推論，不冒充實跑結果。

**1．現在 proto5 每個環節的逾時事實**

| 環節 | 有沒有限時／預設／在哪定 | 到了怎樣、殺不殺 | 狀態怎麼變 | 依據 |
|---|---|---|---|---|
| **inst.json 本身** | **沒有** `timeout_ms`。只有七個執行欄位；未知頂層 key 忽略 | 寫 `"timeout_ms": 1000` 不會啟用限時 | 不適用 | [inst 格式](/home/guanyu/projs/aos/proto5/spec/inst-posix.md:56)、[解析實作](/home/guanyu/projs/aos/proto5/lib/aos_inst.py:103) |
| **aos-exec 子程式** | 有可選限時：CLI `--timeout-ms`、library 參數；**預設 0＝不限** | 到期 TERM 整個工作 group；最多等 **2 秒**，必要時 KILL；另補殺殘留 group | 回實際 child 結束碼；有指定 `exit` 檔就寫入。exec 不懂 agent state | [旗標規格](/home/guanyu/projs/aos/proto5/spec/exec.md:42)、[_spawn](/home/guanyu/projs/aos/proto5/lib/aos_exec.py:210) |
| **aos-llm-ask HTTP** | **有，預設 120000 ms**；`info.json.engine.timeout_ms`，必須正整數，不能用 0 表示無限 | urllib/socket 逾時→`EngineFailed`；CLI 退 **3**。關閉本地連線，**沒有取消遠端推論的協定** | aos-llm-ask 不改記憶、不讀寫 state、不重試 | [engine 規格](/home/guanyu/projs/aos/proto5/spec/aos-llm-ask.md:117)、[call](/home/guanyu/projs/aos/proto5/lib/aos_llm_ask.py:77) |
| **idle 一格** | **沒有整格限時**。讀設定、記憶及 input 都沒有獨立期限 | 正常沒輸入就立刻退 101；讀寫卡住則沒有 watchdog | 有輸入：接記憶、input rename `.done`、轉 `think`；無輸入：留 `idle` | [格的規格](/home/guanyu/projs/aos/proto5/spec/aos-agent.md:36)、[step](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:191) |
| **think 一格** | **沒有整格限時**；只有內部 HTTP 的上述 timeout | HTTP 能判到的失敗會返回；其他讀寫、DNS、慢速完整回應等不能以 120 秒總期限概括 | 成功有 calls→`act`；無 calls→`idle`；引擎失敗→留 `think`，退 **0** | [規格](/home/guanyu/projs/aos/proto5/spec/aos-agent.md:45)、[實作](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:215) |
| **act 一格** | **沒有整格限時**；所有 tool calls 在一格內**依序跑完** | 某個工具不回，後面工具與記憶寫回都等著 | 全部結果接成 `tool` 訊息後→`think`。中途不回就沒有這次 state 寫回 | [規格](/home/guanyu/projs/aos/proto5/spec/aos-agent.md:48)、[實作](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:230) |
| **工具跑太久** | **沒有**。agent 呼叫 `run_inst(inst, arguments)`，未傳 timeout；library 預設 **0** | **不砍，跑多久等多久**。工具自身另設的限時不算 agent 的保證 | 工具若自行失敗，非零退出碼包成 `tool` 訊息；不回則停在該次 act | [工具呼叫](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:159)、[run_inst 預設](/home/guanyu/projs/aos/proto5/lib/aos_exec.py:87) |
| **工具檔 `_meta`** | **沒有逾時欄位的契約**；目前就是一份 posix inst | 加 `_meta.timeout_ms` 也不會生效：工具讀驗未賦予語意，inst 解析忽略它 | 不適用 | [工具檔規格](/home/guanyu/projs/aos/proto5/spec/aos-llm-ask.md:82)、[工具讀驗](/home/guanyu/projs/aos/proto5/lib/aos_agent_info.py:325) |
| **`waits` 門** | **沒有期限、沒有最大檢查次數**。`mtime`／`since` 只判檔案是否更新 | 每次劃掉已到條目；有剩→101。沒有到期分支，也不殺產生結果的工作 | state 原樣保留；只更新 waits。可以跨無限多次呼叫一直101 | [等待規格](/home/guanyu/projs/aos/proto5/spec/agent.md:110)、[_gate](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:98) |
| **引擎失敗重試** | **沒有連敗上限、沒有退避、没有總期限** | 每次 stderr 一行，退0；外部下一次叫它就再問 | 一直留 `think`，記憶不動；沒有 retry／stuck 狀態或錯誤計數 | [規格](/home/guanyu/projs/aos/proto5/spec/aos-agent.md:46)、[實作](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:219) |
| **整個「走一格」呼叫** | **沒有**。CLI 只收 dir，沒有 timeout 旗標；step 沒有整體計時器 | 沒有人在整格到期時中止它。外部執行器可以另外包限時，但不是目前 agent 契約 | 沒有「整格逾時後」的狀態轉換規格 | [CLI](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:246)、[延後決定事項](/home/guanyu/projs/aos/proto5/spec/aos-agent.md:73) |

規格 §5 明文保留的是：

> 「工具跑太久要不要砍（現在不砍，跑多久等多久）、引擎連續失敗幾次要停、`waits` 等太久要怎樣——之後再定。」  
> — [aos-agent.md:77](/home/guanyu/projs/aos/proto5/spec/aos-agent.md:77)

**為什麼 timeout 不在 inst 裡？**

proto5 的七欄規格沿用「inst 描述怎麼執行，執行者決定願意等多久」的分工。明確理由寫在前代：

> 「時限不是指令的事，是『反覆執行 inst.json 的傢伙』的事。」  
> — [proto4-3/README.md:11](/home/guanyu/projs/aos/proto4-3/README.md:11)

因此，「工具有自己的建議時限」與「把 timeout 重新放回通用 inst」是兩個不同決策，不必綁在一起。

**HTTP 的 120 秒實際管到哪裡？**

`call()` 只有 `urlopen(req, timeout=T)` 接 `resp.read()`，沒有建立整次呼叫共用的 deadline。[實作](/home/guanyu/projs/aos/proto5/lib/aos_llm_ask.py:84)

| 階段 | 120 秒是否涵蓋 | 準確解讀 |
|---|---|---|
| DNS 名稱解析 | **沒有由此參數保證的總上限** | 本機 Python 的 `create_connection()` 先做 `getaddrinfo()`，才替 socket 設 timeout |
| TCP 連線 | **有 socket timeout** | 若解析出多個位址逐一嘗試，並非所有嘗試共用一次120秒 |
| HTTP 送出、等待狀態列／headers、讀 body | **相關 socket 阻塞操作受限** | 不是只管 connect；回應讀取也使用該 socket |
| 完整回應總耗時 | **沒有120秒總上限** | 持續慢慢回資料，可能每次都未觸發 socket timeout，但整份讀取超過120秒 |
| 組 JSON、解析 JSON、讀寫 agent 檔案 | **沒有** | 不在 HTTP timeout 的計時範圍 |
| 遠端模型／遠端排隊 | **沒有可保證的取消** | 本地不等了，不表示服務端停止計算或排隊 |

這與 Python 官方對 timeout 的定義一致：它限制連線等阻塞操作。另核對了本機 Python 3.12 的實作傳遞鏈。[Python urllib 文件](https://docs.python.org/3.12/library/urllib.request.html#urllib.request.urlopen)、[socket.create_connection](/usr/lib/python3.12/socket.py:810)、[HTTP 讀回應](/usr/lib/python3.12/http/client.py:468)

**exec 的 143／137 也要精確理解**

| 容易誤讀的地方 | 實際情況 |
|---|---|
| 「timeout 一定回143或137」 | **不是**。它回 child 的實際退出碼。child 因 TERM 死掉才143，因 KILL 死掉才137；若捕捉 TERM 後自行 `exit(0)`，可以回0 |
| 「看到143／137就知道是timeout」 | **不能單憑碼判定**，其他來源送同樣訊號也可能得到同碼。目前回傳沒有 `timed_out` 欄位 |
| 「設定1000ms就整個 run_target 最多1秒」 | **不是**。真正的 wait／communicate timeout 在 spawn 後開始；讀驗、開檔、啟動、清理寬限、寫exit檔都在之外 |
| 「砍group就是砍所有後代」 | 只保證向**該 group**發訊號；另開 session/group 的後代不在裡面 |
| 「被外層砍掉agent，工具自然跟著死」 | **不能保證**。工具由 `_spawn(start_new_session=True)` 另開group，且目前 agent 沒有轉送終止訊號／清理工具的 handler |

來源：[spawn／計時／回碼](/home/guanyu/projs/aos/proto5/lib/aos_exec.py:218)、[group 清理](/home/guanyu/projs/aos/proto5/lib/aos_exec.py:259)。

另外，proto5 工具 stdout 以 `communicate()` 全量收進記憶體，**沒有輸出上限**；HTTP body 也整份讀取。限時與輸出容量是兩個不同問題。[exec](/home/guanyu/projs/aos/proto5/lib/aos_exec.py:230)、[HTTP](/home/guanyu/projs/aos/proto5/lib/aos_llm_ask.py:88)

**2．歷代怎麼做**

先用每個 proto 一列總覽；後面展開容易混淆的細節。

| Proto | 哪一層管、值多少 | 到了做什麼／之後狀態 | 重試上限 | 踩過的坑／缺口 |
|---|---|---|---|---|
| **proto2** | exec／loop／活PID watchdog：**沒有**；sh 工具60秒、最多120秒；HTTP300秒，另TCP probe10秒；主線等待1800／60格；旁線600秒；長job3600秒 | 主線→`retry`；工具失敗回結果；旁線到期結算error並喚醒；kernel只重開死掉的clock | 主線隔20格再試，第5次失敗→`stuck`；但缺choices有清帳漏洞。kernel重開失敗無上限 | 格數誤當時間／工作量；放棄等待沒撤舊單；idle掉話；互等死結；自製工具仍無限時 |
| **proto4-3** | kernel設定→aos-run→exec；每格預設0不限；run另有整體 `time-limit-ms`；TERM→2秒→KILL；daemon停止流程5秒 | 子工作典型143／137，run預設繼續跑；kernel一般非零累計到`bad_after=10`→`procs/bad/` | run預設無上限；bad_after不是可靠跨換人的全域上限 | quantum算已完成格數，抓不到卡死；daemon平時不抓卡活工作；停止時group層次可能漏清 |
| **proto4-5** | HTTP預設300秒；worker從dispatch算T+5秒；**排隊無期限**；結果`--wait`自訂秒數 | HTTP失敗回error；watchdog TERM worker PID、寫timeout結果、搬done；`--wait`到時只停止等待 | **没有自動重試**；`retryable`只是結果欄位 | `/models`與chat各吃完整T；watchdog只有TERM、未確認死就結帳；撤單與停止等待混淆 |
| **proto4-6** | `wait_for` **沒有上限**；since/checks只是記錄。`bad_after`在kernel，預設10 | 沒檔就101；檔到才清waiting、記history、繼續 | 等待無上限；101不算bad | 有等待計數不代表有期限；bad_after救不了永遠等檔 |
| **proto4-7** | 每工具60秒；給模型的輸出預設8000字元；模型等待600次檢查；20次idle後重送；每題60次ask | 工具錯誤→tool訊息→ask；模型錯誤→idle；errors≥5設`stuck:true`、通知人 | 同題累積5次錯停；新信清帳。沒有獨立retry state | 每工具60秒不是act總上限；等待逾時不撤LLM舊單；README稱連錯，但成功未清errors；輸出是事後截斷 |

主要實作入口：[proto2 agent](/home/guanyu/projs/aos/proto2/aos-agent:18)、[4-3 run](/home/guanyu/projs/aos/proto4-3/aos_run.py:72)、[4-5 scheduler](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:72)、[4-6 waiting](/home/guanyu/projs/aos/proto4-6/step_common.py:74)、[4-7 state machine](/home/guanyu/projs/aos/proto4-7/state_machine.py:78)。

**proto4-3：誰量、誰砍、砍完去哪**

| 問題 | 查到的事實 | 來源 |
|---|---|---|
| aos-run每格誰量？ | run把timeout傳给同進程的exec library，由exec等待／終止child；沒有第二套每格watchdog | [run:82](/home/guanyu/projs/aos/proto4-3/aos_run.py:82) |
| 整體run壽命怎麼算？ | `--time-limit-ms`預設0；有效每格限時＝`min(每格限時, 剩餘整體時間)`，未設每格限時則用剩餘時間。到期run記`stop time_limit`，退出0 | [run:126](/home/guanyu/projs/aos/proto4-3/aos_run.py:126)、[停止回碼](/home/guanyu/projs/aos/proto4-3/aos_run.py:113) |
| timeout後會停run嗎？ | 預設不會，照間隔繼續。`--stop-on-error`只針對`kind=aos`，timeout屬child，不在其中 | [run:95](/home/guanyu/projs/aos/proto4-3/aos_run.py:95) |
| kernel有沒有量一格跑多久？ | **沒有 elapsed watchdog**。quantum預設5，算runs差值；`since`沒有用來判逾時。換inst／rm不殺當次 | [schedule:26](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:26)、[kernel限制](/home/guanyu/projs/aos/proto4-3/docs/kernel.md:188) |
| 143／137怎麼處理？ | 當一般child非零，增加bad_runs；預設10後inst搬`procs/bad/`、cpu換idle、記log。**不修改agent的state，不製造模型訊息** | [bad計數](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:75)、[退件](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:150) |
| bad_after有什麼限制？ | daemon只提供最後一筆退出碼，中間多次runs以最後碼推算；換人時bad_runs不保存。因此不能視為精確、跨排程的10次重試上限 | [觀察結果](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:40)、[換人新紀錄](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:133) |
| 101會變bad嗎？ | 不會。101標waiting，有人排隊就讓出cpu；等待次數無上限 | [waiting與排除碼](/home/guanyu/projs/aos/proto4-3/aos_kernel_schedule.py:68) |
| kernel自己會卡嗎？ | module hook直接在kernel進程執行，只有例外捕捉，無每hook限時；kernel自己那顆cpu也吃boot傳入的timeout，預設仍0 | [module](/home/guanyu/projs/aos/proto4-3/aos_kernel_module.py:53)、[boot](/home/guanyu/projs/aos/proto4-3/aos_kernel_boot.py:37) |
| 自癒到底修什麼？ | daemon表缺cpu就重新add；runs歸零後重設計數。**不是診斷活著但卡死的工作** | [poll_cpus](/home/guanyu/projs/aos/proto4-3/aos_kernel_tick.py:69) |

daemon與控制指令另外一層：

| 情況 | 限時與結果 | 來源 |
|---|---|---|
| 正常running的子工作卡住 | **沒有watchdog** | [Entry狀態與advance](/home/guanyu/projs/aos/proto4-3/aos_daemon_entry.py:132) |
| rm／restart | TERM aos-run，進stopping／restarting；5秒仍活就KILL aos-run group。`--force`另於0.2秒後送第二次TERM，由run handler殺正在跑的工作group | [Entry停止](/home/guanyu/projs/aos/proto4-3/aos_daemon_entry.py:118)、[run訊號处理](/home/guanyu/projs/aos/proto4-3/aos_run_status.py:18) |
| shutdown | CONT＋TERM所有run，等5秒後補KILL；另有每child最多2秒wait、讀線程join，所以不是整體嚴格5秒 | [lifecycle](/home/guanyu/projs/aos/proto4-3/aos_daemon_lifecycle.py:40) |
| pause | 等ready且非running才STOP；pause_pending無期限。若run被STOP，負責timeout的人也停住，工作限時可能失效 | [Entry](/home/guanyu/projs/aos/proto4-3/aos_daemon_entry.py:136)、[README明載](/home/guanyu/projs/aos/proto4-3/README.md:134) |
| daemon-ctl等回覆 | 等回執最多10秒；部分動作再等狀態最多10秒。到時CLI退1，**不撤單、不撤銷已受理動作** | [ctl](/home/guanyu/projs/aos/proto4-3/aos_daemon_ctl.py:108) |
| kernel rm等回覆 | 最多`max(3秒, 3×interval)`；到時退1，**未撤pending syscall** | [syscall](/home/guanyu/projs/aos/proto4-3/aos_kernel_syscall.py:53) |

兩個清理缺口是**源碼推論**：

1. daemon啟動run開一個session，exec啟動工作又開另一個session。daemon的5秒fallback只殺run那個group，可能留下工作group。[daemon spawn](/home/guanyu/projs/aos/proto4-3/aos_daemon.py:68)、[Entry kill](/home/guanyu/projs/aos/proto4-3/aos_daemon_entry.py:160)
2. 舊exec最後補殺時重新 `getpgid(child.pid)`；leader已被wait回收，可能查不到而吞掉錯誤。proto5工作樹已改為直接 `killpg(p.pid)`，修掉這個查詢窗口，但仍只涵蓋同group後代。[舊版](/home/guanyu/projs/aos/proto4-3/aos_exec.py:201)、[proto5](/home/guanyu/projs/aos/proto5/lib/aos_exec.py:259)

**proto4-5：排隊、HTTP、worker、`--wait`是四件不同的事**

| 層 | 精確事實 |
|---|---|
| HTTP值來源 | `request.timeout_ms`優先，其次endpoint，最後預設300000ms；沒有自動retry loop。[aos_llm:116](/home/guanyu/projs/aos/proto4-5/aos_llm.py:116) |
| preflight | 預設先查`/models`，再chat；**兩次各拿完整T**。preflight失敗可記note後繼續chat，因此call總耗時可能超過T。[aos_llm:125](/home/guanyu/projs/aos/proto4-5/aos_llm.py:125) |
| queue | 沒有expiry；容量滿就留著。priority高先跑，同優先看mtime；低優先可一直被插隊。`started`在dispatch才寫。[dispatch](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:192) |
| worker watchdog | 從dispatch起算T+5000ms，下一次tick檢查才觸發。只TERM **PID**，沒KILL、沒確認退出，就寫timeout結果、搬done。[finish_running](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:98) |
| watchdog結果 | HTTP timeout標`retryable:true`；scheduler製造的timeout結果沿用預設`false`。兩條失敗路徑語意不一致。[HTTP](/home/guanyu/projs/aos/proto4-5/aos_llm.py:164)、[scheduler error](/home/guanyu/projs/aos/proto4-5/llm_cpu_tick.py:15) |
| worker晚到 | worker仍可寫同一結果檔；若TERM未讓它停，可能覆蓋watchdog結果、帳面已釋放容量但工作仍活著。**源碼推論**。[worker寫檔](/home/guanyu/projs/aos/proto4-5/llm_cpu_worker.py:49) |

題目中的「`--wait`逾時撤單」必須分清楚：

| 指令／等待階段 | 到期是否撤單 |
|---|---|
| proto4-3 daemon-ctl／kernel rm | **不撤**；這代沒有題目所指的LLM `--wait`機制 |
| proto4-5 **等kernel收單回執** | 最多`max(3秒, 3×interval)`；syscall檔還在，才unlink撤未撿單；已被撿走則不能保證撤回 |
| proto4-5 **`--wait SECS`等結果** | **不撤**。只停止等待、退1、印結果將出現的位置 |
| proto4-5 **明確`llm rm`** | running時TERM group等1秒，再KILL group等1秒；成功才刪queue／running／done／result。沒有留下cancelled結果供等待者收取 |

來源：[收單回執處理](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:154)、[結果wait](/home/guanyu/projs/aos/proto4-5/llm_cpu_module.py:174)、[明確remove](/home/guanyu/projs/aos/proto4-5/llm_cpu_manage.py:85)。

所以「不等了」「單子確定沒送出」「已送出的工作被取消」不能用同一句「逾時撤單」表示。

**proto4-6／4-7：等待計數與retry／stuck**

| 機制 | 事實與限制 | 來源 |
|---|---|---|
| 4-6 `wait_for` | 存`for/since/after_pc/checks`；since只顯示、checks只增加。檔不存在永遠等，101不計bad_after | [step_common](/home/guanyu/projs/aos/proto4-6/step_common.py:74) |
| 4-7工具60秒 | 每個call各自60秒；同一act逐個執行，整格可以遠超過60秒 | [agent_tools](/home/guanyu/projs/aos/proto4-7/agent_tools.py:105)、[do_act](/home/guanyu/projs/aos/proto4-7/state_machine.py:217) |
| 工具輸出8000字元 | 完整capture之後才截斷；**不是執行中的byte／記憶體上限**。錯誤stderr另取前500字元 | [截斷](/home/guanyu/projs/aos/proto4-7/agent_tools.py:122)、[預設設定](/home/guanyu/projs/aos/proto4-7/state_machine.py:32) |
| 重複工具限時 | 預設sh腳本自己又包`timeout 60 sh -c`，與外層60秒重疊，誰先觸發可能影響結果碼 | [預設sh](/home/guanyu/projs/aos/proto4-7/aos_user_cli.py:35) |
| 模型600次檢查 | 第599次仍101，第600次記錯回idle；不是600秒；**不撤原LLM單** | [do_wait](/home/guanyu/projs/aos/proto4-7/state_machine.py:172) |
| retry | 沒有獨立retry state。idle且對話尾是user/tool、未stuck，20次idle檢查後再ask | [do_idle](/home/guanyu/projs/aos/proto4-7/state_machine.py:94) |
| stuck | errors≥5設`stuck:true`，state仍idle，outbox通知人。**成功沒有清errors，實際是同題累積5錯**；新信才清帳 | [記錯](/home/guanyu/projs/aos/proto4-7/state_machine.py:78)、[成功路徑](/home/guanyu/projs/aos/proto4-7/state_machine.py:184) |
| 每題60步 | 只在ask增加step，第61次不送模型。wait／idle檢查不扣；不是所有「走一格」都計數 | [do_ask](/home/guanyu/projs/aos/proto4-7/state_machine.py:119) |

「模型出錯回idle要根治→retry／stuck」的來源在 **proto2**；4-7把這套濃縮成idle上的欄位，而非增加狀態。[proto2 README](/home/guanyu/projs/aos/proto2/README.md:46)、[移植筆記](/home/guanyu/projs/aos/proto4/notes/agent/legacy-harvest.md:40)

**proto2：散落在各層的關卡**

| 類別 | 值與到期動作 | 重要邊界／來源 |
|---|---|---|
| exec／loop | **沒有單次牆鐘限時**；loop的steps只限格數、interval是格間隔 | 一格卡住整顆loop就卡住。[exec](/home/guanyu/projs/aos/proto2/aos-exec:26)、[loop](/home/guanyu/projs/aos/proto2/aos-loop:57) |
| kernel自癒 | running且PID活就略過；只有死亡才重開，重開失敗之後每格再試，**無上限** | 活PID卡死抓不到。[監督](/home/guanyu/projs/aos/proto2/aos-daemon-kernel:492)、[重開](/home/guanyu/projs/aos/proto2/aos-daemon-kernel:436) |
| kernel收工／daemon等待 | 收工TERM clock groups，0.3秒後KILL；daemon CLI預設等10秒，逾時原請求仍留著 | 關機清理不是平時watchdog。[收工](/home/guanyu/projs/aos/proto2/aos-daemon-kernel:518)、[CLI](/home/guanyu/projs/aos/proto2/aos-daemon:111) |
| agent主線等LLM | 請求在queue/running：1800格；不在：60格；缺鐘立即記錯；到期→retry，通知聊天端 | **不撤原單**；1800／60共用waited，請求消失不會從0重新等60格。[do_wait](/home/guanyu/projs/aos/proto2/aos-agent:223) |
| agent連敗 | 間隔20格重送，第5錯→stuck，等新信；新信／成功清帳 | 缺choices的分支在驗證前先清帳，每次歸1，實際到不了5錯。[retry](/home/guanyu/projs/aos/proto2/aos-agent:196)、[清帳漏洞](/home/guanyu/projs/aos/proto2/aos-agent:260) |
| 協定重送／每題上限 | 壞文字tool call救不回，只額外重送1次；每題動作預設60，超過進limit_pause問人 | 等待、睡眠不算動作格；皆非單格timeout。[協定](/home/guanyu/projs/aos/proto2/aos-agent:274)、[題目上限](/home/guanyu/projs/aos/proto2/aos-agent:460) |
| `fs.sh` | 預設60秒，可設到120秒；到期直接KILL group；回timeout錯誤，stdout/stderr各保尾1500字元 | 有工具時限不代表整格有時限。[fs](/home/guanyu/projs/aos/proto2/packs/fs.py:204) |
| 自製工具／toolsmith | **沒有timeout** | 同步shell可卡整格；自製工具回完整輸出。[run_custom](/home/guanyu/projs/aos/proto2/aos_agent.py:234)、[toolsmith](/home/guanyu/projs/aos/proto2/packs/toolsmith.py:163) |
| pyshop／studio測試 | 60秒；TimeoutExpired→失敗，截短輸出 | 使用subprocess timeout，沒有專門killpg清整樹。[pyshop](/home/guanyu/projs/aos/proto2/packs/pyshop.py:212)、[studio](/home/guanyu/projs/aos/proto2/packs/studio.py:240) |
| 旁線／等信 | 預設600秒；記since_ts，agent後续收件時判到期；寫timeout結果、清pending／sleeping、hook可喚醒主線 | **不撤running、不殺worker**；不是獨立timer，agent沒再收件就不會處理到期。[send](/home/guanyu/projs/aos/proto2/aos_agent.py:1193)、[collect](/home/guanyu/projs/aos/proto2/aos_agent.py:1257) |
| 旁線cancel | 刪原路徑request、清pending、寫cancelled結果 | 已搬到running的worker不會被殺。[cancel](/home/guanyu/projs/aos/proto2/aos_agent.py:1316) |
| `run_long` | 命令包`timeout 3600`；旁線也等3600秒；命令exit124解成timeout | 沒有`-k`第二道KILL；兩個3600秒起算不同，會競賽。[jobs](/home/guanyu/projs/aos/proto2/packs/jobs.py:25) |
| 共用鎖 | 預設10秒monotonic等待flock，超時報錯 | 只限等鎖，未限制持鎖工作總長。[lock](/home/guanyu/projs/aos/proto2/aos_agent.py:491) |
| HTTP | TCP probe10秒，之後真正urllib請求300秒；失敗產生LLM error結果，由agent决定重試 | probe不是實際HTTP連線共用的10秒connect deadline。[HTTP](/home/guanyu/projs/aos/proto2/aos-llm:1552) |
| priority.deadline | 到期提高排程優先權，aging最多加300分 | **不是過期撤單，也不是執行期限**。[priority](/home/guanyu/projs/aos/proto2/aos-llm:160) |
| CLI引擎 | Claude CLI300秒subprocess timeout；Codex CLI300秒總期限，TERM group後3秒KILL | Claude路徑沒專門group清理；兩條不等價。[Claude](/home/guanyu/projs/aos/proto2/aos-llm:1095)、[Codex](/home/guanyu/projs/aos/proto2/aos-llm:1322) |

**歷史踩坑與使用者原話**

下表是歷史實驗／整理筆記，**不是把它們當成使用者逐字指令**。

| 坑 | 當時處理／對本題的意義 | 來源 |
|---|---|---|
| 七人共用兩路引擎，排隊超60格便放棄重送，舊請求仍在燒 | 改「請求仍排隊／執行中就等」，實際上限1800格；等待不扣每題動作格 | [journey:33](/home/guanyu/projs/aos/proto2/notes/2026-09-07-studio-journey.md:33) |
| PM等chief回信，chief等PM補額度，互等死結 | 睡著的人也要被未讀信叫醒；單有timeout未必能判斷業務死結 | [journey:39](/home/guanyu/projs/aos/proto2/notes/2026-09-07-studio-journey.md:39) |
| 凍住300格再喊，sales反覆回「撥不出來」 | 通知太吵；額度抬高後也不該再等300格，後改每10格嘗試自動撥款 | [studio-4:34](/home/guanyu/projs/aos/proto2/notes/play/2026-09-07-studio-4.md:34)、[journey:155](/home/guanyu/projs/aos/proto2/notes/2026-09-07-studio-journey.md:155) |
| 模型失敗回idle，未回覆的話永遠不再送 | retry／stuck與dangling safety net處理的是「誰再喚醒」，不只是幾秒timeout | [lessons:7](/home/guanyu/projs/aos/proto2/notes/2026-09-07-lessons.md:7) |
| 任務做到一半idle | 45格提醒、最多3次；再不動改報主管 | [studio:802](/home/guanyu/projs/aos/proto2/packs/studio.py:802) |
| idle55分鐘，ticks還一直增加 | 「進程活著」「tick有增加」都不等於任務有進度 | [studio-3](/home/guanyu/projs/aos/proto2/notes/play/2026-09-07-studio-3.md:7) |
| 旁線120格期限隨排程速度失真 | 改600秒牆鐘時間；文件部分仍留120格，需看程式 | [simplify-2](/home/guanyu/projs/aos/proto2/notes/play/2026-09-07-simplify-2.md:5) |

`thinking/`目前四份檔案已讀完，**沒有「逾時／限時／超時／卡住／timeout／deadline」的原話**。最接近的是pause：

> 「交給外部cpu跑的東西，回來的結果也是會存，但agent不會反應」  
> 「shell跑的東西，會跑完，但agent不會反應」  
> — [thinking/aos-agent.md:17](/home/guanyu/projs/aos/thinking/aos-agent.md:17)

這描述的是**暫停狀態機、不取消外部工作**。

真正相關的使用者原話在另一份明確標成「抒發原文，不是規格」的筆記：

| 原話 | 出處 |
|---|---|
| 「基本上agent的每一歩都是建議盡可能短小，否則可能會影響fps，也就是每次tick的時間。」 | [world-clock-agent:11](/home/guanyu/projs/aos/proto2/notes/2026-09-06-world-clock-agent.md:11) |
| 「某些操作要跑很久，那通常會將該操作弄成新的世界，請求daemon另開一個時鐘去處理」；另提直接fork可能「逃離daemon的管束」 | [同檔:15](/home/guanyu/projs/aos/proto2/notes/2026-09-06-world-clock-agent.md:15) |
| 「原本預期中很快就好的操作卡很久，通常情況下就是乖乖阻塞停在他那邊」；接著提出逾時後另fork繼續tick的構想，並說「再想想吧」 | [同檔:19](/home/guanyu/projs/aos/proto2/notes/2026-09-06-world-clock-agent.md:19) |
| 「至於LLM，通常agent會將相關請求丟到某個資料夾，讓那個資料夾的時鐘處理。」 | [同檔:19](/home/guanyu/projs/aos/proto2/notes/2026-09-06-world-clock-agent.md:19) |

這些支持「短格、長工作由別的執行者負責」的方向，但**沒有拍板具體timeout值或到期處置**。

**3．限時應該放在哪一層：候選方案分析**

以下全部是**分析與建議，尚未決定**。

先區分四個問題：**單次工作跑太久、等待結果太久、連續失敗太多、任務沒有進展**。一個timeout欄位管不了全部。

| 候選位置 | 管得到 | 管不到 | 到期後建議的狀態／訊息 | 清理責任 |
|---|---|---|---|---|
| **(a) 工具檔的timeout** | 一次tool call，包括shell／工具自身死循環、等待外部命令 | 整批act累積時間、agent讀寫卡住、HTTP、跨格waits | 為該call產生`role:tool`失敗，帶`tool_call_id`；其餘calls仍各自得到結果；act結束→think | **exec**負責TERM／KILL工具group；agent只決定預算、翻譯結果 |
| **(b) aos-agent整格上限** | 若由外部監督，可以涵蓋讀驗、HTTP、整批工具、寫回 | 跨很多格永遠101、每格都很快但一直重試；已脫離管束的工作 | 正常局部timeout由agent收尾；**整格被硬砍則記`step_timeout`並停排，先保留原state**，不能假裝工具未做 | 外部監督者要能清agent及其工具groups；agent自己量只能做合作式收尾 |
| **(c) kernel／aos-run上限** | 一般程式一格卡死、agent自身壞掉、kernel module卡死 | 不知道某個tool call是否已產生副作用；不懂waits业务期限 | kernel記執行失敗、把行程停放到bad／待處理；**不直接改寫agent history**。agent恢復器才翻成模型訊息 | **aos-run／共用exec執行機制量與砍；kernel定政策、停排**，不再另寫一套相同計時器 |
| **(d) waits每條加`until`** | 結果檔永不到、等待條目已失去意義；重啟後仍可判過期 | 檢查門的程式根本沒被叫；同步tool卡住；不自動取消產生結果的人 | 區分`arrived`與`expired`。過期不能偽裝有结果；一般等檔可產生`wait_timeout` user事件；未完成tool協定則必須補匹配的tool結果 | waits判定者只結算等待；**原工作owner**處理撤單／kill |
| **(e) 引擎連敗N次停** | HTTPtimeout、連線失敗、模型格式失敗不斷重試 | 單次永不返回；每次成功但毫無進度；工具失敗 | 建議明確`stuck`，保留未回覆的對話，記錯因、通知使用者一次；沒有tool call就不要捏造tool訊息 | 引擎／worker先結束本次呼叫；agent只管「下一次還送不送」 |
| **(f) LLM CPU排隊／執行期限** | queue飢餓、worker卡死、HTTP慢、worker死亡無結果 | agent取件／寫history卡住；遠端是否真的取消需服務端支援 | 終態結果明列`queue_timeout`、`execution_timeout`、`worker_died`、`cancelled`；agent收取後套同一連敗政策 | **LLM CPU**擁有queue、worker、取消與終態；HTTP client只負責一次連線 |

**(a) 放在inst，還是工具私有欄位？**

| 形狀 | 好處 | 代價／注意 |
|---|---|---|
| 通用`inst.timeout_ms` | 所有執行者能讀同一欄 | 推翻已經移出inst的分工；必須重定CLI／kernel覆蓋優先序；不宜只為工具需求就順手做 |
| `_meta.timeout_ms`，由agent取出後傳exec | 工具描述與執行預算放一起 | `_meta`不再完全等於純inst；要明訂這是agent擴充。**現在直接加不會生效** |
| 工具元素旁的`_timeout_ms` | 保留`_meta`純inst；現有去除`_` key規則已避免送給模型 | 多一個工具私有欄位；agent_info須驗證，agent須傳给exec |

我偏向第三種，原因是能加工具預算，又不把通用inst的方向一起改掉。

**(b) 自己量，還是外面量？**

自己在`step()`進出時看時鐘，只能知道「已經超時」，**不能中止卡在中間、永遠不返回的呼叫**。同進程timer／thread也不能直接當成可可靠清理任意阻塞工作的保證。

整格硬上限應由**仍在運作的另一個進程**量。對目前架構，最自然是run／exec監督agent child；kernel保留政策與結果。不宜讓負責監督的run跟agent一起暫停。

**外層group問題必須同時處理**：現在工具另開group，外層只kill agent group會漏工具。可選「登記每次執行所擁有的groups，讓監督者清理」或「使用cgroup等共同容器」；後者更完整，但需驗證部署環境。只加一個`p.wait(timeout=...)`還不能宣稱整棵工作已清完。

**(d) `until`不能直接拿`since`代替**

`since`是「只接受這個時間之後修改的檔」；`until`才是「最多等到這個時間」。兩者可同時存在，語意不同。

| 到期政策 | 效果／問題 |
|---|---|
| **過期也算到了** | 最省程式，但後續讀結果可能沒有檔，會把timeout變成其他錯誤；不建議無聲採用 |
| **移除過期條目並記失敗事件** | 保留成功／失敗區別；若還有其他waits，門仍關著，事件不一定立即進模型 |
| **任一過期就讓整批等待失敗** | 能快速讓模型重新安排，但需要定義哪些waits屬於同一工作，不能順手清掉人工pause |
| **停住待處理** | 不會錯把失敗當成功；但要人來恢復，不能自動推進 |

檢查可先看是否有合格結果，再看時間；若要严格判「期限前到達」，還得比結果的可信完成時間，不能只靠本次poll的時間。

**跟現有機制怎麼接**

| 現有機制 | 加timeout時應守的界線 |
|---|---|
| **101** | 表示本次快速檢查後「還在等」，不是timeout錯誤。不要用`bad_after`懲罰正常等待 |
| **`waits`門先於state** | 只把timeout通知丟到input，**不會自動穿過沒開的門** |
| **input只在idle收** | think／act的timeout事件不能假設寫input就會立刻進模型；要定義安全的事件合併時機 |
| **`.done`** | 現在代表輸入／等待檔被消費，不代表工作取消、worker已死，也不是timeout標記 |
| **waits.consume** | 等的結果也要由input／專門收件者讀時，不要先consume；否則門開了，結果卻已rename走 |
| **assistant/tool順序** | assistant已有多個calls時，每個call都要有對應tool結果，才能再問模型；不能中途直接插一則user timeout後重問 |
| **現有自癒** | 只處理history先寫、state後寫造成的落差；**不保證工具副作用只發生一次** |
| **kernel自癒** | 能補cpu、重開進程，不應把「剛被timeout停住」立即當成缺cpu而無限重啟 |
| **晚到結果** | timeout／cancel後必須按request id辨認，不得覆寫已結算的終態，也不得混進新一題 |

來源基礎：[gate順序](/home/guanyu/projs/aos/proto5/lib/aos_agent.py:191)、[input與consume規格](/home/guanyu/projs/aos/proto5/spec/agent.md:96)、[自癒與寫回規格](/home/guanyu/projs/aos/proto5/spec/aos-agent.md:51)。

尤其`act`目前是：

`跑工具A → 跑工具B → … → 一次寫全部tool結果 → 寫state`

若A已完成、B卡住而整格被砍，磁碟history可能仍只有原assistant calls；下次照目前邏輯會重跑A。**自動恢復需要逐call執行記錄、結果落盤及「結果未知」處置；這比單加限時大得多。**

**實作要動哪些檔、複雜度**

下列是可能的修改落點，沒有動手。

| 候選 | 現有檔案／新增部分 | 複雜度 |
|---|---|---|
| (a) 每工具限時 | `proto5/spec/aos-llm-ask.md`工具欄位；`aos_agent_info.py`驗預算；`aos_agent.py`傳參與產生timeout tool結果；`aos_exec.py`回傳明確timeout原因 | **低～中**。單傳參很小；可靠結果原因、輸出與清理要一起定 |
| (b) agent整格 | `spec/aos-agent.md`；`lib/aos_agent.py`終止收尾／恢復；`lib/aos_exec.py`執行group登記／輸出關閉；CLI若增加設定也要改 | **中～高**。真正成本在中途被砍後的狀態與副作用 |
| (c) run／kernel | proto5尚未有這些實作；以4-3的`aos_run.py`、`aos_run_status.py`、`aos_kernel_tick.py`、`aos_kernel_schedule.py`、`aos_daemon_entry.py`為移植落點，新增每次執行ID、timeout原因、停排政策 | **中～高**。不能只複製bad_after或5秒kill fallback |
| (d) waits期限 | `spec/agent.md`、`spec/aos-agent.md`；`aos_agent.py`的`_read_state/_gate/step`；事件保存／收取路徑 | **中**；若要取消工作與跨多條waits結算則**高** |
| (e) 連敗停 | `spec/agent.md`新增狀態／計數契約；`spec/aos-agent.md`定重試、清零、恢復；`aos_agent.py`實作 | **低～中**，三狀態契約會改 |
| (f) LLM CPU | 重用`aos_llm_ask.call()`；新增queue／worker／result／cancel協議與模組；改agent的think送件／收件；更新engine／waits規格 | **高**，是跨進程生命週期；已有規劃任務書，但不是已完成能力 |

**4．建議：最精簡的一組關卡**

以下數值是**建議起點，未經效能測量，也不是已拍板預設**。

| 關卡 | 建議預設 | 到期處理 | 先做／後做 |
|---|---:|---|---|
| **一次tool call** | **60000ms**；工具可覆寫 | exec TERM→2秒→KILL；回明確`tool_timeout`結果，agent補對應tool訊息，繼續完成該批calls | **先做** |
| **HTTP** | 保留目前 **120000ms** | 一次呼叫失敗返回；不在client內偷偷重試。文件明說它是socket timeout | **保留並說清楚** |
| **agent連敗** | **總共3次失敗**，不是首發再加3次；兩次之間至少 **5秒** | 保留對話、進`stuck`、通知使用者一次；有效模型回應才清零；明確恢復才重開 | **先做** |
| **整格執行保險** | 初值 **300000ms**，可按行程覆寫；另留清理寬限 | 外部run／exec量與清理；kernel記`step_timeout`並停排，**第一版不自動重跑被中斷的act** | **與run／kernel落地一起做**；group清理和停排是完成條件 |
| **人工pause／一般waits** | **沒有預設期限** | 保留「等continue可以永遠等」；不把所有等待一律300秒失敗 | **先不做通用強制期限** |
| **有owner的非同步工作** | 由工作owner建立有限期限與終態結果 | 成功／timeout／取消都產生可收取結果；waits只等結果到。owner死掉須有監督者結算 | **隨LLM CPU／async工作一起做** |
| **LLM CPU queue** | 建議排隊 **300000ms**，可覆寫 | 未dispatch就到期→`queue_timeout`結果，不送模型 | **LLM CPU第一版就做** |
| **LLM CPU worker總時間** | 建議 **150000ms**，包住HTTP120秒及收尾 | owner終止本地worker、確認清理、寫唯一終態；不自動重送 | **LLM CPU第一版就做** |

300秒整格值有一個明確代價：**它是資源上限，不保證任意數量的60秒工具都能跑完。**若模型一次給很多calls，可能碰到整格上限。若你要保證整批皆可跑到各自期限，就要改成依call數計算整格預算，或改成跨格逐工具執行；那是另一個狀態機決策。

我會先不做：

- 通用inst新增timeout。
- 每條waits都自動套預設期限。
- 被硬砍的act自動重放。
- LLM CPU與agent各自重試。
- 用等待格數當秒數。
- 用「多久沒有任務進展」自動判失敗；那需要業務進度定義，不能從PID或tick數推定。

工具輸出容量也不應誤以為已被上述timeout解决；可以另定上限，但不和本次時間預算混成一個欄位。

**「一個關卡一個地方」具體落實**

| 判斷／動作 | 唯一責任位置 | 不該重複做的地方 |
|---|---|---|
| 每工具願意等多久 | 工具執行政策，由agent讀取 | 不在工具腳本再包相同60秒timeout |
| 每工具怎麼終止 | 共用exec機制 | agent不要另寫一份TERM／KILL流程 |
| 整格是否超時 | run／exec外部監督 | kernel不要再用另一個同值timer競賽 |
| 超時後是否繼續排程 | kernel政策 | daemon自癒不能無條件把已停排工作復活 |
| 引擎失敗是否再試 | agent | HTTP client、LLM CPU不再各自乘一層重試次數 |
| queue是否過期、worker是否超時 | LLM CPU | agent不要另用600格去猜同一請求的期限 |
| 等某個檔的意義是否過期 | 建立該等待的流程 | generic kernel不能把101次數當放棄依據 |
| 終態結果與取消 | 擁有該工作的owner | `.done`、停止等待、CLI退1不能各自冒充取消成功 |

每工具上限與整格上限可以並存，因為保護不同範圍；HTTP socket timeout與worker總期限也可以並存。要避免的是**同一範圍、同一語意，被兩層各自計時、重試或結帳**。

**5．要你拍板的問題**

| 問題 | 選項與一句話利弊 | 我的建議 |
|---|---|---|
| **1．工具預算放哪？** | **A `_timeout_ms`工具私有欄位**：保留純inst，但多一個欄位；**B `_meta.timeout_ms`**：放一起方便，但須承認_meta多了agent專屬語意；**C 通用inst欄位**：所有執行者共用，但推翻目前分層 | **A** |
| **2．工具預設等多久？** | **A 60秒可覆寫**：沿用4-7經驗，慢工具須明示；**B 120秒**：較少誤殺，但卡住佔用較久；**C 不限**：最相容，但目前問題保留 | **A** |
| **3．整格硬上限由誰管？** | **A run／exec外部監督、kernel定政策**：能抓agent自身卡住；**B kernel每tick查elapsed並砍**：集中管理，但受tick延遲與kernel自身卡住影響；**C agent自己量**：改動少，但不能當任意阻塞的硬保證 | **A** |
| **4．整格上限怎麼定？** | **A 固定300秒可覆寫**：簡單、資源有界，很多calls可能被截斷；**B 按HTTP／call數計算**：較少誤殺，需額外預算協議；**C 只限局部操作**：最省，但整格其他卡點無保護 | 第一版 **A** |
| **5．整格被砍後怎麼辦？** | **A 停排、保留state、待處理**：避免盲目重複副作用，但需要人；**B 自動恢复**：不中斷工作，但先做逐call記錄與未知結果處置；**C 原state直接再跑**：最省，可能重複執行工具 | **A**；要B再做恢復協議 |
| **6．引擎失敗幾次停？** | **A 總共3次、至少隔5秒、有效成功清零**：簡單且有界；**B 沿用5次**：較耐暫時故障、等待與成本較高；**C 一直試**：自動恢復機會大，但沒有上限 | **A**，並新增明確stuck |
| **7．stuck怎麼恢復？** | **A 明確continue／恢復操作**：不會被無關輸入重置限制；**B 新input就恢復**：沿用proto2互動習慣，但自動事件可能反覆喚醒；**C 定時自動恢復**：免人工，但等於另開一層長期重試 | **A** |
| **8．waits期限這輪做多少？** | **A 一般waits仍無限，工作owner保證有限終態**：最小改動；**B 加可選until，過期記失敗**：能處理沒owner的等檔，但要定事件與門的互動；**C 所有waits預設期限**：統一有界，但人工pause也會自動失效 | 先 **A**；需要任意等檔期限再做B |
| **9．若做until，過期開門嗎？** | **A 假裝已到**：最省但容易誤導；**B 該條失敗移除、保留其他等待**：語意準確，但未必立即喚醒；**C 整批等待失敗**：能立即重新安排，但須識別工作分組、保留pause | **B**；不要無聲假裝成功 |
| **10．LLM CPU如何分時間？** | **A queue300秒＋worker150秒，兩者分開**：容易定位排隊或执行问题；**B 提交起算單一總期限**：對使用者最直覺，但排隊會吃掉推論時間；**C queue不限、只限worker**：允許長排隊，但可能永遠等 | **A**；值允許覆寫 |
| **11．結果等待CLI逾時要撤嗎？** | **A 只停止等、保留ID**：方便稍後查結果；**B 明確選项要求取消**：意圖清楚，需取消回執；**C timeout一律取消**：直接，但可能取消本來只想稍後看的工作 | **A＋B**，不把「不等」默認成「取消」 |