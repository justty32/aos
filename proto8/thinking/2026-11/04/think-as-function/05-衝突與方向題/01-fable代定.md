← [回入口 05-衝突與方向題.md](../05-衝突與方向題.md)｜段落：fable 代定（可翻案）｜上一份：—｜下一份：—

## fable 代定（可翻案；一句話一條，細節在 02～04）

1. 信的 body 形狀：`{"endpoint": 代號, "request": OpenAI body 去端點, "priority"}`；回信 `{"message","usage","model"}` 或 `{"error"}`；不再有 `inst`／`env`。
2. 代號表放 `kernel.json` 的 `endpoints`（一組一層物件、可 `$ref` 拆檔）、預設代號 `endpoint`；`EndpointMissing`／`EndpointUnknown`；信可臨時覆寫 `request` 內的欄位（含 `model`），不能改 `url`／`key`。
3. kernel 跑的是 `exec` 指的 endpoint 函數（`lib/base/llm_http`、假腦 `llm_fake`），stdin／stdout 契約固定；stack＝那封信的資料夾；沒有 `AOS_KERNEL_REPORT`、`accept`、`_metainfo` 排序依據。11-05 起 kernel 不自己跑，把每次問腦寫成 `procs_added` 信請 daemon 掛成 proc、下一拍收，環境是 daemon 給子項的（[kernel-daemon 03](../../../05/kernel-daemon/03-問腦改掛daemon.md)）。
4. 保留 C++ aos-llm-kernel、改它跑的東西；不另寫 Python kernel。`aos-llm`（`impls/aos-llm`）＝`send／recv／ask／regret`；沒有改定義的 Python `aos-llm`。
5. kernel 當資料夾程式 `demo/llm-kernel/`（aos-loop 拍），掛 daemon 用 `aos-daemon-ctl add`；`AOS_KERNEL` 由人 export（或 daemon 環境繼承）。
6. agent-fsm 四格 idle／think／wait／act；「要不要叫工具」由 act 判斷（沒 `tool_calls`＝退 10）；wait 負責寄＋收＋重試；stack 用 `think/`。
7. aos-agent `llm` 子命令＝aos-json 語法糖；`interfaces.json` 的 `llm` 值＝設定檔路徑 `"llm.json"`（跟 `tools` 同形）；沒有 `aos-agent/llm` 介面、`llm/` 入口資料夾、`aos-eca-llm`；eca 的 `--model` 在 `llm.json`。
8. 串流不做（`stream`＝`RequestBad`）；wait 沒有自己的逾時（kernel 的 `timeout_ms`／`priority.deadline` 守）；取消＝`aos-llm regret`；kernel 處理完整封信刪掉（含金鑰的 `request.json`）。
9. 舊閘門的信（頂層 `inst`／`env`）＝`LetterBad`、不留兩種信。
10. 條文（P-23、C-46、N-42、N-63 ①④、N-16、abbr）已照本設計改（[07](../07-實作結論.md) 條文 commit）。
