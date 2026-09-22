# llm cpu：精簡總結與 proto5 方案（2026-09-22）

astra 唯讀調查了 proto4-5（兩層 LLM）、proto4-7（agent 怎麼交出去、等、收回）、proto4-3 kernel 的 module／syscall
（原報告 1098 行：`2026-09-22-llm-cpu-report-astra.md`）。這份是我的精簡版＋proto5 該怎麼做的方案；決策由使用者做。
跟 [act 總結](2026-09-22-act-summary.md)、[逾時總結](2026-09-22-timeout-summary.md) 一起看。

## 1. proto4 是怎麼做的（事實）

**proto4-5 第一層 `aos-llm`**：同步問一次。endpoint 設定檔（`name`／`kind`／`base_url`／`model`／`timeout_ms`／
`max_concurrent`／`api_key_env`）；request 檔（`messages`／`params`／`tools`／`priority`／`timeout_ms`，禁止 `model`）；
回一個大 envelope（`ok`／`text`／`usage`／`ms`／`raw`／`error{kind,msg,status,retryable}`），`tool_calls` 藏在
`raw.choices[0].message`。不重試。

**proto4-5 第二層 llm-cpu**：家目錄 `L/`＝`endpoints.json`＋`state.json`＋`requests/<id>.json`（排隊）→`requests/running/`
→`requests/done/`＋`results/<id>.json`＋`log/`＋`usage.jsonl`。一次 tick：收尾 running（結果檔在→done；pid 死→`worker_died`；
超過 timeout＋5 秒→TERM、寫 timeout）→驗新請求→照 `(-priority, mtime)` 排序→按 endpoint 容量派**背景 worker 子進程**
（worker 同步打 HTTP、寫結果）。可以獨立跑（`llm-cpu tick`）或掛成 kernel module（家固定 `K/llm`，投遞走 syscall＋收件回音，
`--wait` 另外輪詢結果）。同名同內容用 SHA-256 指紋冪等。**排隊沒期限、兩個 tick 同跑沒鎖、hard timeout 只 TERM 不確認死**。

**proto4-7 agent 四格**：`ask`＝組 request、寫本地檔、開子進程叫 `aos-kernel llm K req --name <name>-e<epoch>-q<題>-s<步>`
（同步等 kernel 收件回音，不等結果）、把**結果檔路徑**存進 `state.request`→`wait`；`wait`＝結果檔存在？沒有就 checks+1、退 101，
第 600 次記錯回 idle（不撤單）；有就驗 `result.ok`、`raw.choices[0].message`→`act`；`act`＝接 assistant、同步跑工具、接 tool→ask。
連錯 5 次 `stuck`（其實是同題累計，不清零）。

**proto4-3 kernel**：module 的 hook 直接在 kernel 進程裡叫；syscall＝`K/syscalls/<名>.json`→同名 `done/<名>.json` 回音
`{ok,msg}`；101 只是「讓出後續 cpu 執行機會」，kernel 不知道 agent 在等哪個檔。

**踩過的坑**：worker 開了但 pid 還沒寫回→下次 tick 誤判 `worker_died`；收件逾時撤單但 kernel 已讀進記憶體→其實送出了；
文件說「連錯五次」實際不是連續；`--wait --json` stdout 不只一個 JSON。

## 2. proto5 的 llm cpu：我的方案

原則：**跟 agent 資料夾同一套長相**（一個資料夾＋`info.json`＋子資料夾），**用檔案交件、用 `waits` 等**，**沒有 worker、沒有 pid**。

### 2.1 格式（之後寫成 `spec/llm-cpu.md`）

```
llm-cpu-A/
  info.json              {"_metainfo": {"_type": "llm_cpu", "_version": 1}}   （其他欄位之後再說）
  requests/<name>.json   排隊中：{"engine": {...}, "body": {...}, "result": "/abs/path/ask-result.json"}
  running/<name>.json    正在問（同一份，rename 過去＝認領）
  done/<name>.json       問完（同一份）
```

- **請求檔**＝agent 那邊 `aos_llm_ask.build_request()` 已經組好的東西：`engine`（endpoint／model／params／api_key／timeout_ms，
  指示詞已解完）＋`body`（chat/completions 的 body）＋`result`（結果要寫到哪，絕對路徑）。cpu 不解指示詞、不讀 agent 資料夾。
- **結果檔**（寫到 `result` 指的路徑，先 `.tmp` 再 rename）：`{"ok": true, "message": <choices[0].message>}` 或
  `{"ok": false, "error": "<白話>"}`。就這兩格。
