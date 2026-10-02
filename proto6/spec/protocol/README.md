# 協議篇：格式的通則

← [規格](../README.md)｜[慣例](../conventions.md)｜[inst](../inst.md)｜[tick 協議](tick.md)｜[daemon 協議](daemon/README.md)

## P-001：範圍

協議篇只定**格式**：檔案與訊息的欄位、JSON、環境變數、輸出行。行為寫在各篇與程式裡，這裡寫到行為只留一句加條號；兩邊衝突以程式與測試為準。argv 與結束碼看各程式的原始碼（`aos-tick`、`aos-exec`、`aos-daemon` 另有 `--help`；`aos-ctl`、`aos-mq` 把 `--help` 當用法錯），結束碼慣例是 [C-08](../conventions.md)，環境變數總表是 [C-10](../conventions.md)。

## P-002：JSON 的規矩

- 輸入格式要求（寫的一方遵守）：UTF-8、無 BOM；一份檔案或一行訊息恰好一個 JSON object；不得有重複 key、非有限數（`NaN`、`Infinity`）、尾隨資料。這是寫的一方的義務，不是 POC 的拒絕保證：daemon 控制與訊息請求直接 `json.loads`，重複 key 取最後一個、`NaN` 照收。
- 陌生欄位與版本怎麼處理見 [C-07](../conventions.md)；時間欄位命名見 [C-01](../conventions.md)。
- 現行沒有 JSON-RPC、沒有 `id`、沒有 256 KiB 上限：daemon 的 socket 請求是 `{"<指令>":…}`、回應是 `{"ok":…}`（[daemon 協議](daemon/README.md)）。

## P-007：schema 與範例

- 正本在本資料夾：[schemas/](schemas/)（JSON Schema 2020-12，`common.schema.json` 放共用型別，其他以相對 `$ref` 引用，所以不能把檔分開搬）與 [examples/](examples/)（`<主題>.<情境>.valid.json`／`.invalid.json`，每種訊息一個最小正例、一個主要錯誤）。`tick-*`、`inst` 管任務表與紀錄，`daemon-*` 管 daemon；舊 daemon 的 `daemon-config`、`daemon-state`、`daemon-rpc`、`daemon-helper`、`daemon-provision`、`daemon-registration`、`daemon-runner-report`、`daemon-launch-error` 屬[暫緩區](../deferred/protocol/daemon/README.md)，現行用 `daemon-core-config`、`daemon-ctl`、`daemon-mq`、`daemon-module-state`。
- schema 通過不代表授權或狀態正確，也表達不了跨欄位的關係；後者由 `examples/messages/validate.py` 的 `extra_errors` 補（tick 紀錄那部分在 `record_rules.py`，測試也共用）。
- 驗：`cd proto6/spec/protocol/examples && uv run -q --no-project --with jsonschema python messages/validate.py`，驗全部 schema 能載入、`$ref` 都解得開、每個範例的正反例都如預期。`examples/daemon/` 裡列在 validate.py `SUPERSEDED` 的九份 `mq_*` 是第二十五批之前的舊範例，只留給舊裁定紀錄的連結，不驗、不是現行範例。`tests/_tick_util.py` 也會拿 `tick-record` schema 驗真的跑出來的紀錄。
- 舊的 agent、kernel、LLM、work、messages、ops、resources 協議與它們的 schema、範例整批封存在 [notes/archive/spec-2026-10-02/protocol/](../../notes/archive/spec-2026-10-02/protocol/)。
