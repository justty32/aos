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
| N-18 | 舊動作不能倒寫新 daemon 的回合 | 已做（本輪；astra-5 補重開後接管舊持鎖者，限 owner 身分可驗證；astra-6 補認不出時的說明） |
| N-19 | 請求不能無痕消失 | 部分（spawn、加掛已修；沒有統一的請求 id） |
| N-20 | 回合關閉可恢復、不重複 | 已做（本輪；astra-5 補同回合去重、逾時補 tock；astra-6 補半行總結） |
| N-21 | 一個任務或設定壞掉，不連坐、修好能恢復 | 已做（本輪；astra-5 補起任務／ctl 回條／加掛的單項隔離；astra-6 補 daemon 控制檔、reload 驗證） |
| N-22 | 一般 I/O 失敗走受控路徑 | 部分（不退出、有記錄；掃描看不到不當消失；沒有降級策略） |
| N-09 | 回條與停機說清涵蓋範圍 | 部分 |
| N-12 | 狀態檔有世代、版本、能表達 unknown | 部分（有 gen；掃描錯誤、用量讀不齊有 unknown；沒有 snapshot 序號） |
| N-54 | tick／tock 要有逾時，卡住不拖住停機 | 已做 |
| N-17 | 負載下控制面仍可用 | 部分（冷啟動、控制檔洪水、壞回條擋 stop 已修；容量沒管） |
| N-25 | 任務資源歸屬不靠任務能刪的目錄與主 PID | **已答 Q1 (a)**：照現在，spec 寫明 kill 只保證收到哪些 |
| N-40 | 歷史任務資料夾的成本要有界 | **已做**（Q3 (a)：tock 搬到 tasks-old/；搬移中的讀取 astra-5 已補） |
| N-45 | 跨 daemon 的控制端點要能照文件配置 | 部分 |
| N-47 | 路一子根要有標記，父才不會搶 | 已做（本輪；astra-5 補第一次掃描） |
| N-56 | 讀 JSON 遇到 FIFO 等非一般檔不能卡住 | 已做（第二波） |
| N-58 | 一個 node 的壞檔不能讓整個 daemon 退出 | 已做（第二波） |
| N-59 | 壞項目的檢查涵蓋 name／argv 型別，spawn 也適用，毒丸不留 | 已做（第二波） |
| N-55 | 起程序的測試／示範／探針先收程序、再刪空間 | 已做（astra-5；astra-6 補 atexit 的 group／grace） |
| N-63 | kill 不能被任務改過的 pid.json 導去打別人 | 已做（第二波） |
| N-77 | 服務驗得出請求是誰送的（可信執行身分，E-01；只在宣稱付費硬限制時必要） | 沒做，要使用者決定（ledger 探針） |

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
| N-09 | 回條分清 accepted／applied；停機說清哪些收完了、哪些沒收完 | astra R7 | 三層停機後 1.4 秒還有 6 個活程序；父的 `live=[]` 被讀成整棵都收完了 | 必要 | S-01、S-17、S-18、S-21 | **部分**：回條有 ok／msg，本輪加 `queued_at`，spec 寫明「ok＝接受」；沒有 applied 階段，也沒有「剩下沒收完」的清單；astra-5 F-01：stop 帶 kill 收完後 log `stop-sweep`（收到幾個群組、乾不乾淨）；astra-6 G-10：認不出身分的舊持鎖者在 status `last_error` 說明為何不能安全回收 | — |
| N-10 | 控制送錯對象要回失敗 | multid N4；sched N4 | pause 子 daemon 裡的 node 拿到 ok:true，但對方照跑（0.5 秒多跑 2～5 回合） | 應該 | 之後再說（跨 daemon 的 id） | **已做**（本輪）：落在子 daemon 根底下的回 `ok:false`；不存在的 node 照收，msg 加註 | 技術選型 |
| N-11 | daemon 是死是活，看檔案就判斷得出來 | multid N5 | kill -9 後 status.json 一字不變；看 `at` 停更要 0.5 秒，而且分不出死了還是卡住 | 應該 | S-01、S-06 | **部分**（本輪）：status 加 `poll_s`、`stopped`、`gen`；被強殺仍只能靠 `at` 停更 | 技術選型 |
| N-12 | 狀態檔要有世代、snapshot 序號、觀察範圍，並能表達 unknown | astra R18 | 只看檔案時，fork 留下的孫程序、自己刪掉 taskdir 的任務都答不出來 | 必要 | S-01 | **部分**（本輪加 `gen`）；沒有 snapshot 序號，也沒有 unknown／orphan 狀態；astra-5：掃描看不到記 `scan-error`（F-03）、用量讀不齊回 `usage_total: null`＋`unknown`（F-02）、round.json 標 `replayed`／`incomplete`（F-05）——unknown 有了最小的幾處，snapshot 序號仍沒有 | — |
| N-13 | 錯誤要有一致的入口：哪個元件、哪個 node、哪個任務、哪個階段 | selfmod 6；astra R5、R18 | tasks.json 壞掉時 tick rc 0、毫無紀錄；`from_round` 寫成字串時整回合 rc 1 | 必要（併入 N-21） | S-01、S-06 | **已做**（本輪）：`tasks_error`；總結的 `errors`；`last_error.prog="timeline"`；log 的 `io-error`；astra-5 F-06：起任務、任務 ctl 回條、加掛的單項錯誤也有入口（`tasks_error`、ctl 紀錄的 `err`、mounts 的 `receipt_error`） | 技術選型 |
| N-14 | 上層看得到下層 daemon 的狀態 | nest3 N8；llmteam（父看不到子 daemon 的 status，LLM 只能直接讀子根的 status.json） | D0 的 status 對下層只有 `live:["d1-r1"]` | 可以 | S-20、S-21（daemon 核心不知道從屬） | **沒做**；建議交給工具（例如 `aos7-ctl tree`） | — |
| N-15 | node 一出生就停著 | sched N3 | 沒預先停的話，沒輪到的 4 條各多跑 2 回合 | 應該 | 之後再說（node 怎麼出生） | **部分**：可以先 pause 一個還不存在的 node（本輪 msg 有註明）；node+ 的 log 帶 `paused` | 技術選型 |
| N-16 | ctl-done／ 不要只增不減 | sched N7 | 2.6 秒累積 64 個檔 | 可以 | 沒有 | **沒做**（astra-5 F-10 只做了每圈處理預算；一萬個 wake 仍留一萬個回條） | — |
| N-17 | 負載重時控制面仍然可用 | fleet N2；astra I-11、R8 | 150 條時間線時，啟動 12 秒沒寫 status、不處理 stop；200 條空 node 時第一份 status 晚 4～10 秒 | 必要 | S-06、S-18 | **部分**（本輪）：一圈最多起 20 條新時間線；容量與過載沒管（見 N-41）；astra-5 F-10：控制檔每圈最多 200 件／50 ms，其餘下一圈照檔名接著做，status 照常寫。I-11「首份 status 之後的公平性」沒動：新 node 已照檔名每圈起 20 條，200 空線首測 15 秒只 167 線完成過 tick 是負載問題，使用者已接受慢（N-41）；astra-6 G-01：daemon 控制檔逐件錯誤邊界，一件回條寫不進去搬到 `ctl-failed/`、不再擋住同圈的 stop（`test_astra6.G01`）。200 空線 stop 回條 8.4 秒的容量面沒動（N-41） | 技術選型 |

