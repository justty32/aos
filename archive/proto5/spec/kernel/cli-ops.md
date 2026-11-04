← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：add／ack／halt／check／退出碼

（2026-09-24 proto5-2 池式納入：halt 改等「每個池消失或歸 0」；check 改看池表；ls 的 health 行搬到 [health.md](health.md)、ls 本體在 [cli-ls.md](cli-ls.md)、cpu 在 [cli-cpu.md](cli-cpu.md)。2026-09-24 one-boot：halt 的 `not running` 改看 tick 登記；check 加 `tick` 項、拿掉 kernel 池；新增的 `proc` 放在 [cli.md](cli.md)。）

**add**：TARGET 轉絕對路徑放單（kernel 不解指示詞，指示詞是跑的時候 aos-exec 以它自己的規則解——`.json`
是檔所在資料夾、資料夾目標是資料夾本身）；旗標一對一對到 §2 的 params，`-- ARG...` 對到 `args`。
反覆＝等回音印 NAME；`--once` 預設不等、印自己取的檔名（`--name` 沒給時 NAME 就用這個檔名）跟回音會出現的路徑，
`--wait-ms N` 才等跑完印回音。`--pool` 省略＝`default`；池不在時 kernel 回 `-32602`，CLI 在訊息尾補「先 aos-kernel cpu add --target K --pool P」。

**CLI 等到回音就替你 ack**；沒等或等逾時就印出回音的路徑，之後自己去讀、自己 ack（逾時不取消工作）。
拿到 JSON-RPC `error` 印代號與 message、退 1；拿到 exec 的 `result` 整段印出來、退 0——**工作本身成不成功看內容**
（`kind`、`code`、`timed_out`、`stopped`），不看退出碼。

**ack**：`aos-kernel ack NAME [--target K]` 替 `K/responses/NAME` 放一則 ack（NAME 給檔名或路徑都行）；回音不在＝`NotFound`、退 1、不放檔。放了印一行 `acked NAME（ack 已放進 K/requests/，下一格 tick 刪掉回音）`（試玩 one-boot 追加：以前什麼都不印，新手以為沒成功）。
給 `add --once` 不等的人用。

**halt** 預設等停好（機制見 [§6 停機](boot.md)）：
- 沒帳本（沒 boot 過）＝印 `stopped`、退 0。帳本還是舊的 `state.json`＝`LedgerVersion`、退 1（先 `aos up`）。
- 帳本沒 `ticker`、那個 daemon 不活、或它沒登記這個 kernel（`D/kernels/` 沒這格）＝沒人開 tick：**不放單**（放了下次 boot 一開機就停）、印 `not running`。
  `phase` 已是 `stopped` 就不再放單、直接等。
- 其餘放 stop 單，等到 `phase=stopped` 且帳本裡每個池（含搬池中的舊位置，按 (daemon, dpool) 去重）在 daemon 那邊都確定消失
  或 `count 0`、`running 0`、`killing 0`、`draining 0`，印 `stopped`、退 0。
- 等超過 `--wait-ms`（預設 30000）＝`Timeout`、退 1（單已放、不撤回，用 `ls` 看）；訊息印出哪池讀不到或哪格不是 0，並提醒「這時去停 daemon 會留下非 0 的宣告，下次開 daemon 會拉回來」。
- `--no-wait`：只放單、不印、退 0，之後自己用 `ls` 等。停好之後才去停 daemon。

**check** 啟動前檢查，每項一行 `ok`／`warn`／`bad`，有 `bad` 退 1：
- `info`：讀驗（第 2 版池表）。`dirs`：`requests/`、`responses/`、`pools/` 在不在，缺＝bad（手建的家要 `mkdir -p` 補）。
- `daemon`：池表裡提到的每個 daemon 家、還有開 tick 的那個（頂層 `daemon`），都查活不活（沒開＝warn）；池或開 tick 的解不出 daemon＝bad（boot 會 `NoDaemon`）；
  活著時分開印「kernel 設定的池：…」與「daemon 目前有：…」（沒有就寫「還沒有」）。`--daemon-target D`（只能給一次，重複＝用法錯 2）再多查一個 daemon 家。
