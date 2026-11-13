# kernel-chain-check：在獨立暫存樹驗證 kernel 鏈的七段整鏈行為（兩站的鏈＋照規則分流＋留著等表態）。

執行 `python3 proto8/extras/kernel-chain-check/check.py`；使用已安裝的 aos 指令，不 build、不安裝、不下載、不操作 git。每次用 `mktemp -d` 在 `/tmp` 建獨立樹。文件、註解繁中，程式輸出英文。

```text
root daemon
 ├ _clock
 ├ station_a     procs-kernel：沒寫 next，環境 AOS_KERNEL=foreman/requests，reply_via_me=true
 │               before_verdict：evil → exit 10
 │               after_verdict（ask）：body 的 hold_me 是 true → verdict=hold（留著等表態）
│               after_verdict（route）：body 的 lane 是 side → next=station_b/requests
 ├ station_b     procs-kernel（旁站）：沒寫 next、沒給 AOS_KERNEL，放行的進根 daemon 的 ctl 信箱，reply_via_me=true
 └ foreman       daemon-kernel：沒寫 next，身體的環境 AOS_KERNEL=foreman/requests（自己）
     │           max_running=4，queue=true，reply_via_me=true
     ├ agent     agent-fsm 範本；AOS_KERNEL=station_a/requests，AOS_DAEMON=foreman
     └ other     無關的測試 loop
```

驗證第 1、2、4、5、6、7、8 段；第 3 段「查詢信拿刪減表」等 aos-daemon 認 procs_state_path 後補，程式同處留 TODO。各站另掛只記錄事件的 hook，核對信件路徑、原回信箱、代回內容與每封信只進站一次；不改被測框架。

兩站的 `kernel.json` 都不寫 `next`，下一站靠三段裡的後兩段：`station_a` 的 `loop.json` 與領班的 `daemon.json` 都在站那支程式的 `exec.envs` 給 `AOS_KERNEL`＝領班的 `requests/`。A 照它轉給領班（A 沒設 `max_running`，不需要 `count_daemon`）；領班發現它指到自己就跳過、照 `AOS_DAEMON` 轉進自己的 ctl 信箱。hook 把自己看到的 `AOS_KERNEL` 記進事件，劇本逐封核對兩站都真的帶著這個值在跑。

- 第 1 段用現成 `llm_fake` 的 `script/tool_calls` 產生 `subagent add`，劇本手動跑這一輪的真 `lib/agent/subagent` 工具；工具內部走 `aos-agent ctl add`。agent-fsm 保持 idle，不另起問腦總機，也不假稱完整 FSM 問腦回合。另寄一封同型掛子信，保留最終信封，核對兩站代回後的 `in_reply_to`。
- 第 2、4、5、6、7、8 段，以及第 1 段的信封探針，由劇本帶 agent 的環境直接呼叫 `aos-post send/take-all/see/done`，走真 kernel 與 daemon。使用公開的 `procs_added`／`ping` body，沒有模擬框架的回信。每封探針有獨立的 agent 工具回信箱。
- 第 2 段先填滿四格，再確認額外信件留在領班 `queue.json` 且未掛上。測試 loop 讀到自己 stack 的 `finish` 標記後自然退非零，daemon 留下 stopped 列；空格釋放後驗證出隊、上表與代回。
- 第 4 段在滿格時送 evil，確認仍立即得到 `applied:false`／`HookRejected`，且信件未到領班。
- 第 5 段留兩封排隊信，透過自有根 daemon 的 shutdown 再起整棵樹，使 A 與領班各重起一次；根 daemon 與其他仍在跑的子項也一起重起。核對兩站 PID 改變、完整隊列與順序不變、A 的待代回對照不變；逐格釋放後核對原寄件人收到原信名的回覆、沒有重轉與多回。
- 第 6 段寄 ping，核對兩站 hook 與 daemon 回覆；再等數輪，檢查晚到的重複回覆。
- 第 7 段（照規則分流）：一個站、兩個下一站。A 多掛一個 `after_verdict` hook `route`（`condition: "pass"`），body 的 `lane` 是 `side` 就回 `{"next": <station_b 的 requests>}`，其餘不說話。寄兩封 ping（`lane` 各是 `side`、`main`）：`side` 那封只進 A 與 B、領班沒看到，回信由根 daemon 經 B、A 兩站代回；`main` 那封照舊走 A → 領班、B 沒看到；前面各段的信也都沒進過 B。兩封回信的 `in_reply_to` 都是原信名，A 的待代回對照清空，沒有晚到或多出的回信。
- 第 8 段（留著等表態）：A 再掛一個 `after_verdict` hook `ask`（`condition: "pass"`），body 的 `hold_me` 是 `true` 就回 `{"verdict": "hold"}` 並在 A 的 stack 記一列 `ask.jsonl`，其餘不說話。名字排序是記錄事件的 `after_verdict` → `ask` → `route`：記錄看到的是規則的 pass，`route` 給的 `next` 只在表態 pass 重判那次才算。寄三封 ping，各帶 `hold_me` 與一個額外鍵（`desc` 字串、`why` 物件、`desc` 物件）：
  - 三封都留在 A：`hold.json` 正好三列、`requests/cur/` 正好三封、`before_verdict` 只跑一次、`ask` 只被問一次，領班與 B 沒看到、寄件人沒收到回信；等一秒（數輪）再核一次，仍然如此。
  - 第一封寫 `decisions/<信名>.json`＝`{"verdict": "pass"}`（先寫暫存檔再改名）：照平常的路 A → 領班 → 根 daemon，回信 `{"applied": true}` 經兩站代回、`in_reply_to` 是原信名；領班收到的 body 跟寄件人寫的逐鍵相同；A 的放行事件兩筆（`decision` 依序 null、`"pass"`），`ask` 在重判時再被問一次。
  - 第二封寫 refuse（`NotNow`／`say what it is for`）：寄件人收到 `{"applied": false, "error": {"code": "NotNow", "msg": "say what it is for"}}`，領班與 B 都沒看到，`ask` 沒再被問。
  - 第三封另帶 `lane: "side"`，寫 pass 後由 `route` 分到 B、領班沒看到，回信經 B、A 代回，B 收到的 body 原樣。
  - 收尾：A 的 `hold.json` 是 `{"held": []}`、`decisions/` 是空的、`requests/cur/` 沒有信、待代回對照清空，沒有晚到或多出的回信。

所有 aos 啟動都由移除全部外來 `AOS_*` 的環境衍生，只加入本劇本需要的值；HOME、XDG 設定與快取都指到暫存夾，不讀寫任何既有樹。`aos-daemon-ctl` 永遠明給 `-d` 的自有絕對路徑；shutdown 前解析路徑、確認位於暫存夾並印出。清理只使用這個 shutdown，或對自己 `Popen` 記錄的 PID 送訊號，送前再次以 `/proc/<pid>/cwd` 核對；不按名字、命令列或行程群組收行程。

成功依序印 `ok 1`、`ok 2`、`ok 4`、`ok 5`、`ok 6`、`ok 7`、`ok 8`，清理也通過後印 `kernel-chain-check: 7/7 ok`、退 0。失敗印段號、原因與暫存路徑、相關 log 尾端，仍清理後退 1；若留下行程則保留暫存夾並回報，不擅自擴大收尾範圍。不寫證據／報告檔。

收尾以 `pgrep -af <本次暫存路徑>` 核對為空後才刪除暫存夾（`pgrep` 只拿來核對，不拿它的輸出送訊號）。機器上別的 daemon 一概不看、不碰。