## C. 中斷、重啟與恢復

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-18 | 換了 daemon 之後，舊的 tick／tock 不能倒寫新的回合 | astra I-01、R1 | 舊 tick／tock 停在 rename 前，新 daemon 跑到 r2 後放行，round.json 從 2 退回 1 | 必要 | S-03、S-06、S-08 | **已做**（本輪）：`.aosd/gen.json` 世代＋`AOS7_GEN`；tick／tock 整段拿 `.aos/action.lock`，拿到後比對世代，舊世代什麼都不寫；astra-5 F-04：拿鎖後寫 `.aos/action.owner.json`（pid、gen、starttime），新 daemon 的動作等鎖逾時就 SIGKILL 舊世代且確定同一程序的持有者（不 unlink 鎖檔）；astra-6 G-10：有界接管**只限 owner 身分可驗證**；缺欄位、讀不到 starttime、對不上時照樣不殺，status `last_error`（`prog: "action-lock"`）與 log `stale-holder-unverified` 記原因與人工恢復方法 | 技術選型 |
| N-19 | 請求不能無痕消失：spawn、ctl、加掛都追得到去向 | astra I-02、R2；swarm N3 | tick 刪了 spawn 檔、還沒起任務就被 kill -9，工作沒了，零紀錄 | 必要 | S-01、S-06、S-10 | **部分**（本輪）：spawn 起完才刪（至少一次），birth.json 記 `spawn`；沒有統一的請求 id 與狀態；astra-5：加掛先寫回條再刪請求、回條寫不進去留請求、重做冪等（F-07）；spawn batch 壞項只跳過那項（F-06）；astra-6 G-01：daemon 控制檔回條寫不進去時原檔搬到 `.aosd/ctl-failed/`、log `ctl-error`、status `last_ctl_error`，追得到去向；仍沒有統一的請求 id | 技術選型（選「至少一次」，不選「恰好一次」） |
| N-20 | 回合關閉中途被打斷，不能永久漏事件，也不能重複寫總結 | astra I-03、R3；nest3 N1 | 寫了 ended.json 但總結沒寫，該結束事件永遠不報；kill 子 daemon 時一半機率總結跳號或重複 | 必要 | S-08、S-11 | **已做**（本輪）：先寫總結再寫 ended.json；tick／tock 不理 SIGTERM（SIGKILL 保底）；回合已關就不再 tock；astra-5 F-05：同回合已有總結就不寫第二行（只收尾、補 ended.json 限總結裡報過的、round.json 標 `replayed`／`incomplete`）；tock 逾時被殺時 daemon 立刻補一次；astra-6 G-08：append 中途只留半行時，`append_jsonl` 先補換行（半行留著），tock 寫完讀回確認本回合總結已提交才寫 ended／關回合，總結 `errors` 記 `phase: "rounds.jsonl"`（`test_astra6.G08`）。斷電、fsync 語意沒測 | 技術選型 |
| N-21 | 一個任務壞掉不連坐同一條線；設定寫壞修好後能自己恢復 | astra I-05、I-06、R5；selfmod 6、7、bug 1～3 | birth 改成 `[1]` → 每次 tick rc 1；tock.json 被改成資料夾 → 整條線的 tock 全失敗；interval 寫 `"fast"`／null／1e309 → 時間線永久停，修檔＋rescan 也不恢復；keep 沒寫 name → 每回合起一份 | 必要 | S-05、S-06、S-11 | **已做**（本輪）：birth 讀不到時從 tid 推 name；tock 每個任務各自 try；interval 壞了用預設並記錯；時間線出例外後等 0.5 秒接著跑；壞的一項只跳過那項；astra-5 F-06：起任務前整項驗完、start_task／run_all_ctl／serve_mounts 每項各自 try、batch 壞項只跳那項、`interval_ms` 先檢查範圍再 isfinite（10**309）、wait-tock 讀到非物件當沒有；astra-6：daemon 控制檔也逐件隔離（G-01）；reload 先過第 4 節完整檢查（G-05）。控制入口（任務 ctl、daemon ctl、加掛、spawn、reload）都已單項隔離 | 技術選型 |
| N-22 | 一般 I/O 失敗走受控路徑 | astra I-07、R6 | `.aosd` 唯讀，或寫 status 時 ENOSPC，daemon 直接 exit 1，不收任務、不留紀錄 | 必要 | S-03、S-06 | **部分**（本輪）：主迴圈每一步出 OSError 都不退出，印 stderr、log 記 `io-error`、status 的 `io_errors` +1；沒有「停止接新工作／降級」的策略；astra-5 F-03：掃描分「確定不存在（ENOENT／ENOTDIR）／看不到（其他 OSError）」，看不到不 kill、記 `scan-error`、`io_errors` +1、下一圈重掃；整體降級策略仍沒有；astra-6：daemon 控制檔逐件錯誤邊界（G-01）、半行總結修復（G-08）、daemon 綁 root fd，root 寫不進去／換掉就照 stop 收尾（G-03）；仍沒有降級策略 | 技術選型 |
| N-23 | 啟動時有恢復清單：沒關的回合、失聯的 runner、留下的 tmp | astra R16 | runner 寫完 exit 的 tmp、還沒 rename 就被殺，tmp 裡有 23 但被判成 lost | 應該 | S-01、S-06 | **沒做**（astra-5 補了兩項：重開後仍持鎖的舊 tick／tock 由等鎖逾時回收（F-04）；已 append 未 closed 的回合由 tock 去重收尾（F-05）。runner 寫了 tmp 沒 rename 的 exit 仍判 lost）；astra-6 補兩項診斷：半行 rounds.jsonl 由 tock 補換行後繼續（G-08）；認不出身分的舊持鎖者記 `stale-holder-unverified` 與恢復提示（G-10）。runner 的 tmp exit 仍判 lost | — |
| N-54 | tick／tock 要有逾時；一條線卡住不能拖住停機 | 批次評估隊（[eval/2026-10-03-batch-tick.md](eval/2026-10-03-batch-tick.md)）順帶發現 | `run_prog` 沒有逾時：tick 卡在 I/O 時，那條線的 thread 永遠不回來，daemon 收到 SIGTERM 後 5 秒仍在，最後被 SIGKILL（rc −9） | 必要 | S-06 | **已做**：tick／tock 超過 `action_timeout_s`（預設 30 秒）就 SIGKILL，記錯並標 `incomplete`，下一回合照常；停機時正在跑的動作最多再等 3 秒。測試用「tasks.json 是沒人寫的 FIFO」重現；重開後遺留的持鎖者見 N-18（astra-5 F-04），逾時後補 tock 見 N-20 | 技術選型 |
| N-24 | 刪掉或搬走的 node 不能被建回來 | subtimeline 1；rename N9 | rm -rf 8 次有 6～8 次被 tock 或 aos7-run 建回 `.aos/round.json`；搬家落在 tick／tock 中途時，總結寫進鬼資料夾 | 應該 | S-06 | **已做**（本輪）：tick／tock 先看 timeline.json；aos7-run 經 fd 寫 exit.json；astra-5 F-09：tick／tock 抓 node 目錄 fd（`/proc/self/fd/N`）做整個動作，鎖內被刪→寫不進去、印 gone，被搬→寫到新位置，不建鬼目錄；astra-6 G-02：起任務前比 node 字串路徑與抓著的 fd，已搬走／換掉就受控失敗（exit 127，不建掛載、不起 runner）；node 底下的掛載目標經 fd 建；aos7-run 拿任務資料夾 fd 與 node cwd。G-03：daemon 的 `.aosd` 經 root fd 寫，不建回舊根（`test_astra6.G02`、`G03`） | 技術選型 |