- `pools/<池>`：（試玩 one-boot 追加）那池在它的 daemon 那邊的名字（`dpool`）已經有 `pool.json`、而 `owner` 不是這個 K＝bad，提示在 info 那池寫不撞的 `dpool`（不然 `aos up` 會報 `NameTaken`）。daemon 沒開也查得到（`pool.json` 留著）。
- `ledger`：（one-boot）帳本還是舊的 `K/state.json`＝warn（`aos up` 或 boot 會換成 sqlite），這時不印 `tick`、`cpus`。
- `tick`：（one-boot）帳本 `phase` 是 `running`／`stopping` 時看開 tick 的 daemon：活著卻沒登記這個 kernel＝bad（`aos up` 或 boot）；登記著但連敗＝warn（看 daemon 的 stderr，例如 `D/daemon.log`）；正常＝ok `daemon D 每 N ms 開一格 tick`。
- `cpus`：帳本在、`phase` 是 `running`／`stopping`、daemon 活著的已宣告池，看摘要（同 [health](health.md)：工作池少顆＝warn）。一個都沒有就不印。
- `path`：`aos-exec`、`aos-cpu`、`aos-kernel`、`aos-agent`、`aos-llm` 在 daemon 的 PATH 找不找得到（讀得到 `/proc/<daemon pid>/environ` 就用它，省略 `--daemon-target` 時取開 tick 的那個 daemon；否則用目前 shell 的並註明）。
- `pools`：列出每池 `count`（沒有工作池＝`還沒有工作池`）；info 還有舊版的 `kernel` 池＝warn（可以刪）；**不強制**有叫 `llm` 的池（agent 可以把 `llm.pool` 設成別的名字，純工具的 kernel 也合法）。`K/pools/<P>/envs.json` 跟 info 的 envs 不同＝warn。
- `llm/<池>`：**對每個 envs 裡有 `AOS_LLM_CONFIG` 的池各查一次**（`K/pools/<池>/envs.json` 在就讀它，否則讀 info；envs 整個是指示詞、看不出來的池不查）：
  路徑在不在、llm.json 讀驗過不過、有哪些模型代號。
- **agent 不在這裡查**：`aos-kernel check` 給 `--agent`（帶不帶值、給幾次都一樣）＝用法錯 2，stderr 指到 [`aos-agent check`](../aos-agent/cli-check.md)；`-h` 不列 `--agent`。
  那邊查的池項：`tick.pool`／`llm.pool`／`tool_pool` 三格都要是 K 的 `pools` 的 key、不是 `kernel`（不是＝bad），那池 `count` 是 0＝warn（會一直排隊）；
  llm 項只查**那個 agent 的 `llm.pool`** 那池（envs 整個是指示詞也照查）。
- check 預設只驗設定，**不連 endpoint**：全綠不代表模型連得上。最後印一行總結：沒 `bad`＝`設定檢查通過；未測模型連線（--probe 會測）`，有 `bad`＝`有 bad，照上面的提示修好再 boot`。
- **`--probe`**：llm 項讀驗過的每份 llm.json，每個模型代號（endpoint＋model＋api_key 一樣的只打一次）打一次最小請求，每個一行 `probe/<代號>`：
  先 `GET <endpoint>/models`（有 `api_key` 就帶 `Authorization`），2xx＝ok（清單讀得懂又沒有這個 `model` 就改 warn「endpoint 通，但模型清單裡沒有 <model>」）；
  回 404／405 就改 `POST <endpoint>/chat/completions` 一句話（`max_tokens: 1`），2xx＝ok；連不上、逾時、其他 HTTP 錯＝bad，寫原因與 endpoint（金鑰遮掉）。
  每個請求最多等 `min(timeout_ms, 10 秒)`。有 `--probe` 時總結行改成 `設定檢查通過；模型連線也測過`。

**proc**（2026-09-24 one-boot 新增，查一筆行程、`--json` 的形狀與退出碼）：在 [cli.md](cli.md) 的 proc 段。

**退出碼**：0 成功；1 讀驗／daemon／I/O 錯，stderr 一行 `aos-kernel: <代號>: <白話>`；2 用法錯。`tick` 另有 75＝鎖被佔（別的一格在跑，[§3](tick.md)）。