- `name` 由 agent 取（建議 `<agent 資料夾名>-<epoch ns>`）；同名已在 requests／running／done 任一處＝拒收（拒收也是寫一個 `ok:false` 結果？
  還是 agent 寫檔前先看？——待定）。

### 2.2 程式（之後寫成 `spec/aos-llm-cpu.md`）

`aos-llm-cpu [dir]`，一次做一件事：

1. 先收屍：`running/` 裡超過 `engine.timeout_ms`＋寬限還沒 done 的（上次 cpu 崩了）→寫 `ok:false` 結果、搬 `done/`。
2. `requests/` 照檔名排序拿第一個，**rename 到 `running/`＝認領**（兩顆 cpu 搶同一份，輸的 rename 失敗就拿下一個；不用鎖）。
3. `aos_llm_ask.call(engine, body)` 同步問；成功寫 `ok:true`＋message、`EngineFailed` 寫 `ok:false`；搬 `done/`。退 0。
4. `requests/` 空的→退 101。

- **容量**＝你開幾個 `aos-llm-cpu` 同時跑同一個家（kernel 的事），不在 cpu 裡設 `max_concurrent`。
- 不重試（agent 那邊管連敗）、不排優先序（先來先問；之後要再加）、不記 usage（之後要再加）。

### 2.3 aos-agent 的 `think` 要怎麼改

`info.json` 的 `engine` 多一格 **`cpu`**（路徑，指到 llm cpu 資料夾；沒寫＝現在的同步問法）。有 `cpu` 時：

| think 進場看到 | 做什麼 | 寫回 | 退出碼 |
|---|---|---|---|
| `ask-result.json`（agent 資料夾裡）存在 | **收回**：`ok:true`→message 接記憶（同現在）、`ok:false`→stderr 一行、記憶不動；rename 成 `.done` | `act` 或 `idle`（失敗留 `think`） | 0 |
| 不存在 | **送出**：寫 `cpu/requests/<name>.json`（result＝`<agent>/ask-result.json`），再往 `waits` 加一條 `"ask-result.json"`（不開 `consume`，think 自己 rename） | `think` 不變 | 0 |

- 下一次被叫：門看 `ask-result.json` 沒到→101；到了→劃掉→進 `think`→上表第一列。**不用新狀態、不用新欄位**，靠「結果檔在不在」分辨送出／收回。
- 順序：先寫請求檔、再加 `waits`。崩在中間→下次 think 會再送一次（cpu 可用同名拒收擋掉，或就多問一次）；反過來先加 waits 再寫請求，崩了就永遠等，更糟。
- 現有自癒照舊：進 think 先看記憶尾巴是不是帶 tool_calls 的 assistant。
- aos-agent.md 要改的：§3 `think` 那兩列拆成上表；「aos-agent 只劃不加 waits」那句拿掉；§5 的 llm cpu 移到正文。

### 2.4 跟 act 總結對齊

tool cpu 之後就是同一套：`requests/<name>.json`＝`{"inst": 解好的 inst, "stdin": arguments, "result": 路徑}`、結果＝`{"ok", "code", "stdout"}`；
`act` 送出＋`waits`、門開了照順序接 tool 訊息。所以「提交一個工作、結果寫回你指定的檔、你用 `waits` 等」這個外框先在 llm cpu 定好。

## 3. 要你拍板的

1. **請求檔帶不帶完整 `engine`**（含 `api_key`，會落地到 cpu 家）：**A** 帶（最簡單，agent 已經解好）／B cpu 自己有 endpoint 表、agent 只寫名字（多一份設定、多一層對應）。建議 A，`api_key` 落地的問題你決定要不要在意。
2. **結果寫哪**：**A** 寫回 agent 資料夾（請求檔指定路徑；跟 `input`／`waits` 同一處、權限簡單）／B 留在 cpu 家 `results/<name>.json`（agent 要記路徑）。建議 A。
3. **交件方式**：**A** agent 直接寫檔進 cpu 的 `requests/`／B 經 kernel syscall（4-5 的走法；kernel 還沒有）。建議 A。
4. **cpu 形狀**：**A** 一次 tick 同步問一件、容量＝開幾顆（沒 worker、沒 pid）／B 照 4-5 派背景 worker（tick 短、但要收屍、pid、hard timeout 那一堆）。建議 A。
5. **同步／丟出去怎麼切**：**A** `engine.cpu` 有寫就丟、沒寫就同步／B 一律丟。建議 A（測試與小 agent 還是同步方便）。
6. **送出／收回怎麼分辨**：**A** 看 `ask-result.json` 在不在（不加欄位）／B `state.json` 加 `ask` 欄位記路徑。建議 A。
