# llm cpu：精簡總結與 proto5 方案（2026-09-22）（精簡版）
完整版：[../notes/2026-09-22-investigations/2026-09-22-llm-cpu-summary.md](../notes/2026-09-22-investigations/2026-09-22-llm-cpu-summary.md)

## 結論

Claude 建議 proto5 把問模型做成「交一個請求檔，結果寫回指定檔案，agent 用 `waits` 等」。llm cpu 自己同步問一件，容量交給外面決定要開幾顆；不用 proto4 那套以背景 worker 與 PID 為中心的排程。這仍是待使用者決定的方案，並非已實作或已拍板。

同步問法繼續保留：`engine.cpu` 有路徑就交出去，沒寫就照現在同步問，方便測試與小 agent。llm cpu 先把交件外框定好，日後 tool cpu 也能沿用。

## proto4 的實際做法與教訓

| 層次 | 怎麼做 | 最需要記住的限制 |
|---|---|---|
| 第一層 `aos-llm` | endpoint 決定 URL、model、timeout、key；request 帶 messages、params、tools 等，禁止自帶 model。同步 HTTP 後回 `ok/text/usage/ms/raw/error` 大包裝 | 不重試；tool calls 藏在 `raw.choices[0].message`，不是頂層欄位 |
| 第二層 llm-cpu | `requests/` 排隊，移到 `requests/running/` 派背景 worker；worker 同步 HTTP、寫 `results/`，後續 tick 搬到 `requests/done/` | 每個 endpoint 有容量，按 priority、mtime 排序；排隊沒有期限，兩個 tick 同跑沒有鎖 |
| 一次 tick | 先收尾：有結果就 done，PID 死了記 `worker_died`，超過 timeout 加 5 秒便 TERM；再驗件、排序、派工 | hard timeout 只送 TERM，不確認 worker 真死，舊 worker 仍可能回寫 |
| 掛入 kernel | 既可獨立 tick，也可當 module，家固定 `K/llm`；投遞透過 syscall，先等收件回音，`--wait` 才另外等結果 | 同名同內容用 SHA-256 指紋接回既有單；收件成功不代表模型成功 |
| agent 的 ask | 組 request，呼叫 kernel CLI，以 `<name>-e<epoch>-q<題>-s<步>` 命名；同步等收件，把結果路徑存進 `state.request` | agent 沒在 ask 等模型回答，而是轉到 wait |
| agent 的 wait／act | 查不到結果就退 101；第 600 次記錯回 idle。有結果驗收後轉 act，接 assistant、同步跑工具、接 tool，再 ask | 600 是查檔次數，不是秒；等太久不撤單。所謂「連錯 5 次」其實是同題累計，成功輪不清零 |
| kernel | module hook 在 kernel 行程直接執行；syscall 回音只有 `{ok,msg}` | 101 只讓出後續執行機會；kernel 不知道 agent 等哪個檔 |

幾個已辨識的坑：worker 開了但 PID 尚未存回，下一 tick 可能誤判死亡；CLI 收件逾時刪單時，kernel 可能已讀入記憶體，結果仍會送出；`--wait --json` 的 stdout 還有結果路徑文字，不能當作單一 JSON。

## proto5 的家、請求與結果

| 位置／項目 | 擬定內容與責任 |
|---|---|
| `llm-cpu-A/info.json` | `{"_metainfo":{"_type":"llm_cpu","_version":1}}`；其他欄位以後再談，長相沿用 agent 資料夾 |
| `requests/<name>.json` | 排隊單：`{"engine":{...},"body":{...},"result":"/abs/path/ask-result.json"}` |
| `running/<name>.json` | 同一張請求 rename 過來，代表已認領、正在問 |
| `done/<name>.json` | 問完後保存同一張請求 |
| `engine` | 帶 endpoint、model、params、api_key、timeout_ms；指示詞由 agent 先解好 |
| `body` | `aos_llm_ask.build_request()` 已組好的 chat/completions body；cpu 不再讀 agent 資料夾、不再解指示詞 |
| `result` | 絕對結果路徑。成功寫 `{"ok":true,"message":<choices[0].message>}`；失敗寫 `{"ok":false,"error":"白話錯誤"}` |
| 寫結果 | 先寫 `.tmp` 再 rename，避免 agent 讀到半份 |
| 請求名稱 | agent 取名，建議 `<agent 資料夾名>-<epoch ns>`。同名已在 requests、running、done 任一處便拒收 |

