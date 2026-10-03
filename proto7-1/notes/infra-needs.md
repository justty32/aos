# daemon／tick 需求清單（探針＋astra-4）

← [proto7-1](../README.md)｜探針：[probes/](../probes/README.md)｜astra-4 報告：[play/2026-10-03-astra-4-infra.md](play/2026-10-03-astra-4-infra.md)｜核心 spec：[core.md](../../proto7/spec/core.md)

這份清單只看 daemon／tick（含 tock、aos7-run、掛載、daemon 控制檔）**為了撐住各種 kernel／agent 還缺什麼**。來源有兩個：一是 12 個發散探針（`probes/<名字>`，探針自己的編號寫成「探針名 N?」），二是 astra 第四輪基礎設施試驗（`astra-4 R?／I-?`）。兩邊講的是同一件事的，併成一條。

**怎麼讀**

- 編號 `N-01`～：本檔統一編號。之後還有來源要併進來，就接著編號往下加，並在「來源」欄列上去。
- 優先：**必要**＝不補就做不了某一類 kernel／agent，或會默默丟資料。**應該**＝做得到，但很彆扭或有坑。**可以**＝有更好。astra-4 標了優先度的，兩邊取較高的。
- 核心：對應的 S- 條號。核心「不在核心」那節列的，寫「之後再說」。核心完全沒提的，寫「沒有」。
- 現況：**已做**／**部分**／**沒做**。這輪（10-03）改的會寫「本輪」，細節在 [spec.md](../spec.md)，測試在 `tests/test_infra.py`。
- 決定：**Q?**＝要使用者決定，見文末。「已答 D-?」＝使用者答過「照現在」，這裡只補代價，不再問。「技術選型」＝這輪自己取最簡單的做法，不問。

## 必要級一覽

| 編號 | 需求 | 現況 |
|---|---|---|
| N-18 | 舊動作不能倒寫新 daemon 的回合 | 已做（本輪） |
| N-19 | 請求不能無痕消失 | 部分（spawn 已修；沒有統一的請求 id） |
| N-20 | 回合關閉可恢復、不重複 | 已做（本輪） |
| N-21 | 一個任務或設定壞掉，不連坐、修好能恢復 | 已做（本輪） |
| N-22 | 一般 I/O 失敗走受控路徑 | 部分（不退出、有記錄；沒有降級策略） |
| N-09 | 回條與停機說清涵蓋範圍 | 部分 |
| N-12 | 狀態檔有世代、版本、能表達 unknown | 部分（有 gen；沒有 snapshot 序號、沒有 unknown） |
| N-54 | tick／tock 要有逾時，卡住不拖住停機 | 已做 |
| N-17 | 負載下控制面仍可用 | 部分（冷啟動已修；容量沒管） |
| N-25 | 任務資源歸屬不靠任務能刪的目錄與主 PID | **已答 Q1 (a)**：照現在，spec 寫明 kill 只保證收到哪些 |
| N-40 | 歷史任務資料夾的成本要有界 | **已做**（Q3 (a)：tock 搬到 tasks-old/） |
| N-45 | 跨 daemon 的控制端點要能照文件配置 | 部分 |
| N-47 | 路一子根要有標記，父才不會搶 | 已做（本輪） |

