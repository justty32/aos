# daemon／kernel 調查報告（2026-09-22）（精簡版）
完整版：[../notes/2026-09-22-investigations/2026-09-22-daemon-kernel-report-astra.md](../notes/2026-09-22-investigations/2026-09-22-daemon-kernel-report-astra.md)

本報告記錄 2026-09-22 工作樹中的實作。astra 逐支讀程式與測試，另用記憶體 JSON、mock 讀檔核對部分解析差異；沒有啟動 daemon、worker 或執行會建立檔案的測試。下述重疊執行與子孫清理風險是程式流程推導，未動態重現。

**結論：run 負責反覆執行，daemon 管 runner，kernel 靠換指令檔排程。三層已有可用協議，但沒有完整事件歷史、跨檔交易、崩潰復原或同一行程不重疊的保證。** 下列型別是正常寫出的形狀，不代表讀取端都有完整驗證。

## 最重要的事實：aos-run

| 編號 | 事實 | 使用時的意思 |
|---|---|---|
| 1 | run 沒有家目錄、state 或持久計數，每次啟動從 1 算。每次重新辨識 target、讀 inst。 | target 必填；普通檔、JSON、資料夾都能交執行器。資料夾預設讀 `.aos/inst.json`；JSON／資料夾後面不能加 `--` 參數。 |
| 2 | interval 預設 1000ms，第一次立即跑；預設從完成後算，`--from-start` 改從本次開始算。 | 趕不上不補格，下一次直接跑。max-runs=0、timeout-ms=0、time-limit-ms=0 都表示不限；失敗嘗試也計一次。 |
| 3 | 整體期限會縮短本次 subprocess timeout；剩不到 1ms 不開新一輪。 | 不涵蓋全部讀檔、解析與清理時間，TERM 後還可能等 2 秒才 KILL，不能當絕對截止。 |
| 4 | 執行結果分 child、aos、usage。aos 的 library code 1 轉成 125；usage 通常 2；child 保留子程式碼，也用 126／127 表示啟動失敗、128＋訊號表示被殺。 | `--stop-on-error` 只看 kind=aos；`--stop-exit 125` 則連 child 真退 125 都會停。100／101 對 run 沒有特殊意思。 |
| 5 | 停止優先序：訊號→stop-on-error→stop-exit→max-runs→整體期限。 | 正常停止 run 自己回 0；aos 錯誤停止回 125；用法錯回 2。子程式非零通常不會讓 loop 自動停。 |
| 6 | 第一次 TERM／INT 只要求這次跑完；同一訊號第二次才 KILL child group。TERM 一次加 INT 一次不算兩次同種。 | status 事件是 ready、start #n、done #n exit=C kind=K 耗時、stop REASON。寫 fd 失敗會忽略，沒有重送或落盤保證。 |

## 最重要的事實：daemon 與 ctl

| 編號 | 事實 | 使用時的意思 |
|---|---|---|
| 7 | 家目錄依序取非空 `--home`、AOS_DAEMON_HOME、`~/.aos-daemon`；不會 chdir，也不因 --home 自動設定環境變數。 | 家中有 requests、requests/done、daemon.pid、state.json、daemon.log。PID 只查 `/proc` 且非 zombie，不核對身分；沒有家目錄鎖。 |
| 8 | entry key 是 target 的 realpath；執行 target 則保留 abspath。add／restart 只收 `.json` 路徑，不收資料夾，但不要求檔已存在或 inst 合法。 | 同 key 不能再 add；同目錄不同 JSON 可各開 runner。更新檔案下次生效；symlink 改指向後，既有 key 不會跟著更新。 |
| 9 | 八個 op 是 add、remove、restart、get、ls、pause、resume、stop；CLI 的 rm 轉成 remove。 | 回應保留原請求並加 ok／result；壞輸入則回 req／ok／result。按檔名字典序處理，先刪原單，再寫 done，存在失單窗口；done 是受理回應，不是非同步動作已完成。 |
| 10 | state 頂層是 pid、home、runs；每筆含 pid、target、args、started_at、state、ready、running、runs、last_exit、last_kind、last_line、alive。 | runs 是最近 done 編號；start 不清上次退出碼。ready 是收到 ready 事件；running 是本次是否正在跑；alive 由 poll 判定，三者不同。 |
| 11 | 五態是 running、pause_pending、paused、stopping、restarting。pause 等 ready 且非 running 再 STOP runner PID。 | STOP 與下次 start 有競態，只停 runner 不停 child。resume 可取消 pending；restart 等舊 runner 退出再開新支，新 args 未提供就清空，不保留舊旗標。 |
| 12 | remove 先 CONT／TERM，5 秒後 KILL runner group；force 約 0.2 秒後再送第二次 TERM。daemon、runner、inst child 分屬不同 session。 | daemon KILL runner 不保證殺到 inst 子孫。force 若由 runner 收到第二發 TERM，才走 runner 主動 KILL child group 的路徑。 |
| 13 | 每輪是處理請求→推進狀態→reap，再等約 0.2 秒；週期存檔門檻 0.5 秒。reap 會對兩個 reader thread 各 join 最多 1 秒。 | 啟動從空 table 開始，不讀舊 state 收養 runner。崩潰可留孤兒、舊 pid／state、失單或重做；單檔 tmp＋replace 沒有 fsync、多 writer 鎖或跨檔交易。 |
| 14 | ctl 的 ls／get 直接讀快照；其他命令先確認 daemon 活著才投單。add／resume 等回音最多 10 秒；rm／restart／pause 之後另等到位最多 10 秒。 | add 成功不保證 ready、旗標合法或第一格成功；restart 到位不要求 ready。stop 不讀回音，只等原 PID 消失 10 秒。逾時不撤單。退出碼為成功 0、失敗 1、用法 2；沒有穩定具名錯誤。 |

