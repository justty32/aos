← [回入口 README.md](../README.md)｜段落：llm kernel 範本 llm-kernel（11-04 晚；11-05 改成一台 daemon；11-05 午 能力包）｜上一份：—｜下一份：[02-kernel-modes](02-kernel-modes.md)

## llm kernel 範本 llm-kernel（11-04 晚；11-05 改成一台 daemon；11-05 午 能力包）

使用者 11-04 晚：「llm呼叫這塊，我希望是把請求丟到llm kernel(一個loop)，處理好後收回信」「也可以是一個daemon，實際endpoint呼叫就是aos exec」「包起來的」「我是希望走2」「各種llm設定也可以包裝，這樣寄信的時候只要寫簡單的代號就可以」。11-05：「問腦，他本身也可以包裝成一個aos函數，掛成proc去跑。我也建議這樣」「cd ~/llm_kernel && aos-exec --stack . def，把llm的daemon+kernel叫起來」。11-05 午：「把endpoint打包成smart-high, stupid-fast, ...這類，並且附上各種屬性(各種temperature也固定)」。設計：[thinking 11-04 think-as-function](../../thinking/2026-11/04/think-as-function/README.md)、[11-05 kernel-daemon 03、07](../../thinking/2026-11/05/kernel-daemon/07-llm-daemon佈局.md)、[feat-proto 02 能力包](../../thinking/2026-11/05/feat-proto/02-endpoint-packs.md)。

**問腦＝寄一封請求信進 `$AOS_LLM_KERNEL/requests/`、之後收回信**。這個資料夾是一台 **llm daemon** 的定義：daemon 的身體就是 [aos-llm-kernel](../../impls/aos-llm-kernel/README.md)，每 300 ms 拍一次；每封請求，kernel 請這台 daemon 掛成一個問腦 proc（`llm_<信件名稱>`），跑完收結果寄回信。呼叫端只看到信箱＋[`aos-llm`](../../impls/aos-llm/README.md)（`send`／`recv`／`ask`／`regret`／`ls`），裡面怎麼跑不用知道。
像一台專門打電話的總機：各部門（agent daemon）把要問的事丟進總機的收件匣，總機自己排隊、撥號、把答案送回各部門；整棟樓的電話費（`slots`、`budget`）都記在總機這裡。

```
llm-kernel/
  _entry       ["aos-daemon", "--enable-logs", "daemon.json"]
  daemon.json  {"exec": {"argv": ["aos-llm-kernel", "kernel.json"]}, "interval_ms": 300, "procs": {"_sweeper": {…}}}（身體＝kernel；procs 只帶清道夫一列（11-10，見 cmd/aos-sweeper；不要就刪）、不帶鐘列，聽外層的 `AOS_CLOCK`）
  kernel.json  slots 2、reserved＝{"high": 1}（11-07 使用者裁定 sol 審查 #7）、timeout_ms 120000、exec＝預設 endpoint 函數 ../../lib/base/llm_http、endpoint＝預設代號 fake、
               不設 budget（11-11 使用者選「從範本拿掉」；要限寄件人就自己加 budget.senders，例子在 03 件 5）、
               endpoints＝能力包表（下表）
  fake_slow/   demo 用的慢假腦 endpoint 函數：睡 endpoint.delay_s 秒，再把同一份 stdin 交給 lib/base/llm_fake（03 件 3）
  endpoints/litellm/_entry  ["aos-exec", "../../../../lib/base/llm_http", "--key-env", "LITELLM_KEY"]（三個 LiteLLM 包共用）
```