## A. 回合與時間

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-01 | 外部或任務要能叫某條時間線「現在就開下一回合」 | event N1 | interval 2000 ms 時，靠 tick-tock 的延遲 p50 955 ms、最慢 1907 ms；改 interval、rescan、pause＋resume 都催不動；唯一催得動的是讓 node 消失再出現（66 ms），但會留下沒 tock 的回合 | 應該 | S-08；tock 何時進場屬之後再說 | **已做**（本輪）：daemon ctl `wake`，只縮短 idle 的等待，回合中照舊 | 技術選型（選 event 的選項 a；回合中途直接 tock 的 b 沒做） |
| N-02 | 改了 interval，要看得到實際生效的值，也要能叫它馬上重算 | selfmod 10；astra I-08、R14 | 1500 ms 回合中途改成 50 ms，要約 1.3 秒才生效；status 看不到實際值 | 應該 | S-08 | **部分**（本輪）：status 加 `interval_ms`；`wake` 讓新值馬上生效；沒有 config revision | 技術選型 |
| N-03 | 任務要看得出這次 tock 是不是提前進場（本回合起的都結束了） | swarm N2 | 40 個 map、interval 150 ms，只有 1～3/5 回合提前；`early` 原本只寫在 daemon log | 應該 | S-09 | **已做**（本輪）：tock.json 與 rounds.jsonl 加 `early` | 技術選型 |
| N-04 | 「每回合必須回報」的任務要有回應 tock 的管道，基礎設施要知道誰回報了 | longrun N-1 | 51 回合裡，輪詢 150 ms 的漏 17 回合（33%），做事 150 ms 的漏 19 回合（37%）；rounds.jsonl 只有 alive／ended | 應該 | 之後再說（訊息交流） | **沒做** | 已答 D-2（照現在），這裡只記代價 |
| N-05 | 任務漏看的回合要補得回來 | longrun N-2 | tock.json 是覆寫的；任務看得出跳號，但看不到中間發生什麼 | 可以 | S-11 | **已做**（spec 寫明：漏掉的回合看 node 的 rounds.jsonl） | 技術選型 |
| N-06 | 讓某條時間線「只跑 N 回合就停」 | sched N2 | kernel 自己補 pause：naive 有 1/8～3/8 次多跑 1 回合；resume、pause 同一批寫會互相抵掉，變 0 回合 | 應該 | S-18 | **已做**（本輪）：`resume` 帶 `rounds: N` | 技術選型 |
| N-07 | 調度與牆鐘分開；遲到後有界地前進 | astra R9；longrun N-7 | 牆鐘 ±1h，實際間隔仍是 100 ms；別組同時跑時一次 tick→tock 約 1 秒 | 必要 | S-08 | **已做**（monotonic 等待）；沒有給人看的經過時間欄位 | — |

## B. 控制與狀態看得見

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-08 | pause 是「已要求」還是「已停住」要分得開 | sched N1；astra R7 | 回條只表示改了 paused 清單；status 有 36 次是 paused:true 但還在跑；不等就換人，同時跑到 4 條（N=2） | 應該 | S-18 | **已做**（本輪）：status 加 `pause_pending` | 技術選型 |
| N-09 | 回條分清 accepted／applied；停機說清哪些收完了、哪些沒收完 | astra R7 | 三層停機後 1.4 秒還有 6 個活程序；父的 `live=[]` 被讀成整棵都收完了 | 必要 | S-01、S-17、S-18、S-21 | **部分**：回條有 ok／msg，本輪加 `queued_at`，spec 寫明「ok＝接受」；沒有 applied 階段，也沒有「剩下沒收完」的清單 | — |
| N-10 | 控制送錯對象要回失敗 | multid N4；sched N4 | pause 子 daemon 裡的 node 拿到 ok:true，但對方照跑（0.5 秒多跑 2～5 回合） | 應該 | 之後再說（跨 daemon 的 id） | **已做**（本輪）：落在子 daemon 根底下的回 `ok:false`；不存在的 node 照收，msg 加註 | 技術選型 |
| N-11 | daemon 是死是活，看檔案就判斷得出來 | multid N5 | kill -9 後 status.json 一字不變；看 `at` 停更要 0.5 秒，而且分不出死了還是卡住 | 應該 | S-01、S-06 | **部分**（本輪）：status 加 `poll_s`、`stopped`、`gen`；被強殺仍只能靠 `at` 停更 | 技術選型 |
| N-12 | 狀態檔要有世代、snapshot 序號、觀察範圍，並能表達 unknown | astra R18 | 只看檔案時，fork 留下的孫程序、自己刪掉 taskdir 的任務都答不出來 | 必要 | S-01 | **部分**（本輪加 `gen`）；沒有 snapshot 序號，也沒有 unknown／orphan 狀態 | — |
| N-13 | 錯誤要有一致的入口：哪個元件、哪個 node、哪個任務、哪個階段 | selfmod 6；astra R5、R18 | tasks.json 壞掉時 tick rc 0、毫無紀錄；`from_round` 寫成字串時整回合 rc 1 | 必要（併入 N-21） | S-01、S-06 | **已做**（本輪）：`tasks_error`；總結的 `errors`；`last_error.prog="timeline"`；log 的 `io-error` | 技術選型 |
| N-14 | 上層看得到下層 daemon 的狀態 | nest3 N8 | D0 的 status 對下層只有 `live:["d1-r1"]` | 可以 | S-20、S-21（daemon 核心不知道從屬） | **沒做**；建議交給工具（例如 `aos7-ctl tree`） | — |
| N-15 | node 一出生就停著 | sched N3 | 沒預先停的話，沒輪到的 4 條各多跑 2 回合 | 應該 | 之後再說（node 怎麼出生） | **部分**：可以先 pause 一個還不存在的 node（本輪 msg 有註明）；node+ 的 log 帶 `paused` | 技術選型 |
| N-16 | ctl-done／ 不要只增不減 | sched N7 | 2.6 秒累積 64 個檔 | 可以 | 沒有 | **沒做** | — |
| N-17 | 負載重時控制面仍然可用 | fleet N2；astra I-11、R8 | 150 條時間線時，啟動 12 秒沒寫 status、不處理 stop；200 條空 node 時第一份 status 晚 4～10 秒 | 必要 | S-06、S-18 | **部分**（本輪）：一圈最多起 20 條新時間線；容量與過載沒管（見 N-41） | 技術選型 |

