# delivery / outbox / 目標生命週期

只由 README 進入，沿 spec 與 problems.md、第一輪報告讀取協議，再做下列實驗；沒有修改產品程式。先跑檔案協議後才讀 `aos7_agent_tools.py`、`aos7_mount.py` 解釋結果。`reproduce.py` 直接呼叫公開 bin 的 tick／tock，每次等 agent 的 progress；另外兩支腳本使用真 daemon，沒有 import 產品內部函式。所有 agent 都用 fake。

重跑（從 workspace 根）：

```sh
python3 proto7-1/notes/play/2026-10-03-astra-2-evidence/delivery/reproduce.py
python3 proto7-1/notes/play/2026-10-03-astra-2-evidence/delivery/pause_probe.py
python3 proto7-1/notes/play/2026-10-03-astra-2-evidence/delivery/pending_pause.py
```

## 新 bug：掛載目標消失會殺掉寄件 agent，而不是讓那封信退回 outbox

**重現：** 建 sender（keep fake agent）與 receiver 的 timeline。sender 初始不掛 receiver，由 goal 寄第一封，r2 進 outbox、r3 加掛後寄到。跑到 r5，刪掉 `receiver/inbox`，再寫第二個 goal；另一組改為把整個 `receiver` 搬成 `moved`。繼續到 r13。

**看到：** broken-link 快照裡 birth 與 mount-done 都仍說已掛、回條 `ok:true`，但是 `mnt/receiver_inbox` 的 symlink `exists:false`。r7 agent 寄第二封，拋出 `FileExistsError`（`write_json` 嘗試 `makedirs` 那個懸空連結）；`agent-r1/exit.json` 是 `code:1`。錯誤不是送信失敗回條，也未將該信留到 outbox，而是 agent 停在 act／pc 0，state.last 還是「think（fake）：1 個動作」。keep 在 r8 補起 `agent-r8`，接續 pc 0，這次沒有前任的動態掛載，先排 outbox，r9 重新申請、寄到。

搬家組還有可見後果：原 `moved/inbox` 只有第一封；第二封寄到**重新長出的舊位置** `receiver/inbox`，那裡沒有 `.aos/timeline.json`、沒有人收信。這裡的 node id 隨路徑改變本身是 S-14／P-15 已知選型；新 bug 是懸空掛載導致 agent 程序例外退出，新證據則是補起後會默默重建舊路徑寄信。

**牽涉：** S-23（掛載通訊）、S-19（工具 I/O 例外中斷 agent）、S-01（birth／成功回條不能證明目前掛載可用）；搬家的地址語意另涉及 S-14。**分類：〔bug〕。** 未主張 symlink 會自動追蹤改名，也未要求 core 額外承諾可靠投遞；未捕捉寄信 I/O 失敗足以獨立報 bug。

**證據：** `deleted-initial.json` → `deleted-broken-link.json` → `deleted-after-change.json`；`moved-initial.json` → `moved-broken-link.json` → `moved-after-change.json`。after-change 含原始 traceback、exit、state、birth、掛載回條及全部信件。

## 新證據：不存在的 node 收到「成功寄出」的信，寄件者看不到它沒人接

**重現：** 不建 ghost，只在 sender 放 `goal.json={"say_first":{"to":"ghost","body":"delivery to nonexistent node"}}`，跑 12 回合。

**看到：** r3 `mount-done` 是 `ok:true`，log 是 `outbox → ghost`；r12 sender idle、outbox 頂層無信，但 `ghost/inbox/<信>.json` 存在，ghost 沒有 timeline。這比 M-2 已知的「打錯路徑會建空資料夾」多一步：會產生有信卻沒有時間線消費的幽靈 inbox。沒掛上的情況與沒有收件 agent 不同：本例掛載其實成功，不能把信稱作仍卡 outbox。

**牽涉：** S-01、S-13、S-23。**分類：〔技術選型；M-2 新證據〕。** core 尚未定 node 出生／消失與訊息投遞保證，不先替使用者選應否拒絕不存在 node。

**證據：** `missing-after-12.json`。

## 其他覆蓋，不另列舊問題

| 情境 | 觀察與新證據 |
|---|---|
| 目標一直加掛不成：mount_allow=[] | r2 outbox、r3 拒絕後搬 failed，r8 還在 failed；並不是永久保留待寄。這是 M-8 已知行為。 |
| 改 allow＋刪拒絕回條＋restart | r8 後把 allow 改 `['.']` 並刪回條，跑到 r16；再 restart 跑到 r24。舊信始終在 failed，沒有新 mount-req。新證據：M-8 說的「刪回條即可重請」只是解除未來請求的阻擋，不會把已 failed 的舊信重新排隊。`denied-failed.json`、`denied-allow-and-delete-receipt.json`、`denied-restart.json`。分類〔技術選型；M-8 新證據〕，S-01／S-23。 |
| 待寄時 restart | r2 的 outbox 與 mount-req 尚未處理，寫 task restart，r3 新任務啟動，r4 信寄出、r8 idle。信名保持相同、只一封，證明正常 restart 會透過 node outbox 接續。`pending-restart-queued.json`、`pending-restart-after-restart.json`。 |
| 目標 node 被真 daemon pause | receiver 預先 pause，sender 至 r30；receiver status round 0／phase paused，sender 的新加掛回條成功，信已在 receiver/inbox。resume 後 receiver r2 把信移 inbox/done，寫成果。符合 A-7，新增動態掛載覆蓋；目標 pause **不阻止寄件端 tick 加掛**。`paused-recipient-paused-30.json`、`paused-recipient-resumed.json`。 |
| 寄件者 pause，無下一個審核 tick | r2 outbox 剛排隊就以 daemon ctl pause sender；等 1.5 秒（大於 interval 1000ms），回合仍 2，mount-req、outbox 同時保留，無 mount-done；resume 後 r3 寄到。`pending-paused-sender-before-wait.json`、`pending-paused-sender-after-wait.json`、`pending-paused-sender-resumed.json`。只觀察這段時間，並非實測無窮等待；原因是**寄件方停 tick**，不是收件方 pause。S-08／S-18／S-23，既有選型的覆蓋。 |

## S-01：cat 能回答的界線

- 「誰掛了誰」：讀每個 task 的 birth.mounts，名稱與 to 可直接懂；成功加掛回條也有原因 why。但懸空連結之後，兩份 JSON 都不會更新；只 cat birth 不能判定可用。
- 「為何被拒」：mount-done.result.msg 可讀出 mount_allow 拒絕。失敗信本身只有 from／to／round／body／at，沒有拒絕原因或回條路徑；要到當時的 task 查 mount-done 或 out.log。restart 後回條留舊 task，新增 task 的 state 不會指到那封失敗信。
- 「信卡在哪」：outbox 頂層代表等掛、failed 表示不再自動送，收件 inbox 表示已落檔但未處理；這三種要分開查。不存在 node 的案例 outbox 已清空，sender state.last 也只剩「回到 idle」，得實際 cat 目標信與檢查有無 timeline，才能知道沒人收。刪／搬案例的 FileExistsError 可在 out.log 看懂；需要知道 keep 重起與地址按路徑計，才能解釋為何最後又出現一個舊 inbox。

## 清理

每組以 task ctl kill 或 daemon stop＋kill 結束，等所有紀錄到的任務 pid／runner_pid 不存在或只剩不可執行的 zombie，再刪除自身 `/tmp/astra2-delivery-*`。`index.json`、`pause-index.json`、`pending-pause-index.json` 每組均記 `cleanup_survivors:[]`；daemon 組退出碼 0。沒有保留實驗空間或活程序。