## D. 任務歸屬、kill 與收尾

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-25 | 任務的資源歸屬不依賴任務自己能刪的 taskdir 和主 PID；主程序結束、fork、setsid、taskdir 被刪之後都還盤點得到 | astra I-04、I-05、R4；polyglot N5 | 主程序結束後，孫程序 kill 回「already ended」、stop 後還活著；`setsid sleep` 收不到；任務刪掉自己的 taskdir，status 看不到它，keep 又起三份 | 必要 | S-03、S-06、S-10、S-17 | **已答**：kill 另外用 `/proc/*/environ` 找 `AOS7_TID`＋`AOS7_NODE` 相符的程序；已結束的任務被 kill 時也收殘留；spec 寫明只保證到這裡，故意脫離的任務自己負責；astra-5 F-01：正常 stop（含 SIGTERM）也照這個範圍收尾：所有時間線結束後一次掃 /proc，收 `AOS7_NODE` 屬於本 daemon 各 node 的殘留（含已結束、tasks-old 的任務）；astra-6 G-09：spec 寫明 stop-sweep 以 `AOS7_NODE`＋`AOS7_TID` 識別、不比 ROOT，不是 daemon 身分驗證 | 〔使用者 10-03〕選 (a) |
| N-26 | node 消失或搬家時，上面的活任務要有人收，或至少被看見 | subtimeline 2；rename N8 | rm -rf 後 sleeper 還活著，status 不列它，stop --kill 也收不到；搬家後任務的 `AOS7_TASK` 指舊路徑，從此收不到 tock | 應該 | 之後再說（node 怎麼消失） | **已做**：node 消失（含只刪 timeline.json、搬家）就 kill 上面的活任務；daemon 在記憶體記各 node 活任務的 pgid，另找 `AOS7_NODE` 相符的程序；結束碼經 fd 寫到新位置；新位置由 keep 重起（rename、subtimeline 探針已改驗這些）；astra-5 F-03：只有「確定不存在」才 kill，I/O 錯看不到的保留；spec 寫明 pgid 清冊是 0.25 秒週期採樣；astra-6：搬家時起到一半的任務不再永遠 born（G-02），子 daemon 不再把 status／log 建回舊根、root 消失照 stop 收尾（G-03） | 〔使用者 10-03〕選 (a) |
| N-27 | 多層停機要有總期限，不能每層各自 1 秒互相搶 | nest3 N2；astra R15 | 三層加上不理 SIGTERM 的任務：D1 一定被 -9，一半機率留下 2 個孤兒 | 應該 | S-06、S-21 | **沒做** | 技術選型（先不做；P-04） |
| N-28 | keep 任務要有正規的「別再起我」 | lifecycle N-5；swarm N6；llmkernel（LLM kernel 寫成 keep，結束後又起一份、再燒一次 LLM，只好改 spawn） | 29 回合裡，rc0、標記檔、自己 kill 各留 29 個資料夾；只有改 tasks.json 有效 | 應該 | 之後再說（任務表誰能改） | **沒做**；本輪提供 `aos7_fs.edit_json`，讓改 tasks.json 不會互相蓋掉 | 已答 D-3 |
| N-29 | crash loop 要有退避，或至少看得到連續失敗幾次 | lifecycle N-6；llmteam（子 daemon 的 argv 寫錯，keep 每 300 ms 重起，兩場各約 68 個任務資料夾，LLM 10～20 秒後才去看 out.log） | 52 回合起 52 次、52 個資料夾；50 ms interval 下約每分鐘 19 MiB；寫壞的任務默默死了 31 回合都沒人發現 | 應該 | 沒有 | **部分**：ended 有 name、code、by_ctl，kernel 可以自己算；tick 沒有退避 | — |
| N-30 | ended 要說清是哪個任務、為什麼結束 | lifecycle N-4 | 只有 tid＋code；被 restart 收掉的 code 是 0，跟自己正常結束分不出來 | 應該 | 之後再說（失敗與結束碼） | **已做**（本輪）：ended 加 `name`、`by_ctl` | 技術選型 |
| N-31 | 能「照新的定義重起」 | selfmod 9；llmops（**真模型 4 次有 3 次先下 restart**，事後讀 birth.json 才改 kill；換新卡後 luna 看出要重起卻停在「等它重啟」）→ **Q6** | 改了 argv 再 restart，新實例仍跑舊的 v1（restart 抄 birth.json） | 應該 | S-17 | **已做**：ctl.json 的 restart 加 `"reload": true`＝照 node 現在 tasks.json 的同名項目重起，回條 `result.diff` 列舊→新；找不到就整個不執行（不 kill）；`aos7-ctl task … restart --reload`。沒有 reload 的 restart 不變（`tests/test_owner_reload.py`）；astra-6 G-05：reload 先過第 4 節完整檢查（含 mode／from_round／max_live 型別），不合格不 kill；G-06：被宣告接管的同名掛載改標宣告來源，`mounts_dyn` 只帶沒被接管的，之後刪宣告能生效、diff 看得到（`test_astra6.G05`、`G06`） | 〔使用者 10-03〕Q6 加 flag reload |
| N-32 | pause 時能搶佔正在跑的任務 | sched N5 | 低優先 pause 生效的那一刻，12 次裡 12 次都還有任務在跑 | 應該 | S-17、S-18 | **沒做** | 已答 D-4 |

