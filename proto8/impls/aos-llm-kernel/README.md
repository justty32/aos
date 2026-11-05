# aos-llm-kernel

`aos-llm-kernel - 從信箱挑最該跑的信、跑、回信，一次一輪`（NAME，C-54 R1）

**一句話：`aos-llm-kernel [旗標] kernel.json`——LLM kernel 跑一次：看信箱 `new/` 裡排隊的請求信（每封是一份「問腦」的 OpenAI 形狀請求＋一個代號），照優先度挑最該跑的幾封（`slots`），每封用 aos-exec 跑**自己定義裡的 endpoint 函數**（`kernel.json` 的 `exec`），把函數的 stdout 寫成回信寄回 `reply_to`，然後結束。**
要它一直顧著，就讓 aos-loop 或 aos-daemon 一次次拍它（C-47）。寄信收信的一方是 [aos-llm](../aos-llm/README.md)（`send`／`recv`／`ask`／`regret`）；呼叫端只看得到「信箱＋信的形狀」，裡面怎麼打端點是封裝細節（使用者 11-04 晚「包起來的」「我是希望走2」）。
一個 lib（`lib/libaos-llm-kernel.a`，公開標頭 `aos/llm_kernel.hpp`：信箱與信的格式，aos-llm 也用）加一支薄命令列（`bin/aos-llm-kernel`）。連 [aos-loop](../aos-loop/README.md) 的公開 API（擋訊號、`resolve_keys`；它又帶進 aos-exec 的 `run_inst`）與 [aos-post](../aos-post/README.md)（寄回信）。全家慣例見 [impls/README.md](../README.md)。

像醫院掛號櫃台只叫號一次：候診室（`new/`）每張掛號單寫著要問什麼、找哪位醫生（代號）、急不急；叫號的人看一眼，急的先、時限近的先、等很久的先、其餘先來先看，一次叫幾個（診間數＝`slots`），醫生是誰、怎麼聯絡只有櫃台知道（`endpoints` 表），看完把結果寄回病人留的地址（`reply_to`），這一輪就下班。
上一輪的醫生昏倒、診間裡還有人（`cur/`）——還在看的讓他看完，沒人在看又沒結果的，回一張「沒看完」（`RunFailed`），不重看。

```sh
cat kernel.json
# {"mailbox": "mailbox", "slots": 2, "timeout_ms": 120000, "exec": "../../lib/base/llm_http", "endpoint": "fake",
#  "endpoints": {"luna": {"url": "http://localhost:4000/v1", "model": "chatgpt-gpt-6-luna-low", "key": {"$env": "LITELLM_KEY"}},
#                "fake": {"exec": "../../lib/base/llm_fake"}}}
cat loop.json
# {"exec": {"argv": ["aos-llm-kernel", "kernel.json"]}, "interval_ms": 300}
AOS_STACK=$PWD/st/ aos-loop loop.json &                       # kernel 一直顧著信箱 st/mailbox/
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | AOS_KERNEL=$PWD/st/mailbox aos-llm ask
# {"role": "assistant", "content": "FAKE ANSWER to: hi"}
cat st/used.json      # {"window": "day", "since": "2026-11-04T00:00:00+08:00", "counter_calls": 3, "counter_tokens": 129, "counter_all_calls": 3, "counter_all_tokens": 129}
```

設計與決定見 [thinking 2026-11-04 think-as-function](../../thinking/2026-11/04/think-as-function/README.md)（信與 kernel.json 在 [02](../../thinking/2026-11/04/think-as-function/02-設計-信與kernel.md)）；排隊、額度、收拾的來由見 [thinking 2026-10-24 LLM kernel](../../thinking/2026-10/24/llm-kernel/README.md)、[10-15 LLM kernel 稿](../../thinking/2026-10/15/llm-kernel.md)；規範 [N-42](../../docs/NORMS/09-kernel.md)、信箱 [N-16](../../docs/NORMS/05-基礎設施-窗/05-N-16.md)（條文還沒跟上 11-04 的改動，由隊長另外處理）。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法](docs/01-用法.md) | 用法：開頭（命令列、kernel.json、$AOS_STACK 的檔、信箱、信、回信） |
| [02-token-回報與額度](docs/02-token-回報與額度.md) | 用法（續）：跑一封（endpoint 函數）、token 與額度、一次、訊號 |
| [03-元素等](docs/03-元素等.md) | 元素；做法；錯誤代號；建置與測試 |
| [04-已知限制](docs/04-已知限制.md) | 已知限制 |

<a id="用法"></a>
<a id="token-回報與額度thinking--token-回報與額度"></a>
<a id="跑一封endpoint-函數"></a>
<a id="一次"></a>
<a id="訊號"></a>
<a id="元素"></a>
<a id="做法"></a>
<a id="錯誤代號"></a>
<a id="建置與測試"></a>
<a id="已知限制"></a>