## C. 中斷、重啟與恢復

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-18 | 換了 daemon 之後，舊的 tick／tock 不能倒寫新的回合 | astra I-01、R1 | 舊 tick／tock 停在 rename 前，新 daemon 跑到 r2 後放行，round.json 從 2 退回 1 | 必要 | S-03、S-06、S-08 | **已做**（本輪）：`.aosd/gen.json` 世代＋`AOS7_GEN`；tick／tock 整段拿 `.aos/action.lock`，拿到後比對世代，舊世代什麼都不寫 | 技術選型 |
| N-19 | 請求不能無痕消失：spawn、ctl、加掛都追得到去向 | astra I-02、R2；swarm N3 | tick 刪了 spawn 檔、還沒起任務就被 kill -9，工作沒了，零紀錄 | 必要 | S-01、S-06、S-10 | **部分**（本輪）：spawn 起完才刪（至少一次），birth.json 記 `spawn`；沒有統一的請求 id 與狀態 | 技術選型（選「至少一次」，不選「恰好一次」） |
| N-20 | 回合關閉中途被打斷，不能永久漏事件，也不能重複寫總結 | astra I-03、R3；nest3 N1 | 寫了 ended.json 但總結沒寫，該結束事件永遠不報；kill 子 daemon 時一半機率總結跳號或重複 | 必要 | S-08、S-11 | **已做**（本輪）：先寫總結再寫 ended.json；tick／tock 不理 SIGTERM（SIGKILL 保底）；回合已關就不再 tock | 技術選型 |
| N-21 | 一個任務壞掉不連坐同一條線；設定寫壞修好後能自己恢復 | astra I-05、I-06、R5；selfmod 6、7、bug 1～3 | birth 改成 `[1]` → 每次 tick rc 1；tock.json 被改成資料夾 → 整條線的 tock 全失敗；interval 寫 `"fast"`／null／1e309 → 時間線永久停，修檔＋rescan 也不恢復；keep 沒寫 name → 每回合起一份 | 必要 | S-05、S-06、S-11 | **已做**（本輪）：birth 讀不到時從 tid 推 name；tock 每個任務各自 try；interval 壞了用預設並記錯；時間線出例外後等 0.5 秒接著跑；壞的一項只跳過那項 | 技術選型 |
| N-22 | 一般 I/O 失敗走受控路徑 | astra I-07、R6 | `.aosd` 唯讀，或寫 status 時 ENOSPC，daemon 直接 exit 1，不收任務、不留紀錄 | 必要 | S-03、S-06 | **部分**（本輪）：主迴圈每一步出 OSError 都不退出，印 stderr、log 記 `io-error`、status 的 `io_errors` +1；沒有「停止接新工作／降級」的策略 | 技術選型 |
| N-23 | 啟動時有恢復清單：沒關的回合、失聯的 runner、留下的 tmp | astra R16 | runner 寫完 exit 的 tmp、還沒 rename 就被殺，tmp 裡有 23 但被判成 lost | 應該 | S-01、S-06 | **沒做** | — |
| N-54 | tick／tock 要有逾時；一條線卡住不能拖住停機 | 批次評估隊（[eval/2026-10-03-batch-tick.md](eval/2026-10-03-batch-tick.md)）順帶發現 | `run_prog` 沒有逾時：tick 卡在 I/O 時，那條線的 thread 永遠不回來，daemon 收到 SIGTERM 後 5 秒仍在，最後被 SIGKILL（rc −9） | 必要 | S-06 | **已做**：tick／tock 超過 `action_timeout_s`（預設 30 秒）就 SIGKILL，記錯並標 `incomplete`，下一回合照常；停機時正在跑的動作最多再等 3 秒。測試用「tasks.json 是沒人寫的 FIFO」重現 | 技術選型 |
| N-24 | 刪掉或搬走的 node 不能被建回來 | subtimeline 1；rename N9 | rm -rf 8 次有 6～8 次被 tock 或 aos7-run 建回 `.aos/round.json`；搬家落在 tick／tock 中途時，總結寫進鬼資料夾 | 應該 | S-06 | **已做**（本輪）：tick／tock 先看 timeline.json；aos7-run 經 fd 寫 exit.json | 技術選型 |