## E. 任務表與 spawn

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-33 | tasks.json 要能安全地多人改 | selfmod 8；lifecycle N-5 | 兩個任務各改 100 次，沒鎖只剩 100 項；3 次有 2 次 lost update | 應該 | 之後再說 | **已做**（本輪）：約定 flock `<檔>.lock`，`aos7_fs.edit_json` | 技術選型（選 selfmod 的選項 a） |
| N-34 | 一批 spawn 要能一次交出去 | swarm N3 | 每寫一個 spawn 停 3 ms，3 批全被拆成兩回合 | 應該 | 沒有 | **已做**（本輪）：`{"batch": [...]}`；astra-5：batch 裡壞項只跳過那項 | 技術選型 |
| N-35 | 條件起（有檔才起）、只起一次 | swarm N6；selfprog（「每個檔只算一次」3 個模型全失敗：都寫進 tasks.json 的 keep／each）→ 見 N-65 | each 沒事件時每回合也起一個 Python | 可以 | 沒有 | **沒做** | — |
| N-36 | each 任務要能設並行上限 | longrun N-3 | 跑 1 秒的 each 任務在 100 ms 回合下堆到 7～8 個 | 應該 | 沒有 | **已做**（本輪）：`max_live` | 技術選型 |
| N-37 | 新 node 要有「準備好了」的規則 | subtimeline 4 | 先寫 timeline.json 再寫 tasks.json，有 1～8 個空回合 | 可以 | 之後再說 | **已做**（spec 寫明順序：tasks.json 先、timeline.json 最後） | 技術選型 |
| N-38 | daemon 要記得 node 的歷史（同名重建時分得開） | subtimeline 12 | rm -rf 後同名重建，回合從 1 重數，log 裡分不出是兩段 | 可以 | S-14 | **沒做** | — |
| N-39 | tid 不能被誤讀成名字 | swarm N7 | `a/b` 和 `a_b` 都變成 `a_b-r1…` | 可以 | 沒有 | **已做**（spec 寫明要看 birth.json） | — |

## F. 規模與成本

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-40 | 歷史任務資料夾不能讓 tick／tock／status 越跑越慢 | swarm N4；fleet N3；astra R12；lifecycle N-6 | 4000 個舊資料夾：tick 4→56 ms，tock 3→46 ms，daemon CPU 10%→52%；一個短命任務約 16 KB | 必要 | 沒有（P-12 原列默認正常） | **已做**：status 的 live 每 0.25 秒才重算；tock 把結束超過 `keep_ended_rounds`（預設 20）回合的搬到 `.aos/tasks-old/`。swarm：4000 個舊資料夾時 tick 53～70→4～5 ms、tock 63～86→3 ms、回合週期 164～206→100 ms；搬的那一次 tock 85～110 ms；astra-5 F-02：搬移中的讀取用 `aos7_fs.task_read`（讀完原路徑不在就重定位、整份重讀；讀不齊回 unknown），`task_dirs_of` 同 tid 只回一次。磁碟上的歷史總量仍無界 | 〔使用者 10-03〕選 (a) |
| N-41 | 每回合兩個 Python 程序的成本要有對策 | fleet N1；astra R11、R17 | 150 條時間線約吃 12 核，回合只跑到該有的 45%；astra 10→200 條，每條完成的回合數 123→11（中位） | 應該 | S-04、S-12 | **已答**：接受，容量寫清楚（約每秒 100～150 回合，見文末） | 已答（10-03） |
| N-42 | 每個任務的 aos7-run 包裝太重 | fleet N4 | 一個 14 MB；75 個 keep 任務約 1 GB | 可以 | 沒有 | **沒做** | — |
| N-43 | tick 起大量任務很慢，吃掉 interval | swarm N5 | 起 52 個任務 133 ms | 可以 | S-09 | **沒做** | — |
| N-44 | CPU、程序數、輸出空間能設上限 | astra R13 | 8 MiB 輸出、單核忙迴圈，基礎設施都不管 | 應該 | S-17（上層定策略） | **沒做** | — |

## G. 掛載、跨 daemon、非 Python 任務

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-45 | 跨 daemon 的控制端點要能照文件配置（匯入或 re-export），仍然走掛載 | astra I-09、R10；multid N7 | 空間外的 daemon：宣告與加掛都被拒，只能用絕對路徑硬寫，寫入紀錄看不見；反向掛父的 `.aosd` 被拒，要把實體目錄 re-export 進去才成 | 必要 | S-07、S-21、S-23 | **部分**：空間內的符號連結掛得上，拒絕會說明理由；沒有照做的流程 | — |
| N-46 | 路二要能把 daemon 起回來；daemon 的身分不跟著路徑變 | multid N6 | 只能走路一起；起回來後 `status.root` 變成掛載點路徑 | 應該 | S-21 | **沒做** | — |
| N-47 | 路一的子根要有標記，父 daemon 才不會先把它當 node 搶走 | nest3 N3 | 沒先建 `.aosd/` 時，三層悄悄塌成兩層，D2 起在錯的位置 | 必要 | S-15、S-21 | **已做**（本輪）：tasks.json 項目加 `subroot`，tick 先建 `<subroot>/.aosd/`；astra-5 F-08：daemon 掃描時，新 node 落在祖先 node 的 tasks.json／spawn 宣告的合格 subroot 底下就不收（tick 建 `.aosd/` 前的第一次掃描也不搶）；astra-6 G-04：子根已有 daemon 在跑時，別的任務認領不改 owner | 技術選型 |
| N-48 | 掛載目標消失後重掛，不能默默建出鬼資料夾 | rename N10；llmops（restart 陷阱那 3 次都讓 tick 建出鬼資料夾 `n5/inbox`，沒有一次被發現） | restart 後照舊宣告重掛 `a/inbox`，信「寄成功」但進了沒人看的資料夾 | 應該 | S-23 | **沒做** | — |
| N-49 | 寫入紀錄要分得出 `.aos/` 裡哪些是基礎設施的檔；看得到空間外的寫入；不混進 aos7-run 自己的寫入 | selfmod 5；multid N7；polyglot N7 | 任務把 round.json 撥到 1000、偽造別人的 exit.json，全記 ok；每個任務混進約 9 筆 aos7-run 的寫入 | 應該 | S-10 | **部分**（本輪）：aos7-run 不再載入 audit；前兩項沒做 | — |
| N-50 | 父要管自己 node 裡的子時間線 | subtimeline 11；selfprog（3 個模型都直接改自己開的子 node，全被記 ok:false；沒有一個想到先加掛）。技術選型：照 M-5，卡寫明「要改子 node 先加掛」 | 父直接寫子的 tasks.json：記 ok:false 但照樣生效；判不判違規看寫的順序 | 可以 | S-15 | **沒做**（照 M-5） | — |
| N-51 | 非 Python 任務要能等 tock、讀欄位 | polyglot N6 | sh 每 20 ms 輪詢，花 7～9% 一核；靠 sed 抓排版讀 JSON | 應該 | S-01、S-11 | **已做**（本輪）：`aos7-wait-tock`；astra-5：tock.json 不是物件當沒有、繼續等 | 技術選型 |
| N-52 | 原子寫的暫存檔不能被別人當成正式檔讀到 | polyglot N11 | 讀到 `x.json.tmp.1383587` | 可以 | S-01 | **已做**（本輪）：暫存名以 `.` 開頭 | 技術選型 |
| N-53 | inst 任務的輸出預設不要丟掉 | polyglot N12 | inst 任務的 out.log 是 0 bytes | 可以 | S-12 | **沒做** | — |


