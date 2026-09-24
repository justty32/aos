← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 1.7 `check`：start 之前先查一遍（09-24 advice-r1 補）

```
aos-agent check [--target DIR] [--probe]
```

使用者定的（09-24 advice-r1）：agent 的啟動前檢查不放在 `aos-kernel` 底下，改成 `aos-agent check`，家照 §1 的規矩用 `--target`、省略＝目前資料夾。
舊的 `aos-kernel check --agent DIR` 拿掉了，改成用法錯 2，訊息指到這裡（[kernel §6 check](../kernel/cli-ops.md)）。

**只讀**：不拿 tick 鎖、不寫檔、不放單；`--probe` 以外不連網路。家不是 agent 家＝`NotAnAgent`、退 1（跟其他子命令一樣，§1）。

## 找 K

不用給 `--target K`：先看 `AOS_KERNEL_HOME`（`start` 用的那個），沒設就用家裡 `tick.json` 記的（上次 `start` 寫的，§11；fix-r4 前的舊鍵 `AOS_K` 也認）。第一行講用了哪個：

- 找到：`ok   kernel: K＝<絕對路徑>（取自 AOS_KERNEL_HOME｜tick.json）`。
- `AOS_KERNEL_HOME` 不是絕對路徑＝`bad  kernel`（`start` 也會拒絕），K 的項目全部略過。
- `AOS_KERNEL_HOME` 有設、`tick.json` 也在，但它記的 K 跟 `AOS_KERNEL_HOME` 逐字不同、或讀不到字串 K（檔壞了、沒有 `envs.AOS_KERNEL_HOME`／`AOS_K`、值不是字串）＝多一行 `bad  kernel`（判法跟 `start` 一樣）：`start` 會回 `KernelMismatch`，要換 K 先 `stop` 再刪 `tick.json`；K 的項目照 `AOS_KERNEL_HOME` 那個查。
- 沒設 `AOS_KERNEL_HOME`，`tick.json` 在但讀不到絕對路徑 K＝`bad  kernel: 找不到 K：沒設 AOS_KERNEL_HOME，<家>/tick.json 也讀不到合法的絕對路徑 K；…`；兩個都沒有＝`bad  kernel: 找不到 K：沒設 AOS_KERNEL_HOME，也沒有 tick.json（沒 start 過）；export AOS_KERNEL_HOME=<kernel 家的絕對路徑> 再跑`。這兩種 K 的項目全部略過。

daemon 家：`AOS_DAEMON_HOME`，沒設就用 K 的 `info.json` 記的 `daemon`（上次 boot 寫的），再沒有才是目前資料夾（跟 `aos-kernel check` 不同：這裡沒有 `--daemon-target`，也通常不在 daemon 家裡跑）。

## 查什麼、印什麼

每項一行 `ok`／`warn`／`bad`，格式跟 `aos-kernel check` 一樣（`%-4s <項目>: <一句>`）。順序：

1. `kernel`（上面）。
2. **整段 kernel 的檢查**，跟 `aos-kernel check --target K` 同一份（[kernel §6 check](../kernel/cli-ops.md)）：`info`、`dirs`、`daemon`、`cpus`、`path`、`pools`、`llm/<cpu>`。K 的 `info.json` 讀不到＝`bad  info: …（K＝<路徑>，取自 …）`，後面的 kernel 項目不印。
3. **這個 agent 家**（原本 `--agent` 那幾項，內容不變）：`agent`（info 讀驗）、`agent/tick.pool`、`agent/llm.pool`（池在不在 K 的 cpu 表）、`agent/llm.model`（代號在不在 llm 項讀到的模型表）、`agent/tool/<名字>`（`_meta.argv[0]` 找不找得到、有沒有執行位；有 `/` 的相對路徑從家算，沒有 `/` 的照 daemon 的 PATH 找；寫成指示詞＝warn）。
   K 讀不到時池與模型沒法查：印一行 `warn agent/pools: K 讀不到，池與模型代號沒查；先修好上面的 kernel 項`，工具照查。agent 的 info 讀不到＝`bad  agent: <代號>: …`，後面的 agent 項不印。
4. （09-24 access-impl，round2 改 bad）**權限牆**（[access.md](access.md)）：
   - 沒 access 檔：家裡有要關牢的工具（沒寫 `_jail: false`）＝`bad  access: 沒有 access.json：<前 5 支名字> 這 N 支工具都不會跑（NoAccess）。先建一份：mkdir -p … && aos-agent access set ws … --cwd --target …`；工具全部 `_jail: false` 或沒工具就不印；以下略過。
   - `access`：解得開、名字、路徑存在、`cwd`、重疊（同送件那一套）＝`ok  access: <檔> 讀驗通過：N 個 mount、起點 …、net …`；不合＝`bad  access: <代號>: …`。`info.json` 明寫 `access` 卻指到不在的檔也是 bad。
   - `access/<名>`：mount 頂層有 socket／FIFO＝warn（牢裡連得到，唯讀也擋不住）。
   - `access/bwrap`：跑一次固定、無副作用的 bwrap（跟 aos-jail 同一組參數、不掛任何 mount、程式是 `true`）；找不到＝`bad … NoBwrap: …安裝指令`，開不起來＝bad 帶 bwrap 的訊息。
   - `access/aos-jail`：送件用的 `<這份 proto5>/cli/aos-jail`（絕對路徑，不看 PATH）不在或沒執行位＝bad。
   - `agent/tool/<名字>` 追加：`_jail: false`＝warn（這支不關牢）；關牢的工具 `_meta` 用 `$env` 讀了敏感名字＝`bad … EnvUnsafe: _meta 的 <位置> 用 $env 讀了 <名字>…`（跟送件同一個判定，位置像 `envs.FOO`、`argv.1.$fmt.k`，經 `$ref` 讀到的寫明找不到字面位置）；`argv[0]` 不含 `/`、而且在 PATH 找到的實體不在 `/usr/` 下（或找不到）＝warn（牢裡只有 `/usr`，可能找不到）；`argv[0]` 含 `/` 時，程式所在的資料夾（整個唯讀掛到 `/opt/tool`）是 agent 家、蓋到 agent 家、或裝著程式以外的信任資料＝warn。
   靜態查不完的（牢裡的直譯器、動態函式庫）不查。
5. `--probe` 才有：`probe/<代號>`，跟 `aos-kernel check --probe` 同一套（llm.json 裡每個 endpoint＋model＋api_key 只打一次）。
6. 最後一行總結：有 `bad`＝`有 bad，照上面的提示修好再 aos-agent start`；沒有＝`設定檢查通過；未測模型連線（--probe 會測）`，有 `--probe` 時是 `設定檢查通過；模型連線也測過`。

`check` 不看登記狀態、暫停與錯誤紀錄——那是 `status`（§1.3）。

## 退出碼

0＝沒有 `bad`（`warn` 不算）；1＝有 `bad`，或家不是 agent 家（stderr `aos-agent: NotAnAgent: …`，stdout 空）；2＝用法錯（例如 `--json`、不認得的旗標）。

## 例子

```
$ export AOS_KERNEL_HOME=$W/K
$ aos-agent check --target $W/bob --probe
ok   kernel: K＝/tmp/w/K（取自 AOS_KERNEL_HOME）
ok   info: kernel 設定讀驗通過
…
ok   agent/llm.model: 模型 default 存在
ok   agent/tool/date: 可執行 date
ok   probe/default: endpoint 通，模型清單裡有 deepseek-chat（…）
設定檢查通過；模型連線也測過
```
