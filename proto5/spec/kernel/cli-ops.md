← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：add／halt／check／ls 的 health 行／ack

**add**：TARGET 轉絕對路徑放單（kernel 不解指示詞，指示詞是跑的時候 aos-exec 以它自己的規則解——`.json`
是檔所在資料夾、資料夾目標是資料夾本身）；旗標一對一對到 §2 的 params，`-- ARG...` 對到 `args`。
反覆＝等回音印 NAME；`--once` 預設不等、印自己取的檔名（`--name` 沒給時 NAME 就用這個檔名）跟回音會出現的路徑，
`--wait-ms N` 才等跑完印回音。

**CLI 等到回音就替你 ack**；沒等或等逾時就印出回音的路徑，之後自己去讀、自己 ack（逾時不取消工作）。
拿到 JSON-RPC `error` 印代號與 message、退 1；拿到 exec 的 `result` 整段印出來、退 0——**工作本身成不成功看內容**
（`kind`、`code`、`timed_out`、`stopped`），不看退出碼。

**halt**（09-24 試玩 r1 補；fix-r4 從 `stop` 改名，行為不變）預設等停好：沒帳本或已經 `phase=stopped` 且孩子表沒有這個 kernel 的 cpu＝印 `stopped`；daemon 不活或 kernel cpu 不在孩子表（鏈沒在跑）＝**不放單**
（放了下次 boot 一開機就停）、印 `not running`；其餘放 stop 單，等到 `phase=stopped` 且 `D/state.json` 裡這個 kernel 的 cpu（target 在 `K/cpus/` 底下的）都不見了才印 `stopped`、退 0。
等超過 `--wait-ms`（預設 30000）＝`Timeout`、退 1（單已放、不撤回，用 `ls` 看）。`--no-wait` 是舊行為：只放單、不印、退 0，之後自己用 `ls` 等。
停好之後才去停 daemon。其餘等回音最多 10 秒。

（09-24 試玩 r1 補）**check** 啟動前檢查，每項一行 `ok`／`warn`／`bad`，有 `bad` 退 1：`info` 讀驗；`daemon` 活不活（沒開＝warn）；`path`——`aos-exec`、`aos-cpu`、`aos-kernel`、`aos-agent`、`aos-llm`
在 daemon 的 PATH 找不找得到（讀得到 `/proc/<daemon pid>/environ` 就用它，否則用目前 shell 的並註明）；`pools`——沒有 `llm` 池＝bad；
`llm`——llm 池每顆 cpu 的有效 envs（`cpus/<c>/inst.json` 在就用它）有沒有 `AOS_LLM_CONFIG`、檔在不在、llm.json 讀驗過不過、有哪些模型代號。
（09-24 fix-r4 改）daemon 家：`--daemon-target D`，其次 `AOS_DAEMON_HOME`，再其次目前資料夾（跟 daemon 自己一樣，不再優先看 info 的 `daemon`）；info 的 `daemon`（boot 寫的）在而且跟這次的 D 不同，`daemon` 項多一行 `warn`，說 info 記的是哪個。（09-24 advice-r1 改）**agent 不在這裡查了**：原本的 `--agent DIR` 搬到 [`aos-agent check`](../aos-agent/cli-check.md)（K 由 `AOS_KERNEL_HOME` 或 agent 家的 `tick.json` 找，先跑這整份 kernel 檢查再查 agent）。`aos-kernel check` 給 `--agent`（帶不帶值、給幾次都一樣）＝用法錯 2，stderr 一行 `aos-kernel: Usage: --agent 搬走了：agent 的檢查改用 aos-agent check --target <DIR> [--probe]（K 由 AOS_KERNEL_HOME 或 agent 家的 tick.json 找）`；`-h` 不列 `--agent`。其餘參數本身有用法錯（例如 `--agent --target`、不認得的旗標）時 argparse 先報那個錯，一樣退 2、但沒有搬家提示。
（09-24 試玩 r2 補）另外兩項：`dirs`——K 家的 `requests/`、`responses/`、`cpus/` 在不在（§1 的目錄圖；`cpus/<name>/` 不查，boot 會補），缺＝bad，手建的家要 `mkdir -p` 補；`cpus`——帳本在、`phase` 是 `running`／`stopping`、daemon 活著，而 info 的 cpu 或帳本的 `kcpu` 有不在 daemon 孩子表的＝bad：`daemon 重開過／cpu 不在（…）：執行 aos-kernel boot --target <K> --daemon-target <D>`（沒帳本、已 `stopped`、daemon 沒活就不印這項）。`--daemon-target` 只能給一次，重複＝用法錯 2。check 預設只驗設定，**不連 endpoint**：全綠不代表模型連得上。
（09-24 fix-r5 補）所以最後印一行總結：沒 `bad` 時是 `設定檢查通過；未測模型連線（--probe 會測）`，有 `bad` 時是 `有 bad，照上面的提示修好再 boot`。
**`--probe`**（09-24 fix-r5 補）：llm 項讀驗過的每份 llm.json，每個模型代號（endpoint＋model＋api_key 一樣的只打一次）打一次最小請求，每個一行 `probe/<代號>`：
先 `GET <endpoint>/models`（有 `api_key` 就帶 `Authorization`），2xx＝ok（回的清單讀得懂又沒有這個 `model` 就改 warn「endpoint 通，但模型清單裡沒有 <model>」）；回 404／405（有些端點不給清單）就改 `POST <endpoint>/chat/completions` 一句話（`max_tokens: 1`），2xx＝ok；
連不上、逾時、其他 HTTP 錯＝bad，寫原因與 endpoint（金鑰遮掉）。每個請求最多等 `min(timeout_ms, 10 秒)`。有 `--probe` 時總結行改成 `設定檢查通過；模型連線也測過`。