## H. 第二波探針：LLM 當操作者（10-03）

來源是 `probes/llmkernel`、`llmops`、`selfprog`、`llmteam`（LLM 只有 read_file／write_file 兩個工具加一張操作卡 [probes/llm_card.md](../probes/llm_card.md)）與 `probes/chaos`（不用 LLM，高頻亂寫控制面加 10 個單一壞輸入 B1～B10）。N-55 留給 astra-5 報告建議的那條（[play/2026-10-03-astra-5-infra.md](play/2026-10-03-astra-5-infra.md)），這裡從 N-56 起。測試在 `tests/test_wave2.py`。

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-56 | 讀 JSON 遇到 FIFO、資料夾等非一般檔不能卡住 | chaos B10；llmops | `.aosd/ctl/f.json` 是 FIFO：daemon 主迴圈卡在 open()，status 停更、stop 也不收（只能 SIGKILL）；任務 ctl.json 是 FIFO 卡住 tock，spawn 是 FIFO 卡住 tick；tasks.json 是 FIFO 讓 tick 每回合跑滿逾時 | 必要 | S-06 | **已做**：`read_json` 用 O_NONBLOCK 開、不是一般檔當不存在；tasks.json 不是一般檔記 `tasks_error` | 技術選型 |
| N-57 | 控制檔名字不合格（不是 .json、是資料夾）要有回條 | chaos B5；llmkernel | `ctl/` 裡的 `x.txt` 默默略過、寫的人等不到回條；`d.json` 是資料夾時每圈「處理」一次，log 每秒約 50 行 | 應該 | S-01、S-18 | **已做**：原物搬到 `ctl-done/<名>.bad`、回條 ok:false | 技術選型 |
| N-58 | 一個 node 的壞檔不能讓整個 daemon 退出 | chaos B1 | 新出現的 node 的 round.json 是 `[]`：daemon rc 1，其他 node 的任務變孤兒（`guard` 只接 OSError） | 必要 | S-05、S-06 | **已做**：時間線讀壞 round 當 0；主迴圈任何例外都記 `ev: "error"` 再試 | 技術選型 |
| N-59 | 壞項目的欄位檢查要涵蓋 name／argv 型別；spawn 也一樣；壞的 spawn 不能變毒丸 | chaos B2～B4；astra-5 F-06 一部分 | `name: 5` 讓整個 tick 例外、好項目永遠起不來；spawn 檔 name 是陣列＝毒丸（檔不刪、每回合死）；`argv: ["sleep", 5]` 讓 aos7-run 當場例外、任務永遠算剛起（一次冒出約 200 個，stop --kill 超過 15 秒） | 必要（併入 N-21） | S-06 | **已做**：tick 的 `validate` 給 tasks.json 與 spawn 共用；spawn 每項各自 try、檔照刪；aos7-run 對型別錯也寫 exit.json 127；astra-5 F-06：起任務本身丟的例外也只記那一項；astra-6 G-05：restart reload 也走同一套完整檢查 | 技術選型 |
| N-60 | round.json 被寫壞不能讓回合重數、重號 | chaos B6 | round 改成字串：下個 tick 從 1 重數，rounds.jsonl 重號 | 應該 | S-08 | **已做**：從 rounds.jsonl 最後一行接著數，記 `tasks_error` | 技術選型 |
| N-61 | 回合中消失又出現的 node、回合中死掉重開的 daemon，那一回合要補 tock | chaos B8 | rounds.jsonl 每次亂寫缺 6～14 個回合號 | 應該 | S-08、S-11 | **已做**：時間線第一次開回合前先 tock 掉沒關的回合（`incomplete: "unclosed"`）；chaos A 段缺號 0 | 技術選型 |
| N-62 | 負數 interval 算壞值 | chaos B9 | -5 默默當 1 ms 全速跑，不記錯 | 可以 | S-08 | **已做**：負數用預設並記 last_error；0 合法（＝不等，實際 1 ms） | 技術選型 |
| N-63 | kill 不能被任務自己寫的 pid.json 導去打別人 | chaos B7 | 任務把 pid.json 的 pgid 改成別的群組，kill 就送 SIGTERM 過去（被害的 sleep 退出碼 -15）；改成 daemon 的 pgid 就打到 daemon | 必要 | S-17；權限屬之後再說 | **已做**：kill 前確認群組裡有程序（或它的父程序 aos7-run）的 `AOS7_TID`＋`AOS7_NODE` 是這個任務，不是就不打、回 ok:false；node 消失時用 daemon 記著的 pgid 那條路還沒加這個檢查 | 技術選型（chaos 選項 (b)；不搬 pid.json，不碰 Q1） |
| N-64 | spawn 要看 keep／max_live | llmops | luna 改好 tasks.json 又寫 spawn 補起，n1 和 hub 都變兩份，之後 kill 多的再 spawn，每次又多一份，直到呼叫用完 | 應該 | S-10 | **已做**：spawn 項目也過 `should_start`，被擋記 `tasks_error`、檔照刪；restart 的 spawn 沒有 mode，不受影響 | 技術選型 |
| N-65 | 「做一次就好」要有讓 LLM 想得到的正規寫法 | selfprog；llmkernel | 「每檔只算一次」3 個模型全失敗：deepseek 用 keep（做完又起，每檔 10～14 次）、haiku 用 each（每檔 63～69 次）、luna 先用 spawn 後又退回 each（約 200 次） | 應該 | 之後再說（任務表誰能改） | **部分**：卡寫明「做一次的用 spawn，不要寫進 tasks.json」；tasks.json 的 `mode: "once"`（成功結束過就不再起）沒做 | 技術選型（先只寫文件） |
| N-66 | 路一的子根：範圍、路徑、寫入紀錄要說得清 | llmteam | 兩個 A 都寫 `argv: ["aos7-daemon", "lab/sub"]`（cwd 是 node，實際指到 `lab/lab/sub`）→ crash loop；`subroot: "sub"` 照收、在空間根建了 `.aosd`；子 daemon 繼承任務的 audit 環境，寫自己的根全記 ok:false | 必要 | S-10、S-21 | **已做**：subroot 限在自己 node 底下；`AOS7_SUBROOT` 環境變數（argv 寫 `$AOS7_SUBROOT`）；寫入紀錄把子根算任務的；卡與 spec 寫明「等子根 status.json 出現再建子 node」 | 技術選型 |
| N-67 | `stop` 帶 node 要拒絕 | llmteam | A 寫 `{"op":"stop","node":"w1"}` 想停一個 node，回條 ok、整個子 daemon 停了 | 應該 | S-18 | **已做**：回 ok:false 並指向 pause | 技術選型 |
| N-68 | 從沒開過回合的 node、還沒 pause 過的 daemon，讀的人要看得出「正常、還沒有」 | llmkernel | 一出生就 pause 的 node 沒有 round.json／rounds.jsonl／tasks/；luna 讀錯 8 次、花 5 輪猜；paused.json 第一次 pause 前不存在 | 應該 | S-01 | **部分**：daemon 一起來就寫 paused.json；卡寫明「round 0＝還沒開過，沒有那些檔是正常的」；status 沒加 `started` 欄 | 技術選型 |
| N-69 | `last_error` 要分得出新舊 | llmops | 4 次都要翻 rounds.jsonl 才確定 n3 的錯是舊的；luna 第一次因為看到逾時的 last_error 一直調大 `action_timeout_s` | 應該 | S-01 | **部分**：卡寫明「拿 last_error.round 跟 round 比」；沒有 `last_ok_round` 之類的欄位 | — |
| N-70 | tick／tock 逾時要說得出卡在哪 | llmops | `err` 只有 `aos7-tick killed (timeout after 2.0s)`，4 次有 3 次去改逾時而不是換掉 FIFO | 應該 | S-01、S-06 | **部分**：最常見的原因（FIFO）改成 `tasks_error` 直接說；逾時時附 `/proc/<pid>/wchan` 沒做；astra-6 G-10：等鎖逾時而持鎖者身分無法驗證時，`last_error` 說出原因（缺欄位／starttime 讀不到／對不上）與人工恢復方法 | — |
| N-71 | 任務一直失敗要在 status 看得見 | selfprog；llmteam | sub 上的任務寫錯 cwd 一直 crash，LLM 要自己翻 tasks/、tasks-old/ 的 exit.json；crash loop 10～20 秒後才被注意 | 應該 | 之後再說（失敗與結束碼） | **沒做**（建議 status 每 node 加 `last_task_fail: {"tid","name","code","round"}`，併 N-29） | — |
| N-72 | 結束的任務不要在一輪 LLM 思考之內就被搬走 | selfprog | 200 ms 一回合、keep_ended_rounds 20：4 秒就搬到 tasks-old/，比模型想一輪還短；luna 先讀到「不存在」才去猜 tasks-old | 可以 | 沒有 | **部分**：卡寫明「不在 tasks/ 就去 tasks-old/」；沒加時間下限 | — |
| N-73 | 寫給停著的 daemon 的控制檔怎麼處理 | llmteam | B 寫的 rescan、wake 一直沒回條，花約 20 輪才確定 daemon 死了；留著的 stop 會在下次起來瞬間又停 | 可以 | 之後再說 | **照現在**：下次起來才執行，spec 與卡寫明（llmteam 的選項 a） | 技術選型 |
| N-74 | daemon 自己的檔被別人寫，要不要報錯 | llmops | haiku 把 `.aosd/paused.json` 寫成空清單想 resume，沒效果也沒錯誤 | 可以 | S-01 | **部分**：卡寫明「status、paused.json、log 是 daemon 的，寫了沒用」 | — |
| N-75 | 路二的 stop 會被路一的 keep 抵銷 | llmteam D1 | 外部 LLM 只用子 daemon 的控制檔：stop 回條 ok、子 daemon 也退出了，0.16～0.3 秒後父的 keep 以新 gen 把它起回來；外部擋不住，只有改父 node 的 tasks.json 才行 | 應該 | S-21 | **已做**：tick 寫 `<subroot>/.aosd/owner.json`；擁有者沒設 `allow_stop` 時路二的 stop 回 ok:false；允許時 stop 留 `stopped.json`，擁有者的 tick 看到就不起、刪掉才再起；llmteam 探針改驗新行為（`tests/test_owner_reload.py`）；astra-6 G-04：tick 寫 owner.json 前試子根的 daemon.lock，已有 daemon 在跑就不起、不改 owner、記 `tasks_error`，失敗的第二個啟動者改不掉現役 owner（`test_astra6.G04`；剩兩個 tick 在子 daemon 拿鎖前同時認領的窗口）。G-09：spec 寫明 owner.json／stopped.json 是**合作式檔案協定**，任務改得動、分不出是誰改的 | 〔使用者 10-03〕Q5 子 daemon 歸擁有者 |
| N-76 | 只會整份讀檔的 LLM 要看得到 jsonl 的尾端 | llmteam；llmops | 第一版 read_file 只回前 6000 字：3 個模型都說要看 rounds.jsonl／log 的結尾，B 因此驗不了「剛好 3 回合」 | 可以 | S-01 | **探針工具已改**（`llmop.clip` 回開頭＋結尾）；基礎設施沒有「最新一回合總結」的固定小檔 | — |

