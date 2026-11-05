← [回入口 README.md](../README.md)｜段落：llm kernel 範本 llm-kernel（11-04 晚；11-05 改成一台 daemon；11-05 午 能力包）｜上一份：[02-agent-fsm](02-agent-fsm.md)｜下一份：[04-kernel-modes](04-kernel-modes.md)

## llm kernel 範本 llm-kernel（11-04 晚；11-05 改成一台 daemon；11-05 午 能力包）

使用者 11-04 晚：「llm呼叫這塊，我希望是把請求丟到llm kernel(一個loop)，處理好後收回信」「也可以是一個daemon，實際endpoint呼叫就是aos exec」「包起來的」「我是希望走2」「各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以」。11-05：「問腦，他本身也可以包裝成一個aos函數，掛成proc去跑。我也建議這樣」「cd ~/llm_kernel && aos-exec --stack . def，把llm的daemon+kernel叫起來」。11-05 午：「把endpoint打包成smart-high, stupid-fast, ...這類，並且附上各種屬性(各種temperature也固定)」。設計：[thinking 11-04 think-as-function](../../thinking/2026-11/04/think-as-function/README.md)、[11-05 kernel-daemon 03、07](../../thinking/2026-11/05/kernel-daemon/07-llm-daemon佈局.md)、[feat-proto 02 能力包](../../thinking/2026-11/05/feat-proto/02-endpoint-packs.md)。

**問腦＝寄一封請求信進 `$AOS_LLM_KERNEL/mailbox/`、之後收回信**。這個資料夾是一台 **llm daemon** 的定義：daemon 的身體就是 [aos-llm-kernel](../../impls/aos-llm-kernel/README.md)，每 300 ms 拍一次；每封請求，kernel 請這台 daemon 掛成一個問腦 proc（`llm_<信件名稱>`），跑完收結果寄回信。呼叫端只看到信箱＋[`aos-llm`](../../impls/aos-llm/README.md)（`send`／`recv`／`ask`／`regret`／`ls`），裡面怎麼跑不用知道。
像一台專門打電話的總機：各部門（agent daemon）把要問的事丟進總機的收件匣，總機自己排隊、撥號、把答案送回各部門；整棟樓的電話費（`slots`、`budget`）都記在總機這裡。

```
llm-kernel/
  _entry       ["aos-daemon", "daemon.json"]
  daemon.json  {"exec": {"argv": ["aos-llm-kernel", "kernel.json"]}, "interval_ms": 300}（身體＝kernel；procs 不寫，表上只會有問腦的列）
  kernel.json  slots 2、timeout_ms 120000、exec＝預設 endpoint 函數 ../../lib/base/llm_http、endpoint＝預設代號 fake、
               budget＝只有一格寄件人額度的例子（/tmp/aos-demo-sender 每天 1 次，05 件 5 演；別的寄件人不限）、
               endpoints＝能力包表（下表）
  fake_slow/   demo 用的慢假腦 endpoint 函數：睡 endpoint.delay_s 秒，再把同一份 stdin 交給 lib/base/llm_fake（05 件 3）
```

| 代號 | 是什麼 | 屬性（kernel.json 裡寫的） |
|---|---|---|
| `smart-high` | LiteLLM `localhost:4000` 的 `claude-haiku-5-5`（真名以 `curl localhost:4000/v1/models` 為準） | `fixed.temperature` 0.2、`slots` 4、`speed` normal、`cost` high、`context` 200000 |
| `stupid-fast` | LM Studio `localhost:1234` 的 `qwen3-1.7b` | `fixed.temperature` 0.7、`slots` 1、`speed` fast、`cost` free、`context` 4096 |
| `luna`、`sol` | LiteLLM 的 gpt-6 luna（low）、sol | `sol` 有 `fixed.temperature` 0.2；`cost` high |
| `fake`（預設） | `lib/base/llm_fake`：有工具先叫 `tool` 寫的那個（範本 `clock`，沒有就第一個）、再答「FAKE ANSWER to: …」 | `speed` fast、`cost` free |
| `fake-demo-self`、`fake-demo-spawn` | `llm_fake`＋`script` 劇本（[05](05-feat-proto.md) 件 1、件 4） | 劇本裡的路徑寫 `{"$env": "AOS_CD", "$path": "../agent-fsm"}`：kernel 用到那組時解，`AOS_CD`＝起 llm daemon 時 aos-exec 給的定義資料夾，所以**只在直接跑 repo 裡這份定義時對** |
| `fake-demo-fast`、`fake-demo-slow` | `fake_slow`，每封 3 秒 | `slots` 1；`speed` fast／slow（[05](05-feat-proto.md) 件 3）；`fake_slow` 從自己的位置找 `lib/`，也只在 repo 裡對 |

