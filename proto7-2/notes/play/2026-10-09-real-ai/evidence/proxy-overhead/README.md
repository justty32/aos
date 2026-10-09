# EF1 證據：代理前置 token，MC 修補後重量（2026-10-09）

← [給使用者的一頁](../../proxy-overhead.md)｜基線：[metrics-baseline](../../metrics-baseline.md)｜原因：[litellm-truncation](../../litellm-truncation.md)

## 怎麼量的

- 同 R1：`packs/author/examples/llm-request/run.sh chatgpt-gpt-6-<模型> OUTDIR`，同一份需求（`csv1`），同六種模型、同 12 圈（sol×3、sol-high、astra×3、astra-max、luna×3、luna-nothink），每批 3 圈同時跑，共 4 批。另跑一次冒煙（`packs/llmcall/examples/litellm/run.sh`，只回 OK）。真 AI 共 **13 次**，全是 gpt 系、走 llmcall。
- 暫存 root 依基線的做法凍結在 `roots/`（只留 metrics 讀的檔）。從 repo 根重跑：
  `python3 proto7-2/modules/metrics/aos7-metrics job proto7-2/notes/play/2026-10-09-real-ai/evidence/proxy-overhead/roots/* --overhead 1644 --detail`
  輸出和凍結前的 `after-mc/metrics-after-mc.txt` 相同。
- `after-mc/calls-after-mc.csv`：每次的 token、HTTP 秒數、`choices_n`、略過幾段、回覆是不是以 `{` 開頭。
- `count_instructions.py`／`.out`：用 tiktoken o200k_base 數 LiteLLM 1.87.5 內建的 Codex 系統提示有多少 token。

## 前後表（12 圈平均）

| 指標 | MC 前（R1 基線） | MC 後（本次） | 差 |
|---|---|---|---|
| 每單 token | 2561 | 2606 | +45 |
| ├ 代理前置 | 1644（64%） | 1644（63%） | 0 |
| ├ 自己的 prompt | 721 | 765 | +44（MC 在 system 尾加的「沒有工具、不要開場白」） |
| └ completion | 197 | 197 | 0 |
| choice 數 | 12/12 一個 | 12/12 一個 | — |
| 開場白（略過段） | 0 | 0 | — |
| 回覆以 `{` 開頭 | 12/12 | 12/12 | — |
| 三關／step／答案／close | 12/12 | 12/12 | — |
| 重試 | 0 | 0 | — |
| 收單→結案秒數 | 9.467 | 10.785 | 本次每批 3 圈同時跑，daemon 回合等待較長；不是 MC 造成 |
| 冒煙 prompt／cached | 1644／1408 | 1644／1408 | 0 |

依模型（每單 token，MC 前→後）：sol 2600→2605；sol-high 2566→2622；astra 2504→2548（cached 1408～2176）；astra-max 2688→2858；luna 2558→2598；luna-nothink 2499→2543。

## 1644 是什麼

冒煙請求自己只有十幾個 token，其餘全是 LiteLLM chatgpt provider 硬加在 instructions 最前面的 Codex CLI 系統提示（`litellm/llms/chatgpt/responses/transformation.py:78`，文字在 `common_utils.py:25`）。實數是 **1620 token**（7572 字元），不是先前寫的「約 1.4k」（1408 是 astra 快取命中的區塊大小）。換成一句 `You are a helpful assistant. You have no tools; answer directly.` 是 14 token。

預期：每次呼叫省約 **1606 token**，這題每單 2606→約 1000（約 −62%）。省的量固定，大請求（A5 那種 5k～10k）比例較小（約 −15～30%）。

## 沒做的

- 沒有改 LiteLLM 設定，也沒有另起 proxy 試打：交接書寫「使用者點頭後再量」。設定後的實測欄留白。