## D. 任務歸屬、kill 與收尾

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-25 | 任務的資源歸屬不依賴任務自己能刪的 taskdir 和主 PID；主程序結束、fork、setsid、taskdir 被刪之後都還盤點得到 | astra I-04、I-05、R4；polyglot N5 | 主程序結束後，孫程序 kill 回「already ended」、stop 後還活著；`setsid sleep` 收不到；任務刪掉自己的 taskdir，status 看不到它，keep 又起三份 | 必要 | S-03、S-06、S-10、S-17 | **已答**：kill 另外用 `/proc/*/environ` 找 `AOS7_TID`＋`AOS7_NODE` 相符的程序；已結束的任務被 kill 時也收殘留；spec 寫明只保證到這裡，故意脫離的任務自己負責 | 〔使用者 10-03〕選 (a) |
| N-26 | node 消失或搬家時，上面的活任務要有人收，或至少被看見 | subtimeline 2；rename N8 | rm -rf 後 sleeper 還活著，status 不列它，stop --kill 也收不到；搬家後任務的 `AOS7_TASK` 指舊路徑，從此收不到 tock | 應該 | 之後再說（node 怎麼消失） | **已做**：node 消失（含只刪 timeline.json、搬家）就 kill 上面的活任務；daemon 在記憶體記各 node 活任務的 pgid，另找 `AOS7_NODE` 相符的程序；結束碼經 fd 寫到新位置；新位置由 keep 重起（rename、subtimeline 探針已改驗這些） | 〔使用者 10-03〕選 (a) |
| N-27 | 多層停機要有總期限，不能每層各自 1 秒互相搶 | nest3 N2；astra R15 | 三層加上不理 SIGTERM 的任務：D1 一定被 -9，一半機率留下 2 個孤兒 | 應該 | S-06、S-21 | **沒做** | 技術選型（先不做；P-04） |
| N-28 | keep 任務要有正規的「別再起我」 | lifecycle N-5；swarm N6 | 29 回合裡，rc0、標記檔、自己 kill 各留 29 個資料夾；只有改 tasks.json 有效 | 應該 | 之後再說（任務表誰能改） | **沒做**；本輪提供 `aos7_fs.edit_json`，讓改 tasks.json 不會互相蓋掉 | 已答 D-3 |
| N-29 | crash loop 要有退避，或至少看得到連續失敗幾次 | lifecycle N-6 | 52 回合起 52 次、52 個資料夾；50 ms interval 下約每分鐘 19 MiB；寫壞的任務默默死了 31 回合都沒人發現 | 應該 | 沒有 | **部分**：ended 有 name、code、by_ctl，kernel 可以自己算；tick 沒有退避 | — |
| N-30 | ended 要說清是哪個任務、為什麼結束 | lifecycle N-4 | 只有 tid＋code；被 restart 收掉的 code 是 0，跟自己正常結束分不出來 | 應該 | 之後再說（失敗與結束碼） | **已做**（本輪）：ended 加 `name`、`by_ctl` | 技術選型 |
| N-31 | 能「照新的定義重起」 | selfmod 9 | 改了 argv 再 restart，新實例仍跑舊的 v1（restart 抄 birth.json） | 應該 | S-17 | **沒做** | — |
| N-32 | pause 時能搶佔正在跑的任務 | sched N5 | 低優先 pause 生效的那一刻，12 次裡 12 次都還有任務在跑 | 應該 | S-17、S-18 | **沒做** | 已答 D-4 |