**撞名如何回報還沒定**：可以由 cpu 寫 `ok:false` 結果，也可以讓 agent 寫入前先檢查。原文沒有替這個細節選定答案，不能當作已經解決。

## `aos-llm-cpu [dir]` 一次做什麼

| 次序 | 動作 | 理由／邊界 |
|---|---|---|
| 1 | 先處理 running 中超過 `engine.timeout_ms` 加寬限仍未完成的單：寫失敗結果，搬 done | 用來處理上次 cpu 崩掉留下的工作；寬限長度原文尚未指定 |
| 2 | requests 按檔名排序拿第一件，rename 到 running 認領 | 多顆 cpu 搶同一份，rename 失敗者拿下一件；方案不另設鎖 |
| 3 | 直接同步呼叫 `aos_llm_ask.call(engine, body)` | 成功寫 message；遇 `EngineFailed` 寫白話錯誤，再搬 done、退 0 |
| 4 | requests 空了就退 101 | 沒事可做，交回排程 |

容量等於同時跑這個家的 cpu 數量，由 kernel 管；cpu 不設 `max_concurrent`。第一版不重試，連敗由 agent 處理；不設優先序，先按檔名拿件；不記 usage，這些有需要再加。之後分別寫成 `spec/llm-cpu.md` 與 `spec/aos-llm-cpu.md`。

## agent 的 think 怎麼交出、收回

`info.engine` 新增可選 `cpu` 路徑。沒有它就沿用同步模式；有它則用 agent 家裡的 `ask-result.json` 判斷這次要送出還是收回。

| think 進場看到 | 動作 | 寫回與退出 |
|---|---|---|
| 結果檔存在，`ok:true` | 把 message 接入記憶，結果 rename 成 `.done` | 按回覆進 act 或 idle，退 0 |
| 結果檔存在，`ok:false` | stderr 一行，記憶不動，結果 rename 成 `.done` | 留在 think，退 0 |
| 結果檔不存在 | 寫 `cpu/requests/<name>.json`，結果路徑指向 agent 的 `ask-result.json`；再向 waits 加 `"ask-result.json"` | think 不變，退 0 |

waits 不開 `consume`，因為 think 自己負責 rename。下次執行時，門看到結果還沒到就退 101；到了就劃掉等待條件、進 think 收回。因此方案不新增狀態，也不另加記路徑的欄位。

順序一定是**先寫請求、再加 waits**。崩在兩者之間，下次可能重送；原文提出同名拒收擋掉或容許多問一次，尚未定案。若反過來先加 waits，崩掉後可能根本沒有請求，卻永遠等結果。現有「think 先看記憶尾巴是否為帶 tool_calls 的 assistant」自癒仍保留。

規範要跟著更新：think 的原兩列拆成送出／收回；移除「aos-agent 只劃不加 waits」；把原先附帶說明的 llm cpu 移到正文。

tool cpu 日後可用相同外框：請求帶解好的 `inst`、arguments 作為 `stdin`、結果路徑；回 `{ok,code,stdout}`。act 交件、加 waits，門開了再依順序接 tool 訊息。

## 六題要使用者拍板

| 題號 | 問題與選項 | Claude 的建議與理由 |
|---|---|---|
| 1 | **請求帶不帶完整 engine？** A：完整帶上，含 api_key；B：cpu 自管 endpoint 表，agent 只寫名字 | **A**。agent 已解好，直接交最簡單；B 多一份設定與名稱對應。key 會落地到 cpu 家，是否接受由使用者決定 |
| 2 | **結果寫哪裡？** A：寫回請求指定的 agent 路徑；B：留在 cpu 家 `results/<name>.json` | **A**。與 input、waits 同一處，權限簡單；B 需要 agent 記住外部結果路徑 |
| 3 | **怎麼交件？** A：agent 直接寫 cpu 的 requests；B：透過 kernel syscall | **A**。直接寫最直；B 沿用 proto4-5 路線，但 proto5 kernel 還沒有 |
| 4 | **cpu 長怎樣？** A：一次同步問一件，開幾顆就是多少容量；B：tick 派背景 worker | **A**。不用 worker、PID；B 雖讓 tick 很短，卻帶回收屍、PID 與 hard timeout 那整套複雜度 |
| 5 | **同步與交出如何切換？** A：有 engine.cpu 才交出，沒有就同步；B：一律交出 | **A**。測試與小 agent 保留同步較方便 |
| 6 | **如何分辨送出與收回？** A：看 ask-result.json 在不在；B：state.json 加 ask 欄位記路徑 | **A**。用結果檔就能分辨，不增加狀態欄位 |
