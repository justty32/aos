# 第三段之二：控制模組（暫名）

← [plan 入口](README.md)｜**接在 [m3-daemon-core](m3-daemon-core.md) 之後，m3 做完才開工。**｜依據：[最核心 aos-daemon（已裁定 10-01）](../notes/2026-10-01-daemon-core-sketch.md)、[verdicts 11 篇末 2026-10-01](../notes/verdicts/11-tick-as-unit.md#2026-10-01最核心-daemon待統一更新-spec)｜結束碼：[aos 結束碼慣例](../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)｜舊 spec 參考（以本檔裁定為準）：[B-612 通道](../spec/settled/daemon/channel.md#b-612tickdaemon-通道)、[P-117 通道變數](../spec/settled/protocol/daemon/channel.md)、[B-607 叫醒暫停](../spec/settled/daemon/registration.md#b-607叫醒暫停故障停格與格次序號)

**做完的樣子**：m3 的 `aos-daemon` 設定檔頂層加 `"enable_control": true` 與 `"socket": "./aos.sock"`，daemon 開起來就多開一個 unix socket，收四種指令：**叫醒**（現在就跑一次）、**暫停**、**恢復**（也救回被 `stop_on_nonzero` 停掉的項）、**看狀態**。小工具 `aos-ctl <指令> [<id>]` 送指令。daemon 開 `aos-exec` 時把 socket 位置與該項 id 放進環境變數，一路傳到 tick 的每個任務、再傳到下層 `aos-tick --node 下層` 的任務，所以**任何一層的任務跑 `aos-ctl wake` 就叫醒頂層那一項**。沒開時 daemon 就是 m3 原樣。

> **使用者裁定（2026-10-01，原話節錄）**：「不用另外設nodes這個key，就直接嵌入在insts中，額外添加所需的key。在沒掛載node相關模組的時候會忽略這些key。」「daemon只需要管理最頂層的node就好。」（下層 node 由上層任務表裡的 `aos-tick --node 下層` 帶起來，daemon 不知道有哪些下層。）「不要用檔案，必須用socket」「不要管上下層。」另同意：socket 路徑寫設定檔頂層、相對路徑起點同 `insts`、靠檔案權限不另驗身分；請求只帶 id、一行進一行出（例 `{"wake":"<id>"}` → `{"ok":true}`）；用環境變數 `AOS_DAEMON_SOCKET`、`AOS_DAEMON_ID` 往下傳。之前已定：正在跑時被叫醒就記「跑完再補一次」、多次只補一次；叫醒後週期從這次重新算。
>
> 看過初稿後追加：「可以，就叫他叫醒模組，但這功能太小，我覺得可以跟其他相關的小功能合併成一個模組。」所以本檔把叫醒擴成走同一條 socket 的控制模組，叫醒是其中一個指令；收哪些指令、模組與工具叫什麼，見待問 1、2。

> **POC 總原則**：默認一切正常——socket 建得起來、路徑不超長、沒有兩個 daemon 搶同一個 socket、客戶端照規矩送一行。不為這些寫處理，出事自然丟錯、回 1。唯一例外見步驟 3：客戶端送壞了不能讓整個 daemon 掛掉。

> **結束碼**：0＝預料之中；非 0＝要額外處理；1＝通用錯誤，本段沒有特別指定的碼，錯一律 1。

## 先講結論：這些指令都跟 node 無關，insts 不用加鍵

叫醒、暫停、恢復、看狀態做的都是「清單上 id 為 X 的那一項怎樣」。daemon 本來就不認得 node（m3：它只認 inst），所以這些對任何 inst 都一樣通用，沒有哪一個鍵是「node 專屬」的：

- 誰能被控制？清單上每一項都能（默認一切正常，不設「不讓別人碰」）。
- 指哪一項？用 id，也就是 `inst` 字面值，m3 已經有了。
- 往下傳什麼？socket 位置與 id，daemon 自己就知道，不用寫在設定檔。

所以這版 **`insts` 每一項一個鍵都不用加**，只在頂層加兩個鍵（開關與 socket 路徑）。使用者裁定的「模組鍵嵌在 insts 裡、沒掛載時忽略」照樣成立，只是這個模組剛好用不到——以後真有每項自己設的東西（例如「這項不准別人暫停」），就照這條規則加在 insts 裡。

## 收哪些指令

| 指令 | 做什麼 | 狀態 |
|---|---|---|
| `wake` | 現在跑一次；正在跑就跑完補一次，多次只補一次；週期從這次重新算 | 已定 |
| `pause` | 不再照週期跑；正在跑的那次不殺、讓它跑完 | 建議收（待問 1） |
| `resume` | 取消暫停，也救回被 `stop_on_nonzero` 停掉的項；之後立刻跑一次 | 建議收（待問 1、3） |
| `status` | 回各項狀態（正在跑、暫停、已停、上次結束時間與碼、下次預定時間） | 建議收（待問 1） |
| `reload` | 重讀設定檔 | 候選、待定，這版不做（待問 1） |
| `shutdown` | 讓 daemon 退出 | 候選、待定，這版不做（待問 1） |

暫停只放在記憶體：重開 daemon 就全部恢復。要「重開也不跑」照舊用 tick 的擋板檔（[m3 這段不做的](m3-daemon-core.md)那張表）。

## 跟 m3 的介面

控制模組跟 m3 同一支程式（`aos-daemon`），靠設定檔開關。需要 m3 提供或小改的地方（m3 完工後再對一次實際程式）：

| m3 的東西 | 控制模組要它 | 要不要改 m3 |
|---|---|---|
| 每項一條執行緒，迴圈「叫 → 等 → 印 → 睡」 | 睡的那一下要叫得醒；暫停時一直睡 | **要改**：`time.sleep(interval)` 換成「等一個條件、最多等 interval」（`threading.Condition.wait(timeout)`）；`stop_on_nonzero` 停掉時執行緒不結束、改成一直等（才救得回來）。模組關著時行為一模一樣 |
| 每一項的物件（`Item`） | 加狀態：`running`、`pending`（待補一次）、`paused`、`stopped`、上次結束時間與碼、下次預定時間 | **要改**：加欄位，跟上面的 Condition 共用一把鎖 |
| `id → 項` 的對照 | 收到 id 要找到那一項 | 小改：讀完設定建一張表；同字面值重複默認不會發生（後面的蓋前面的） |
| 開 `aos-exec` 的 `Popen` | 加兩個環境變數 | **要改**：`Popen` 多帶 `env=`；模組關著時不傳（照 daemon 的環境） |
| 讀設定檔 | 認頂層 `enable_control`、`socket` | 小改：m3 本來就忽略不認得的鍵，只要多讀這兩個 |
| SIGINT／SIGTERM 直接 `os._exit(0)` | 退出前刪 socket 檔 | 小改：模組開著時先 `unlink` 再退出 |
| stdout 那一行 | 暫停、恢復也要看得到 | 小改：多兩種行 `id=<id> paused`、`id=<id> resumed`（照 m3 `stopped` 那行的樣子） |
| 起點資料夾（頂層 `cwd` 算出來的絕對路徑） | socket 相對路徑的起點 | 不改，直接用 |

檔案（建議）：伺服器端放 `lib/aos_daemon_ctl.py`（或併進 `lib/aos_daemon.py`，AI 隊定）；客戶端 `lib/aos_ctl.py` 與薄殼 `bin/aos-ctl`（`.gitignore` 擋 `bin/`，要 `git add -f`）；測試 `tests/test_ctl.py`。做完補 [src/py README](../src/py/README.md) 檔案表與 [code map](../../wf/workflows/common/code-map.md)（鐵律 3）。

## 步驟 1：設定檔開關

- **要做到**：設定檔頂層 `enable_control` 為 `true` 時才開控制模組；否則 daemon 跟 m3 一模一樣，`socket` 鍵（以及以後放進 insts 的模組鍵）一律忽略、不建 socket、不傳環境變數。
- **依據**：使用者「沒掛載時忽略這些 key」；m3 步驟 1「其他鍵一律忽略」；名字比照舊 spec [B-615](../spec/settled/daemon/components.md) 的 `enable_*` 開關。
- **設定檔**：

  ```json
  {
    "cwd": "/home/u/nodes",
    "interval_ms": 60000,
    "enable_control": true,
    "socket": "./aos.sock",
    "insts": [{"inst": "a"}, {"inst": "jobs/report.json", "interval_ms": 5000}]
  }
  ```

  - `enable_control`：布林，沒寫＝`false`。
  - `socket`：開著時必填，字串。相對路徑以 m3 的起點資料夾為準（跟 `insts` 同一個起點），daemon 開起來時算成絕對路徑。開著卻沒寫：自然丟錯、回 1。
- **要使用者裁定的點**：待問 2（名字）、待問 4（要不要另一個開關鍵）。
- **驗收**：
  - 沒寫 `enable_control`、但寫了 `socket`：不建 socket 檔、子程序環境裡沒有 `AOS_DAEMON_SOCKET`／`AOS_DAEMON_ID`，其他照 m3。
  - `enable_control: true`、`socket: "./s"`、`cwd: "sub"`：socket 檔出現在啟動目錄底下的 `sub/s`。
  - `enable_control: true` 沒寫 `socket`：回 1。

## 步驟 2：叫得醒、停得住的週期迴圈

- **要做到**：m3 每一項的迴圈改成照旗標走。
- **依據**：之前已定的叫醒三條（跑完再補一次、多次只補一次、週期從這次重新算）；m3 步驟 3、4；舊 spec [B-607](../spec/settled/daemon/registration.md#b-607叫醒暫停故障停格與格次序號) 的叫醒、暫停只取意思。
- **規則**（每項一把鎖、一個 Condition；指令只改旗標、喚醒那條執行緒，不自己開程序，「同一項不疊著開」照 m3）：
  - **wake**：在睡→立刻跑；在跑→設 `pending`，跑完不睡、立刻再跑一次（跑的期間叫幾次都只補這一次）；暫停中→也跑一次、跑完照樣暫停（待問 3）；已停→回錯 `stopped`，要救用 `resume`。
  - **pause**：設 `paused`；正在跑的那次不殺，跑完不再排下一次，`pending` 一併清掉。已暫停再 pause 也回成功。
  - **resume**：清掉 `paused` 與 `stopped`，然後當成一次 wake（立刻跑、週期從這次重新算）。沒暫停也沒停時等於 wake。
  - **跑完之後**：碼非 0 且 `stop_on_nonzero` → 設 `stopped`、印 `stopped`、一直等；否則有 `pending` 就立刻再跑，沒有就從這次結束起等 `interval_ms`（暫停時一直等）。
- **要使用者裁定的點**：待問 3。
- **驗收**（短週期）：
  - 週期 10 秒、假 inst 每次寫一行時間：第一行之後 0.3 秒 wake，0.2 秒內出現第二行；之後要再等約 10 秒才有第三行（週期重新算）。
  - 假 inst `sleep 0.5`、週期 10 秒：跑的期間 wake 5 次，結束後立刻再跑**剛好一次**，之後照週期。
  - 週期 100 ms：pause 後 1 秒內沒有新的一行（正在跑的那次照樣印完）；resume 後立刻有一行、之後照週期。
  - `{"argv": ["false"]}` 帶 `stop_on_nonzero: true`：停掉後 wake 回 `stopped`、沒跑；resume 後跑一次、又停。
  - 指令不會讓同一項疊著跑（檔裡永遠沒有兩個同時在跑的記號）。
  - 模組關著時，m3 的所有測試照樣全過。

## 步驟 3：socket 與協議

- **要做到**：daemon 在 `socket` 路徑開一個 unix socket（`SOCK_STREAM`），一條執行緒收連線；**一連線一請求**：讀一行、回一行、關掉。
- **依據**：使用者「必須用 socket」、同意的三點；舊 spec 通道（[P-117](../spec/settled/protocol/daemon/channel.md)）只取「一行 JSON」，method、封包、憑證都不沿用。
- **請求**（一行 JSON，`\n` 結尾）：**指令名當鍵、id 當值**，照使用者已同意的 `{"wake":"<id>"}` 長相推廣：

  ```text
  {"wake":"a"}   {"pause":"a"}   {"resume":"a"}   {"status":"a"}   {"status":null}
  ```

  一個請求只放一個指令鍵；`status` 的值是 `null` 時回全部項。
- **回應**（一行 JSON，`\n` 結尾）：

  | 狀況 | 回應 |
  |---|---|
  | wake／pause／resume 成功（含「正在跑、記補一次」「本來就暫停」） | `{"ok":true}` |
  | status | `{"ok":true,"items":[{…}]}`，每項見下 |
  | 清單上沒這個 id | `{"ok":false,"error":"unknown_id","detail":"<id>"}` |
  | wake 一個被 `stop_on_nonzero` 停掉的項 | `{"ok":false,"error":"stopped","detail":"<id>"}` |
  | 指令名不認得 | `{"ok":false,"error":"unknown_cmd","detail":"<指令名>"}` |
  | 讀不到一行、不是 JSON 物件、指令鍵不是剛好一個、值型別不對 | `{"ok":false,"error":"bad_request","detail":"<白話>"}` |

  status 每一項：`{"id":"a","running":false,"pending":false,"paused":false,"stopped":false,"last_exit":0,"last_end":"2026-10-01T15:04:05+08:00","next":"2026-10-01T15:05:05+08:00"}`。還沒跑完過時 `last_exit`、`last_end` 是 `null`；正在跑、暫停、已停時 `next` 是 `null`。時間格式跟 m3 stdout 那一行一致（本地時間、ISO 8601、帶時區、到秒）。
- **回的時機**：旗標記好那一刻就回，**不等那一項跑完**；wake 成功的意思是「排上了」，不是「跑成功了」（結果照 m3 看 stdout 那一行，或之後 status）。
- **連線生命週期**：客戶端連上、送一行、讀一行、雙方關。daemon 一次處理一條連線（處理只是改旗標或抄狀態，很快）；每條連線設 1 秒逾時，免得一個連上不送的客戶端卡住後面的人（逾時就關掉、不回）。
- **權限**：能不能連照 socket 檔的檔案權限（建出來照 daemon 的 umask），不另驗身分。
- **不讓 daemon 掛**：單一連線出的任何錯（壞 JSON、對面先關、逾時）只影響那一條連線，回 `bad_request` 或直接關，收連線的執行緒繼續跑。這是本段唯一的「異常處理」，因為外面的人送壞東西不該把整個 cron 打掉。
- **要使用者裁定的點**：待問 1、3。
- **驗收**：
  - 用 Python 標準庫直接連 socket 送 `{"wake":"a"}`：回 `{"ok":true}`，而且 `a` 立刻跑一次。
  - `{"status":null}` 回全部項、`{"status":"a"}` 只回一項；欄位跟實際一致（跑 `sleep 0.5` 的項中途查 `running:true`、`next:null`）。
  - 不存在的 id 回 `unknown_id`；`{"kill":"a"}` 回 `unknown_cmd`；送 `hello` 回 `bad_request`；之後再送正確的請求照樣成功。
  - 連上不送東西：1 秒多一點被關掉，期間別人的請求最多晚約 1 秒。

## 步驟 4：往下傳環境變數

- **要做到**：模組開著時，daemon 開每一次 `aos-exec` 都在環境裡加 `AOS_DAEMON_SOCKET=<socket 絕對路徑>`、`AOS_DAEMON_ID=<這一項的 id>`（蓋過 daemon 自己環境裡同名的）。
- **依據**：使用者同意的第三點；名字沿用舊 spec [P-117](../spec/settled/protocol/daemon/channel.md) 的 `AOS_DAEMON_SOCKET`，`AOS_TICK_TOKEN`（憑證）不做。
- **一路傳下去不用寫新程式**：`aos-exec` 照 inst 的 `envs` 規則用繼承的環境；`aos-tick` 開任務時也是繼承的環境加 `AOS_*`；下層 `aos-tick --node 下層` 本身就是上層的一個任務，它的任務又繼承下去。所以**每一層的任務看到的都是頂層那一項的 id**，指到的永遠是頂層（使用者「不要管上下層」「daemon 只管最頂層」）。inst 或任務寫了 `envs` 清空時，那一支往下就沒有這兩個變數，是 inst 自己的選擇。
- **要使用者裁定的點**：無（模組關著時要不要清掉繼承來的同名變數，見待問 6）。
- **驗收**：
  - 假 inst 把兩個變數寫進檔：值是 socket 絕對路徑與 `inst` 字面值。
  - node 資料夾 `a`（inst 跑 `aos-tick`）的任務表有一項寫檔、另一項跑 `aos-tick --node b`，`b` 的任務也寫檔：三個檔裡的 `AOS_DAEMON_ID` 都是 `a`。

## 步驟 5：`aos-ctl` 小工具

- **要做到**：一支普通程式送四種指令；**不另做 `aos-wake`**（最單純，`aos-ctl wake` 就是它）。
- **用法**：`aos-ctl <wake|pause|resume|status> [<id>]`
  - wake／pause／resume 沒給 id 用 `AOS_DAEMON_ID`（任務裡最常用：叫醒、暫停自己的頂層項）。
  - status 沒給 id 回全部項（人在 shell 最常用；任務要看自己就 `aos-ctl status "$AOS_DAEMON_ID"`），見待問 5。
  - socket 一律用 `AOS_DAEMON_SOCKET`，不另設參數；人在 shell 手打就 `AOS_DAEMON_SOCKET=./aos.sock aos-ctl status`。
  - 連上、送一行、讀一行、關掉。不重試、不另設逾時（默認一切正常）。
- **輸出**：wake／pause／resume 成功時不印；status 成功時把回應那一行原樣印到 stdout（一行 JSON，要好看自己接 `jq`）。
- **結束碼**：回應 `ok:true` 回 0；其餘一律 1，stderr 一行 `代碼: 說明`：
  - 缺變數（沒 `AOS_DAEMON_SOCKET`，或該用 `AOS_DAEMON_ID` 時沒有）：`no_daemon:`，不連 socket。
  - 連不上（檔不在、沒人聽、沒權限）：`connect:`。
  - daemon 回 `ok:false`：照回應的 `error` 印（`unknown_id:`、`stopped:`、`unknown_cmd:`、`bad_request:`）。
  - 指令名不在四個裡、多給參數：用法錯、回 1，不連 socket。
- **依據**：使用者同意的第二、三點；結束碼慣例；舊 spec 的 `no_channel`（缺變數客戶端自己擋）改名 `no_daemon`。
- **要使用者裁定的點**：待問 2（工具名）、待問 5（status 不帶 id）。
- **驗收**：
  - daemon 開著、任務裡跑 `aos-ctl wake`：回 0，而且自己這一項跑完立刻補一次；跑 `aos-ctl pause`：回 0，這一項之後不再照週期跑。
  - 下層 node 的任務裡跑 `aos-ctl wake`：叫醒的是頂層那一項。
  - `aos-ctl status`：stdout 一行 JSON、裡面有全部項。
  - 給不存在的 id：回 1、stderr `unknown_id:`；沒變數：回 1、stderr `no_daemon:`；daemon 沒開：回 1、stderr `connect:`；`aos-ctl kill`：回 1。
- **用法上要知道**：任務每一格都無條件 `aos-ctl wake` 自己，那一項就會不停跑（每次補一次）；任務 `aos-ctl pause` 自己，就要靠外面的人 `resume`。都是用法問題，不擋。

## 步驟 6：socket 檔的開與收

- **要做到**：最簡單、默認一切正常下不會撞的做法。
- **做法**：
  - **開**：bind 前路徑上若已有檔就先刪（上次被 `kill -9` 留下的），再 bind。默認沒有兩個 daemon 用同一個 socket，所以不檢查那個舊檔還有沒有人在聽（待問 7）。
  - **收**：SIGINT／SIGTERM 時先 `unlink` socket 檔再 `os._exit(0)`（m3 的退出方式不變，只多這一行）。
  - 被 `kill -9` 或自己出錯退出時檔會留著；客戶端連過去得到 `connect:`、回 1；下次開 daemon 時照上一條刪掉重建。
- **要使用者裁定的點**：待問 7。
- **驗收**：
  - SIGINT 後 socket 檔不見了；SIGTERM 一樣。
  - 先在路徑放一個普通檔（或上次 `kill -9` 留下的 socket），daemon 照樣開得起來、指令照樣通。

## 步驟 7：整段驗收

- 步驟 1～6 的驗收合成 `tests/test_ctl.py`，一條指令跑完；不需要 root、systemd、網路，全部用暫存資料夾、短週期、假 inst，每條幾秒內結束。
- socket 放暫存資料夾裡（unix socket 路徑上限約 108 字元，`tempfile.mkdtemp()` 放 `/tmp` 底下夠短；測試自己用短路徑，程式不檢查）。
- 測試結束自己殺掉 daemon 和留下的子程序（照 m3 步驟 7 的做法）。
- m3 的 `tests/test_daemon.py` 與原有測試（tick、exec、inst）照樣全過。

## 這段不做的

| 不做 | 這版的樣子 |
|---|---|
| 身分驗證、憑證（`AOS_TICK_TOKEN`） | 只靠 socket 檔權限 |
| reload、shutdown | 改設定就重開；要停就送 SIGTERM（待問 1） |
| 登記、送訊息等其他舊 spec method | 只有四個指令 |
| 控制下層 node | 指到的是頂層那一項；下層跟著上層的格跑 |
| 暫停寫進檔、重開還在 | 只在記憶體；要持久用擋板檔 |
| 等 wake 那一次跑完再回 | 排上就回 |
| 一條連線送多個請求 | 一請求一連線 |
| 清掉舊 socket 前確認沒人在用 | 直接刪（默認沒有兩個 daemon） |

## 待問

1. **收哪些指令？** 建議這版收 wake（已定）、pause、resume（含救回 `stop_on_nonzero` 停掉的項）、status 四個。reload、shutdown 先不收：shutdown 跟送 SIGTERM 一樣，多做只為了「沒有 pid 也停得掉」；reload 要定「正在跑的項被刪掉、週期改了、id 換了」怎麼辦，比其他三個加起來還大，值得自己一份 plan。
2. **模組與工具叫什麼？** 使用者先說了「叫醒模組」，合併後暫名「控制模組」，開關 `enable_control`、工具 `aos-ctl`，不另做 `aos-wake`。其他可選：模組「遙控模組」、工具 `aos-daemonctl`（像 `systemctl`，比較長）。
3. **指令之間怎麼互動？** 建議：暫停中 wake 會跑一次、跑完照樣暫停（暫停只停「週期」，不擋人手叫）；`stop_on_nonzero` 停掉的項 wake 回 `stopped`、要用 resume 救；resume 一律立刻跑一次。另一種是「暫停中 wake 也不跑」，那暫停就等於整個關掉。
4. **開關要不要獨立一個鍵？** 建議要（`enable_control`），理由是使用者說「沒掛載時忽略這些 key」，開關跟設定分開，暫時關掉不用刪 `socket`。另一個做法是「有寫 `socket` 就算開」，少一個鍵、沒有冗餘，但暫時關掉得刪掉或改名那一行。
5. **`aos-ctl status` 不帶 id 回全部，跟其他三個「不帶 id 用 `AOS_DAEMON_ID`」不一樣。** 建議就這樣（人在 shell 看全部最常用，而且那時通常沒有 `AOS_DAEMON_ID`）。要一致的話就是 status 也預設自己、看全部另寫 `aos-ctl status --all`。
6. **模組關著時，繼承來的 `AOS_DAEMON_*` 要不要清？** 例如這個 daemon 本身是別的 daemon 底下某個任務開的：關著時不動環境，它的任務 `aos-ctl` 會指到外面那個 daemon（id 多半對不上、回 `unknown_id`）。建議：默認一切正常，不清。
7. **開 daemon 時舊 socket 檔直接刪？** 建議直接刪（最簡單；`kill -9` 後重開不用人手清）。代價是不小心開了第二個 daemon 時會搶走第一個的 socket，第一個從此收不到指令——但「沒有兩個 daemon 跑同一份清單」本來就是 m3 的默認。