## E. 任務表與 spawn

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-33 | tasks.json 要能安全地多人改 | selfmod 8；lifecycle N-5 | 兩個任務各改 100 次，沒鎖只剩 100 項；3 次有 2 次 lost update | 應該 | 之後再說 | **已做**（本輪）：約定 flock `<檔>.lock`，`aos7_fs.edit_json` | 技術選型（選 selfmod 的選項 a） |
| N-34 | 一批 spawn 要能一次交出去 | swarm N3 | 每寫一個 spawn 停 3 ms，3 批全被拆成兩回合 | 應該 | 沒有 | **已做**（本輪）：`{"batch": [...]}` | 技術選型 |
| N-35 | 條件起（有檔才起）、只起一次 | swarm N6 | each 沒事件時每回合也起一個 Python | 可以 | 沒有 | **沒做** | — |
| N-36 | each 任務要能設並行上限 | longrun N-3 | 跑 1 秒的 each 任務在 100 ms 回合下堆到 7～8 個 | 應該 | 沒有 | **已做**（本輪）：`max_live` | 技術選型 |
| N-37 | 新 node 要有「準備好了」的規則 | subtimeline 4 | 先寫 timeline.json 再寫 tasks.json，有 1～8 個空回合 | 可以 | 之後再說 | **已做**（spec 寫明順序：tasks.json 先、timeline.json 最後） | 技術選型 |
| N-38 | daemon 要記得 node 的歷史（同名重建時分得開） | subtimeline 12 | rm -rf 後同名重建，回合從 1 重數，log 裡分不出是兩段 | 可以 | S-14 | **沒做** | — |
| N-39 | tid 不能被誤讀成名字 | swarm N7 | `a/b` 和 `a_b` 都變成 `a_b-r1…` | 可以 | 沒有 | **已做**（spec 寫明要看 birth.json） | — |

## F. 規模與成本

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-40 | 歷史任務資料夾不能讓 tick／tock／status 越跑越慢 | swarm N4；fleet N3；astra R12；lifecycle N-6 | 4000 個舊資料夾：tick 4→56 ms，tock 3→46 ms，daemon CPU 10%→52%；一個短命任務約 16 KB | 必要 | 沒有（P-12 原列默認正常） | **已做**：status 的 live 每 0.25 秒才重算；tock 把結束超過 `keep_ended_rounds`（預設 20）回合的搬到 `.aos/tasks-old/`。swarm：4000 個舊資料夾時 tick 53～70→4～5 ms、tock 63～86→3 ms、回合週期 164～206→100 ms；搬的那一次 tock 85～110 ms | 〔使用者 10-03〕選 (a) |
| N-41 | 每回合兩個 Python 程序的成本要有對策 | fleet N1；astra R11、R17 | 150 條時間線約吃 12 核，回合只跑到該有的 45%；astra 10→200 條，每條完成的回合數 123→11（中位） | 應該 | S-04、S-12 | **已答**：接受，容量寫清楚（約每秒 100～150 回合，見文末） | 已答（10-03） |
| N-42 | 每個任務的 aos7-run 包裝太重 | fleet N4 | 一個 14 MB；75 個 keep 任務約 1 GB | 可以 | 沒有 | **沒做** | — |
| N-43 | tick 起大量任務很慢，吃掉 interval | swarm N5 | 起 52 個任務 133 ms | 可以 | S-09 | **沒做** | — |
| N-44 | CPU、程序數、輸出空間能設上限 | astra R13 | 8 MiB 輸出、單核忙迴圈，基礎設施都不管 | 應該 | S-17（上層定策略） | **沒做** | — |

