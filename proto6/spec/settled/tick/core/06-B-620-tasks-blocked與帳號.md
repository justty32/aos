← [通用 tick：核心](../../tick.md)（分檔 6/9）｜所在段落：B-620：任務註冊表：照表依序跑｜[上一份](05-B-620-讀表與跑每一項.md)｜[下一份](07-B-620-核心結束碼.md)

### tasks-blocked 與擋板檔〔暫定〕

使用者 2026-10-01：擋板檔與 tasks-blocked 的機制之後會詳細設計，下面是目前的做法。**tasks-blocked 的內容已定案**〔使用者 2026-10-01 第十八批：「3.對，我就不想了。」〕：tick 只看存不存在、永遠不讀內容；內容要寫什麼、怎麼用，交給 `modules.tasks_blocked` 的 insts 自己讀（[B-636](../tasks-blocked.md)）。〔使用者 2026-10-01 第十六批〕原停格檔 `tick/stop` 改名 `tick/tasks-blocked`：「然後是stop，我要稍微改個名字：.aos/tick/tasks-blocked。」改成每一項之前看、內容 tick 不管、整格最後 tick 自己刪：「task_blocked要改成tick在最後會自動刪掉。然後tasks-blocked中的內容，tick不管。」擋板檔改成只看存不存在、直接結束、stderr 不印：「正常機制結束的話stderr不應該印東西。hook也根本不會啓動。」

任務能影響之後的項或之後的格，只有這兩個檔；**結束碼沒有特別意義**，任務回 3、100 都只是一般的非 0，照記、照跑。

| | tasks-blocked `<狀態資料夾>/tick/tasks-blocked` | 擋板檔 `<狀態資料夾>/tick-blocked` |
|---|---|---|
| 擋什麼 | **本格**還沒跑的項（含正要跑的那一項） | 擋住**之後各格**，直到有人刪 |
| 誰建 | 任務、hook，或在格與格之間由人或別的程式放 | 任務（例如發現需要人處理的故障）或人手；`aos-git` 故障時也寫它（[B-622](../../deferred/git.md)） |
| 內容 | **tick 不管**，只看存不存在（空檔、資料夾、讀不到、壞 symlink 都算在） | **tick 不看**，只看存不存在；要寫原因給人看可以 |
| 核心什麼時候看 | **每一項跑之前**（含第一項） | 取鎖後、讀表前 |
| 核心看到時 | 這一項與後面的都不跑；**stderr 不印**（正常機制）；紀錄寫 `ended:true`、`exit:0` 與 `blocked_before`＝被擋下、沒跑的那一項（[P-213](../../protocol/tick.md)）；`after_all` 照跑（它跟任務無關，[B-635](../hooks.md)）；這格回 0 | 直接結束：一項都不跑、hooks 不啟動、不寫結束碼紀錄、不加 `seq`；**stderr 不印**（正常機制結束不印，[C-08](../../conventions.md)），回 0。所以人手或 cron 直接跑也被擋 |
| 誰刪 | **核心，整格最後**：`after_all` 跑完、回結束碼之前（〔AI 隊定、可改〕被擋下的格與最後才出現的〔例如 hook 寫的〕都刪；開格時不刪；是資料夾就整個刪） | **只有人手**，修好後刪；aos 不自動刪 |
| daemon | 不看它 | 現行 daemon 核心照常叫，由 `aos-tick` 自己擋；舊設計是有它就不開格（[B-607](../../deferred/daemon/registration.md)，在暫緩區） |