## 最重要的事實：kernel

| 編號 | 事實 | 使用時的意思 |
|---|---|---|
| 15 | kernel CPU 是 daemon 管的 runner，反覆讀 `cpus/<n>.json`；邏輯 pid 是檔名，不是 Linux PID。 | 家有 inst、config、state、procs（含 done／bad）、cpus、syscalls（含 done）、kernel.log。主入口是獨立 init／boot／tick，以及 aos-kernel add／rm／ls／module 名。 |
| 16 | config 八欄：ncpu 必填；interval_ms=1000、timeout_ms=0、quantum=5、done_exit=100、wait_exit=101、bad_after=10、modules=[]。 | ncpu 不含 kernel 自己那支 runner。直接讀 config 比 init 驗證寬，bool／非法範圍可混入；每格重讀，但已存在 CPU 的 run flags 不更新，縮 ncpu 不會完整熱拔除。 |
| 17 | init 要求家不存在；boot 把 kernel 自己的 inst 掛進 daemon，不等首格完成；既有 entry 為 running／paused 就成功。 | add 把來源 cwd 正規化成絕對路徑，要求已存在；argv[0] 含斜線也先驗路徑。自動名取活躍、done、bad 數字名最大值＋1；加檔後等下一 tick 才進 queue。 |
| 18 | state 頂層是 cpus、queue、waiting；每顆 CPU 記 pid、since、runs_at、seen_runs、waiting、wait_runs、bad_runs、bad_exit、aos_ticks。 | 沒有 invocation id 或完整退出歷史。行程可在 queue、CPU、等待、done、bad，或被移除。waiting 仍會排回 CPU，kernel 不監看它等的檔案。 |
| 19 | 一格順序：讀 state／daemon→補 idle 檔與缺 CPU→載 modules→逐張 syscall→module.tick→驗 procs→重建 FIFO／逐 CPU 排程→存 state／log。 | CPU key 在 daemon 表中就算本輪可用，不驗 alive、ready、state、running。新 add 成功的 CPU 當輪仍不排；每顆補 CPU 的 ctl subprocess 可等 20 秒。 |
| 20 | 保留仍存在的 queue，新檔按數字名數值、再非數字字典序排尾。idle 取隊首；有人排隊時，完成次數達 quantum 才輪替，waiting 跑過一次即可讓位。 | 換人先 hard-link 舊 CPU 檔回 procs，再 replace 新檔；等待計數跨換人保存，一般連敗與 aos_ticks 不保存。沒人排隊就繼續跑。 |
| 21 | 判定依序是完成→觀察新結果→aos 連敗退件→一般連敗退件→waiting 讓位→quantum。完成須 child＋done_exit 且本配置 ran≥2。 | done_exit=0 關閉完成；bad_after=0 只關一般非零退件。child 0／done／wait／125 清一般連敗；其他非零碼即使不同也累加。kind=aos 且 ran≥2，連看兩格就可退件，快照不變也會累加。 |
| 22 | kernel 只看最新退出碼與 runs 差額；一次跳 5 次就把五次全歸最新碼。runs 倒退才清計數，沒有比對 runner PID／世代。 | done 的 ran≥2 只是避舊回報，不代表精確歸屬，退出 100 後仍可能再跑。done／bad 歸檔後當輪不補下一人。 |
| 23 | swap、rm、done、bad 只換 CPU 檔，不等或中斷已開始的 child。 | 舊 invocation 沒完，行程可能被後面的另一顆 CPU 取走而重疊。多 tick 無鎖；state 壞掉不從 CPU 檔還原 pid；CPU 檔消失就補 idle，原行程不自動回來。 |
| 24 | 內建 syscall 是 `{op:"rm",pid:"名稱"}`，回音 `{ok,msg}`；按 CPU→procs→done／bad 找。 | CLI 固定等 `max(3秒,3×interval)`，讀完刪回音；逾時不撤單，之後仍可能刪行程。直接寫 syscall 的 pid 驗證比 CLI 寬，沒有禁止斜線。 |
| 25 | module 是 config 列的 Python 檔，NAME、OPS 加可選 handle／tick／status／cli；同 process 執行。 | 捕捉例外但不回滾副作用；重複 NAME／OPS 取第一個，內建 rm 優先。ls 只讀狀態，不推 tick；它找 daemon 家只看環境變數，沒有預設家 fallback。 |