## G. 掛載、跨 daemon、非 Python 任務

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-45 | 跨 daemon 的控制端點要能照文件配置（匯入或 re-export），仍然走掛載 | astra I-09、R10；multid N7 | 空間外的 daemon：宣告與加掛都被拒，只能用絕對路徑硬寫，寫入紀錄看不見；反向掛父的 `.aosd` 被拒，要把實體目錄 re-export 進去才成 | 必要 | S-07、S-21、S-23 | **部分**：空間內的符號連結掛得上，拒絕會說明理由；沒有照做的流程 | — |
| N-46 | 路二要能把 daemon 起回來；daemon 的身分不跟著路徑變 | multid N6 | 只能走路一起；起回來後 `status.root` 變成掛載點路徑 | 應該 | S-21 | **沒做** | — |
| N-47 | 路一的子根要有標記，父 daemon 才不會先把它當 node 搶走 | nest3 N3 | 沒先建 `.aosd/` 時，三層悄悄塌成兩層，D2 起在錯的位置 | 必要 | S-15、S-21 | **已做**（本輪）：tasks.json 項目加 `subroot`，tick 先建 `<subroot>/.aosd/` | 技術選型 |
| N-48 | 掛載目標消失後重掛，不能默默建出鬼資料夾 | rename N10 | restart 後照舊宣告重掛 `a/inbox`，信「寄成功」但進了沒人看的資料夾 | 應該 | S-23 | **沒做** | — |
| N-49 | 寫入紀錄要分得出 `.aos/` 裡哪些是基礎設施的檔；看得到空間外的寫入；不混進 aos7-run 自己的寫入 | selfmod 5；multid N7；polyglot N7 | 任務把 round.json 撥到 1000、偽造別人的 exit.json，全記 ok；每個任務混進約 9 筆 aos7-run 的寫入 | 應該 | S-10 | **部分**（本輪）：aos7-run 不再載入 audit；前兩項沒做 | — |
| N-50 | 父要管自己 node 裡的子時間線 | subtimeline 11 | 父直接寫子的 tasks.json：記 ok:false 但照樣生效；判不判違規看寫的順序 | 可以 | S-15 | **沒做**（照 M-5） | — |
| N-51 | 非 Python 任務要能等 tock、讀欄位 | polyglot N6 | sh 每 20 ms 輪詢，花 7～9% 一核；靠 sed 抓排版讀 JSON | 應該 | S-01、S-11 | **已做**（本輪）：`aos7-wait-tock` | 技術選型 |
| N-52 | 原子寫的暫存檔不能被別人當成正式檔讀到 | polyglot N11 | 讀到 `x.json.tmp.1383587` | 可以 | S-01 | **已做**（本輪）：暫存名以 `.` 開頭 | 技術選型 |
| N-53 | inst 任務的輸出預設不要丟掉 | polyglot N12 | inst 任務的 out.log 是 0 bytes | 可以 | S-12 | **沒做** | — |

## 要使用者決定

原本留了四條（Q1～Q4），使用者 10-03 全部答了；下面保留題目與答覆。其餘照使用者 10-03 說的「普通的直接做」，取最簡單的做法，記成技術選型。

### Q1 daemon 要不要擁有任務的所有子孫程序？（N-25，astra R4）〔使用者 10-03〕選 (a)

> 照現在，不做 subreaper／cgroup。spec.md 第 6 節寫明 kill／stop 只保證收到：程序群組、活著的後代、環境變數 `AOS7_TID`＋`AOS7_NODE` 相符的。故意脫離（setsid、雙 fork、改環境變數、刪 taskdir）的由任務自己負責。

- **發生了什麼**
  - 任務的主程序結束了，它 fork 出來的孫程序還活著。kill 回「already ended」，daemon stop 之後孫程序照樣活（astra I-04；同一個程序群組也一樣）。
  - 用 `setsid` 或雙 fork 脫離的子程序，kill 收不到（polyglot：`sleep 303` 一直活著）。
  - 任務刪掉自己的 taskdir：status 看不到它，keep 再起三份，stop 全部漏掉（astra I-05 deletekeep）。
  - 三層巢狀時，四個不理 SIGTERM 的任務就讓中間層被 -9，父停下 1.4 秒後還有 6 個活程序。
- **本輪先做的**：kill 時另外掃 `/proc/*/environ`，找環境變數 `AOS7_TID`、`AOS7_NODE` 都相符的程序一起收。已結束的任務被 kill 時，也照這個方法收殘留。任務改了自己的環境變數、或刪了 taskdir 時，仍然收不到。
- **要決定的**：「任務」在資源上的邊界在哪？（不代替你選）
  - (a) 照現在：程序群組＋活著的後代＋環境變數相符的。故意脫離（改環境變數、刪 taskdir）的算任務自己負責，spec 寫明「kill 只保證收到這些」。
  - (b) aos7-run 用 `PR_SET_CHILD_SUBREAPER` 收養所有子孫，主程序結束後先收完子孫才寫 exit.json；daemon 另在 `.aosd/` 記一份獨立的任務清冊（不怕 taskdir 被刪）。只靠 Linux 的程序機制，不碰 cgroup。
  - (c) 每個任務一個 cgroup，用 `cgroup.kill` 整棵收掉。最徹底，但這會把 cgroup 拉回 daemon 裡，跟你先前「cgroup／帳號／權限拉出 daemon」的方向相反。

