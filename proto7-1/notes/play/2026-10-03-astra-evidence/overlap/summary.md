# 共享資料夾與巢狀 daemon 實測

入口閱讀順序：`README.md` → `spec.md` → 自寫與執行 `run.py` → `core.md`／`problems.md` → `takeover-routing.py` → `problems-core.md` 去重。**完全沒有讀產品程式碼。** 場景均在新的 `/tmp/astra-overlap-*`、`/tmp/astra-route-*`；全部自行啟動的 daemon 已 stop，任務 PID／runner PID 複查沒有非 zombie 活程序，見 `cleanup.json`。

## 覆蓋與可用證據

- **兩條時間線共同管理同個額外資料夾：** `alpha`、`beta` 每條 interval=100 ms，各 `each` 任務宣告 `dirs: ["../mail"]`；新程序 cwd 為各 node，向 `../mail/events.jsonl` append。跑到 alpha 第 25 回合才 stop kill，兩方各寫 99 筆事件（第 25 回合最後一次寫入被 stop 打斷）。兩邊 birth.json 中 `dirs[1]` 都解析成同一絕對路徑。共用資料夾可行，資料協定與衝突沒有由時間線代管；這是 D-1／S-15 目前選型的證據，不重報成新 bug。
- **同一 root 重開：** 第二個 daemon 退出碼 1，stderr 是 `aos7-daemon: <root> 已經有 daemon 在跑`。符合文件，不是問題。
- **正常巢狀：** 預建 `team/sub/.aosd/`，父的 team 時間線 keep 起子 daemon；子 root 是 team/sub，其 unit 時間線 keep 起 sleeper。不讀碼就搭得成。父 team 第 6 回合時子 unit 第 10 回合。往父 ctl 寫 `stop, kill:true`，兩個 daemon 都 stopped，子 daemon 任務 code 0，sleeper code -15。這重現 I-1，沒有新問題。直接寫子 root ctl stop 亦成功，證明 S-21 路二的控制形式相同。
- **活躍子樹被新 daemon 接手：** 父原本管理 `child/work`，在第 3 回合起 `aos7-daemon <root>/child`。父 `nodes` 變空，子從原 round 接著跑到 12，子 status 的 node 叫 `work`，但活任務 birth.node 仍叫 `child/work`。子 stop 後 `.aosd/` 持續存在，父沒有重新納管（父 nodes 仍空）。後者符合 spec 掃描規則，不重報。

## 可納入報告的「已知問題新證據」

### P-10／P-02：管轄轉移後，錯送的自我 pause 會收到成功回條，真正時間線仍繼續跑

- **重現：** 跑 `python3 proto7-1/notes/play/2026-10-03-astra-evidence/overlap/takeover-routing.py`。它先在新 root 的 `child/work` 起一個常駐任務；任務只使用 spec 所列 `AOS7_ROOT`、`AOS7_NODE_ID`。父跑到 3 後，啟動以 `child` 為 root 的新 daemon；新 daemon 接到第 8 回合，讓舊任務依自己的環境往 `<AOS7_ROOT>/.aosd/ctl/self-pause.json` 寫 `{"op":"pause","node":"child/work","by":"self-control-r1"}`。
- **看到什麼：** `takeover-routing-results.json` 同時保存 task environment、birth、父子 status、控制回條及前後 round。舊父回 `result.ok: true, msg: "pause child/work"`，但父已 `nodes:{}`；真正管理者子 daemon 的 `work.paused:false`，回合從 8 走到 13，`live:["self-control-r1"]`。這比「ROOT 沿用舊值」多了實際控制已被接受卻完全沒作用的證據；只看 ctl-done 的 LLM 會認為 pause 成功。
- **牽涉：** S-01、S-14、S-15、S-18、S-21。
- **分類：** 〔技術選型〕（P-10 既有的跨 root 接手與身分問題的新證據；不是另立一個「巢狀 daemon 不支援」）。若報告另有「不存在 node 的 pause 仍回成功」案例，可合併避免重複。
- **後果而非替使用者選：** 任務對「控制已成功」的信任，不能只依 ctl-done.ok；還需知道此刻由哪個 daemon 管該資料夾並檢查其 status。這多了一項 S-01 使用者必須拼接的狀態。

## 對 D-1～D-4 的證据範圍

D-1：相同共享 dirs 確實可給兩條時間線並行讀寫，屬可運行方案；本次只做 append，不足以證明任意 JSON 覆寫安全。D-2：兩條自訂 each 時間線能各自前進，父子 round=6/10 也顯示不能拿跨 daemon round 直接比較；沒有替使用者判斷應採用哪種同步。D-3：本組沒有單獨做 keep kill 後復活，不重複已有結論。D-4：本組沒有把 pause 後 task kill 當新證據。
