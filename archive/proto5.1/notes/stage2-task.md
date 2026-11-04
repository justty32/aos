# proto5.1 第 2 段任務書：tool cpu、act 送出／收回、請求對帳（2026-09-22）

接 [stage1-task.md](stage1-task.md)；先讀 [findings.md](findings.md)（第 1 段撞到的 17 條）與 [stage1-report.md](stage1-report.md)。
一樣只動 `proto5.1/`，`proto5/` 不碰；問題繼續記進 `findings.md`（接著第 18 條往下編）。

## A. 把「提交一個工作、結果寫回指定檔」抽成共用層

第 1 段的 `aos_llm_cpu.py` 裡佇列機制（`queue_lock`、認領、收屍、遲到回覆不覆蓋、結果原子寫）跟「怎麼執行一份請求」是兩件事。
抽成 `lib/aos_cpu.py`（佇列層：`submit(cpu_dir, name, request)`、`tick(cpu_dir, execute)`——`execute(request) -> result dict`；
info.json `_metainfo._type` 由呼叫者給），`aos_llm_cpu.py` 變成薄薄一層（`_type`＝`llm_cpu`、execute＝`aos_llm_ask.call`）。
規範：`spec/cpu-queue.md`（格式：資料夾、請求檔共同欄位 `result`＋各 cpu 自己的 payload、結果檔共同欄位 `ok`／`error`、鎖、收屍規則）；
`llm-cpu.md` 改成只講 llm 的 payload 與結果。既有 64 條 llm cpu 測試不能壞。

## B. tool cpu

- 格式 `spec/tool-cpu.md`：`_type`＝`tool_cpu`；請求 payload＝`{"inst": <aos_inst.load_obj 解好的 dict>, "stdin": "<arguments 字串>", "timeout_ms": N}`
  （agent 那邊解好、路徑都是絕對的，cpu 不解指示詞、不讀 agent 資料夾）；結果＝`{"ok": true, "code": N, "kind": "child"|"aos", "timed_out": bool, "stdout": "..."}`
  或 `{"ok": false, "error": "..."}`（請求檔壞掉那類）。
- 程式 `spec/aos-tool-cpu.md`＋`lib/aos_tool_cpu.py`＋`cli/aos-tool-cpu`：execute＝`aos_exec.run_inst(inst, stdin, timeout_ms)`；收屍寬限＝`timeout_ms`＋30 秒。

## C. act 送出／收回

- 工具元素多一格 `_run`：`"sync"`（預設，現在的做法）｜`"cpu"`。`info.json` 頂層多一格 `tool_cpu`（路徑，相對 agent 資料夾；有 `_run: "cpu"` 的工具但沒寫＝讀驗錯 `FieldTypeMismatch`）。
- `act` 進場（記憶尾巴是帶 tool_calls 的 assistant）：
  1. 沒有任何待收的結果檔：sync 的 call **先不跑**；把所有 `_run: "cpu"` 的 call 各寫一份請求（result＝`<agent>/tool-results/<i>.json`，i＝call 在 `tool_calls` 的索引；資料夾不在就建），往 `waits` 加一條 `{"$opt": "all", "$val": [那些結果檔]}`，state 留 `act`，退 0。**一個 cpu call 都沒有→照現在一格跑完。**
  2. 結果檔都到了（門開了進來）：照 `tool_calls` 順序組 tool 訊息——sync 的現在跑、cpu 的讀結果檔（`ok:true`：exit 0＝stdout、非 0＝「工具 xxx 失敗（exit n）：」＋stdout、timed_out＝「工具 xxx 逾時」；`ok:false`＝「工具 xxx 跑不起來：」＋error）；整批接記憶、結果檔 rename `.done`、state＝`think`。
  3. 崩在中間怎麼自癒：照第 1 段 think 的做法想一套，記 findings。
- 規範改 `aos-agent.md` §3 act、`agent.md` §4（`tool_cpu`）、`aos-llm-ask.md` §2.3（`_run`）。

## D. 請求對帳（**只評估、不實作**——使用者說保持 KISS）

第 1 段 findings 11／13 說固定 `ask-result.json`＋沒有請求 id，崩在中間對不了帳。**不要做**：state.json 不加 `ask`／`calls`、
結果檔不加 `name`。只在 findings 寫一段評估：要加什麼、多多少複雜度、解掉第 1 段哪幾個情境、還剩哪些。給使用者拍 llm cpu 第 6 題用。

**整體原則（使用者的話）：保持 KISS。** A 節抽共用層只准一個檔、幾個函式，不要類別階層；C 節 act 自癒用最簡單能過測試的做法，
邊角案例記 findings 不堆判斷；能少一個欄位就少一個、能少一個分支就少一個。

## E. 測試、真跑、文件

- 測試：`test_cpu.py`（共用層）、`test_tool_cpu.py`、`test_agent.py` 補 act 送出／收回／混合 sync＋cpu／順序／逾時／`ok:false`／對帳丟舊結果；全套綠。
- 真跑：第 1 段的 demo 加一個 `_run: "cpu"` 的工具（例如 `sleep 2; date`）與一顆 tool cpu，交替叫 `aos-agent`／`aos-llm-cpu`／`aos-tool-cpu` 直到回話、101；貼退出碼與 state／waits 變化。
- 文件：`lib/README.md`、`README.md`（分段表第 2 段「做完」、規範表加 cpu-queue／tool-cpu／aos-tool-cpu）。
- 只動 `proto5.1/`；不 commit／push／stash／checkout。回報：檔案清單、測試數字、真跑紀錄、findings 新增幾條＋最重要 5 條、D 的結論一段。