### （已答）每個動作一個程序太貴（N-41，astra R11）

> **〔使用者 10-03〕慢就慢，沒關係**：容量寫清楚就好，不為速度改架構；C 或其他語言改寫之後再說。「一個 tick 程序一次處理好幾條時間線」使用者直覺不妥，另派一隊評估，這邊不做。拿掉 aos7-run 包裝、改成每 node 常駐 runner 這類是技術選型，可以自己定，但 node 的定義（tick 所服務的資料夾）不能變。

**容量（這台機器：AMD Ryzen 7 9800X3D，16 邏輯 CPU，Python 3.14）**：

| 情境 | 全 daemon 每秒回合數 |
|---|---|
| 每回合起三個很短的任務（astra-4，50～200 條時間線） | 約 **110**（10 條時約 80） |
| 一半 keep、一半一個 `true`（fleet，150 條） | 約 **270**（每秒約 544 個 tick／tock 程序） |

- 一般估法：這台機器**約每秒 100～150 回合**，到了就會遲到。
- 遲到時每條線一起變慢，不會丟回合（S-08 不準時無妨）。
- 要更多就分到多個 daemon。

### Q3 歷史任務資料夾要不要由基礎設施清掉？（N-40，astra R12）〔使用者 10-03〕選 (a)

> tock 把 ended.json 寫了超過 `keep_ended_rounds` 回合（timeline.json 可設，預設 20）的資料夾搬到 `.aos/tasks-old/`，tick、tock、status 只掃 `.aos/tasks/`。kernel 接前任狀態、kernel 算用量總和、agent 接前任 state.json 都改成兩處都找。swarm 前後的數字見 N-40。

- **發生了什麼**
  - 任務資料夾只增不減。tick、tock、status 每次都全掃。
  - 4000 個舊資料夾時，tick 56 ms、tock 46 ms，daemon CPU 52%。
  - 群體型（每回合 52 個）約 25 秒就到 4000 個。crash loop 約每分鐘 19 MiB。
  - 本輪只把 status 的重算改成每 0.25 秒一次，治標。
- **為什麼要問你**：kernel 接前任的狀態（`restart_of`）、kernel 看任務、tock 判斷「新結束」，都靠「任務資料夾一直在」。清掉會改它們看到的東西。
- **選項**：（不代替你選）
  - (a) tock 把「已寫 ended.json 超過 N 回合」的資料夾搬到 `.aos/tasks-old/`，平常只掃 `.aos/tasks/`。kernel 要看歷史就去 tasks-old 找。
  - (b) 加一個控制（例如 `ctl.json {"op": "archive"}`，或 daemon ctl `gc`），由 kernel 或人決定清哪些；基礎設施自己不清。
  - (c) 不清，只加一份活任務索引（`.aos/live.json`，tick／tock 維護），tick／tock／status 只看它。磁碟仍然一直長。

### Q4 node 消失或搬家時，上面還活著的任務怎麼辦？（N-26）〔使用者 10-03〕選 (a)

> daemon 看到 node 消失（資料夾或 timeline.json 不見）就 kill 上面的活任務。搬家等於舊任務全死，新位置由 keep 重起。daemon 在記憶體記著各 node 活任務的 pgid（跟 status 的 live 一起每 0.25 秒更新），再加上找環境變數 `AOS7_NODE` 相符的程序，所以 rm -rf 之後也收得到。

- **發生了什麼**
  - 子時間線被 rm -rf 之後，活任務繼續跑。status 不列它，daemon stop --kill 也收不到（subtimeline）。
  - 搬家改名之後，活任務的 `AOS7_TASK`／`AOS7_NODE` 還指著舊路徑，從此收不到 tock，永遠卡住；keep 也不會起新的（rename）。
  - 只刪 timeline.json，等於「不經 pause 的暫停」：任務留著，但收不到 tock。
  - 本輪做了：結束碼跟著資料夾走；被刪的 node 不會被建回來。