| 代號 | 是什麼 | 屬性（kernel.json 裡寫的） |
|---|---|---|
| `smart-high` | LiteLLM `localhost:4000` 的 `claude-haiku`（真名以 `curl localhost:4000/v1/models` 為準） | `fixed.temperature` 0.2、`slots` 4、`speed` normal、`cost` high、`context` 200000 |
| `stupid-fast` | LM Studio `localhost:1234` 的 `qwen3-1.7b`（本機載的是別的就改這包的 `model`，真名看 `curl localhost:1234/v1/models`；家機試驗場指 `google/gemma-4-e4b`） | `fixed.temperature` 0.7、`slots` 1、`speed` fast、`cost` free、`context` 4096 |
| `luna`、`sol` | LiteLLM 的 gpt-6 luna（low）、sol | `sol` 有 `fixed.temperature` 0.2；`cost` high |
| `fake`（預設） | `lib/base/llm_fake`：有工具先叫 `tool` 寫的那個（範本 `peek_now_time`，沒有就第一個）、再答「FAKE ANSWER to: …」 | `speed` fast、`cost` free |
| `fake-demo-self`、`fake-demo-spawn` | `llm_fake`＋`script` 劇本（[03](03-feat-proto.md) 件 1、件 4） | 劇本裡的路徑寫 `{"$env": "AOS_HOME", "$path": "/templates/agent-fsm"}`：用到那組時解，`cp -r` 抄出去也指得對（11-10 templates-cp） |
| `fake-demo-fast`、`fake-demo-slow` | `fake_slow`，每封 3 秒 | `slots` 1；`speed` fast／slow（[03](03-feat-proto.md) 件 3）；`fake_slow` 從找到的 `aos_flags.py`（`proto8/py`）旁找 `lib/`，複製出 repo 也對（11-05 夜第二輪邊緣：原本從自己的位置找、出 repo＝`EndpointFailed … can't open file …/lib/base/llm_fake/_entry`） |

**包怎麼讀**（全文在 [aos-llm-kernel docs/01](../../impls/aos-llm-kernel/docs/01-用法.md)）：信與 agent 的 `llm.json` 只寫代號；kernel 自己看 `exec`／`slots`／`budget`／`speed` 與 `backend` 五個（拿掉後才交給 endpoint 函數），其餘（`url`、`model`、`fixed`、`script`、`delay_s`…）原樣交給函數。金鑰由端點小 proc 自己讀環境，kernel 不讀、不寫、不轉交。**`fixed` 是釘死的**：信的 `request` 寫了 `fixed` 裡的 key、或那包有 `model` 而信寫了 `model`＝那封回 `RequestBad`；換溫度、換模型＝換代號（多登記一包）。`cost`／`context`／`summary` 只給人與腦挑代號用，kernel 每拍寫進窗 `$AOS_STACK/endpoints.json`，`aos-llm ls` 印它。

**起來**（PATH 放 `proto8/impls/*/bin` 與 `proto8/cmd/*/bin`，或跑過 `proto8/install.sh`）：

```sh
mkdir ~/llm_kernel && cd ~/llm_kernel
cp -r <repo>/proto8/kernel/llm-kernel def   # 複製到 repo 外後，兩處指向 lib 的路徑都要改：
sed -i 's#"\.\./\.\./lib/#"<repo>/proto8/lib/#g' def/kernel.json   # 沒改＝問腦回 aos-llm: error: EndpointFailed … EntryMissing entry not found: …/lib/base/llm_fake
sed -i 's#"\.\./\.\./\.\./\.\./lib/#"<repo>/proto8/lib/#g' def/endpoints/litellm/_entry
                                            # 格（fake_slow 等）找 aos_flags.py：先 ../../../py、再 PATH 上 aos-tools 的真位置（11-05 晚）
aos-exec --stack . def                      # 起 llm daemon；信箱在 ~/llm_kernel/requests/，Ctrl-C 收工
# 另一個殼：
export AOS_LLM_KERNEL=~/llm_kernel
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | aos-llm ask
# {"role": "assistant", "content": "FAKE ANSWER to: hi"}
aos-llm ls                                  # 一行一包、照代號排：代號 speed cost context slots backend summary（缺的印 -）；節錄：
# fake fast free - - - fake brain: calls peek_now_time (or the first tool), then answers FAKE ANSWER to ...
# smart-high normal high 200000 4 - LiteLLM claude haiku: careful answers, costs money
echo '{"endpoint": "smart-high", "request": {"messages": [{"role": "user", "content": "hi"}], "temperature": 1}}' | aos-llm ask
# aos-llm: error: RequestBad temperature is fixed by endpoint smart-high (remove it from the request; to change it pick another endpoint name)
aos-daemon-ctl --daemon ~/llm_kernel ls     # 正在飛的問腦，一封一列 llm_<信件名稱>
```

