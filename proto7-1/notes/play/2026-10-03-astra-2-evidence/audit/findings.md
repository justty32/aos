# 掛載邊界與 AOS7_AUDIT：第二輪證據

入口是 `proto7-1/README.md`，再讀 `spec.md`、核心 S-01～S-23、第一輪報告與 `notes/problems.md`。沒有改產品。重跑：

```sh
python3 proto7-1/notes/play/2026-10-03-astra-2-evidence/audit/reproduce.py
```

腳本建 `/tmp/astra2-audit-*/space`，所有五個任務都是 `aos7-tick` 真正啟動，環境設 `AOS7_AUDIT=1`。第 1 次 tick 起五個短任務；第 2 次 tick 審核加掛。五個任務退出碼都是 0。腳本等任務與 runner 不再執行後刪掉整個暫存空間。未啟動 daemon。

完整原始檔保留在 [raw-files.json](raw-files.json)，每個鍵是原檔相對暫存根的位置，每個值是原檔文字。摘要、檔案實際位置、連結目標、tick 輸出及 scan 結果在 [results.json](results.json)。這次 `scan` 回 `tasks: 5, writes: 62`，僅三筆 `bad`，都是 baseline 任務預期的越界測試。

## 新發現 1：允許清單審核通過的符號連結可以指向清單外，甚至空間根外〔bug〕

**重現步驟：**

1. 建 `a`、`b`、`c` 三個 node，a 的 tasks.json 設 `mount_allow: ["allowed"]`。
2. 在空間根建 `allowed/inside -> <root>/c`、`allowed/outside -> <root 的同層>/outside`；後者仍是本次暫存目錄，沒有碰真實使用者資料。
3. 由 tick 起 request 任務，寫兩份 mount-req：`{"name":"inside","path":"allowed/inside"}` 與 `{"name":"outside","path":"allowed/outside/new-created-by-tick"}`。
4. 下一次 tick 審核。任務等回條後，只經 `mnt/inside`、`mnt/outside` 寫檔。

**看到什麼：** 兩份 mount-done 都是 `ok:true`。第一份寫入真實 `c/via-approved-link.txt`，audit 標 `ok:true`。第二份讓 tick 在空間外建出 `outside/new-created-by-tick/`，任務再寫入該處，audit 完全沒有那筆。這不是任務自己用絕對路徑偷寫，而是審核器正式批准並建連結、建立目標資料夾。

M-1 已知符號連結不強制隔離；新增的是「已有明確 mount_allow 時，審核成功仍可導向清單外／空間外」。M-10 的沒寫允許清單全給不適用，這裡明確寫了清單。細部 spec 宣稱目標不能跑出空間根，實作卻只檢查字面路徑。S-14 允許符號連結的命名細節隨意，不能單凭它推論這樣的實際邊界是預期設計；若想把允許規則定成純邏輯別名，需另說清楚，此處以現有細部 spec 判 bug。

**牽涉：** S-23、S-10、S-07；回條不能揭露實際目標也影響 S-01。

**證據位置：** raw-files 的 `space/a/.aos/tasks/request-r1/mount-done/{inside,outside}.json`、birth.json、writes.jsonl；results 的 symlinks 與 actual_files。

## 新發現 2：Python 的 dir_fd 寫檔會被 audit 記成錯誤位置且通過〔bug〕

**重現步驟：**

1. a 的 dirfd 任務不掛任何目標，cwd 是 a。由 tick 啟動。
2. `fd = os.open(<root>/b, os.O_RDONLY | os.O_DIRECTORY)`。
3. 用 `os.open("dirfd.txt", os.O_CREAT | os.O_WRONLY, dir_fd=fd)` 寫檔；另以相同 fd 作 mkdir、rename、unlink。
4. 對照真正的 b 目錄與該任務 writes.jsonl。

**看到什麼：** 真正新增 `b/dirfd.txt`、`b/dirfd-dir/`，把 `b/rename-src.txt` 改為 `b/rename-dst.txt`，刪掉 `b/remove.txt`。audit 卻依 cwd 記為 `a/dirfd.txt`、`a/dirfd-dir`、`a/rename-src.txt`、`a/rename-dst.txt`、`a/remove.txt`，全部 `ok:true`，scan 沒列出任何 dirfd 任務違規。這些 a 檔案並不存在。

這不是 M-3 的非 Python 缺口：是普通 Python 標準庫呼叫，而且 hook 的確記了事件，只是對路徑的解讀錯了。不能用「只記不擋」解釋錯誤位置與錯誤的 ok。

**牽涉：** S-10、S-23（audit 作為範圍檢查的實作）、S-01（讀到的文字證據誤導）。

**證據位置：** raw-files 的 `space/a/.aos/tasks/dirfd-r1/writes.jsonl`，results 的 actual_files、dirfd_mkdir_actual、dirfd_remove_actual。

