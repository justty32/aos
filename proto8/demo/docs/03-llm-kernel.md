← [回入口 README.md](../README.md)｜段落：llm kernel 範本 llm-kernel（11-04 晚；11-05 改成一台 daemon）｜上一份：[02-agent-fsm](02-agent-fsm.md)｜下一份：[04-kernel-modes](04-kernel-modes.md)

## llm kernel 範本 llm-kernel（11-04 晚；11-05 改成一台 daemon）

使用者 11-04 晚：「llm呼叫這塊，我希望是把請求丟到llm kernel(一個loop)，處理好後收回信」「也可以是一個daemon，實際endpoint呼叫就是aos exec」「包起來的」「我是希望走2」「各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以」。11-05：「問腦，他本身也可以包裝成一個aos函數，掛成proc去跑。我也建議這樣」「cd ~/llm_kernel && aos-exec --stack . def，把llm的daemon+kernel叫起來」。設計：[thinking 11-04 think-as-function](../../thinking/2026-11/04/think-as-function/README.md)、[11-05 kernel-daemon 03、07](../../thinking/2026-11/05/kernel-daemon/07-llm-daemon佈局.md)。

**問腦＝寄一封請求信進 `$AOS_LLM_KERNEL/mailbox/`、之後收回信**。這個資料夾是一台 **llm daemon** 的定義：daemon 的身體就是 [aos-llm-kernel](../../impls/aos-llm-kernel/README.md)，每 300 ms 拍一次；每封請求，kernel 請這台 daemon 掛成一個問腦 proc（`llm_<信件名稱>`），跑完收結果寄回信。呼叫端只看到信箱＋[`aos-llm`](../../impls/aos-llm/README.md)（`send`／`recv`／`ask`／`regret`），裡面怎麼跑不用知道。
像一台專門打電話的總機：各部門（agent daemon）把要問的事丟進總機的收件匣，總機自己排隊、撥號、把答案送回各部門；整棟樓的電話費（`slots`、`budget`）都記在總機這裡。

```
llm-kernel/
  _entry       ["aos-daemon", "daemon.json"]
  daemon.json  {"exec": {"argv": ["aos-llm-kernel", "kernel.json"]}, "interval_ms": 300}（身體＝kernel；procs 不寫，表上只會有問腦的列）
  kernel.json  slots 2、timeout_ms 120000、
               exec＝預設 endpoint 函數 ../../lib/base/llm_http、endpoint＝預設代號 fake、
               endpoints＝代號表：luna／sol（LiteLLM localhost:4000）、local-qwen（LM Studio localhost:1234）、fake（exec 指 ../../lib/base/llm_fake）
```

**起來**（PATH 放 `proto8/impls/*/bin` 與 `proto8/bin`）：

```sh
mkdir ~/llm_kernel && cd ~/llm_kernel
cp -r <repo>/proto8/demo/llm-kernel def     # kernel.json 的兩個 exec 改成絕對路徑（<repo>/proto8/lib/base/llm_http、llm_fake）
aos-exec --stack . def                      # 起 llm daemon；信箱在 ~/llm_kernel/mailbox/，Ctrl-C 收工
# 另一個殼：
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | AOS_LLM_KERNEL=~/llm_kernel aos-llm ask
# {"role": "assistant", "content": "FAKE ANSWER to: hi"}
aos-daemon-ctl --daemon ~/llm_kernel ls     # 正在飛的問腦，一封一列 llm_<信件名稱>
```

- **跑 agent 的 daemon 另起一台**：起之前 `export AOS_LLM_KERNEL=~/llm_kernel`（或寫進那台定義的 `.env`，絕對路徑），它的子項就寄得到。好幾台可以共用一個 llm kernel：`slots`、`budget` 是整台電腦共用的上限。
- **收工、搬家**：Ctrl-C 時在飛的問腦列變 `sleeping`，再 `aos-exec --stack . def` 自己醒、照樣答完。整包 `cp -a` 到別處起來照樣續答。端點連不上只卡那一封。
- **代號**：信的 body 寫 `"endpoint": "sol"` 就用那一組；沒寫用 `kernel.json` 的 `endpoint`（這裡是 `fake`）。加一組、改模型、放金鑰＝改 `kernel.json`（金鑰寫 `{"$env": "變數名"}` 或 `{"$ref": "repo 外的檔#/key"}`）。
- **起 llm daemon 的殼別設 `AOS_KERNEL`**：問腦會掛到別台（[已知限制](../../impls/aos-llm-kernel/docs/04-已知限制.md)）。
- agent-fsm 問腦一定經這裡（沒設 `AOS_LLM_KERNEL`＝`LlmKernelMissing`），要先起這個。
