# daemon／kernel：精簡總結與 proto5 該怎麼寫規範（2026-09-22）（精簡版）
完整版：[../notes/2026-09-22-daemon-kernel-summary.md](../notes/2026-09-22-daemon-kernel-summary.md)

astra 調查了 proto4-3 的 aos-run、daemon、kernel，以及 module、syscall、LLM module。這份保留 Claude 對 proto5 規範的整理與建議；六項取捨仍由使用者拍板。

## 結論：三層分工可以沿用，執行與收尾的漏洞要補

| 層 | 做什麼 | 家目錄與對外資料 |
|---|---|---|
| aos-run | 反覆呼叫執行器，每次重新讀指令。管單次逾時、間隔、整體期限、次數與停止條件。 | 沒有家目錄或持久狀態；每次啟動從第 1 次算起。用 status-fd 回報事件。 |
| aos-daemon | 管一批 aos-run，受理新增、移除、重啟、查詢、暫停與停止。 | `AOS_DAEMON_HOME`，預設 `~/.aos-daemon`；有 requests、requests/done、daemon.pid、state.json、daemon.log。 |
| aos-kernel | 決定哪個邏輯行程放到哪顆 CPU，依完成、等待、失敗與量子換人。 | kernel 家 `K/`；有 inst.json、config.json、state.json、procs、cpus、syscalls、kernel.log。 |

kernel 的一顆 CPU，其實是 daemon 管的一支 aos-run，反覆執行 `cpus/<n>.json`。排程就是更換該檔內容。kernel 只看退出碼，不知道 agent 正在等模型、工具或信件。

## 原型已經有哪些行為

| 主題 | 要保留的事實 |
|---|---|
| run 的節奏 | `--interval-ms` 預設 1 秒，從完成後算；`--timeout-ms` 限每次，`--time-limit-ms` 限整體；另有 `--max-runs`、`--stop-exit`、`--stop-on-error`。最後一項只對 `kind=aos` 生效。 |
| run 的事件與訊號 | status-fd 送 `ready`、`start #n`、`done #n exit=C kind=K`、`stop REASON`。第一次停止訊號讓這次跑完；第二次同種訊號才 KILL 子程式 group。 |
| daemon 請求 | `requests/<名>.json` 的 op 共八種：add、remove、restart、get、ls、pause、resume、stop。處理後刪原單，另寫同名 done，內容是原請求加 `ok`、`result`。 |
| daemon 狀態 | 每支 runner 的 entry 記 pid、target、args、state、ready、running、runs、last_exit、last_kind、last_line、alive 等。五態是 running、pause_pending、paused、stopping、restarting；state 的 running 與「本次執行中」的 running 布林是兩回事。 |
| daemon 收尾 | 先 TERM，等 5 秒，再 KILL aos-run group。 |
| kernel 每格 | 讀 daemon 狀態、補 CPU、處理 syscall、跑 module tick、驗 queue、排程、存 state。 |
| kernel 退出碼 | 預設 `done_exit=100` 表示完成，指令歸檔到 procs/done；`wait_exit=101` 表示等待，有人排隊就讓位。一般非零累計到 `bad_after=10`，歸到 procs/bad。 |
| kernel 量子 | `quantum=5` 是完成 5 次後可換人，不是 5 秒。 |
| syscall 與 module | syscall 投到 syscalls，同名回音在 syscalls/done，格式是 `{ok,msg}`。module 是 config 登記的 Python 檔，以 NAME、OPS 與 handle／tick／status／cli 四個 hook 接上；直接在 kernel 進程內呼叫。 |

## 會影響 proto5 的六個坑

| 問題 | 為什麼需要處理 |
|---|---|
| 同一行程可能重疊執行 | 換人只看完成次數，沒看 daemon 的 running。上一顆 CPU 的執行可能還沒完，換下的行程就被另一顆取走。agent 假設同一資料夾不會同時跑兩份，kernel 必須守住這點。 |
| 砍不乾淨 | daemon、aos-run、inst 子程式分開 session；daemon 最後 KILL 的是 runner 那組，工具等子孫可能留著。 |
| 崩潰後不對帳 | daemon 重啟從空表開始，不收養舊 runner；kernel 只看最新快照，runs 若跳 5，五次全算成最新碼。request 先刪再寫 done 有失單窗口；兩個 tick 同跑也沒鎖。 |
| 文件保證過強 | 主迴圈其實會 join；每 0.5 秒存 state 只是門檻；tick 有退出 1／2；行程早已能以 done_exit 結束。README 的 add 自動名是數字，跟後面的 rm 範例對不上。 |
| kernel 只吃 inst 子集 | add／queue 先要求原始 argv 是 list、argv[0] 與 cwd 是字串，擋住頂層 `$ref`、cwd 指示詞與 mkdir 選項；argv[0] 含斜線且不存在還會事先拒收。 |
| 沒有具名錯誤 | daemon／kernel 主要回中文訊息與退出碼 1／2，只有 inst 那層有穩定代號。 |