**包怎麼讀**（全文在 [aos-llm-kernel docs/01](../../impls/aos-llm-kernel/docs/01-用法.md)）：信與 agent 的 `llm.json` 只寫代號；kernel 自己看 `exec`／`slots`／`budget`／`speed` 四個（拿掉後才交給 endpoint 函數），其餘（`url`、`model`、`key`、`fixed`、`script`、`delay_s`…）原樣交給函數。**`fixed` 是釘死的**：信的 `request` 寫了 `fixed` 裡的 key、或那包有 `model` 而信寫了 `model`＝那封回 `RequestBad`；換溫度、換模型＝換代號（多登記一包）。`cost`／`context`／`summary` 只給人與腦挑代號用，kernel 每拍寫進窗 `$AOS_STACK/endpoints.json`，`aos-llm ls` 印它。

**起來**（PATH 放 `proto8/impls/*/bin` 與 `proto8/bin`，或跑過 `proto8/install.sh`）：

```sh
mkdir ~/llm_kernel && cd ~/llm_kernel
cp -r <repo>/proto8/demo/llm-kernel def     # kernel.json 裡 ../../lib 開頭的 exec 改成絕對路徑（<repo>/proto8/lib/base/llm_http、llm_fake）
aos-exec --stack . def                      # 起 llm daemon；信箱在 ~/llm_kernel/mailbox/，Ctrl-C 收工
# 另一個殼：
export AOS_LLM_KERNEL=~/llm_kernel
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | aos-llm ask
# {"role": "assistant", "content": "FAKE ANSWER to: hi"}
aos-llm ls                                  # 一行一包、照代號排：代號 speed cost context slots summary（缺的印 -）；節錄：
# fake fast free - - fake brain: calls clock (or the first tool), then answers FAKE ANSWER to ...
# smart-high normal high 200000 4 LiteLLM claude haiku: careful answers, costs money
echo '{"endpoint": "smart-high", "request": {"messages": [{"role": "user", "content": "hi"}], "temperature": 1}}' | aos-llm ask
# aos-llm: error: RequestBad temperature is fixed by endpoint smart-high (remove it from the request; to change it pick another endpoint name)
aos-daemon-ctl --daemon ~/llm_kernel ls     # 正在飛的問腦，一封一列 llm_<信件名稱>
```

- **跑 agent 的 daemon 另起一台**：起之前 `export AOS_LLM_KERNEL=~/llm_kernel`（或寫進那台定義的 `.env`，絕對路徑），它的子項就寄得到。好幾台可以共用一個 llm kernel：`slots`、`budget` 是整台電腦共用的上限。
- **收工、搬家**：Ctrl-C 時在飛的問腦列變 `sleeping`，再 `aos-exec --stack . def` 自己醒、照樣答完。整包 `cp -a` 到別處起來照樣續答。端點連不上只卡那一封。
- **代號**：信的 body 寫 `"endpoint": "sol"` 就用那一包；沒寫用 `kernel.json` 的 `endpoint`（這裡是 `fake`）。加一包、改模型、放金鑰＝改 `kernel.json`（金鑰寫 `{"$env": "變數名"}` 或 `{"$ref": "repo 外的檔#/key"}`；一包要獨立成檔寫 `{"$ref": "packs/smart-high.json"}`，整份檔不帶 `#/`）。
- **排程**（[feat-proto 03](../../thinking/2026-11/05/feat-proto/03-scheduling.md)）：信的 `priority` 級數（含等久了升級）→ deadline → 包的 `speed`（fast 先）→ 等得久 → 先寄；包的 `slots` 滿了＝跳過、讓下一封別包的補位；包的 `budget` 到頂＝那封 `BudgetMissing`，不替人降級換包。
- **額度**：kernel 總的 `budget`、每包的 `budget`、每個寄件人的 `budget.senders`（寄件人＝信封 `sender`，agent 就是它的工作區；不驗身分）；用量帳在 `$AOS_STACK/used.json`（`packs`、`senders` 各一格）。範本的 `senders` 只列了 `/tmp/aos-demo-sender`，換成你 agent 的工作區就限它。
- **起 llm daemon 的殼別設 `AOS_KERNEL`**：問腦會掛到別台（[已知限制](../../impls/aos-llm-kernel/docs/04-已知限制.md)）。
- agent-fsm 問腦一定經這裡（沒設 `AOS_LLM_KERNEL`＝`LlmKernelMissing`），要先起這個。
