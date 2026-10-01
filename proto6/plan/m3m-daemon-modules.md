# 第三段之三：daemon 的五個模組

← [plan 入口](README.md)｜**接在 [m3 核心](m3-daemon-core.md)、[m3n 控制模組](m3n-control-module.md) 之後。**｜spec 正本：[B-640 核心](../spec/settled/daemon/core.md)、[B-641 控制](../spec/settled/daemon/control.md)、格式 [P-120](../spec/settled/protocol/daemon/core.md)、[P-121](../spec/settled/protocol/daemon/control.md)｜舊規劃（暫緩區）：[總表](../spec/settled/deferred/README.md#daemon-與-helper)

**狀態（2026-10-01 第十二批裁定後）**：

| 模組 | 狀態 | spec |
|---|---|---|
| 一、重讀設定 `reload` | **已做**（R1～R4 照建議，R3 改成 stdout 警告） | [B-642](../spec/settled/daemon/reload.md)、[P-122](../spec/settled/protocol/daemon/reload.md) |
| 二、收屍／cgroup `cgroup` | **已做**（第十二批：C1～C4 照建議） | [B-644](../spec/settled/daemon/cgroup.md)、[P-124](../spec/settled/protocol/daemon/cgroup.md) |
| 三、記住狀態 `state` | **已做**（S1～S3 照建議，設定改成 `$ref`） | [B-643](../spec/settled/daemon/state.md)、[P-123](../spec/settled/protocol/daemon/state.md) |
| 四、訊息 `mq` | **已做**（第十二批：M1～M4 照建議） | [B-645](../spec/settled/daemon/mq.md)、[P-125](../spec/settled/protocol/daemon/mq.md) |
| 五、帳號 `account`（原草稿叫 helper） | **排隊**（第十二批：要做、排最後；H1 改成拆 root 端、主程式降權，下面草稿待重寫） | — |

做了什麼、自己定的細節見篇末[做完了沒](#做完了沒)；裁定見 [verdicts 11 第十一批](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十一批daemon-模組)、[第十二批](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十二批cgroup-與帳號)。下面各節保留原本的草稿，裁定處就地標註。

> **使用者方向（2026-10-01，原話）**：「node這塊不要動，我有預感，node相關概念以後會不存在。剩下這些都值得做成模組。」「剩下這些」＝重讀設定、收屍／cgroup、記住狀態、訊息、helper／跨帳號五個。所以：**不做 node 模組**（[verdicts 11「node 模組方向」](../notes/verdicts/11-tick-as-unit.md#node-模組方向2026-10-01記錄用未排程)照留、不排程），**五個模組一律以「daemon 設定檔 `insts` 裡的一項」為單位**，不認得資料夾、任務表、上下層。

> **POC 總原則**（[plan 入口](README.md)）：默認一切正常，不為異常寫處理，出事自然丟錯、回 1。結束碼 0＝預料之中、非 0＝要額外處理、1＝通用錯誤。

## 先講現在的 daemon

`aos-daemon --config F` 就是一個叫 `aos-exec` 的 cron：設定檔 `insts` 是物件，鍵＝inst 字面值、值＝這一項的設定（`interval_ms`、`stop_on_nonzero`）；每一項一條執行緒，開起來先跑一次，之後「上一次結束後隔 `interval_ms`」再跑；每次結束 stdout 印一行 `inst=… exit=… ms=…`；非 0 且 `stop_on_nonzero` 就印 `stopped`、不再叫；Ctrl-C 直接退出、不殺子程序。整份設定先展開指示詞。掛了控制模組時多一個 unix socket，收 wake／pause／resume／status（每個只對一項），並把 `AOS_DAEMON_SOCKET`、`AOS_DAEMON_INST` 傳給每次的 `aos-exec`。狀態（暫停、已停、待補）都在每項的 `Item` 裡、只放記憶體。程式：`src/py/lib/aos_daemon.py`、`aos_daemon_ctl.py`、`aos_ctl.py`。

## 模組怎麼掛

- 設定檔頂層 `modules` 物件，**一個模組一個鍵，有寫就開**，沒寫就跟現在一模一樣（[B-640「模組」](../spec/settled/daemon/core.md#模組modules)）。核心不認得的模組鍵照收不理。
- 本檔用的鍵名（**都是建議**，見待問 G1）：`reload`、`cgroup`、`state`、`mq`、`helper`。
- **跟某一項有關的模組設定**（例如這一項的記憶體上限、這一項用哪個帳號）放在 `insts` 那一項的設定物件裡、用模組名當鍵；模組沒掛時核心照「不認得的鍵忽略」不看（m3n「這段不做的」末列已提過這個寫法；見待問 G2）：

  ```json
  {
    "interval_ms": 60000,
    "modules": {"control": {"socket": "./aos.sock"}, "cgroup": {}},
    "insts": {
      "a": {"cgroup": {"memory.max": "512M"}},
      "jobs/report.json": {"interval_ms": 5000}
    }
  }
  ```

## 本檔原則

1. **能用 hooks、包一層程式、inst 自己做到的，就不做模組。** 每個模組都寫一句「為什麼不能只靠包一層」；說不出來的部分就砍掉。
2. **照 POC 總原則砍到最單純。** 每個模組只留「沒有它就做不到」的那一件事；邊緣情況、上限、權限分級、事項、重試都先不做，列在各節「建議先不做」。
3. **不碰 node。** 舊規劃裡靠 node、上下層、runner、通道憑證、登記表的前提一律拿掉，各節「舊前提已不在」逐條列。
4. **模組之間盡量不互相依賴。** 每個都要能單獨掛；有關係的（例如記住狀態要記控制模組的 pause）寫清楚「沒掛另一個時會怎樣」。

---

## 模組一：重讀設定（`modules.reload`）

> **已做**（2026-10-01 第十一批）：R1～R4 照建議，但 **R3 改**：使用者原話「R3這邊，如果最上層這些改了，那就stdout輸出警告。」——`cwd`、`modules` 改了不套用、在 **stdout** 印 `reload: need restart: cwd`（或 `modules`）。R4 照建議（stderr 一行、舊的照跑）。spec [B-642](../spec/settled/daemon/reload.md)。

舊規劃：[暫緩區 B-608 熱重載](../spec/settled/deferred/daemon/reload.md)。

### 要做到什麼（最單純的版本）

改了設定檔，送 daemon 一個 SIGHUP，daemon 重讀同一份設定檔（照樣整份展開指示詞），跟現在比對 `insts`：

| 情況 | 怎麼辦 |
|---|---|
| 新出現的鍵 | 開一條新執行緒，**照「開起來先跑一次」立刻跑** |
| 不見的鍵 | 不再排下一次；正在跑的那次不殺、讓它跑完印完；之後控制指令對它回 `unknown_inst` |
| 鍵還在、設定改了（`interval_ms`、`stop_on_nonzero`，含頂層預設改了連帶影響的） | 原地換值；暫停、已停、待補照留；新週期從**上一次結束時刻＋新 `interval_ms`** 重算（待問 R2） |
| 頂層 `exec_out_path`、`exec_err_path` 改了 | 照新的算，下一次寫出起生效 |
| 頂層 `cwd`、`modules` 改了 | **不套用**，印一行說要重開（待問 R3） |

- stdout 每項印一行：`inst=<inst> added`、`inst=<inst> removed`；最後一行 `reloaded`。設定改了的項不另印（status 看得到）。
- 拿掉的鍵之後又加回來：當成新的一項（狀態從頭）。
- 沒掛這個模組時，SIGHUP 照 Python 預設（就是現在的樣子：daemon 被殺）。

### 設定

```json
"modules": {"reload": {}}
```

`reload` 物件裡沒有鍵；有寫就開。

### 跟控制模組、其他模組的關係

- **控制模組**：使用者已定控制 socket 只收四個指令、不收 reload（[m3n 開頭裁定 1](m3n-control-module.md)），所以觸發走 SIGHUP，控制模組一行不用改；只有它手上那份 `{inst: Item}` 對照表要換成重讀後的（加一把鎖）。要不要之後讓任務也觸發得到，見待問 R1。
- **記住狀態**：拿掉的項，下一次寫狀態檔時一併拿掉。
- **收屍**：新項建自己的 cgroup；拿掉的項等它這次跑完、清完再刪 cgroup。
- **訊息**：拿掉的項，信箱裡沒取的信丟掉；之後寄給它回 `unknown_inst`。
- **helper**：某項的 `helper.user` 改了，下一次開 `aos-exec` 起用新帳號。

### 為什麼不能只靠包一層

daemon 手上的清單只有 daemon 自己改得了；外面能做的只有「重開 daemon」，那會把所有項的暫停、待補、週期一起洗掉（掛了記住狀態也只留得住暫停與已停）。

### 舊前提已不在

roots、`node_id` 改名、`identity_grant`、`provision`、helper 固定設定副本、`common_user`、`socket_path`、`state_dir`、`cgroup_root`、五個 `enable_*` 開關、`restart_required`／`config_invalid` 寫進 daemon 事項、排空中不重載——這些欄位與機制現在都沒有。B-608 的「免重開／要重開」大表縮成上表五列。

### 建議先不做

- 自動偵測設定檔改了（看 mtime、inotify）：`$ref` 引進來的檔也要一起看，麻煩；先手動 SIGHUP。
- 套用一半：重讀出錯時不做任何部分套用（見待問 R4）。
- 重讀時印出不認得的欄位。
- 改 `modules`（掛上或卸下模組）免重開：一律要重開。

### 要使用者裁定的點

- **R1．用什麼觸發？** (a) SIGHUP；(b) 控制 socket 加 `reload` 指令（推翻「只收四個」）；(c) daemon 自己每隔幾秒看設定檔有沒有改。**建議 (a)**：不用新協議、不靠控制模組，人手 `kill -HUP <pid>`。缺點是任務裡不知道 daemon 的 pid；真要讓任務觸發，之後再在控制模組加 (b)。
- **R2．某項的 `interval_ms` 改了，下一次什麼時候跑？** **建議：上一次結束時刻＋新週期**（已經過了就立刻跑）。另一種是「等原本排好的那次跑完才換新週期」，週期從 1 小時改 1 分鐘時要白等 1 小時。
- **R3．頂層 `cwd`、`modules` 改了怎麼辦？** **建議：不套用，stdout 印一行 `reload: need restart: cwd`（或 `modules`），其他照套。** `cwd` 一改，所有相對的 inst 意思都變了，等於換一份清單；`modules` 一改要開關 socket、cgroup，留給重開最單純。
- **R4．重讀時設定檔壞了（JSON 壞、指示詞錯、缺 `interval_ms`）怎麼辦？** 照 POC 總原則該「自然丟錯、回 1」，但那會把一個跑得好好的 daemon 打掉。**建議：當成跟控制 socket 壞請求一樣的例外——整份不套用、stderr 印一行 `aos-daemon: reload: <說明>`，舊設定照跑。** 這是本模組唯一的異常處理。

### 驗收草稿

- 兩項跑著，設定檔加第三項、送 SIGHUP：第三項 1 秒內有 `exit=` 行，stdout 有 `added`、`reloaded`；原本兩項的週期不受影響。
- 拿掉一項（假 inst `sleep 1`、正在跑）、送 SIGHUP：那次照樣印完 `exit=`，之後再也沒有它的行；`aos-ctl status` 它回 `unknown_inst`。
- 某項 `interval_ms` 從 10 秒改 100 毫秒：重讀後很快開始密集跑。
- 暫停中的項，重讀後（設定沒動它）還是暫停。
- 設定檔改壞、送 SIGHUP：daemon 沒死、stderr 一行、舊設定照跑；改回來再送一次照常套用。
- 改頂層 `cwd`：stdout 有 `need restart`，各項照舊跑。
- 沒掛模組：m3、m3n 的測試照樣全過。

---

## 模組二：收屍與資源上限（`modules.cgroup`）

> **已做**（2026-10-01 第十二批）：C1～C4 使用者原話「都先按照建議。」下面草稿照原樣留著；做法與 AI 隊定的細節見篇末[做完了沒](#做完了沒)，正本 [B-644](../spec/settled/daemon/cgroup.md)。

舊規劃：[暫緩區 B-605 與各條 cgroup 部分](../spec/settled/deferred/daemon/cgroup.md)；tick 側 [`aos-cg`（B-634）](../spec/settled/tick/cg.md)。

### 要做到什麼（最單純的版本）

- daemon 開起來時，把**自己所在的 cgroup** 當子樹根（要求是委派給自己的 cgroup v2 子樹，例如用 `systemd-run --user --scope -p Delegate=yes aos-daemon --config F` 開）。先開一個子框 `daemon`、把自己搬進去（cgroup v2 規定開了 controller 的那層不能放程序），再在根上開 `+cpu +memory +pids`。
- **每一項一個框** `i-<h>`（`<h>`＝inst 字面值 UTF-8 的 sha256 前 16 個 hex；字面值有 `/`，不能直接當框名）。第一次跑前建。
- 每次開 `aos-exec` 都放進那一項的框（子程序 exec 前把自己寫進 `cgroup.procs`）。
- **`aos-exec` 結束後**：框裡還有程序就寫 `cgroup.kill`，等 `cgroup.events` 的 `populated 0`，再印那一行 `exit=`、排下一次。這就是「收屍」：任務 `setsid`、double fork 留下的常駐程序，都在這一刻清掉。
- 有清到東西時另印一行 `inst=<inst> reaped`（建議，讓人知道有殘留）。
- **上限**：那一項設定裡寫的 cgroup 檔名與值，建框時原樣寫進框裡（`memory.max`、`cpu.max`、`pids.max`）。沒寫就不設限。
- **開起來時**：框已經在（上次同一個 scope 裡留下的）就先 `cgroup.kill` 清空再用。

### 設定

```json
"modules": {"cgroup": {}},
"insts": {
  "a": {"cgroup": {"memory.max": "512M", "cpu.max": "50000 100000", "pids.max": "200"}},
  "b": {}
}
```

- `modules.cgroup` 物件裡沒有鍵（子樹根就是 daemon 自己所在的那層）。
- 每項的 `cgroup`：鍵＝cgroup 檔名、值＝字串，原樣寫進去；daemon 不認得也不檢查是哪些檔（默認一切正常）。

### 跟控制模組、其他模組的關係

- **核心的週期**：「上一次結束」改成「`aos-exec` 結束**而且框清空**」，下一次才排。所以同一項的殘留絕不會跟下一次疊著跑。
- **控制模組**：不用改；status 的 `running` 在清框期間仍是 `true`。要不要加一個「現在就砍掉這一項」的指令，見「建議先不做」。
- **重讀設定**：新項建框；拿掉的項清完刪框；某項上限改了就重寫那幾個檔（cgroup 上限本來就能隨時改）。
- **helper**：daemon 是 root 開的時候，框要先交給那一項的帳號才搬得進去，見模組五的待問 H3。
- **Ctrl-C**：daemon 照現在「直接退出、不殺子程序」；框留著，下次開起來時才清（上面最後一條）。

### 為什麼不能只靠包一層

其實**包一層做得到一大半**：inst 的 argv 寫 `["systemd-run", "--user", "--wait", "--pipe", "-p", "MemoryMax=512M", "--", "aos-tick", "."]`，systemd 會開一個 service、主程序結束時把同一框的殘留殺掉。缺點：要另外帶環境、工作目錄（service 不繼承）；每次多一個 systemd unit；控制模組的環境變數要手動傳；沒 systemd 就不能用。使用者已定「值得做成模組」，模組的好處是設定一處寫、每項自動有框、跟週期綁在一起（清完才排下一次）。

### 舊前提已不在

node 框 `n-<h>` 與它底下的 `tick`、`task-*`、`mount-*`、子 node 框（上下層）；runner 開在框裡、runner 回報後收；掛載行程的框；逃生口（node 自開子框、`kill_escape_cgroups`）；`state.json` 的 `cgroup_root_last` 找舊框；B-611 的 cgroup 子樹鎖；`cgroup_limits` 走 `node.provision`；helper 建框交框；`--create-cgroup`、`cgroup_root` 設定；啟動印 `cgroup=on/off`。現在一項就一個平的葉框，掛在 daemon 自己的子樹下。

### 建議先不做

- **沒 cgroup 時的退路**（舊規劃退回 runner／程序群組）：照默認一切正常，掛了模組就要有 cgroup，沒有就自然丟錯、回 1（見待問 C1）。
- 逃生口：想留常駐程序的就別放進這個 daemon，或之後再加。
- 逾時（跑太久就砍）。
- 控制指令「現在就砍掉這一項」（`kill`）。
- 量測（記憶體用量、CPU 時間、OOM 次數）寫進 status 或 stdout。
- `aos-cg`（每個任務一框）：它原本放在 node 框底下；要跟這個模組接，項的框得改成「分支＋葉框 `run`」，等真的要用再說。暫緩區記的已知問題（`aos-cg` 收尾會殺到自己，[暫緩區「已知的設計問題」](../spec/settled/deferred/README.md#已知的設計問題記錄這輪不改)）也一起留著。
- 多個 daemon 用同一棵子樹的偵測。

### 要使用者裁定的點

- **C1．掛了模組卻沒有委派好的 cgroup v2 時怎麼辦？** **建議：照 POC 總原則自然丟錯、回 1，不退回。** 另一種是退回「殺掉 `aos-exec` 的程序群組」（現在每次本來就開在新 session 裡，幾行就寫得出來），但 `setsid` 跑掉的抓不到，等於半套收屍；要的話可以另做成模組選項。
- **C2．每項的上限寫在哪？** **建議：寫在 `insts` 那一項的 `cgroup` 鍵**（見 G2），鍵用 cgroup 檔名原樣寫（`memory.max`），daemon 不翻譯。另一種是在 `modules.cgroup` 裡放 `{"<inst>": {...}}` 對照表，或改用好記的名字（`memory_max_mb`）由 daemon 換算。
- **C3．收屍要不要先客氣一下？** 舊規劃與 `aos-cg` 都是直接 `cgroup.kill`（SIGKILL），不先送 SIGTERM。**建議：照舊直接殺**；任務要收乾淨，自己在結束前收。
- **C4．框名用 inst 字面值的雜湊還是第幾項？** **建議：雜湊**（重讀設定後「第幾項」會變，框就對不上）。缺點是人看框名認不出是哪一項；daemon 開框時可以在 stdout 印一次 `inst=<inst> cgroup=i-<h>`。

### 驗收草稿（要有委派的 cgroup v2；沒有就整組跳過，不算失敗）

- 用 `systemd-run --user --scope -p Delegate=yes` 開 daemon：子樹根下有 `daemon` 與每項一個 `i-<h>`，daemon 自己在 `daemon` 裡。
- 假 inst 用 `setsid sleep 100 &` 留程序：`exit=` 那行之後有 `reaped`，`sleep` 已經不在；下一次跑之前框是空的。
- `memory.max` 設 `64M`、假 inst 吃 200M：被 OOM 殺，`exit=` 照實印（137）。
- `pids.max` 設 `5`：fork 第 6 個失敗。
- 沒委派（直接在 shell 開）：回 1、stderr 有 traceback 或一行說明（看 C1）。
- 沒掛模組：m3、m3n 測試照樣全過。

---

## 模組三：記住狀態（`modules.state`）

> **已做**（2026-10-01 第十一批）：S1～S3 照建議（不記上次結束時間；已停也跨重開；每次變動當場寫整份）。**設定改了**：使用者原話「"state":{"$ref":...}會比較好，因為有時候它會頻繁被改動。」——下面「設定與檔案」那段的 `{"path": …}` 作廢，改成 `"modules": {"state": {"$ref": "aos-state.json"}}`，`$ref` 指的檔就是狀態檔，展開後 `modules.state` 就是目前狀態。spec [B-643](../spec/settled/daemon/state.md)。

舊規劃：[暫緩區 B-603「存檔與讀回」「pause 批次存檔」](../spec/settled/deferred/daemon/lifecycle.md#存檔與讀回)、格式 [P-116 state.json](../spec/settled/deferred/protocol/daemon/shutdown.md)。

### 要做到什麼（最單純的版本）

- 每次某一項的「暫停」或「已停」變了（pause、resume、`stop_on_nonzero` 停掉），**當場**把所有項的這兩個狀態整份寫進一個 JSON 檔（先寫暫檔再 rename）。
- daemon 開起來時讀這個檔：還在 `insts` 裡的項，照檔裡的恢復成暫停或已停，**這些項開起來就不先跑那一次**；不在 `insts` 裡的鍵丟掉；檔不在就當全部正常。
- 恢復時 stdout 印 `inst=<inst> paused`、`inst=<inst> stopped`（跟平常同樣的行），讓人看得出它沒在跑。

### 設定與檔案

~~`"modules": {"state": {"path": "./aos-state.json"}}`，`path` 必填，相對以起點為準。~~（第十一批改成下面這樣）

```json
"modules": {"state": {"$ref": "aos-state.json"}}
```

- 原始值必須是 `$ref`（不帶 `#` 位置），相對以**設定檔所在資料夾**為準（跟其他 `$ref` 一樣）；檔不在＝全部正常，第一次要寫時才建（先寫暫檔再 rename）。
- 檔的內容只列「不是普通狀態」的項：

  ```json
  {"insts": {"a": {"paused": true}, "jobs/report.json": {"stopped": true}}}
  ```

### 跟控制模組、其他模組的關係

- **控制模組**：暫停只能經控制模組下；沒掛控制模組時，這個模組只記得住「被 `stop_on_nonzero` 停掉」，而且救不回來（沒有 resume），只能刪狀態檔再重開。這樣也合理：重開 daemon 不會讓一個已經壞掉的項默默又開始跑。
- **控制的 status**：不用改。
- **擋板檔**：m3n 說「要重開也不跑，用 tick 的擋板檔」；掛了這個模組之後，daemon 這層就有自己的辦法，擋板檔照舊是 tick 那層的事，兩者不衝突。
- **重讀設定**：拿掉的項，下一次寫檔時就不在了。
- **其他模組**：訊息信箱、cgroup 框都不記。

### 為什麼不能只靠包一層

暫停與已停是 daemon 記憶體裡的狀態，外面看不到也寫不進；包一層只能做「擋板檔」那種 tick 層的停法。

### 舊前提已不在

`state_dir`、登記表存讀與讀回後重核身分授權、`clean_shutdown`、`pause_save_interval_ms` 批次存檔、未處理 wake 接回、boot id、PID 提示檔、`cgroup_root_last`、B-611 的排他鎖、逐層重建。現在只有「哪幾項暫停、哪幾項已停」兩個布林。

### 建議先不做

- 記待補的那次 wake（重開就算了）。
- 記上次結束時間、讓週期跨重開接續（見待問 S1）。
- 記 `last_exit`。
- 寫不進、讀不懂的處理（默認一切正常）。
- 多個 daemon 共用同一份檔的保護。

### 要使用者裁定的點

- **S1．要不要連「上次什麼時候跑完」也記，讓重開後不立刻跑？** 例如一天一次的項，現在每次重開 daemon 都會馬上多跑一次。**建議：第一版不記**，照 B-640「開起來先各跑一次」；真的有每天一次的項再加（加的時候是同一個檔多一個欄位）。
- **S2．`stop_on_nonzero` 停掉的狀態也要跨重開嗎？** 使用者方向是要。**建議：要**；但這樣「重開 daemon 救回停掉的項」這條路就沒了（B-640 現在寫「沒掛控制模組就重開 daemon」），要救得 `aos-ctl resume` 或刪狀態檔。B-640 那句之後跟著改。
- **S3．什麼時候寫？** **建議：每次變動當場寫整份**（暫停、恢復、停掉都很少發生，不用像舊規劃那樣批次）。另一種是只在 Ctrl-C 退出時寫，但被 `kill -9` 或當機就全丟。

### 驗收草稿

- 掛控制與狀態模組，`aos-ctl pause a`：狀態檔裡 `a` 是 `paused:true`；Ctrl-C 重開：`a` 沒有先跑那一次、stdout 有 `inst=a paused`、status 是 `paused:true`；`resume` 後馬上跑、檔裡 `a` 不見了。
- `{"argv":["false"]}` 帶 `stop_on_nonzero`：停掉後檔裡有 `stopped:true`；重開後它不跑、有 `inst=… stopped`。
- 檔裡有一個設定檔已經沒有的鍵：重開時忽略，下一次寫檔時它就不見了。
- 檔不在：全部照常先跑一次。
- 沒掛模組：m3、m3n 測試照樣全過。

---

## 模組四：訊息（`modules.mq`）

> ~~暫緩~~（第十一批：「aos-mq先不做」）→ **已做**（2026-10-01 第十二批：M1～M4 照建議）。下面草稿照原樣留著；做法與 AI 隊定的細節見篇末[做完了沒](#做完了沒)，正本 [B-645](../spec/settled/daemon/mq.md)。

舊規劃：[暫緩區 B-614 暫存訊息與急件](../spec/settled/deferred/daemon/messaging.md)、格式 [P-119](../spec/settled/deferred/protocol/daemon/channel.md#p-119送訊息取訊息與通道錯誤碼使用者方向-2026-09-30第十九批參數與上限為建議預設)；tick 側 [`aos-mq get`／`post`（B-623、B-624）](../spec/settled/tick/mq.md)。

**單位換了**：舊規劃是「node 寄給 node」，收件人是 node id、權限看收件 node 資料夾 `.aos/mq/get/` 的寫權。使用者預感 node 會消失，所以這裡**收件人就是 daemon 的一項**（inst 字面值）；不認得資料夾，inst 是檔也收得到信。

### 要做到什麼（最單純的版本）

- daemon 另開一個 unix socket（**不走控制 socket**，使用者 m3n 裁定 5），協議照控制 socket 的樣子：一連線一請求、一行 JSON 來、一行 JSON 回。
- **每一項一個信箱**，放 daemon 記憶體、先進先出。daemon 重開就丟（不保證送達）。
- 兩個請求：
  - **寄**：`{"send":"<收件 inst>","msg":<任何 JSON 值>,"from":"<寄件 inst 或 null>","urgent":false}`。收件人不在 `insts` 回 `unknown_inst`；否則放進信箱、回 `{"ok":true}`。
  - **取**：`{"take":"<inst>"}`，回 `{"ok":true,"messages":[{"from":…,"msg":…},…]}`，一次全部取走、信箱清空。
- **急件**：`urgent:true` 時，放進信箱後**照控制模組 wake（不帶選項）的規則叫醒收件那一項**（正在跑就補一次；暫停中跑一次；已停不跑）。這段邏輯 daemon 已經有（`Item` 的 `pending`），不用掛控制模組也做得到。
- 小工具 `aos-mq`（名字見待問 M4）：

  ```text
  aos-mq send [--urgent] <收件 inst> <JSON>     # JSON 也可以從 stdin 讀（給 -）
  aos-mq take [<inst>]                          # 每封一行 JSON 印到 stdout
  ```

  - socket 從 `AOS_DAEMON_MQ_SOCKET` 拿；`take` 沒給 inst 就用 `AOS_DAEMON_INST`；`send` 的 `from` 自動填 `AOS_DAEMON_INST`（沒有就 `null`）。
  - 結束碼、stderr 照 `aos-ctl`：成功 0；`no_daemon:`、`no_inst:`、`connect:`、`unknown_inst:`、`bad_request:`、`usage:` 一律 1。

### 設定

```json
"modules": {"mq": {"socket": "./aos-mq.sock"}}
```

- `socket` 必填，相對以起點為準。掛了之後每次開 `aos-exec` 多放 `AOS_DAEMON_MQ_SOCKET`（絕對路徑）與 `AOS_DAEMON_INST`（見待問 M2）。

### 跟控制模組、其他模組的關係

- **控制模組**：各開各的 socket、互不依賴。急件叫醒直接動 `Item` 的狀態，不經控制 socket；規則跟 wake 一樣，以後 wake 規則改了（m3n 待問 1）兩邊一起改。
- **重讀設定**：拿掉的項連信箱一起丟；之後寄給它回 `unknown_inst`。
- **記住狀態**：信不記。
- **helper**：跨帳號的項要連得上這個 socket，見模組五的待問 H4。
- **tick 那一側**：任務裡直接叫 `aos-mq take`、`aos-mq send` 就能用，tick 核心一行不用改。

### 為什麼不能只靠包一層

**一部分可以**：寄件方把檔寫進收件方的資料夾、再 `aos-ctl wake <收件 inst>`，就有「信＋急件叫醒」。這是普通程式的事，aos 本來就不管（[B-623「檔案收件 aos 不管」](../spec/settled/tick/mq.md#檔案收件-aos-不管)）。模組多給的只有：不用對收件方的資料夾有寫權（跨帳號時有差）、收件方是檔不是資料夾也行、信不進 git 追蹤的範圍。使用者已定「值得做成模組」，所以做，但只做這三點用得到的最小部分。

### 舊前提已不在

node id 當收件人；`node.send`／`node.take` 的 method 名、封包與通道憑證（`AOS_TICK_TOKEN`）；「看寄件帳號對收件 node `.aos/mq/get/` 有沒有寫權」的授權；「每個 node 只有 `aos-mq get` 取」的約定（現在誰在那一項底下都能取，先取先得）；急件越過上層 kernel 節流（沒有上層）；B-615 `enable_messaging` 開關與 `not_available`；tick 側的 `.aos/mq/post/` 待送檔、`.aos/mq/failed/` 失敗紀錄、「先 git 提交再送」的排序、兩版範本裡的 `mq-get`／`mq-post` 系統級任務。

### 建議先不做

- 上限（每箱幾封、單封多大）：默認一切正常，先不設。
- 寄件權限：能連 socket 就能寄給任何一項、也能取任何一項的信（跟控制模組「能連就能做」一樣）。
- 送達確認、去重、重送。
- tick 側的 `aos-mq get`／`post` 系統級任務與 `.aos/mq/` 檔案流程（等真的有任務要「先提交再送」再說）。
- 跨 daemon 送信。
- 訊息格式檢查（舊規劃要求是 P-301 請求或回應物件；這版什麼 JSON 都收）。

### 要使用者裁定的點

- **M1．`from` 誰填？** **建議：`aos-mq send` 自動填 `AOS_DAEMON_INST`，daemon 原樣存、不核對。** 能連 socket 的人本來就能冒充，POC 不管；不要的話就拿掉 `from`，寄件人寫在信的內容裡。
- **M2．`AOS_DAEMON_INST` 誰放？** 現在只有掛了控制模組才放。**建議：掛了控制或訊息任何一個就放**（同一個值）；另一種是乾脆改成核心一律放（改 B-640），比較單純，但會讓「沒掛模組時跟 m3 一模一樣」不再成立。
- **M3．取信要不要限「只取自己」？** **建議：不限**，`aos-mq take <inst>` 可以取別項的（跟 `aos-ctl` 能對任何一項下指令一樣），沒給才用自己。
- **M4．名字：沿用 `aos-mq`、子命令改 `send`／`take`？** 舊名 `aos-mq get`／`post` 是「讀寫 `.aos/mq/` 檔」的系統級任務，意思不一樣。**建議：程式叫 `aos-mq`，子命令用 `send`／`take`**（跟 socket 上的請求名一致），舊的 `get`／`post` 留在 spec 當暫緩；模組鍵叫 `mq`。

### 驗收草稿

- 兩項 a、b；a 的任務跑 `aos-mq send b '{"hi":1}'`：回 0；b 下一次跑時 `aos-mq take` 印出一行 `{"from":"a","msg":{"hi":1}}`；再取一次是空的（回 0、什麼都不印）。
- 同上加 `--urgent`、b 週期 1 小時：b 在 1 秒內跑了一次。
- b 正在跑時連寄三封急件：b 跑完只補跑一次，三封一次取到。
- 寄給不存在的 inst：回 1、`unknown_inst:`。
- 沒有 `AOS_DAEMON_MQ_SOCKET`：回 1、`no_daemon:`。
- 先寄的先取到。daemon 重開後信箱是空的。
- 壞請求只影響那一條連線（照控制模組）。
- 沒掛模組：m3、m3n 測試照樣全過。

---

## 模組五：helper 與跨帳號（`modules.helper`）

> ~~暫緩~~（第十一批：「帳號也先不做」）→ **要做，排最後**（2026-10-01 第十二批）：模組鍵改叫 `account`（不叫 helper）；**H1 不照建議**，要拆出 root 端、主程式降權；socket 先 chmod 666（H4），之後會有多個 socket、權限另外設計。下面草稿是第十二批之前寫的，動工前要照這條重寫。

舊規劃：[暫緩區 B-303 root helper 與 `aos-as`](../spec/settled/deferred/helper.md)、[B-609 佈建與 helper 動作](../spec/settled/deferred/daemon/helper-actions.md)、P-102、P-107、P-108（[暫緩區 daemon 協議](../spec/settled/deferred/protocol/daemon/README.md)）。

### 要做到什麼（最單純的版本）

**某一項指定用哪個帳號跑**，daemon 就用那個帳號開那一項的 `aos-exec`。單位是 daemon 的一項：要換帳號的事，就做成另一項 inst，不在一格裡面中途換。

- 要 `sudo aos-daemon --config F` 開（root）。掛了模組卻不是 root：自然丟錯、回 1。
- 每項設定寫 `"helper": {"user": "bob"}`：開 `aos-exec` 時切成 bob（UID、主群組、補充群組都照 bob，等於 `initgroups`；環境裡 `HOME`、`USER`、`LOGNAME` 換成 bob 的）。
- 沒寫 `user` 的項：用**預設帳號**跑——`modules.helper.user`，沒寫就用 `SUDO_USER`（叫 sudo 的那個人）。**任何一項都不准用 root 跑**（寫 `root` 或 UID 0 就是設定錯、回 1）。
- 第一版的「helper」就是 daemon 自己（root）在開子程序時切帳號（Python 3.9 的 `subprocess.Popen(user=, group=, extra_groups=)` 一行做到）；**主程式降權、拆出獨立 root helper 程序**列在待問 H1。

### 設定

```json
"modules": {"helper": {"user": "guanyu"}},
"insts": {
  "a": {},
  "/srv/bob-job": {"helper": {"user": "bob"}}
}
```

### 跟控制模組、其他模組的關係

- **控制、訊息的 socket**：daemon 是 root，建出來的 socket 歸 root；bob 的任務要跑 `aos-ctl`、`aos-mq` 就得連得上。見待問 H4。
- **輸出檔**：`exec_out_path`、`exec_err_path` 是 daemon（root）寫的，檔會歸 root。默認一切正常，先不管；要的話寫完 chown 給預設帳號。
- **收屍**：root 建框、把子程序搬進去都沒問題，不用交框（舊規劃的交框是因為主程式不是 root）。見待問 H3。
- **記住狀態**：狀態檔由 root 寫。
- **重讀設定**：某項的 `user` 改了，下一次起生效。

### 為什麼不能只靠包一層

**其實包一層就做得到**：daemon 用一般帳號開，inst 的 argv 寫 `["sudo", "-n", "-u", "bob", "--", "aos-tick", "/srv/bob-job"]`，再在 sudoers 給一條 `guanyu ALL=(bob) NOPASSWD: /path/to/aos-tick`，一行程式都不用寫。缺點：每個帳號、每支程式都要寫 sudoers；環境變數要另外放行（sudo 預設會清掉 `AOS_DAEMON_*`）；設定散在兩個地方。模組的好處是帳號寫在 daemon 設定裡一處管。這點列成待問 H2。

### 舊前提已不在

node 的身分額度（`identity_grant`）、登記綁 UID；`aos-as` 經通道帶本格憑證送 `spawn_as`、交鎖 fd 與 stdio、回報 pipe、`.aos/jobs/` 暫存 inst；runner；`provision` 動作（建帳號、chown、quota、建群組、加群組成員、chgrp）；B-615 `enable_helper_actions` 與 `helper_unavailable`／`not_available`；PID 提示檔；inst 頂層 `user`（使用者 2026-10-01 已撤，這裡的 `user` 寫在 daemon 設定的那一項裡，不在 inst 裡）。

### 建議先不做

- **拆出獨立 root helper、主程式降權**（見 H1）。
- `aos-as`（一格裡某個任務換帳號跑）：要換帳號就拆成另一項。
- 佈建動作（建帳號、群組、chown、quota）：部署的人自己用系統指令先做好。
- 多帳號之間交接檔案的群組規劃：部署的人自己設。
- helper 被 kill 之後的處理。
- 檢查帳號存不存在、有沒有權限讀 inst（默認一切正常，錯了就是那一項回非 0）。

### 要使用者裁定的點

- **H1．第一版要不要真的「主程式降權＋獨立 root helper」？** 舊規劃的安全設計是：sudo 開時先 fork 出 root helper，主程式立刻永久降成一般帳號，要換帳號時才請 helper 開程序。**建議：POC 第一版不拆，daemon 整個留在 root、只在開子程序時切帳號**；介面（設定檔、行為）跟拆開後一樣，之後要拆不影響使用者。代價：daemon 本身（含 socket 收到的請求解析）以 root 跑，有漏洞就是 root 漏洞。
- **H2．要不要乾脆不做這個模組，改用「inst 自己包 `sudo -u`」？** **建議：照使用者方向做模組**，但在 plan／spec 記一句「不掛模組時，包 `sudo -n -u` 也行」當退路。
- **H3．收屍模組在 root 底下的子樹根從哪來？** root 開的 daemon 通常不在委派給它的 scope 裡。**建議：照樣要求「自己所在的 cgroup」**，寫成 `sudo systemd-run --scope -p Delegate=yes aos-daemon --config F`；不另加 `cgroup_root` 設定。
- **H4．root 建的 socket，別的帳號怎麼連？** (a) socket 檔 chmod 666，本機誰都能連；(b) chown 給預設帳號、chgrp 給一個群組、660，要用的帳號加進那個群組；(c) 每個帳號一個 socket。**建議：(a)**，POC 不設權限（照控制模組「能連就能做」）；正式版再改 (b)。

### 驗收草稿（要 root 與兩個測試帳號，手動跑、不進自動測試）

- 在可丟棄的機器上建 `aostest1`、`aostest2`；`sudo aos-daemon` 開，`a` 不寫 user、`b` 寫 `aostest2`：`a` 的任務 `id -un` 印叫 sudo 的人，`b` 印 `aostest2`，`id -G` 有 `aostest2` 的補充群組。
- 某項寫 `"user": "root"`：daemon 不開、回 1。
- 不用 sudo 開、掛了模組：回 1。
- `b` 的任務跑 `aos-ctl status`：連得上（看 H4）、回自己那一項。
- 掛收屍模組時，`b` 的殘留程序（歸 `aostest2`）照樣被清掉。
- 沒掛模組：m3、m3n 測試照樣全過（一般帳號跑）。

---

## 建議的實作順序

先前建議是 **重讀設定 → 收屍 → 記住狀態 → 訊息 → helper**。我的意見：**大致同意，只把「記住狀態」挪到第二**：

1. **重讀設定**：讓「清單會變」先成立，後面每個模組（框、狀態檔、信箱、帳號）一開始就照「項會加會減」寫，不用回頭補。它也是唯一要把 `{inst: Item}` 對照表改成會變的，先做最順。
2. **記住狀態**：最小（一個檔、兩個布林），而且跟控制模組的 pause／resume 直接接上，做完「暫停」這件事就完整了；跟重讀設定都在處理「項的集合變了」，接著做順手。
3. **收屍／cgroup**：要有委派的 cgroup v2 才驗得到，自動測試得能跳過；跟其他模組幾乎沒關係，放中間不卡人。
4. **訊息**：新 socket、新小工具，是五個裡最大的；要先定 M2（`AOS_DAEMON_INST` 誰放）。
5. **helper**：要 root 與測試帳號，只能手動驗；而且 H4 牽涉前面所有 socket，放最後一次看清楚。

收屍與記住狀態互換也可以（兩個互不依賴）；使用者偏好原順序就照原順序。

## 跨模組的待問

- **G1．模組鍵名**：`reload`、`cgroup`、`state`、`mq`、`helper`。**建議照這五個**；`cgroup` 也可以叫 `reap`（重點是收屍），但上限也在它裡面，叫 `cgroup` 比較貼。
- **G2．跟某一項有關的模組設定放哪？** **建議：放在 `insts` 那一項的設定物件裡，用模組名當鍵**（`"a": {"cgroup": {...}, "helper": {"user": "bob"}}`）；模組沒掛時核心照「不認得的鍵忽略」。另一種是全部放在 `modules.<名字>` 底下用 inst 字面值當鍵的對照表，好處是「沒掛模組時那一項的設定一個字都不多」。
- **G3．這五個要不要都進 spec 正本（B-642 起編號）？** **建議：每個模組做完、使用者看過再寫進 spec**，跟控制模組 B-641 一樣；暫緩區對應的舊條（B-608、B-605、B-603、B-614、B-303、B-609）屆時標「部分已被 B-xxx 取代」。〔第十一批：重讀設定、記住狀態做完就照使用者指示寫進 spec，B-642、B-643；B-608、B-603 已標部分取代。鍵名 `reload`、`state` 照 G1。〕

## 待問總表

| # | 模組 | 問題 | 建議 |
|---|---|---|---|
| R1 | 重讀設定 | 用什麼觸發 | SIGHUP；任務要觸發再加控制指令 |
| R2 | 重讀設定 | `interval_ms` 改了下一次何時跑 | 上一次結束＋新週期，過了就立刻跑 |
| R3 | 重讀設定 | 頂層 `cwd`、`modules` 改了 | 不套用，印一行「要重開」，其他照套 |
| R4 | 重讀設定 | 重讀時設定檔壞了 | 整份不套用、stderr 一行、舊的照跑（唯一例外） |
| C1 | 收屍 | 沒委派好的 cgroup v2 | 自然丟錯、回 1，不退回 |
| C2 | 收屍 | 上限寫在哪、用什麼名字 | `insts` 那一項的 `cgroup` 鍵，cgroup 檔名原樣 |
| C3 | 收屍 | 先 SIGTERM 再殺？ | 直接 `cgroup.kill` |
| C4 | 收屍 | 框名 | inst 字面值的 sha256 前 16 hex，開框時印一次對照 |
| S1 | 記住狀態 | 記上次結束時間、重開不立刻跑 | 第一版不記 |
| S2 | 記住狀態 | 已停也跨重開 | 要；B-640「重開救回」那句跟著改 |
| S3 | 記住狀態 | 何時寫檔 | 每次變動當場寫整份 |
| M1 | 訊息 | `from` 誰填 | `aos-mq send` 自動填 `AOS_DAEMON_INST`，不核對 |
| M2 | 訊息 | `AOS_DAEMON_INST` 誰放 | 掛了控制或訊息任一個就放 |
| M3 | 訊息 | 取信限不限自己 | 不限，沒給才用自己 |
| M4 | 訊息 | 名字 | `aos-mq send`／`take`，模組鍵 `mq` |
| H1 | helper | 主程式降權＋獨立 helper | POC 不拆，root 開子程序時切帳號 |
| H2 | helper | 改用 `sudo -u` 包一層就好？ | 照方向做模組，記 `sudo -u` 為退路 |
| H3 | helper | root 底下 cgroup 子樹從哪來 | 照樣用自己所在的 cgroup（`sudo systemd-run --scope -p Delegate=yes`） |
| H4 | helper | root 建的 socket 別的帳號怎麼連 | POC chmod 666 |
| G1 | 共通 | 模組鍵名 | `reload`、`cgroup`、`state`、`mq`、`helper` |
| G2 | 共通 | 每項的模組設定放哪 | `insts` 那一項裡、模組名當鍵 |
| G3 | 共通 | 何時進 spec | 每個做完、看過再寫，編 B-642 起 |
| — | 順序 | 實作順序 | 重讀設定 → 記住狀態 → 收屍 → 訊息 → helper |

## 做完了沒

**模組一、三做完了**（2026-10-01，AI 隊）：照上面與第十一批裁定做，驗收寫進 `tests/test_daemon_reload.py`（15 條）、`tests/test_daemon_state.py`（11 條），全過、兩檔單獨連跑 10 次都過；全部測試由 502 條變 528 條。

- 程式：`lib/aos_daemon.py`（`load_full()`／`Setup`、`_state_ref()`、共用的 `_items` 與 `_items_lock`、`Item.removed`／`end_mono`、`state_changed()`、`_catch_hup()`）、新的 `lib/aos_daemon_reload.py`、`lib/aos_daemon_state.py`；`lib/aos_daemon_ctl.py` 的 `handle()` 在 pause／resume 後通知記住狀態。`load_config()`、`load_setup()` 照舊。用法見 [src/py README](../src/py/README.md#重讀設定與記住狀態m3m)。
- spec：[B-642](../spec/settled/daemon/reload.md)、[B-643](../spec/settled/daemon/state.md)、[P-122](../spec/settled/protocol/daemon/reload.md)、[P-123](../spec/settled/protocol/daemon/state.md)；schema `daemon-core-config` 加 `modules.reload`、`modules.state`，新 schema `daemon-module-state`（舊的 `daemon-state` 是暫緩區 P-116）；暫緩區 B-608、B-603、P-116 標部分取代。

**AI 隊自己定的細節**（使用者可改）：

1. **重讀時狀態以記憶體為準**：重讀不讀狀態檔、不拿檔覆蓋還在的項；新加的項一律從頭（跟「拿掉又加回來＝新的一項」一致）。套用完照記憶體寫一次檔，拿掉的項就不見了。
2. **狀態檔內容沒變就不寫**（跟上次寫的、或開起來讀到的比）。所以沒有任何異常時不會建檔；暫停又恢復之後檔留著、內容是 `{"insts":{}}`。
3. **沒掛 `reload` 時 SIGHUP 照 Python 預設**：daemon 被殺（跟 m3、m3n 一樣，socket 檔不刪）。掛了才接。
4. **SIGHUP 不會漏**：用 `signal.set_wakeup_fd` 把訊號編號寫進 pipe，主執行緒讀 pipe 再重讀；重讀中連來幾次，讀完再重讀一次。
5. ~~**`exec_out_path`／`exec_err_path` 改了照套**（plan 表上那列），不算 R3 的「要重開」；R3 只警告 `cwd`、`modules`。~~〔第十二批改〕這兩個也不套用、stdout 警告，比設定裡的原字；新加的項的輸出路徑照開起來時的算。`modules` 裡任何改動都算（含換狀態檔、換 socket 路徑、加不認得的模組鍵）。警告每次重讀都印，直到重開或改回。
6. **重讀時設定壞了**：所有例外都接（不只 JSON／指示詞錯，型別錯也算），stderr `aos-daemon: reload: <說明>`，stdout 不印 `reloaded`。
7. **重讀後第幾項照新的鍵順序**（`aos-exec` 輸出標頭的 `index=` 跟著變）；`interval_ms` 改了但那一項還沒跑完過一次（例如開起來就恢復成暫停）照原本的排程。
8. **`modules.state` 的格式檢查**：原始值必須是只有 `$ref` 一個鍵、非空、不帶 `#`；`modules` 本身也要直接寫在設定檔裡。不合就是設定錯、回 1。狀態檔在但壞掉：照一般 `$ref` 錯回 1（默認一切正常）。
9. 開起來恢復時印 `inst=<inst> paused`／`stopped`（兩個都有先 paused），在任何 `exit=` 行之前。
10. 拿掉的項正在跑、還沒結束時又被加回來：新的一項會立刻開跑，可能跟舊的那次短暫疊著（同一個 inst 兩個 `aos-exec`）。照「默認一切正常」不處理。

**模組二做完了**（2026-10-01 第十二批，AI 隊）：照上面草稿與 C1～C4 建議做，驗收寫進 `tests/test_daemon_cgroup.py`（15 條；每條用 `systemd-run --user --scope -p Delegate=yes` 包 daemon，拿不到委派的 scope 時整組跳過）。全部測試 543 條（528＋15）。公司那台寫完；當晚在家裡 Manjaro 實跑 cgroup 那 14 條都過（「模擬沒委派」那條在測試自己的 cgroup 寫得進去時跳過）。

- 程式：新 `lib/aos_daemon_cgroup.py`（`Tree`、`clear()`、`frame_name()`）；`lib/aos_daemon.py`（`Item.cgroup`／`frame`、`run_once()` 回 `(碼, 毫秒, 有沒有收屍)`、`_gone()` 刪框、`main()` 建樹）；`lib/aos_daemon_reload.py`（`_apply()` 先建框寫上限、`NEED_RESTART` 加 `exec_out_path`／`exec_err_path`）。用法見 [src/py README](../src/py/README.md#收屍cgroupm3m-模組二)。
- spec：[B-644](../spec/settled/daemon/cgroup.md)、[P-124](../spec/settled/protocol/daemon/cgroup.md)；schema `daemon-core-config` 加 `modules.cgroup` 與每項的 `cgroup`；暫緩區 B-605 標部分取代。

模組二 AI 隊定的細節（使用者可改）全文在 [verdicts 11 第十二批](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十二批cgroup-與帳號)，要點：進框用 `sh -c` 墊一層（不用 `preexec_fn`）；`ms=` 不含清框；殘留拿著輸出 pipe 時另開執行緒讀、清完才收齊；重讀時拿掉的上限鍵不還原、出錯前寫進去的不還原；拿掉的項跑完才刪框、又加回來就不刪。

**模組四做完了**（2026-10-01 晚，AI 隊，在家裡那台）：照上面草稿與 M1～M4 建議做，驗收寫進 `tests/test_mq.py`（14 條，約 4 秒；連跑 10 次都過）。全部測試 557 條（543＋14）。

- 程式：新 `lib/aos_daemon_mq.py`（`serve()`、`parse()`、`handle()`）、`lib/aos_mq.py`、`bin/aos-mq`；`lib/aos_daemon_ctl.py` 的 `serve()` 多收一個 `answer`（訊息模組共用那套收連線、1 秒逾時、壞請求只影響那一條）；`lib/aos_daemon.py`（`Item.mailbox`、`Setup.mq_sock`、`give_env()` 改吃 `Setup`、`_sock_paths` 退出時兩個 socket 都刪）。用法見 [src/py README](../src/py/README.md#訊息與-aos-mqm3m-模組四)。
- spec：[B-645](../spec/settled/daemon/mq.md)、[P-125](../spec/settled/protocol/daemon/mq.md)；新 schema `daemon-mq`、`daemon-core-config` 加 `modules.mq`；範例 `examples/daemon/mq_request.*`、`mq_reply.*`、`core-config.mq*`；暫緩區 B-614、P-119 標部分取代；[C-10](../spec/settled/conventions.md) 加 `AOS_DAEMON_MQ_SOCKET`、`AOS_DAEMON_INST` 改成掛任一個就放。

模組四 AI 隊定的細節（使用者可改）全文在 [verdicts 11 第十二批](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十二批cgroup-與帳號)。

**下一個：模組五帳號 `account`**——上面草稿是第十二批之前寫的（H1 原建議「POC 不拆」已被推翻），動工前要先照第十二批重寫、給使用者看過。