- **掛了 tick 模組 `modules["tasks-blocked"]`**（[B-636](../tasks-blocked.md)，第十六批）時，看到 tasks-blocked 不直接擋下：先依序跑那一串 inst（拿被擋下那一項的 `AOS_TASK_ID`／`AOS_TASK_INDEX`、碼不記），跑完再看一次，檔被刪了就放行這一項與後面的，還在才擋下。
- **開格時不刪**：格與格之間有人放的 tasks-blocked，下一格第一項之前就擋下（`ran:0`、`blocked_before` 是第一項），整格最後再刪。
- **跟 hooks**：hook 之間不看 tasks-blocked（hook 寫的也不擋下一個 hook，只擋下一項任務），整格最後一樣刪。被擋下、沒跑的任務不觸發 `after_task`、`after_every_task`；任務跑完接著跑它的 hook 時不看 tasks-blocked〔第十六批〕。`before_all` 在第一項的檢查之前跑，它寫的 tasks-blocked 會擋下第一項〔第十七批〕。
- 〔暫緩，`aos-git` 第十七批搬暫緩區〕**有 git 時，tasks-blocked 等於這格作廢**：排在後面的 `aos-git close` 不跑、不提交，下一格 `aos-git open` 把 aos 範圍還原（[B-630](../../deferred/git.md)）。想提早結束又保住結果的任務，別建它，改讓後面的項讀紀錄自己跳過。〔使用者方向 2026-09-30，納入 cgroup 與 git 疑-1〕
- 要知道這格是不是被擋下，讀紀錄的 `blocked_before`；外層要分出 `busy` 看 stderr。被擋板檔擋下的格什麼都不留（stderr 空、紀錄與 `seq` 不變），要知道就自己看擋板檔在不在。
- **tick 子篇裡還沒實作的程式**（`aos-git`、`aos-cg`、`aos-mq` 等）寫「建停格檔」的地方，現在讀成「建 tasks-blocked」；它們的設計是照舊停格檔寫的，回來實作時要照上表重看。

兩個檔都 ignored。檔名、stderr 細節是〔建議預設，未拍板〕；兩種都回 0 照 [C-08](../../conventions.md)。

使用者 2026-10-01 第十六批：「我們可以弄一個tick的module，用於設定讀取tasks-blocked的時候，要做的事情，類似hook，但是是在發現有tasks-blocked這個檔案之後，要做的insts」——已做成 tick 模組 `modules["tasks-blocked"]`（[B-636](../tasks-blocked.md)）。〔未來方向，記錄用、現在不做〕更早第五批記過的方向（停格檔變成特定 JSON、`aos-tick-check-task-continue` 檢查與改寫它）由 tick 那側來看已被第十八批定案取代（tick 不讀內容）；內容格式要怎麼用是 `tasks-blocked` insts 的事；會建停格檔的普通程式 `aos-tick-check-task`（[B-621](../../deferred/tick/03-B-624與B-621.md#暫緩b-621-前面的項沒跑好就停格aos-tick-check-task)）第十六批搬暫緩區。

### 任務的帳號

- **任務沒有 `user`**〔使用者方向 2026-10-01〕：inst 頂層沒有 `user`（[inst](../../../base/inst.md)），任務是 inst 的超集，所以也沒有；寫了就是陌生鍵、照收不理，一律用 tick 自己的帳號跑。原本「帶了不同帳號就那一項回 125」的歷史記錄在[暫緩區](../../deferred/tick/01-B-628上下層與B-602-B-620細節.md#暫緩b-620-任務的帳號125)，隨 `user` 一起撤回、不會回來。
- **tick 不切帳號**。要用別的帳號跑，就在 daemon 設定檔把它拆成另一項、指定帳號（帳號模組 `modules.account`，[plan m3m 模組五](../../../../plan/m3m-daemon-modules/06-模組五-帳號.md#模組五帳號modulesaccount)，還沒做）；單位是 daemon 的一項，不在一格裡面中途換。在 argv 包 `aos-as <帳號> --` 的做法〔使用者 2026-10-01 第十三批：「aos-as弄成暫緩。」〕搬到暫緩區（[B-303](../../deferred/helper.md)、[P-212](../../deferred/protocol/tick/01-P-207加入設定與P-212切換帳號.md#p-212aos-as切換帳號建議預設未拍板)）。
- 不另設服務帳號（第九批）；要 root 的固定步驟交給 helper（[B-609](../../deferred/daemon/helper-actions.md)）；管成員的事由上層 kernel 在自己的 tick 用自己的帳號做。任務類別不授予身分或權限。