## Claude 建議規範怎麼拆

依使用者定的「格式一份、程式一份」整理：

| 規範 | 應寫進去的內容 |
|---|---|
| `spec/daemon-home.md` | 家目錄、request／response、八個 op、欄位、ok／result、entry 欄位與五態、daemon.pid。 |
| `spec/aos-daemon.md` | daemon 啟動與每輪工作、TERM→5 秒→KILL、崩潰後行為；ctl 各命令、等待多久及退出碼 0／1／2。 |
| `spec/kernel-home.md` | K 的各檔、config 八欄、state 的 cpus／queue／waiting；CPU 紀錄中的 pid、since、runs_at、seen_runs、waiting、wait_runs、bad_runs、bad_exit、aos_ticks；queued／running／waiting／done／bad／removed 六種去處；syscall 與 module 介面。 |
| `spec/aos-kernel.md` | init／boot／tick、add／rm／ls／module 命令、tick 的 12 步、退出碼判定次序、換檔與 CLI 退出碼。排程先判完成，再觀察結果、aos 連敗、bad、waiting 讓位、quantum。 |
| `spec/aos-run.md` | run 沒有家，不另拆格式檔；一份寫旗標、每格執行、退出碼、訊號與 status-fd 事件。 |

| 處置 | Claude 的建議與理由 |
|---|---|
| 沿用基礎 | 以 proto4-3 各家的長相、八個 op、五態、config 八欄、100／101／bad_after／quantum、同名 syscall 回音、module 四 hook、status 事件為整理基線；第一版最後留下哪些功能，仍依下面拍板。 |
| 防止重疊 | 換人前確認 daemon entry 不在 running；概念上維持一個行程只在一顆 CPU，並在 daemon 回報 done 後才換。 |
| 把行程砍到底 | 優先讓 aos-run 第一次 TERM 就轉送到正在跑的 child group；另一方案是 daemon 自己記 child pgid。 |
| 降低失單與撞名 | daemon 改成先寫 done、再刪原 request；檔名加隨機尾巴，避開同毫秒、同 pid 撞名。 |
| 接完整 inst | add／queue 用 `aos_inst.load()` 解完再驗，避免合法 proto5 指令被 raw 檢查擋掉。 |
| 統一錯誤 | 沿用 agent 的具名代號，例如 NotAHome、ReadFailed、JsonSyntax、FieldTypeMismatch，讓錯誤可辨識。 |
| 保留既有退件 | `.json` 不存在回 125 已在 proto5 exec 定了；kernel 的 `aos_ticks>=2` 退件照舊。 |
| 第一版先省 | pause／resume、restart、module 機制與 ls 欄寬先不做；agent 已有 waits，重啟能 rm＋add，LLM CPU 改普通行程後不需要 module。這是建議，尚待決定。 |

## 要使用者拍板的六題

| 題號與問題 | 選項 | Claude 建議與理由 |
|---|---|---|
| 1．module 機制要不要留？ | A：不留，LLM CPU／tool CPU 都是一個資料夾加 inst 的普通行程，由 kernel 排程。B：保留 4-3 module，在 kernel 內執行 hook。 | **A**。普通行程即可承載 CPU 工作；hook 留在 kernel 內會拖住 tick。 |
| 2．pause／resume／restart 要不要進第一版？ | A：先不要。B：三者都要。 | **A**。agent 有 waits 暫停；重啟可以先 rm 再 add，第一版不必另做整套控制。 |
| 3．daemon 與 kernel 要不要合併？ | A：維持兩支、各有自己的家；daemon 管 Linux 進程，kernel 管排程。B：合一，省一層檔案協議與 20 秒 ctl 等待。 | **A，沿用 4-3**。合併後 kernel 一崩，aos-run 就全沒人管；分工仍有用。 |
| 4．怎麼擋同一行程重疊？ | A：kernel 換人前看 daemon entry.running，還在跑就不換。B：每次執行加 invocation id，再由 agent 自己加鎖。 | **A**。在排程端守住「同一資料夾不會同時跑兩份」的 agent 前提。 |
| 5．怎麼把子程式砍到底？ | A：aos-run 第一次 TERM 就一起 TERM child group。B：daemon 記 child pgid，自己砍。 | **A**。runner 本來就持有正在執行的子程式；把目前要第二次訊號才動作的流程提前。 |
| 6．要不要具名錯誤代號？ | A：三支統一以 `aos-xxx: <代號>: <白話>` 寫 stderr。B：維持 4-3 只有白話。 | **A**。與 agent 一致，也補上 daemon／kernel 目前無法穩定辨識錯誤種類的缺口。 |
