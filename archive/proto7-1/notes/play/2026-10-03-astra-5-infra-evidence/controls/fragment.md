# astra-5 controls 分工實測

證據：`repro.py`、`results.json`、`run.log`。從任何 cwd 執行 `python /絕對路徑/proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/controls/repro.py` 即可重現。全部只起 `sleep`／`true`、本地 tick／daemon，不跑 real.py、不打 LLM。臨時空間用 `/tmp/astra5-controls-*`；finally 停 daemon、以 node 環境盤點殺殘留，再刪空間。

## 新問題／邊界

### C-01 壞 batch 項目令前綴重播、後綴與普通任務永遠不起〔bug〕

- 重現：tasks.json 放 `regular: true`；spawn `poison.json` 放 batch `[prefix: true, {name: 7, argv:["true"]}, suffix: true]`；連跑兩次 tick。
- 實際：兩次皆 rc 1，`new_tid` 的 `re.sub` 拒絕 int name。只有 `prefix-r1`、`prefix-r2`；suffix、regular 一次也沒啟動。poison 檔仍在，故下輪還會重播前綴。round.json 的 started 都是空陣列，已起的 prefix 未納入 tick 回傳／記錄。
- 核心 S-06、S-09、S-10；N-21「已做」仍不成立，N-34 應改「有效 batch 同回合可用；壞項目隔離未完成」。建議在 spawn／一般表共用完整的項目驗證與逐项錯誤紀錄；病項不能無限重試阻塞整線。重播屬 N-19 已選的至少一次，不重新要求 exactly-once；問題是永久毒項造成無限重播、後面健康工作飢餓。
- 優先必要，與主線 name 型別攻擊合併，不另算一個根因。

### C-02 wake 洪水仍能讓控制主迴圈整批失去回應〔技術選型〕

- 重現：一個已 paused 的 node，暫停 daemon 的程序後預排 10,000 個 wake 檔，恢復程序；第一個回條出現時再排 stop --kill。
- 實際：stop 回條晚 0.401 秒，整批排空 0.411 秒；每 0.1 秒觀察的 status.at 全不變。status 宣告 poll_s=0.02。這只是一次本機量測，不宣稱永久死鎖；`handle_ctl` 對進門時整份檔名快照全數處理，沒有時間／數量上限，queue 愈大延遲可繼續增加。SCAN_BATCH 不限制這條路。
- 核心 S-06、S-18；N-17 保持必要／部分，但證據要加入控制輸入本身的洪水。建議每圈控制件數或時間預算，wake 同 node 可合併；保持排序語意，別為搶 stop 任意顛倒既有控制順序。N-16 ctl-done 只增不減仍是獨立問題。

### C-03 wait-tock 對合法 JSON 非物件直接 traceback〔bug〕

- 重現：taskdir/tock.json 分別寫 `[1]`、`2`，執行 `aos7-wait-tock --task <dir> --after 1 --timeout .05`。
- 實際：都 rc 1 並 AttributeError（`.get` 不存在），不是等 timeout。壞 round 字串則會正常等 timeout；正常 `round:3` 印 3 並 rc 0，沒有新回合則 rc 1、無輸出。
- 核心 S-01、S-06、S-11；N-51 的非 Python helper 已存在但防壞資料不完整，併 N-21 的 JSON 型別防線。加入 `isinstance(t,dict)`、round 排除 bool；此修補不改 tock 通知／漏回合的既有語意。優先應該。

### C-04 對不存在 node 的 wake 回條承諾與實作不符〔bug，次要〕

- `Daemon.apply({op:"wake",node:"future"})` 回 `true, "wake future（目前沒有這個 node，出現時才生效）"`，但不存 pending wake；新 Timeline 的 kick=false。
- 新 node 本來就立即起第一回合，所以尚未找到會延迟首回合的功能損害；這是回條措辭錯誤，不應擴大成丟工作。N-10／N-09 小修：wake 對不存在 node 說清目前無對象、沒有排程作用；不要沿用 pause／resume 的持續設定承諾。

## 通過與不可誤讀

- resume/pause/resume：r1 running 下 pause，status 為 paused=true、pause_pending=true；tock 完變 phase=paused、pause_pending=false。之後 `resume rounds:2` 正好到 r3 又 pause。N-06、N-08 這條路通過。
- pause_pending 還沒停穩就 `resume rounds:1`：當時 r7 仍 running，r7 tock 完就停，沒有額外 r8。符合 spec「第 N 次 tock 完自動 pause」的現有實作；上層若要完整新 N 回合，先等 phase=paused。不要拿此現象另外要求使用者決策。pause_pending=false 時 live 仍非空也符合 pause 不 kill／不搶佔（N-32 已答 D-4）。
- edit_json：holder 已拿 flock、進 callback，尚未寫入就 kill -9（rc -9）；後續 edit 在 0.098ms 取得鎖，原值 0 變 1。留下 `.lock` 檔不表示鎖仍被持有，毋須刪鎖檔。N-33 在此中斷點通過；本測試不主張 callback 外部副作用具事務性。
- max_live=2：手動四次 tick 後恰有 s-r1、s-r2 兩個活 sleep；第五次 tick 的合法三件 batch 全為 round=5。N-36 與 N-34 正常輸入通過。

## 給需求清單的修正

1. N-21 由已做改部分（必要）：birth/tock 個別保護不等於完整起任務／spawn／ctl／wait_tock 防線。
2. N-17 保持部分（必要），補控制洪水公平性，不能只列 20 條線的冷啟動節流。
3. N-34 改部分（應該），有效 batch 可用但毒項使整批與後續 tasks 飢餓；修復需求與 N-21 合併。
4. N-51 改部分或註明 malformed shape 未防（應該）；與 N-21 交叉引用，毋須另造需求號。
5. N-06、N-08、N-33、N-36 本組正常路徑／指定 kill 點通過；只補 resume rounds 以收訖後 tock 計數的說明。
6. 沒有需要重新問使用者的核心語意選項。