- **為什麼要問你**：「node 怎麼出生與消失」是核心列為之後再說的事。
- **選項**：（不代替你選）
  - (a) daemon 發現 node 消失（`node-`）時，kill 那個 node 上的活任務。搬家＝舊任務全死，新 id 由 keep 重起。rm -rf 時 pid.json 已經沒了，要 daemon 平常就記著 pid。
  - (b) 不殺，只在 log 記 `orphan`（列 pid），讓人或 kernel 處理。
  - (c) 規定「node 搬家或刪除前要先 pause 或停 daemon」，不支援熱搬，出事是使用者的。

## 答完 Q1、Q3、Q4 之後冒出來的（技術選型，先這樣）

- **kernel 算用量總和也要掃 tasks-old/**，因為總額上限 `cap_tokens` 要算進已結束的任務。所以 kernel 的成本仍會隨歷史長大，只是轉到 kernel 自己身上。之後若有需要，可以讓 kernel 自己累計，或由 tock 在搬走時把用量加總進一份檔。
- **「暫停但保留任務」只剩 pause 一條路**：只刪 timeline.json 現在等於 node 消失，上面的任務會被 kill。event 探針的「把 timeline.json 改名讓 node 消失再出現」催回合 hack，現在會連任務一起殺掉；改用 `wake`。
- **node 被判消失的依據是一次掃描沒看到 timeline.json**：網路檔案系統或掛載斷一下，任務就會被 kill。本機資料夾不會碰到，先不處理。
- **node 消失時的 kill 在背景做**：daemon stop 時最多等這些背景工作 5 秒。

## 這輪改了什麼（摘要）

- **daemon**
  - 世代：`gen.json`、`AOS7_GEN`。
  - 新 op：`wake`；`resume` 可帶 `rounds`。
  - pause 子 daemon 的 node 會拒絕；回條加 `queued_at`。
  - status 加 `gen`、`io_errors`、`poll_s`、`stopped`、`interval_ms`、`pause_pending`、`steps_left`；live 每 0.25 秒才重算。
  - 一圈最多起 20 條新時間線。
  - 主迴圈出 OSError 不退出；時間線出例外後會接著跑；interval 寫壞用預設值。
  - tock 帶 `AOS7_EARLY`。
- **tick**
  - 拿 `action.lock` 並比對世代。
  - node 不在就不寫。
  - 壞的一項只跳過那項，並記 `tasks_error`。
  - keep 沒寫 name 的 bug 修了。
  - 新欄位 `max_live`、`subroot`；spawn 可以是 `batch`，起完才刪，birth 記 `spawn`。
  - 不理 SIGTERM。
- **tock**
  - 拿鎖、比對世代；node 不在不寫；回合已關就不再寫。
  - 每個任務各自 try，錯的記在 `errors`。
  - 先寫總結再寫 ended.json。
  - ended 加 `name`、`by_ctl`；總結與 tock.json 加 `early`。
- **aos7-run**：經任務資料夾的 fd 寫 exit.json；audit 只給任務，不給自己。
- **kill**：收環境變數相符、已被收養的子孫；已結束的任務被 kill 也收殘留。
- **小工具**
  - `aos7-ctl daemon … wake`、`--rounds`。
  - 新的 `bin/aos7-wait-tock`。
  - `aos7_fs.edit_json`（flock）。
  - 暫存檔名以 `.` 開頭。
- **答完 Q1／Q3／Q4 之後**（使用者 10-03 都選 (a)）：
  - spec 寫明 kill 只保證收到哪些。
  - tock 把結束超過 `keep_ended_rounds` 回合的搬到 `tasks-old/`；kernel 接前任、算用量和 agent 接前任都兩處都找；tid 不撞號。
  - daemon 看到 node 消失就 kill 上面的活任務（`node-gone-kill`）。
  - rename、subtimeline、selfmod、swarm 探針改成驗新行為；probelib 預設不搬（`keep_ended_rounds` 很大），swarm 的 D 段量搬之後的數字。
- **動作逾時**（N-54，批次評估隊發現）：tick／tock 超過 `action_timeout_s` 就 SIGKILL，回合標 `incomplete`；停機時最多再等 3 秒。
- **astra-4 的 I-**
  - 修了：I-01、I-02、I-03、I-05、I-06、I-07。
  - 順手做了最簡單版：I-04（kill 已結束的任務時收殘留）、I-08（status 的 `interval_ms`、`wake`）、I-11（一圈最多起 20 條）。
  - 只記錄：I-09，見 N-45。
