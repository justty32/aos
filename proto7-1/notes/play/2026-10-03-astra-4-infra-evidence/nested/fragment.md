# 巢狀、多 daemon 分支（合併素材）

入口依序讀 `proto7-1/README.md`、`spec.md`，再讀核心 spec、problems-core（尤其 P-04、P-10、P-11、P-19）與既有 play。沒有使用 kernel／agent、real.py、LLM。產品原碼未改。

證據：[reproduce.py](reproduce.py)、[results.json](results.json)。重跑：在 repo 根 `python3 proto7-1/notes/play/2026-10-03-astra-4-infra-evidence/nested/reproduce.py`。五個場景各建獨立 `/tmp/astra4-nested-*`；每場結束驗證 0 活程序、移除根。探針 driver 設 Linux subreaper 接住孤兒，以便 reap，**產品 daemon 並未設 subreaper**；這只改 orphan 的接收者，不把 runner 重新變成產品 daemon 的後代。PID 存活判斷排除 zombie。snapshot 非交易式；程序數可能包含當時執行中的 tick。

## 數字

三層路一：A 的 n 時間線經 `mnt/sub` 起 B，B 的 n 再經掛載起 C；C 的 n 起 leaf。每層 interval 150 ms，預建子 `.aosd/` 排除已知 P-11 干擾。所有 daemon 都只管自己的 n。TERM／KILL 施於最上層 A。

| 場景 | 最上層退出耗時 | A 退出後等 1.4 秒的子樹活程序 | 實際狀態 |
|---|---:|---:|---|
| 1 個正常 leaf，SIGTERM A | 113.50 ms | 0 | 三份 status 均 stopped/live=[]；B/C 的 task exit code 0，leaf -15 |
| 4 個忽略 SIGTERM leaf，SIGTERM A | 1,114.91 ms | 6 | B exit=-9；C 與其 runner 仍在，2 個 leaf 與其 runner 仍在。另 2 leaf 已分別收到 -9 |
| 1 個正常 leaf，SIGKILL A | 1.08 ms | 7 | B/C 均繼續到 round 12；2 daemon、3 runner、1 leaf、1 當時正在跑的 tick |

第二列的 C 正在逐一善後，**沒有宣稱這 6 個會永久存活**；量到的是父已宣告停止後，子樹仍未停止。第三列仍運作的 B/C 是已知 P-04 的三層新證據。

路二實測：兩個 daemon A=root、B=root/child，各有 n 與一個純 Python writer。共同 gate 就緒後，writer 只從自己的 `mnt/peer/ctl/` 寫 pause 對方 n。

| 掛載前置條件 | A→B | B→A | 兩邊回合 |
|---|---|---|---|
| 一般巢狀根：B 的 `../.aosd`，以及 B 內 symlink `parent-link`→A/.aosd | 成功 | 直路被拒、symlink 的 realpath 越界也被拒 | B 停在1；A 於400ms觀察窗 4→7 |
| 明示重排控制檔：A/.aosd→child/.parent-aosd；B 掛 `.parent-aosd` | 成功 | 成功 | A/B 均 paused，400ms窗都固定 round1；外部 JSON resume 後都到 round3 |

後者沒有 bind mount／FUSE／改產品；A 的 `.aosd` 是 bootstrap 建立的目錄符號連結，其實體放進 B root 之內，所以兩邊 task 的 peer 掛載都通過現行 realpath 檢查。這是**有前置配置的成環成功**，不能報成一般巢狀根開箱即雙向可控。S-22 本就允許使用者承擔成環風險；不把雙方停住另報 bug。

## 新問題／新證據

### N-1 跨 daemon 路二的可達性取決於控制檔實體配置，沒有文件化的外部控制端點匯入流程〔技術選型〕

重現：以上 cycle-native 場景，A mount `child/.aosd`，B 分別 mount `../.aosd` 與 `parent-link`（link→A/.aosd）。兩個 daemon 不共 root、不熱接管。看 birth.json：B 的 `?0.error` 是「目標要是空間裡的相對路徑」，`peer.error` 是「沿符號連結跑出空間根」；B 的 writer 找不到 `mnt/peer/ctl`，沒有對 A 的 pause。把 A/.aosd 實體移到 child/.parent-aosd，再讓 A/.aosd symlink 指向它，重跑即雙向成功且有回條。