- **跑 agent 的 daemon 另起一台**：跨樹 hub 只在 root 層的殼 `export AOS_LLM_KERNEL=~/llm_kernel`，它的子項就寄得到；若 hub 跟定義在同一棵可搬的樹，定義的 `.env` 可從 `${AOS_CD}/..` 算相對位置，不寫絕對路徑。好幾台可以共用一個 llm kernel：頂層 `slots`、`reserved`、`budget` 是整台電腦共用的設定。
- **收工、搬家**：Ctrl-C 時在飛的問腦列變 `sleeping`，再 `aos-exec --stack . def` 自己醒、照樣答完。整包 `cp -a` 到別處起來照樣續答。端點連不上只卡那一封。
- **代號**：信的 body 寫 `"endpoint": "sol"` 就用那一包；沒寫用 `kernel.json` 的 `endpoint`（這裡是 `fake`）。加一包、改模型＝改 `kernel.json`；一包要獨立成檔寫 `{"$ref": "packs/smart-high.json"}`，整份檔不帶 `#/`。
- **金鑰歸端點小 proc**：`smart-high`、`luna`、`sol` 的 `exec` 都指 `endpoints/litellm`，小定義的 `_entry` 用 `--key-env LITELLM_KEY` 指定變數名。手動起 llm daemon 前，在 root 殼 `export LITELLM_KEY=...`；用 systemd 範例則在 `~/.config/aos/root.env` 填 `LITELLM_KEY=...`，unit 以 `EnvironmentFile=%h/.config/aos/root.env` 讀入，daemon 讓子 proc 繼承；小定義的 `.env` 不放金鑰（11-07 使用者裁定 sol 審查 #35）。`llm_http` 那個變數沒設或空＝不帶 Authorization 照打（11-10 夜使用者「改成變數沒設就不帶金鑰照打」）：LiteLLM 沒開金鑰驗證時不用 export；端點真要金鑰時它回 401／403，錯誤行寫 `EndpointFailed HTTP 401 (the endpoint refused the request and may need a key: environment variable LITELLM_KEY (--key-env) is not set): …`。值含非 ASCII、空白、換行等標頭放不下的字＝送出前 `KeyBad`（不印值；例：把說明裡的中文佔位字原樣貼進去）。stdin 的 `endpoint` 帶 `key`＝`ArgumentsBad`。搬家後設好新機器的 root 殼或 systemd 環境檔，再起 daemon；LM Studio／假腦不用金鑰。
- **排程**（[feat-proto 03](../../thinking/2026-11/05/feat-proto/03-scheduling.md)）：信的 `priority` 級數（每 `aging_cycles` 格升一級，預設 3；有 `AOS_CLOCK` 數 kernel 自己樹的鐘，沒有用 `AOS_CLOCK_INTERVAL` 換牆鐘；凍住時鐘＝不升級）→ deadline → 同後端黏著 → 包的 `speed`（fast 先）→ 等得久 → 先寄；包的 `slots` 滿了＝跳過、讓下一封別包的補位；包的 `budget` 到頂＝那封 `BudgetMissing`，不替人降級換包。跨樹信的 `priority.deadline` 留牆鐘（N-65 ③，ISO 8601 或 epoch 秒），kernel 不讀信裡任何時鐘欄。
- **留格給 high**：範本已在 `kernel.json` 頂層設 `"reserved": {"high": 1}`（11-07 使用者裁定 sol 審查 #7）；程式仍為選填，只認 `high`，值須為非負整數且小於頂層 `slots`（`slots: 1` 只能填 0），不合＝`CfgBad`。沒寫、`{}` 或 `high: 0`＝不保留；`reserved` 同 `slots` 整格先解指示詞。低於 high 的信只補到總在飛數 `slots-N`，看 `priority_of` 的宣告 level、不算 aging；跳過不能補的信，後面的 high 可繼續補。保留格不搶占已在飛的請求，high 要用保留範圍外的格仍可能等在飛的跑完。
- **額度**：kernel 總的 `budget`、每包的 `budget`、每個寄件人的 `budget.senders`（寄件人＝信封 `sender`，agent 就是它的工作區；不驗身分）；用量帳在 `$AOS_STACK/used.json`（`packs`、`senders` 各一格；`senders` 的 key 是相對 kernel stack 的路徑，整包搬家相對位置相同就沿用同一格帳）。範本不設預算（11-11 拿掉原本的 `/tmp/aos-demo-sender` 示範，它每次起來都印一行「不是資料夾」的 warning）；要限某隻 agent 就在自己那份 `kernel.json` 寫 `"budget": {"senders": {"<它的工作區>": {"max_calls": N}}}`（[03 件 5](03-feat-proto.md)）。
- **起 llm daemon 的殼別設 `AOS_KERNEL`**：問腦會掛到別台；非空路徑的 `new/` 不是資料夾時，每行程每路徑 warning 一次，仍用原路徑、不改退路、不因此報錯，後續掛 proc 失敗照舊（[已知限制](../../impls/aos-llm-kernel/docs/04-已知限制.md)）。
- agent-fsm 問腦一定經這裡（沒設 `AOS_LLM_KERNEL`＝`LlmKernelMissing`），要先起這個。