**ls**：（09-24 advice-r1 改）表格的長相、`-v` 與 `--json` 的欄位搬到 [cli-ls.md](cli-ls.md)；這裡只留第一行 health 的判定。
（09-24 試玩 r3 補，取代 r2 的尾巴 `hint` 行）文字摘要**第一行** `health <一句>` 說整體正不正常，把「停住」跟「正常忙碌」分開；先中先印：
缺 `requests/`／`responses/`／`cpus/`＝`K 家缺目錄：…（跑 aos-kernel check --target <K>）`；`phase` 是 `stopped` 或從沒 boot＝`停機中（aos-kernel boot --target <K> --daemon-target <D>）`；daemon 沒活＝`daemon 沒在跑：<D>（先 aos-daemon boot --target <D>，再 aos-kernel boot …）`；info 或帳本的 cpu 不在 daemon 孩子表／`missing`＝`cpu missing：<名字>（跑 aos-kernel boot …）`；（09-24 fix-r5 補）daemon 孩子表裡有這些 cpu、但 `state` 是 `dead`（死了、daemon 等著重拉）＝`恢復中（<名字> cpu dead，daemon 重拉中）`；`phase` 是 `running` 但 `state.json` 超過 max(10 秒, 10 格) 沒更新＝`tick 停住：N 秒沒前進（跑 aos-kernel check --target <K>）`；其他＝`ok`。帳本或 info 讀不到＝`kernel 家讀不到：…`（這時 `ls` 照舊退 1）。`--json` 的 `health: {code, message}` 是同一句（code：`ok`／`dirs`／`stopped`／`daemon`／`cpus`／`recovering`（fix-r5）／`stall`／`broken`，再加下面 agent 的三個；schema 見 [cli-ls.md](cli-ls.md)）。同一套判定在 `lib/aos_kernel_health.py`，`aos-agent status` 也用它。
（09-24 fix-r5 補）**agent 的暫停也上第一行**：上面判完是 `ok` 時，`ls` 再看帳本裡的 agent（名字 `agent-` 開頭、不是 once、target 是某個家的 `tick.json`；讀那個家的 `paused`、`resumed`、`state.json` 的 `errors` 與沒到的 `continue-*.json` 門，不讀記憶、不拿鎖）：
有暫停的＝`agent 暫停中：agent-bob（連敗）、agent-amy（手動）（修好原因後 aos-agent continue --all）`（code `agents_paused`）；否則有連敗 1、2 次的＝`重試中：agent-bob（連敗 1/3）`（code `retrying`）；否則有 `resumed` 的＝`已解除暫停，等下一次成功：agent-bob`（code `resuming`）。這幾個 code 只在 `ls`，`aos-agent status` 不用（它有自己的一套，§1.3）。
每個 agent 的行程也標：`連敗暫停中`／`手動暫停中`／`重試中（連敗 N/3）`／`已解除暫停，等下一次成功`（advice-r1 起在 proc 表的 `備註` 欄）。
（09-24 fix-r5 補）**daemon 沒在跑時** cpu 不印孩子表裡留下的 `running`（daemon 被 KILL 時那份表不會更新；advice-r1 起整欄印 `-`，見 [cli-ls.md](cli-ls.md)）。
（09-24 試玩 r1 補）`bad` 的行程附 `看 <路徑>`：target 的 inst 有字面 `stderr` 就指它（agent 就是 `<agent>/log/agent.err`），否則指 target（advice-r1 起在 proc 表下面另起一行）。

（09-24 補）**ack**：`aos-kernel ack NAME [--target K]` 替 `K/responses/NAME` 放一則 ack（NAME 給檔名或路徑都行）；回音不在＝`NotFound`、退 1、不放檔。
給 `add --once` 不等的人用。

退出碼：0 成功；1 讀驗／daemon／I/O 錯，stderr 一行 `aos-kernel: <代號>: <白話>`；2 用法錯。