這不是要求撤銷 M-13 的越界防護，也不視為其 regression；新證據是它對 **S-21 路二的多 daemon 組合**造成的操作前置條件。S-07 以 daemon 可訪問的資料夾作空間；proto7-1 又採 root realpath 包含關係，兩者在 import 外部 daemon ctl 時需要明確接法。需求是提供可檔案化、可查看的端點匯入／re-export 設定與失敗原因；是否允許哪些端點仍遵守核心「權限之後再說」。牽涉 S-01、S-07、S-21、S-23（S-22 是驗證成功環的預期行為）。

### N-2 正常 TERM 在三層巢狀下，也會先出現父 stopped 而孫仍運作〔技術選型；P-04 的量化新證據〕

重現：三層路一、最下層4個忽略TERM的leaf；SIGTERM最上層。A 1.11491秒退出，B 被升級成SIGKILL（exit=-9）。再等1.4秒，A status=`stopped/live=[]`，C 卻 `stopping=true`、還在逐個收leaf，尚有2 leaf 活著；總共6活程序。對照一般leaf，113.50ms全清。舊 P-04 已說一秒寬限可能不夠，這次新增**三層、4個任務即可出現的規模與跨層不一致狀態**，不另創 SIGKILL 孤兒問題。

使用者需要決定路一任務「結束」是否含它建立的整棵程序資源；實作可以採資源域／監督者／明示 shutdown 完成協定，不宜讓祖先一秒 deadline 與後代每任務一秒串行 deadline互相打架。若只承諾直接子程序退出，檔案狀態至少要把 shutdown-incomplete／remaining-resource 或 unknown 說清楚；父 `live=[]` 只能證明自己時間線沒有直接活任務。牽涉 S-01、S-03、S-06、S-10、S-21。S-21 不要求 daemon 理解父子角色，故可以通用「任務資源域」實作，毋須寫死 daemon 階層。

## daemon／tick 需求候選（重點）

| 需求 | 優先 | 證據 | 核心對應 | proto7-1 現況 |
|---|---|---|---|---|
| 每個 tick 起的任務需有可回收的資源歸屬；若聲稱已 kill，必須有直接任務／整個資源域的明示範圍及未收完結果 | 必要 | term-stubborn：A stopped 後仍6活程序；kill：B/C繼續到12 | S-03、06、10、21；整棵kill語意未定，機制為選型 | **部分**：pgid與當時後代快照，無持久資源域；只能收得到尚未reparent的後代 |
| 停機 deadline 能跨多層組合；批次 TERM 後統一等待，或傳遞剩餘期限／shutdown completion，而非每層互相競爭一秒 | 應該 | 4 leaf 即造成B -9、C仍善後；正常leaf113.5ms成功 | S-06、09、21；deadline細則未定 | **未做到**：外層1秒、內層逐個各1秒 |
| 明確提供別的 daemon ctl 端點的匯入／re-export 方法，保留掛載範圍與人可讀拒絕結果 | 必要 | native反向拒絕；re-export後合法雙向成環 | S-07、21、23；匯入介面未指定 | **部分**：同root範圍能掛；外部端點須手動重排檔案系統，README/spec沒寫流程 |
| pause 全部時間線後，daemon 控制面仍能讀 ctl、留下回條並接受外部resume | 必要 | cycle-reexport互pause後，外部resume兩邊均到round3 | S-18、21、22 | **已做到**；不需替使用者解環 |
| 空間目錄／status 應表達 daemon 實體端點、該 daemon 管哪些時間線、狀態新鮮度與關閉範圍，允許只靠檔案逐層盤點 | 應該 | 三層每份status只列n；root欄是越來越長的task mount alias；父stopped不能推出孫停止 | S-01、13、14、21；總目錄格式未指定 | **部分**：有局部status、birth.mounts，可人工追連結；无總索引/owner世代/停機涵蓋範圍 |

## 清理

results.json 每個場景均 `cleanup.active_processes: 0`、`root_removed: true`；五個空間已刪除。證據最大單檔 results.json 38,892 bytes（<200KB）。