範本出廠帶 stdout log、**不帶鐘列**（11-09 clock-decouple：鐘只放在根 daemon，總機掛在樹裡就聽根的鐘；單獨起又沒設 `AOS_CLOCK`＝退牆鐘）；正式使用可在自己的副本拿掉 `_entry` 的 `--enable-logs`。真要總機自己的鐘，照 [aos-daemon docs/02](../../impls/aos-daemon/docs/02-看寫法決定怎麼起.md#時鐘普通一列) 加鐘列＋`.env`（掛在樹裡時還要掛它的那列加 `--dotenv-override`）。

## 隊 kernel 範本 llm-team：一封信走兩層

[`llm-team/`](../llm-team/) 與 `llm-kernel/` 各複製成並排 stack 的 `def/`。兩份 `_entry` 都起自己的 daemon；隊 kernel 用 `lib/aos/llm_forward`，預設 fake，另有 sol、luna、local（轉主 kernel 的 stupid-fast）。每包的 `kernel` 用 `{"$env":"AOS_STACK","$path":"../llm-kernel"}`，解完仍保留 `..` 字串，轉交函數照原字串記 child。不用改 daemon 的 AOS_LLM_KERNEL；寄信方只把它指向隊 stack。

相對 lib 路徑和主範本相同：若 stack 放 repo 外，可在兩個 stack 的共同上一層放 `lib` 捷徑指向這份 proto8/lib（保留範本原檔），或在自己的定義副本把 exec 改成絕對路徑。隊 timeout 180000 ms，主 timeout 120000 ms；隊 budget 每天 3000 次、不帶寄件人那格（11-11 拿掉 `/tmp/aos-demo-sender` 示範），要限寄件人自己加 `budget.senders`。

兩個定義都有 `interfaces.json` 的 `aos-ledger` 宣告（`ledger.jsonl` 相對 stack）。成功的上層 ledger 用 `child.kernel` 與 `child.letter` 指到下層帳，寄信方只拿這一層的 letter；usage 不重複加總，只加一層。下層合格錯誤原樣穿過，上層不再包一層 EndpointFailed；轉交函數自己的錯才走 EndpointFailed。

主範本 stupid-fast 現在屬於 lmstudio backend（slots 1、max_packs 1）；再加同服務的包時掛同一後端。同級同期限優先把最後掛的包湊完，high 與更近期限仍能換包；第一次掛與換包第一封 ledger 的 switched 為 true。各台只管自己的後端，細節與盲點見 [impls 後端說明](../../impls/aos-llm-kernel/docs/01-用法.md#後端格數與黏著lm-studio)。