## 最重要的事實：LLM 與 agent 如何接上

| 編號 | 事實 | 使用時的意思 |
|---|---|---|
| 26 | LLM module 用全部四 hook，家在 K/llm，不建立 inst。syscall 內嵌 request，回音只表示排單，模型結果另寫 results。 | syscall 先於 module.tick；首格家未建時，預先放的 LLM 單可能先失敗。worker 是跨 tick 存活的背景程序，不占普通 CPU 槽；daemon stop 沒有通用路徑收掉它。 |
| 27 | request 在 requests→running→done 移動，result 保留；endpoint 管模型、並行數與 timeout。請求必須有非空 messages，不准自帶 model，可選 endpoint、priority、timeout_ms、params、tools、tool_choice。 | 同名以 SHA-256 指紋比對，同內容視既有單、不同拒絕；指紋不補語意預設，省略與明寫預設可能不同。排序為 priority 高者先，再 mtime、檔名；error.retryable 只是標記，不會自動重試。 |
| 28 | result 有 ok、id、endpoint、model、model_requested、text、finish_reason、usage、ms、raw、error、指紋；worker 結果另有 notes，scheduler 自造錯誤可沒有。 | usage 記 prompt／completion／total／cached／reasoning。排程收結果、死 worker、timeout＋5000ms，再派工；worker 結果才走 usage append，排程器直接退件未必記帳。 |
| 29 | LLM CLI 新單都先等 syscall 回音，`--wait` 才另外等 result；不會推 tick。第一段逾時嘗試刪原單，第二段逾時不撤已送請求。 | 刪原單不是交易式取消。llm rm 直接收 worker、刪四處請求／結果，不經 syscall；保留 usage、log。 |
| 30 | agent 沒信／等 result 回 101；送 LLM 成功保存結果路徑後回 0；stop 回 100。一般模型錯誤自行記帳，設定資料錯誤才回 1。 | agent 自己最多等 600 次，並要求 bad_after=0；讀 result 的 ok／error、raw.choices[0].message。kernel 不需知道信箱、工具、messages 或 agent 四格。 |

## 文件跟程式對不上的十件要事

| 文件說法／容易誤讀處 | 真正行為及影響 |
|---|---|
| daemon 主迴圈不等人、state 每 0.5 秒更新 | 同步檔案工作與 reap join 都可能拖延；0.5 秒是存檔門檻，沒有最大陳舊時間保證。 |
| request 處理後搬到 done | 是先刪原單再另寫回音；崩潰可能有動作卻沒回音。 |
| daemon 五秒強殺就收乾淨 | KILL runner group 不涵蓋另一 session 的 inst group；exec 最後補 KILL 也可能因直接 child 已回收而取不到 pgid。 |
| run time-limit 是硬時限 | 實際只縮短 subprocess timeout，未涵蓋全部前置與清理。 |
| tick 一律回 0、行程不會自己結束 | tick 有非家 1、參數 2 及未捕捉例外；行程已有 done 與 bad 退件。 |
| add 範例用來源檔名接著 rm | 自動名稱是數字，須指定 --name 或使用回報名稱。 |
| queue 的 cwd 一定絕對；所有合法 inst 都能送 kernel | queue 只驗 raw 字串，接受相對 cwd，換到 cpus 後中心可能變。add／queue 先驗 raw，擋住頂層 ref、指示詞 argv／cwd、mkdir 選項。 |
| 連續失敗、原子換檔就是精確排程 | 最新快照無法還原中間碼；一般連敗換人會丟；rename 不保證 invocation 歸屬、不重疊或跨檔復原。 |
| proto4-3 與 proto5 inst 語意已完全相同 | 舊碼接受 metainfo:null、at:null；ref 不拆 #位置，外部 ref 不支援相對 at；fmt 位置少一層；cwd mkdir 在全部解析後才做。 |
| kind=aos／125 表示子程式根本沒跑 | child 完成後寫 exit 或 fsync 失敗也會轉 aos／125，因此不能推論沒有副作用。 |

## 要拍板的問題

原始調查報告**沒有另列待拍板題、選項或作者建議**；以上是現況與相容性事實。Claude 的六題取捨與建議完整列在同組 [summary 精簡版](2026-09-22-daemon-kernel-summary.md)，包括 module、首版控制功能、daemon／kernel 分合、重疊防護、子程式收尾及錯誤代號。