## 新發現 3：改寫已掛載連結會讓 audit 自動承認未經 tick 批准的目標〔bug〕

**重現步驟：**

1. tasks.json 給 retarget 任務唯一宣告 `mounts: {"box":"b"}`。由 tick 啟動，先寫 `mnt/box/before.txt` 作正常對照。
2. 任務刪掉自己的 `mnt/box` 符號連結，重建成指向 `<root>/c`。
3. 不寫 mount-req、不改 birth.json，直接寫 `mnt/box/retarget.txt`。

**看到什麼：** birth.json 到結束仍宣告 `box.to = "b"`，也沒有給 c 的成功回條。但真實 `c/retarget.txt` 已寫成，writes.jsonl 正確記到 c 卻標 `ok:true`。hook 初次判不過時會重新以 birth 的 `at` 連結「現在指哪裡」作為允許目標，因此把任務自行改指的 c 承認為已掛範圍。

M-1 已知寫得出去；此處新增的問題是檢查工具也認證它合規，而且 `cat birth.json` 的批准目標與 `cat writes.jsonl` 的判定相互矛盾。不是要求此版變成安全沙箱，而是 audit 應忠實反映 tick 批准的範圍。

**牽涉：** S-01、S-10、S-23。

**證據位置：** raw-files 的 `space/a/.aos/tasks/retarget-r1/{birth.json,writes.jsonl}`；results 的 symlinks 與 `space/c/retarget.txt`。

## 已知問題覆蓋／新增證據，不重報

| 測試 | 實際結果 | 舊問題對照 |
|---|---|---|
| Python 寫未掛 b 的絕對路徑 | 寫成功，記到真實 b 路徑，`ok:false` | M-1 覆蓋 |
| Python `../b/dotdot.txt` | 寫成功，記到真實 b 路徑，`ok:false` | M-1 覆蓋 |
| a/escape 符號連結直接指向未掛 b | 寫成功，`ok:false` 並有 via | M-1 覆蓋；與正式加掛及改寫已掛連結不同 |
| `/bin/sh` 寫未掛 b | 寫成功，沒有該次 payload 寫入紀錄 | M-3 覆蓋 |
| sh 任務的 writes.jsonl／scan.tasks | sh 本身沒被 audit，但 Python runner 的 out.log、pid、exit 等操作產生 9 筆全部 `ok:true`，scan 仍把 sh 算一個有紀錄任務 | M-3 新證據：有 writes.jsonl 或 tasks 計數不表示任務 payload 被覆蓋 |
| 普通 Python 絕對路徑寫空間根外 | 寫成功且完全不記 | 已記載的 audit 範圍：細部 spec 明示只記空間根底下；不是新 bug，但 audit 全綠不能證明沒有寫出空間根 |

## S-01 判讀

正常加掛的 birth／mount-done 可以 cat。但上述正式加掛外逃只留下邏輯別名，沒有解析後實際目標；改寫連結後 birth 仍指 b、audit 寫 c 卻說 ok；dir_fd 的 audit 直接給錯位置。非 Python 任務甚至有一份全綠的 writes.jsonl。這些情形若只 cat JSON、不讀連結本身或核對真實落點，無法可靠回答「誰實際掛了誰」與「是否越界」。

清理：results 記錄 `all_started_pids_gone_or_zombie: true`，表示所有 payload／runner 已結束，沒有執行中的程序；reproduce.py 輸出 `temporary_root_removed: true`。不把作業系統尚未回收的 zombie 視為仍在執行的任務。

隨後再次檢查，10 個 payload／runner PID 的 `/proc/<pid>/stat` **全部不存在**，`/tmp/astra2-audit-*` 也沒有殘留。

## 事後定位（用來解釋實驗，不代替重現）

- 加掛符號連結：`lib/aos7_mount.py:27` 只拒絕字面絕對路徑與正規化後開頭 `..`；`:109` 的 `allowed` 用字串前綴；`:41` 取得尚未 realpath 的目標，`:45` 直接 mkdir；`:147`、`:153` 依此通過審核並建掛載。審核回條誤准與 audit 誤判才是此處的問題，並未假定原型提供強制隔離。
- dir_fd：`lib/audit_site/sitecustomize.py:50` 一律用 cwd 拼 path；`:78` 至 `:84` 對 rename、mkdir、remove 等事件只取路徑，忽略事件的 directory fd 語境。`open` 事件本身的可用參數也有限，因此採用哪種補足方式可另定，但不能把不知道的真實位置記為已知且合規。
- 改寫已掛連結：`lib/audit_site/sitecustomize.py:29` 以 `realpath(birth.mounts.*.at)` 作允許目標，`:54` 至 `:56` 在失敗時重載，因此自己改動 mnt 連結也能刷新准許範圍。
- 非 Python 全綠紀錄：`lib/aos7_audit.py:19` 只要有 birth 與 writes 就把任務計入 tasks，沒有區分 payload 與 runner 的紀錄覆蓋。