**LLM 只靠檔案操作 daemon 的成績**（第一版卡；細節在各探針 README）

| 探針 | 成功 | 真模型呼叫 |
|---|---|---|
| llmkernel：三條時間線輪流、超預算的停掉 | 1/3（deepseek 成；luna 輪次記錯；haiku 沒用 `rounds`，每輪多跑約 10 回合）；換新卡後 haiku 重跑成功 | 79＋22 |
| llmops：修五個壞法 | 整張工單 3/4、逐項 17/20；換新卡後 luna 由 2/5 變 4/5 | 127＋18 |
| selfprog：自己開子任務、子時間線、改 interval、wake | 9 個目標平均 6.7/9；result.json 3/3 正確、「每檔只算一次」0/3 | 82 |
| llmteam：路一開子 daemon＋路二外部管 | A 就緒 2/2（都先 crash loop）；B 控制檔 3/3（daemon 活著時）；「停了保持停住」0/2 | 115 |

格式（控制檔、回條、status 的 phase／pause_pending／steps_left）幾乎沒人讀錯；錯的都是**時間與生命週期**：restart 用舊定義、一次性工作寫進 tasks.json、比回合慢卻自己看到再 pause、cwd／子根的路徑基準、把舊 last_error 當現況。

## I. astra-5（10-03）

來源是 [astra-5 報告](play/2026-10-03-astra-5-infra.md)（第二節 F-01～F-11）。F-01～F-10 都併進原號（上面各列「astra-5」字樣），只新增報告建議的 N-55。測試在 `tests/test_astra5.py`（重現情境照報告的 evidence）。

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-55 | 建立程序的測試／示範／探針必須**先回收程序，再刪空間**：正常、逾時、assertion、I/O 錯、中斷都一樣 | astra-5 F-11 | `test_agent.RoundsFlag` 用固定 sleep 送 tock：agent 起得慢只看到最後一次，`--rounds 2` 永遠等不滿；5 秒 communicate 逾時後 cleanup 只 rmtree，agent 留著、`AOS7_ROOT` 指向已刪的 /tmp。`demo/play.py` 沒 finally：寫 stop 檔遇 EIO 就拋錯，daemon 留著還把 `.aosd` 建回 | 必要 | S-06（測試工具不能把自己的洩漏當產品結果） | **已做**：`tests/_proc.py` 的 `track`（Popen 成功當下登記；unittest cleanup 後進先出，比 rmtree 先跑；Ctrl-C 時 atexit 補收）／`reap`（terminate → 限時 wait → kill → wait）；CoreCase 改成 cleanup 先收 daemon（SIGTERM 讓它收自己的任務）與 pid.json 的群組、最後才刪空間；test_agent／kernel／infra／demo 的 Popen 全登記；`RoundsFlag` 每送一次 tock 等 state.json 確認。`demo/play.py`、`real.py` 用 finally 收 daemon（SIGTERM 也走 finally）；探針收 SIGTERM 轉 KeyboardInterrupt 讓 `Space` 照樣收，`run_all` 逾時先 SIGTERM 探針；astra-6 G-07：atexit fallback 沿用每筆登記的 grace／group，加了真的走 interpreter exit 的測試（`test_astra6.G07`） | 技術選型 |

