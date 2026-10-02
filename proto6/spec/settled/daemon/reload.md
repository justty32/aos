# daemon 重讀設定模組：改了設定送 SIGHUP

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[控制 B-641](control.md)｜[記住狀態 B-643](state.md)｜格式：[P-122](../protocol/daemon/reload.md)

本篇只有 B-642，寫重讀設定模組**做什麼**。設定怎麼寫、stdout／stderr 的行、結束碼，寫在格式篇 [P-122](../protocol/daemon/reload.md)。

依據：[verdicts 11 篇末「2026-10-01 第十一批：daemon 模組」](../../../notes/verdicts/11-tick-as-unit/13-1001-第十十一批.md#2026-10-01-第十一批daemon-模組)、[plan m3m 模組一](../../../plan/m3m-daemon-modules.md#模組一重讀設定modulesreload)；現行程式 [重讀設定](../../../src/py/README.md#重讀設定與記住狀態m3m)（`lib/aos_daemon_reload.py`，有出入以程式為準）。

## B-642：重讀設定模組〔使用者 2026-10-01 第十一批〕

**改了設定檔，送 daemon 一個 SIGHUP，daemon 就重讀同一份設定檔、照新的清單跑，不用重開。** 它是 daemon 的一個模組（[B-640](core.md)「模組」），設定檔寫了 `modules.reload` 才有。

- 觸發只有 SIGHUP（人手 `kill -HUP <pid>`）。控制 socket 不收 reload（[B-641](control.md)「四個指令」照舊）。不自己偵測設定檔改了沒。
- **沒掛這個模組時，SIGHUP 照 Python 預設：daemon 被殺**（跟只有核心時一樣，socket 檔不刪）。
- 重讀照開起來時的規則：整份展開指示詞、`$ref` 以設定檔所在資料夾為準（[B-640](core.md)）。

### 跟現在的清單比對

| 情況 | 怎麼辦 |
|---|---|
| 新出現的鍵 | 加成新的一項，照「開起來先跑一次」**立刻跑**；stdout 印 `added` |
| 不見的鍵 | 不再排下一次。**正在跑的那次不殺**，讓它跑完、照樣印 `exit=` 那一行；之後控制指令對它回 `unknown_inst`；stdout 印 `removed` |
| 鍵還在 | 原地換成新設定（`interval_ms`、`stop_on_nonzero`、第幾項；掛了 cgroup 模組還有上限，[B-644](cgroup.md)）；**暫停、已停、待補照留** |
| 頂層 `cwd`、`modules`、`exec_out_path`、`exec_err_path`、`lock_path`〔第十九批〕改了 | **不套用**，stdout 每個印一行警告說要重開；其他照套。新加的項的輸出路徑也照開起來時的設定算 |
| 頂層 `exec_output_max_bytes` 改了〔第十九批〕 | 照套，每一項下一次起用新上限 |

- **`interval_ms` 改了**：下一次＝**上一次結束時刻＋新週期**；那個時刻已經過了就立刻跑。正在跑的，跑完照新週期算。還沒跑完過一次的（例如開起來就恢復成暫停的）照原本的排程。
- 拿掉的鍵之後又加回來：當成新的一項，狀態從頭（不暫停、不停、立刻跑）。
- 改了這四個頂層鍵，每次重讀都會再印一次警告，直到重開或改回來。`modules` 裡任何改動（加減模組、換控制 socket 路徑、換狀態檔）都算。`exec_out_path`／`exec_err_path` 比的是設定裡寫的原字（含 `<inst>`），〔2026-10-01 第十二批〕原本「照新的算、下一次寫出起生效」改成不套用、警告（使用者照建議：最上層的 cwd、modules、exec_out_path 這些改了 → 不套用、印警告，改成 stdout 警告）。
- 不認得的頂層鍵照收不理，不另外印。

### 重讀時設定壞了

JSON 壞、指示詞錯、缺 `interval_ms`、型別不對……**整份不套用**，stderr 印一行，舊設定照跑，daemon 不退出。改好再送一次 SIGHUP 照常套用。這是本模組唯一的異常處理：照 POC 總原則本該「自然丟錯、回 1」，但那會把一個跑得好好的 daemon 打掉（使用者 2026-10-01 同意 R4 建議）。

### 跟其他模組

- **控制模組**：不用改；它查的清單就是重讀後的清單。新加的項一樣拿得到 `AOS_DAEMON_SOCKET`、`AOS_DAEMON_INST`。
- **收屍／cgroup**（[B-644](cgroup.md)）：新加的項建框、印對照；上限改了重寫；拿掉的項最後一次跑完、清完才刪框。建框、寫上限出錯算重讀出錯（下一節）。
- **記住狀態**（[B-643](state.md)）：重讀**以記憶體為準**，不重讀狀態檔、不拿檔覆蓋還在的項；新加的項一律從頭。套用完照記憶體寫一次狀態檔，拿掉的項就從檔裡不見了（內容沒變就不寫）。

依據：使用者 2026-10-01 第十一批：「R1～R4 都照 plan 建議」，R3 改「如果最上層這些改了，那就stdout輸出警告。」；第十二批 `exec_out_path`／`exec_err_path` 併入要重開的鍵。

**驗收：**兩項跑著，加第三項送 SIGHUP：第三項幾秒內有 `exit=` 行、stdout 有 `added`、`reloaded`，原本兩項沒多跑；拿掉正在跑的項：那次照樣印完 `exit=`、之後沒有它的行、`status` 回 `unknown_inst`；`interval_ms` 從 10 秒改 100 毫秒後很快密集跑；暫停中、已停的項重讀後照舊；設定改壞送 SIGHUP：daemon 沒死、stderr 一行、舊設定照跑，改回來再送一次照常套用；改 `cwd`：stdout 有 `need restart`、各項照舊跑；改 `exec_out_path`／`exec_err_path`：stdout 有 `need restart: exec_out_path`／`exec_err_path`，照舊寫原本的檔（新加的項也是）；沒掛模組時 SIGHUP 殺掉 daemon。測試見 `proto6/src/py/tests/test_daemon_reload.py`。
