# aos-llm-kernel

`aos-llm-kernel - 從信箱挑最該跑的信、跑、回信，一次一輪`（NAME，C-54 R1）

**一句話：`aos-llm-kernel [旗標] kernel.json`——LLM kernel 跑一次：看信箱 `new/` 裡排隊的信（每封是一張「問腦」的單子），照優先度挑最該跑的幾封（`slots`），跑完把結果寫成回信，然後結束。**
要它一直顧著，就讓 aos-loop 或 aos-daemon 一次次拍它（C-47：kernel＝以 inst／loop／daemon 為基礎、管某張單子跑不跑的一張單子）。寄信的一方是 [aos-llm-send](../aos-llm-send/README.md)。
一個 lib（`lib/libaos-llm-kernel.a`，公開標頭 `aos/llm_kernel.hpp`：信箱與信的格式，aos-llm-send 也用）加一支薄命令列（`bin/aos-llm-kernel`）。連 [aos-loop](../aos-loop/README.md) 的公開 API（擋訊號、`resolve_keys`；它又帶進 aos-exec 的 `run_inst`）。全家慣例見 [impls/README.md](../README.md)。

像醫院掛號櫃台只叫號一次：候診室（`new/`）每張掛號單寫著要看什麼、急不急；叫號的人看一眼，急的先、時限近的先、等很久的先、其餘先來先看，一次叫幾個（診間數＝`slots`），看完把結果放進取件櫃（`done/`），這一輪就下班。
病人中途走掉（閘門被收掉）就把他的單子抽掉；上一輪的醫生昏倒、診間裡還有人（`cur/`）——還在看的讓他看完，沒人在看又沒結果的，回一張「沒看完」（`RunFailed`），不重看。

```sh
cat kernel.json
# {"mailbox": {"$env": "AOS_KERNEL"}, "slots": 1}
cat loop.json
# {"exec": {"argv": ["aos-llm-kernel", "kernel.json"]}, "interval_ms": 300}
AOS_STACK=st/ AOS_KERNEL=$PWD/mb aos-loop loop.json &    # kernel 一直顧著信箱 mb/
AOS_KERNEL=$PWD/mb aos-llm-send brain.json                    # 寄一封、等回信、結果原樣交回（見 aos-llm-send）
cat st/served.jsonl   # {"served_at": "...", "letter": "0179...", "level": "high", "counter_waited_runs": 0, "code": 0, "signal": null, "error": null, "elapsed_ms": 1085, …, "counter_tokens": 43, "report_bad": false}
cat st/used.json      # {"window": "day", "since": "2026-10-24T00:00:00+08:00", "counter_calls": 3, "counter_tokens": 129, "counter_all_calls": 3, "counter_all_tokens": 129}
```

設計與決定見 [thinking 2026-10-24 LLM kernel](../../thinking/2026-10/24/llm-kernel/README.md)；排序規則是 [10-15 LLM kernel 稿](../../thinking/2026-10/15/llm-kernel.md) 已定的六條；規範 [N-42](../../docs/NORMS/09-kernel.md)、信箱 [N-16](../../docs/NORMS/05-基礎設施-窗/05-N-16.md)。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法](docs/01-用法.md) | 用法：開頭 |
| [02-token-回報與額度](docs/02-token-回報與額度.md) | 用法（續）：token 回報與額度（thinking § token 回報與額度）、accept：只跑名單裡的單子（堵沙箱信箱後門，thinking sandbox S14）、一次、訊號 |
| [03-元素等](docs/03-元素等.md) | 元素；做法；錯誤代號；建置與測試 |
| [04-已知限制](docs/04-已知限制.md) | 已知限制 |

<a id="用法"></a>
<a id="token-回報與額度thinking--token-回報與額度"></a>
<a id="accept只跑名單裡的單子堵沙箱信箱後門thinking-sandbox-s14"></a>
<a id="一次"></a>
<a id="訊號"></a>
<a id="元素"></a>
<a id="做法"></a>
<a id="錯誤代號"></a>
<a id="建置與測試"></a>
<a id="已知限制"></a>