## I2. astra-6（10-03）

來源是 [astra-6 報告](play/2026-10-03-astra-6-infra.md)（第二節 G-01～G-10，第三節 N- 建議）。報告建議把 N-20、N-24、N-31、N-75、N-55 從已做改部分、N-21 改部分；G-01～G-10 這輪都修了（G-09、G-10 是技術選型：G-09 只改文件，G-10 不殺、只說明），所以照實維持已做，各列補「astra-6」字樣。沒有新增 N- 號。測試在 `tests/test_astra6.py`（重現情境照報告的 evidence）。仍照實留著的：N-17 容量面、N-19／N-22 部分、N-23 沒做、N-75 兩個 tick 在子 daemon 拿鎖前同時認領的窗口、N-27／N-41 維持原狀。

`--rounds N` 只是「處理 N 次通知就走」，不是資源清理機制；收程序靠擁有者（測試、demo、daemon）的 finally 與 PID，不用廣泛的 `pkill -f`。

## J. astra 調查報告二的實驗探針（10-03）

來源是 [astra 調查報告二](research/2026-10-03-other-os-borrow.md) §14 的實驗一、二，做成兩個全離線的探針 [probes/namespace](../probes/namespace/README.md)、[probes/ledger](../probes/ledger/README.md)，daemon／tick 沒改。報告 §13 預測「三個實驗都能不改 daemon／tick 先做」，結果成立：服務卡、epoch、去重、委派帳、未知在途都在任務層做得到。逼出的只有下面兩條，「對應」欄是報告的 E- 編號。

| 編號 | 需求 | 來源 | 證據 | 優先 | 核心 | 現況 | 決定 |
|---|---|---|---|---|---|---|---|
| N-77 | 服務要驗得出請求是誰送的（可信執行身分；對應 E-01） | ledger 第 6 步 | Q 的任務拿洩漏的 P grant、在 claim 裡自稱 `p:w-real-r99`：帳本 claim 成、provider 照做、記給 P。請求檔的寄件者都是自報的；mounts 的宣告不受 `mount_allow` 管；寫入紀錄只看得到 Python、是事後的。tick 知道 birth 的 node／tid／mounts，卻沒有交給服務驗的管道 | 必要（只在要宣稱「付費硬限制」時；合作式不需要） | 權限屬之後再說 | **沒做** | **要使用者決定**（權限是核心「之後再說」；做法會牽動 tick／aos7-run 怎麼替任務背書） |
| N-78 | 活任務換服務時，舊目標上的在途請求要有路收尾（對應 E-03） | namespace 第 3、4 步 | reload 換掉整份 mounts，舊服務上還沒回的 a-job5 新任務就看不到了（任務只能報 unknown、不重送）；要 kernel 自己約定多掛 `model-prev`，拿掉它又得再 reload（kill）一次，因為卸掛不做。兩次 reload，4 個控制步 | 可以 | S-23 | **沒做**（現有基底做得到，只是彆扭） | — |

## 要使用者決定

原本留了四條（Q1～Q4），使用者 10-03 全部答了；下面保留題目與答覆。第二波探針新增的 **Q5、Q6**，使用者 10-03 也答了。其餘照使用者 10-03 說的「普通的直接做」，取最簡單的做法，記成技術選型。

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

### Q5 路二的 stop 和路一的 keep，誰說了算？（N-75）〔使用者 10-03 答〕子 daemon 歸起它的 node

> 「子daemon歸屬於哪個node，那他的所有權就歸屬於那個node，如果那個node允許，那stop就有用。」
>
> 做法（細節見 [spec.md](../spec.md) 第 2 節「子 daemon 的所有權」）：tasks.json／spawn 項目多可選 `allow_stop`（bool，預設 false，restart 帶上）。tick 起帶 `subroot` 的任務時寫 `<subroot>/.aosd/owner.json`＝`{"node", "tid", "allow_stop", "at"}`，擁有者可直接改它即時調權限。子 daemon 收到控制檔 stop：有 owner.json 而 `allow_stop` 不是 true → 回 ok:false、說它屬於誰；允許 → 照停並寫 `.aosd/stopped.json`＝`{"by", "why", "at", "kill"}`；頂層 daemon（沒有 owner.json）照舊。SIGTERM（擁有者 kill 任務，路一）照舊。擁有者的 tick 看到子根有 stopped.json 就不起（keep／each／spawn／restart 全部），記 `tasks_error`；刪掉才再起。人手直接跑 aos7-daemon 起來時清掉 stopped.json、log 記 `stopped-cleared`。核心 S-21 加了一句。
>
> 自己補的細節：owner.json 壞掉當「不允許」；只管 `stop`，pause／resume／wake 不看所有權；被擋時不佔 tid；`allow_stop` 型別錯照現有規則只跳過那一項。


- **發生了什麼**（probes/llmteam）
  - A（node `lab` 裡的任務）用路一在 `lab/sub` 開子 daemon，tasks.json 那項是 `keep`。
  - B 從外面只寫子 daemon 的控制檔（路二）。stop 的回條 ok，子 daemon 也正常退出了。
  - 0.16～0.3 秒後，父 node 的下一個 tick 看到沒有同名活任務，用 keep 把子 daemon 起回來（gen 1→2）。B 看得出原因，但它只能寫子 daemon 的控制檔，擋不住；只有改父 node 的 tasks.json 才擋得住。離線照稿每次都重現。
  - 被 stop 收掉的子 daemon 結束碼是 0，跟「自己做完」分不出來。
- **為什麼要問你**：S-21 說兩條路都要，但沒說兩條路對同一個子 daemon 意見不同時誰贏。這是 daemon 的核心語意。
- **選項**：（不代替你選）
  - (a) 照現在：路二的 stop＝「重開一次」；要它一直停，得由路一那邊（父 node 的 tasks.json）拿掉。spec 寫明。
  - (b) stop 在子根留一個標記 `.aosd/stopped.json`（by、at）。有標記時 aos7-daemon 起不來（印說明、退出碼非 0）；父的 tick 看到 `subroot` 有標記就不起那個 keep 項目、記 `tasks_error`。刪掉標記＝路二把它起回來（順便給 N-46「路二要能把 daemon 起回來」一條路）。
  - (c) 同 (b)，但只有 stop 帶 `"sticky": true` 才留標記；平常的 stop 照 (a)。

### Q6 restart 照誰的定義？（N-31）〔使用者 10-03 答〕加 reload 旗標

