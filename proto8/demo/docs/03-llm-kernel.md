← [回入口 README.md](../README.md)｜段落：llm kernel 範本 llm-kernel（11-04 晚）｜上一份：[02-agent-fsm](02-agent-fsm.md)｜下一份：—

## llm kernel 範本 llm-kernel（11-04 晚）

使用者 11-04 晚：「llm呼叫這塊，我希望是把請求丟到llm kernel(一個loop)，處理好後收回信」「也可以是一個daemon，實際endpoint呼叫就是aos exec」「包起來的」「我是希望走2」「各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以」。設計：[thinking 11-04 think-as-function](../../thinking/2026-11/04/think-as-function/README.md)。

**問腦＝寄一封請求信進 `$AOS_LLM_KERNEL`、之後收回信**；這個資料夾就是那個 kernel：一個 aos-loop，每 300 ms 拍一次 [aos-llm-kernel](../../impls/aos-llm-kernel/README.md)。呼叫端只看到信箱＋[`aos-llm`](../../impls/aos-llm/README.md)（`send`／`recv`／`ask`／`regret`），裡面怎麼跑不用知道。

```
llm-kernel/
  _entry       ["aos-loop", "loop.json"]
  loop.json    {"exec": {"argv": ["aos-llm-kernel", "kernel.json"]}, "interval_ms": 300}（ctl／state 窗照 aos-loop 預設開，pause／stop 現成）
  kernel.json  信箱 mailbox（在 $AOS_STACK 底下）、slots 2、timeout_ms 120000、
               exec＝預設 endpoint 函數 ../../lib/base/llm_http、endpoint＝預設代號 fake、
               endpoints＝代號表：luna／sol（LiteLLM localhost:4000）、local-qwen（LM Studio localhost:1234）、fake（exec 指 ../../lib/base/llm_fake）
```

- **代號**：信的 body 寫 `"endpoint": "sol"` 就用那一組；沒寫用 `kernel.json` 的 `endpoint`（這裡是 `fake`）。要加一組、改模型、放金鑰＝改 `kernel.json`（金鑰寫 `{"$env": "變數名"}` 或 `{"$ref": "repo 外的檔#/key"}`，別直接寫進 repo）。範本裡的 LiteLLM 兩組沒放金鑰（家機的 LiteLLM 不用 key）。
- **直接跑**（PATH 放 `proto8/impls/*/bin` 與 `proto8/bin`）：`AOS_STACK=/tmp/k/ aos-exec --ws /tmp/w proto8/demo/llm-kernel`，另一個殼 `export AOS_LLM_KERNEL=/tmp/k/mailbox`，再 `echo '{"request":{"messages":[{"role":"user","content":"hi"}]}}' | aos-llm ask`。
- **當 daemon 的一個 proc**：`aos-daemon-ctl add --name llm proto8/demo/llm-kernel` → 信箱在 `$AOS_DAEMON/procs/llm/mailbox/`，把它 export 成 `AOS_LLM_KERNEL` 給 agent 用。
- agent-fsm 問腦一定經這裡（沒設 `AOS_LLM_KERNEL`＝`aos-llm: KernelMissing`）；要跑 agent-fsm 先起這個。
