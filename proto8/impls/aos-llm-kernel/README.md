# aos-llm-kernel

`aos-llm-kernel - 從信箱挑最該跑的信、請 daemon 掛去問腦、收成品回信，一次一輪`（NAME，C-54 R1）

**一句話：`aos-llm-kernel [FLAGS] kernel.json`——LLM kernel 跑一次：先收上一輪掛出去、已經跑完的問腦結果寄回信，再看信箱 `new/` 裡排隊的請求信（每封是一份「問腦」的 OpenAI 形狀請求＋一個代號），照優先度挑最該跑的，補到 `slots` 封在飛為止——每封請 **daemon** 掛成一個問腦 proc（`llm_<信件名稱>`，跑 `kernel.json` 的 `exec`＝endpoint 函數），然後結束，不等它跑完。**
它要住在 daemon 底下：一般是當那台 daemon 的身體（`daemon.json` 的 `exec`），daemon 每 300 ms 拍它一次（C-47）。寄信收信的一方是 [aos-llm](../aos-llm/README.md)（`send`／`recv`／`ask`／`regret`）；呼叫端只看得到「信箱＋信的形狀」，裡面怎麼打端點是封裝細節（使用者 11-04 晚「包起來的」「我是希望走2」；11-05「問腦，他本身也可以包裝成一個aos函數，掛成proc去跑」）。
一個 lib（`lib/libaos-llm-kernel.a`，公開標頭 `aos/llm_kernel.hpp`：信箱與信的格式，aos-llm 也用）加一支薄命令列（`bin/aos-llm-kernel`）。連 [aos-loop](../aos-loop/README.md) 的公開 API（擋訊號、`resolve_keys`）與 [aos-post](../aos-post/README.md)（寄掛信、寄回信）。全家慣例見 [impls/README.md](../README.md)。

像醫院掛號櫃台：候診室（`new/`）每張掛號單寫著要問什麼、找哪位醫生（代號）、急不急；櫃台每隔一下看一眼，先把看完的病人的結果寄回他留的地址（`reply_to`），再照「急的先、時限近的先、等很久的先、其餘先來先看」叫號，診間（`slots`）空幾間就叫幾個。叫到的人交給院方（daemon）排進一間診間（問腦 proc），櫃台不站在門口等，下一輪再來看結果。醫生是誰、怎麼聯絡只有櫃台知道（`endpoints` 表）。
醫院打烊（daemon 收工）時，看到一半的診間先關燈（`sleeping`）；隔天開門自己再看一次，櫃台照樣收結果。

```sh
mkdir ~/llm_kernel && cd ~/llm_kernel
cp -r <repo>/proto8/demo/llm-kernel def          # 定義放 def/（放哪都行）；kernel.json 的 exec 改成絕對路徑
cat def/daemon.json
# {"exec": {"argv": ["aos-llm-kernel", "kernel.json"]}, "interval_ms": 300}
cat def/kernel.json
# {"slots": 4, "timeout_ms": 120000, "exec": "/絕對/proto8/lib/base/llm_http", "endpoint": "fake",
#  "endpoints": {"smart-high": {"url": "http://localhost:4000/v1", "model": "claude-haiku-5-5", "key": {"$env": "LITELLM_KEY"},
#                               "fixed": {"temperature": 0.2}, "slots": 4, "speed": "normal", "cost": "high", "summary": "..."},
#                "fake": {"exec": "/絕對/proto8/lib/base/llm_fake", "speed": "fast", "cost": "free"}}}
aos-exec --stack . def &                          # 起 llm 的 daemon（身體＝kernel）；信箱在 ~/llm_kernel/mailbox/
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | AOS_LLM_KERNEL=~/llm_kernel aos-llm ask
# {"role": "assistant", "content": "FAKE ANSWER to: hi"}
aos-daemon-ctl --daemon ~/llm_kernel ls           # 正在飛的問腦：llm_<信件名稱> 一封一列
cat used.json   # {"window": "day", "since": "2026-11-05T00:00:00+08:00", "counter_calls": 3, "counter_tokens": 129, "counter_all_calls": 3, "counter_all_tokens": 129, "packs": {"fake": {"counter_calls": 3, "counter_tokens": 129}}, "senders": {"/home/me/ws": {"counter_calls": 3, "counter_tokens": 129}}}
# 每個寄件人的額度：kernel.json 的 "budget": {"senders": {"/home/me/ws": {"max_calls": 1}}} → 那人第二封 aos-llm: error: BudgetMissing sender /home/me/ws: max_calls 1 reached in this window (day); not run
cat endpoints.json   # 窗：包的屬性表 {"fake": {"speed": "fast", "cost": "free"}, "smart-high": {"slots": 4, "speed": "normal", "cost": "high", "summary": "..."}}
echo '{"endpoint": "smart-high", "request": {"messages": [{"role": "user", "content": "hi"}], "temperature": 1}}' | AOS_LLM_KERNEL=~/llm_kernel aos-llm ask
# aos-llm: error: RequestBad temperature is fixed by endpoint smart-high (remove it from the request; to change it pick another endpoint name)
```

設計與決定見 [thinking 2026-11-05 kernel-daemon](../../thinking/2026-11/05/kernel-daemon/README.md)（問腦改掛 daemon 在 [03](../../thinking/2026-11/05/kernel-daemon/03-問腦改掛daemon.md)、`~/llm_kernel` 佈局在 [07](../../thinking/2026-11/05/kernel-daemon/07-llm-daemon佈局.md)）、[thinking 2026-11-04 think-as-function](../../thinking/2026-11/04/think-as-function/README.md)（信與 kernel.json 在 [02](../../thinking/2026-11/04/think-as-function/02-設計-信與kernel.md)）；排隊、額度、收拾的來由見 [thinking 2026-10-24 LLM kernel](../../thinking/2026-10/24/llm-kernel/README.md)、[10-15 LLM kernel 稿](../../thinking/2026-10/15/llm-kernel.md)；規範 [N-42](../../docs/NORMS/09-kernel.md)、信箱 [N-16](../../docs/NORMS/05-基礎設施-窗/05-N-16.md)。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法](docs/01-用法.md) | 用法：開頭（命令列、kernel.json、環境、$AOS_STACK 的檔、信箱、信、回信） |
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