> 「加上flag reload」
>
> 做法（細節見 [spec.md](../spec.md) 第 6 節）：任務 ctl.json 寫 `{"op": "restart", "reload": true}` 時，新任務照 node 現在 `.aos/tasks.json` 裡同名（birth.json 的 name）項目起，去掉 `mode`／`from_round`／`max_live`，帶 `restart_of`，執行中加掛的照樣帶過去。找不到同名、tasks.json 讀不懂、項目不合格、或 `reload` 不是 bool → 整個 ctl 不執行（不 kill），回條 ok:false 說原因。成功時回條 `result.diff` 與 msg 列舊→新。沒有 reload 的 restart 不變，spec 加警告。`aos7-ctl task <taskdir> restart --reload`。
>
> 自己補的細節：同名有好幾項取第一個；執行中加掛的在 birth.json 標 `"dyn": true`，restart 寫的 spawn 帶 `mounts_dyn` 讓新任務照樣標（下次 reload 還分得出來）；掛載同名以 tasks.json 項目為準；diff 比 `argv`、`inst`、`mounts` 宣告、`subroot`、`allow_stop`。


- **發生了什麼**（probes/llmops、selfmod 9）
  - 工單：n5 搬到 n5b，hub 的 relay 任務掛載還指舊路徑。正解是改 hub 的 tasks.json，再 **kill**（keep 照新定義重起）。
  - 操作卡寫明「restart 照 birth.json 原本的定義」，真模型 4 次仍有 3 次先下 restart；新實例照舊掛 `n5/inbox`，tick 還建出沒人看的鬼資料夾（N-48），3 次都沒發現，事後讀 birth.json 才改用 kill。
  - 換了強調「改定義要 kill」的新卡，luna 這次看出 relay 要重起，卻停在「需等該任務重啟後才能確認」，沒有動手。
- **為什麼要問你**：核心把「kill、restart 這些控制塊怎麼做」列為之後再說；改 restart 的語意會改 kernel（卡住就 restart）的行為。
- **選項**：（不代替你選）
  - (a) 照現在：restart＝同一份 birth.json 再起；改定義要 kill，文件加警告。
  - (b) restart 先找現在 tasks.json 裡同名的項目，照它重起；找不到（spawn 起的、已經從表上拿掉的）才用 birth.json。kernel 的 restart 也跟著吃到新定義。
  - (c) 不改 restart，另加 op `reload`：kill 後照現在 tasks.json 同名項目重起。

## 答完 Q1、Q3、Q4 之後冒出來的（技術選型，先這樣）

- **kernel 算用量總和也要掃 tasks-old/**，因為總額上限 `cap_tokens` 要算進已結束的任務。所以 kernel 的成本仍會隨歷史長大，只是轉到 kernel 自己身上。之後若有需要，可以讓 kernel 自己累計，或由 tock 在搬走時把用量加總進一份檔。
- **「暫停但保留任務」只剩 pause 一條路**：只刪 timeline.json 現在等於 node 消失，上面的任務會被 kill。event 探針的「把 timeline.json 改名讓 node 消失再出現」催回合 hack，現在會連任務一起殺掉；改用 `wake`。
- ~~**node 被判消失的依據是一次掃描沒看到 timeline.json**：網路檔案系統或掛載斷一下，任務就會被 kill。~~ astra-5 F-03 已改：掃描分「確定不存在（ENOENT／ENOTDIR）」與「看不到（ESTALE、EIO、EACCES…）」，看不到的保留 node 與 pgid、記 `scan-error`、下一圈重掃，只有確定不存在才 kill。
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

- **第二波探針之後**（10-03，`tests/test_wave2.py`）
  - `read_json` 不讀非一般檔（N-56）；`ctl/` 的怪名字、資料夾、FIFO 給 ok:false 回條（N-57）。
  - daemon 主迴圈接任何例外；時間線讀壞的 round.json 當 0（N-58）；tick 從 rounds.jsonl 接著數（N-60）；沒關的回合先補 tock（N-61）；負數 interval 算錯（N-62）。
  - tick 的 `validate` 給 tasks.json 與 spawn 共用；spawn 每項各自 try、檔照刪、照 keep／max_live（N-59、N-64）；aos7-run 對型別錯寫 exit 127。
  - kill 前驗證 pgid 屬於這個任務（N-63）。
  - `stop` 帶 node 拒絕（N-67）；daemon 一起來就寫 paused.json（N-68）。
  - subroot 限在自己 node 底下、`AOS7_SUBROOT`、寫入紀錄算子根（N-66）。
  - 測試鉤子 `AOS7_TEST_TICK_HANG` 取代 FIFO 的 tasks.json（那招不會卡了）。
  - 操作卡 [probes/llm_card.md](../probes/llm_card.md) 依 LLM 的誤解補了十幾句。

- **astra-5 之後**（10-03，`tests/test_astra5.py`；報告 [F-01～F-11](play/2026-10-03-astra-5-infra.md)）
  - F-01 stop 帶 kill 最後一次掃 /proc 收各 node 殘留（N-25、N-09）；F-02 搬移中的讀取 `task_read`、用量 unknown（N-40、N-12）；F-03 掃描錯誤不當消失（N-26、N-22）。
  - F-04 `action.owner.json`＋等鎖逾時回收舊世代持鎖者（N-18、N-23）；F-05 同回合總結去重、逾時後補 tock（N-20）；F-06 單項隔離補齊（N-21、N-13、N-34、N-51、N-59）。
  - F-07 加掛先回條後刪請求（N-19）；F-08 掃描跳過宣告的子根（N-47）；F-09 tick／tock 抓 node 目錄 fd（N-24）；F-10 控制檔每圈預算（N-17）；F-11 測試／示範／探針先收程序再刪空間（新增 N-55）。
  - I-11（首份 status 之後新 node 的公平性）沒另外做：新 node 已照檔名每圈起 20 條，剩下是負載下的吞吐，使用者已接受慢（N-41）；記在 N-17。

- **astra-6 之後**（10-03，`tests/test_astra6.py`；報告 [G-01～G-10](play/2026-10-03-astra-6-infra.md)）
  - G-01 daemon 控制檔逐件錯誤邊界、失敗件搬 `ctl-failed/`（N-17、N-19、N-21）；G-02 起任務跟抓著的 node fd 一致、搬走受控失敗、aos7-run 拿任務資料夾 fd（N-24、N-26）；G-03 daemon 的 `.aosd` 綁 root fd、root 消失照 stop 收尾（N-24、N-26）。
  - G-04 子根已有 daemon 在跑就不認領（N-75、N-47）；G-05 reload 完整驗證（N-31、N-59）；G-06 被宣告接管的掛載改標宣告來源（N-31）。
  - G-07 `_proc` atexit 沿用 grace／group（N-55）；G-08 半行總結補換行、確認提交才寫 ended（N-20、N-23）；G-09 spec 寫明合作式檔案協定、stop-sweep 不比 ROOT（N-75、N-25）；G-10 認不出身分的持鎖者不殺但說明（N-18、N-70、N-09）。
