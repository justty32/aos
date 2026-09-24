## 1. 總評

三份的分工已經看得懂；現在主要障礙是操作說明分散、摘要漏條件，以及少數照抄就會寫錯的例子。
四件套本身夠簡單，手工送件、收輸出、ack 的完整流程還不夠簡單。
最需要補的是「從零跑起來」「一次問模型」「退件查原因」三條完整路線。
本輪沒有延伸挖崩潰時序；以下矛盾都是現有文字、數字或欄位直接對不上。
全程唯讀，未修改檔案、未執行會寫檔的測試。

## 2. A：措辭與一致性

### W-1｜kernel 的「一句話」先講實作，沒有先講用途

**在哪：** [kernel 開頭](../../spec/kernel/README.md)。

**原句／問題：**「kernel 不是長命行程……像尾遞迴一樣接下去。」讀者先學接鏈，卻還不知道 kernel 替自己做什麼。「尾遞迴」又增加一個不必要的比喻。

**建議改成：**

> kernel 替登記的工作挑一顆空閒 cpu，收回執行結果，再決定要不要重跑；它每次只執行一格 tick，並先排好下一格，讓排程持續下去。

另外兩份的「一句話」有抓到重點：cpu＝逐件跑一次；daemon＝啟動、重拉、停止孩子。daemon 的「當爸爸」可直接換成「管理 cpu 行程的啟動與停止」。

### W-2｜名詞表沒有照初讀順序，kernel 表尤其像把正文先講一遍

**在哪：** 三份 §0：[cpu](../../spec/cpu/terms.md)、[kernel](../../spec/kernel/terms.md)、[daemon](../../spec/daemon/terms.md)。

| 文件 | 缺漏／未用／順序 |
|---|---|
| cpu，20 項 | 共用表缺 `ack`、交件者／收件者；正文「中心是 C」也未白話解釋。沒有確認完全未用的項目。開頭先出現主人、request、response，表卻先講 inst。 |
| kernel，36 項 | `pool` 已在 `kcpu` 定義出現，卻晚很多才解釋；「派工」幾乎排最後。沒有確認完全未用的項目，但很多列已包含整套政策。`Interrupted`／`stopped` 定義漏 once 例外，見 X-7。 |
| daemon，21 項 | 沒有確認完全未用的項目；「退避」「收養」雖未採用，正文有明確排除，保留合理。`spawn`／`restart` 摘要漏條件，見 X-7。 |

kernel §0 說「偷看」見 cpu §0，實際定義在 cpu §1，是一處導引不準。

**建議直接補入 cpu §0：**

> ack：交件者讀完並保存回音後，再送一則「已收件」通知；主人收到才刪回音，格式見 §3.3。  
> 偷看：直接讀狀態或佇列檔案，不送 request，也不修改檔案。

名詞表依正文首次出現重排；fd、訊號等實作詞放後面。每列保留一句定義，政策細節指向正文，不再預講整個演算法。

### W-3｜角色稱呼需要對照，不宜全部硬改成同一個詞

**在哪：** [cpu 交件者／收件者](../../spec/cpu/layout.md)、[kernel「欠客戶的回音」](../../spec/kernel/terms.md)、[daemon 孩子](../../spec/daemon/terms.md)。

**問題：**「交件者／收件者／客戶」常指同一支程式；「孩子／cpu／主人」則是同一支程式的不同關係，不能當同義詞全面替換。

**建議補兩句：**

> 交件者是送出 request 的程式，也是對應 response 的收件者；本文統一稱交件者。

> 在這套配置中，daemon 啟動的 `aos-cpu` 是它的孩子，也是 cpu 家的主人；`aos-cpu` 替工作啟動的程式則是下一層子行程。

「殘單」沒有出現在這三份，目前「殘格」用法一致，不需要另做更名。

### W-4｜「出貨」包含刪檔，定義卻只說放檔

**在哪：** [kernel 出貨箱](../../spec/kernel/terms.md)。

**原句／問題：**「先記進帳本、再放檔、放完清掉。」但 `deletes` 做的是刪原單，第一次讀到這裡得重新理解「出貨」。

**建議改成：**

> 出貨箱是帳本裡尚未完成的四類待辦：送 ack、寫回音、送 stop、刪原 request。本文的「出貨」就是執行這些待辦；前三類會放檔，最後一類會刪檔，每筆完成後才從帳本移除。

之後固定：「放單」＝送 request；「放檔」＝檔案操作；「出貨」＝執行上述待辦。

### W-5｜幾句限定範圍要靠讀者自己補

| 在哪／原句 | 建議直接改成 |
|---|---|
| [cpu §2](../../spec/cpu/layout.md)：「整份解指示詞，中心是 C」 | 「讀取 `info.json` 時先展開指示詞；其中相對檔案引用以 cpu 家 C 為起點，再驗證欄位型別。」 |
| [kernel 帳本](../../spec/kernel/ledger.md)：「tick 只認帳本這兩格，不看 info」 | 「kernel cpu 名稱與執行入口取自帳本的 `kcpu`、`cli`；其他設定仍每格重讀 `info.json`。」 |
| [kernel once](../../spec/kernel/tick.md)：「把回音原樣……當成 pending 那則 add 的回音」 | 「複製 cpu 回音的 `result` 或 `error` 內容，外層 `id` 使用原 add 的 id，檔名使用原 add 的檔名。」 |

### W-6｜重拉責任的主詞寫反

**在哪：** [kernel 第 7 步](../../spec/kernel/tick.md)。

**原句：**「死了的 daemon 自己會重拉，這裡不用管。」

**建議改成：**

> cpu 非 0 退出時，由 daemon 自動重拉；daemon 自己重啟後則需要人重新 boot，見 §6。

這不是修飾語問題，照字面讀會把故障處理責任記反。

### X-1｜LLM 環境範例的 `$fmt` 寫法不合法

**在哪：** [kernel info 範例](../../spec/kernel/home.md)，對照 [directives §3.1](../../spec/directives/fmt.md)。

**問題：** 現文把 `$fmt` 的值寫成字串；被引用的規範明定必須是物件，舊寫法會得到 `DirectiveValueTypeMismatch`。

**建議把 PATH 那格改成：**

```json
"PATH": {
  "$fmt": {
    "$val": "/abs/tools/llm:${PATH}",
    "PATH": {"$env": "PATH"}
  }
}
```

這會直接影響照範例建立 llm cpu，應優先修。

### X-2｜排程公式混用秒與毫秒，也蓋掉了強停例外

**在哪：** [kernel 欄位定義](../../spec/kernel/ledger.md)、[判定表與公式](../../spec/kernel/echo.md)。

**問題：** `not_before` 是 epoch 秒，公式卻是 `now + interval_ms`；表格說 `stopped:true` 保留 `not_before`，通則又一律更新。

**建議改成：**

> 回 queue＝`status=queued`、排到 `queue` 尾；一般情況設 `not_before = 目前 epoch 秒 + interval_ms / 1000`，`result.stopped=true` 時保留原本的 `not_before`。

### X-3｜`SpawnFailed` 與底層錯誤搶同一個 `data.code`

**在哪：** [daemon 啟動失敗](../../spec/daemon/spawn.md)，對照 [cpu 錯誤格式](../../spec/cpu/messages.md)。

**原句／問題：**「回 `-32000`／`SpawnFailed`，`data.code` 是 aos-exec 的代號。」同一格不能同時是 `SpawnFailed` 和 `ReadFailed`。

**建議改成：**

> 啟動失敗時回 `error.code=-32000`、`error.data.code="SpawnFailed"`；`message` 保留底層 aos-exec 的代號與錯誤說明，不登記孩子。

cpu 的「aos 自己的錯誤一律 `-32000`」也應加限定，因為下表的 `FieldTypeMismatch`／`Usage` 使用 `-32602`：

> 信封、method 與 params 驗證使用下表的標準錯誤碼；其餘 aos 錯誤使用 `-32000`。

### X-4｜kernel 對「何時放檔」有兩組過度概括

**在哪：** [開頭](../../spec/kernel/README.md)、[十步前言](../../spec/kernel/syscall.md)、[第 4 步](../../spec/kernel/tick.md)。

**問題一：**「除了接鏈，其他檔都是先記進帳本再放出去」漏掉不進帳本的 tick ack。

**建議改成：**

> 工作派送與四類出貨待辦先記帳，再執行檔案操作；接鏈先放後記。舊 tick 回音的 ack 由第 4 步直接送出，不進帳本。

**問題二：**「第 5～9 步新增的出貨不在當步放」與補派、spawn、派工的步驟相反。

**建議改成：**

> 第 5～9 步加入 `acks`、`replies`、`stops`、`deletes` 的待辦，統一在第 10 步執行；第 6 步補送工作、第 7 步呼叫 daemon、第 8 步派工，仍在各自步驟立即送出。

### X-5｜「每則 syscall 都有兩筆出貨」不適用 once、ack、stop

**在哪：** [kernel syscall 統一流程](../../spec/kernel/syscall.md)。

**原句／問題：** 每則 syscall 都把「回音進 replies、原單名進 deletes」一起記帳；但 once 延後回，notification 不回。

**建議改成：**

> 接受 `add` 或 `rm` 時，判定結果與原單的 `deletes` 紀錄一次寫入帳本；應立即回覆的結果同時加入 `replies`。`once add` 先保存 `pending`，完成或取消時才加入 `replies`；`ack`、`stop` 依各自規則處理，不產生回音。

§0 syscall 定義的「回音寫在……」也應改成「需要回音的請求，回音寫在……」。

### X-6｜「所有 request 都是 aos-exec」與管理方法矛盾

**在哪：** [cpu 已拍板前提](../../spec/cpu/lifecycle.md)。

**建議改成：**

> 所有工作 request 的 method 都是 `aos-exec`；`ack`、`stop` 是管理 request。

### X-7｜名詞表省略條件，與正文產生不同規則

**在哪：** [kernel `Interrupted`／`stopped`](../../spec/kernel/terms.md)、[daemon restart／spawn](../../spec/daemon/terms.md)。

**問題／直接替換句：**

- `Interrupted` 現在一概說算失敗，漏了 once：

  > `Interrupted` 表示結果不明；反覆行程算一次失敗，once 則把錯誤原樣交给交件者。

- `stopped` 現在一概說重新排隊，漏了 once：

  > `stopped:true` 表示這次被強制停止；反覆行程不改計數、重新排隊，once 則原樣交回結果。

- daemon 重拉定義漏了啟用條件：

  > 只有 `restart:true`、非 0 退出、且未被主動叫停的孩子，才會再次啟動。

- daemon spawn 定義說「什麼都不做」，正文卻會更新 `restart`：

  > 同名、同 `target`、同 `dir_target` 的孩子已在跑時，沿用 pid，並更新 `restart` 設定。

`128+N` 那列同樣引用上述重拉條件，不要再簡稱「非 0 就重拉」。

### X-8｜接手舊孩子的等待時間，有 5 秒與 10 秒兩種讀法

**在哪：** [daemon 啟動第 3 步](../../spec/daemon/lifecycle.md)，對照 [正常停機階梯](../../spec/daemon/shutdown.md)。

**問題：**「走 §5 階梯，從 TERM 開始」表示之後等 `kill_wait_ms`，預設 5 秒；下一句卻指定等兩段總和，預設 10 秒。

建議保留正文明寫的總等待時間，改成：

> 接手上一任的孩子時，先送 TERM，再等 `stop_wait_ms + kill_wait_ms`；仍未退出才送 KILL。這是接手專用的等待時間，與 §5 正常停機的 TERM 階段不同。

其餘數字核對：20 ms 輪詢、1000 ms 排程／重拉預設、工作 timeout 0、完成碼 100、連敗 10 次、daemon RPC 等待 5000 ms、boot 交接預設 30 秒、一般 CLI 等待 10 秒、cpu 強停寬限 2 秒，未見彼此誤換。`req`／`proc`／`kcpu`、`Removed`／`Stopping`／`NameTaken` 也未見拼名混用。

## 3. B：三種使用者走一遍

### 人：步數合理，缺的是接起來的路線

照規範，終端 A 執行 `aos-daemon --home /abs/D`，它自行建家，**沒有 daemon init 子命令**。終端 B 執行 `aos-kernel init /abs/K`，準備 `/abs/job.json`，再 `boot /abs/K --daemon /abs/D`、`add /abs/K /abs/job.json --name demo`、`ls /abs/K`。`add` 預設反覆執行。停機先 `aos-kernel stop /abs/K`，繼續看 `ls`，等 kernel 停完且它的 cpu 從 daemon 孩子表消失，最後到終端 A 按 Ctrl-C。人主要準備工作檔、視需要改 `K/info.json`；其餘 state、佇列、cpu 家由程式管理。

把一顆 cpu 當 llm cpu：若 daemon 啟動時的環境已能執行 `llm-http`，不必重設 PATH；在 `K/info.json` 把該 cpu 標成 `pool:"llm"`，工作用 `--pool llm`，工作 inst 呼叫 `llm-http`。若還要改既有 cpu 的環境，則涉及生成後的 `K/cpus/<c>/inst.json`，不是只改 info 就會生效。

出事時：斷鏈查 `ls` 的 kernel cpu `current`、待處理 request 與 `last_seq`，再依規範重新 boot；cpu 一直死查 `D/state.json` 的 `exits`／`last_exit` 及該 cpu 的 log；工作一直退件則有下面 U-4 的資訊缺口。

- **U-1｜缺完整啟停範例，stop 的完成界線尤其重要。**  
  [kernel CLI](../../spec/kernel/cli.md)只承諾 stop 放單成功，[daemon](../../spec/daemon/shutdown.md)卻要求先停 kernel。建議補：

  > `aos-kernel stop K` 成功只表示已送出要求；接著用 `ls` 等到 `phase=stopped`，並確認 daemon 孩子表裡這個 kernel 的 cpu 都已消失，再停 daemon。

- **U-2｜LLM 環境有兩個修改位置，沒有一段說明何時用哪個。**  
  [kernel 初始化規則](../../spec/kernel/home.md)已定「既有家不重寫」，但操作後果不醒目。建議補：

  > `info.cpus.<c>.envs` 只用於第一次建家。家已存在時，要改環境請先停 kernel、等 cpu 全部退出，再改 `cpus/<c>/inst.json`，最後 boot；只改 info 或對仍活著的 cpu 再 boot，不會更新環境。

  再補：

  > inst 裡的 `$env` 讀的是啟動它的 daemon 的環境；在另一個終端 export，不會改到已啟動的 daemon。

- **U-3｜常見的單一工作設定，CLI 要人退回手寫 RPC。**  
  [add RPC](../../spec/kernel/ledger.md)支援 `args`、`dir_target`、`interval_ms`、`timeout_ms`，[CLI](../../spec/kernel/daemon-link.md)沒有對應旗標。不是一定要加，但至少寫：

  > 本版 add CLI 只提供上列旗標；要覆寫單一行程的 `args`、`dir_target`、`interval_ms` 或 `timeout_ms`，請依 §2 直接送 add request。

- **U-4｜退件能看見次數，不保證找得到原因。**  
  [行程紀錄](../../spec/kernel/ledger.md)沒有最後結果，cpu 回音收完會 ack；[kernel.log](../../spec/kernel/tick.md)卻未定必記內容。建議補最小診斷要求：

  > 每次工作失敗，`kernel.log` 至少記錄行程名、cpu 名、request 檔名，以及回音的 `error` 或 `result`；進入 `bad` 時另記退件門檻。子程式詳細錯誤由工作 inst 的 `stderr` 檔保留。

  不需要為此再增加一個狀態檔。

### Python agent：傳輸能照做，模型答案還有另一層檔案

問一次模型，先準備輸入檔及工作 inst，讓 inst 呼叫 `llm-http`，指定答案輸出與 stderr。取全新名稱 R，把下列 request 寫到 `K/requests/` 裡的唯一暫存檔，再 `link` 成 `R.json`、刪暫存檔：

```json
{
  "jsonrpc": "2.0",
  "id": "R",
  "method": "add",
  "params": {
    "target": "/abs/job.json",
    "name": "R",
    "once": true,
    "pool": "llm"
  }
}
```

等原單消失、`K/responses/R.json` 出現，讀執行結果；成功才讀 inst 指定的答案檔。保存自己要留的資料後，以相同放單流程送出全新的 `ack-*.json`：

```json
{"jsonrpc":"2.0","method":"ack","params":{"name":"R.json"}}
```

agent 不刪 K 裡的 request／response；自己的輸入、inst、答案與錯誤檔自行管理。跑工具同樣走這條路，只換目標程式、輸入輸出及 pool。直接跑普通檔可以省 inst，但 response 不會因此包含 stdout。

失敗有兩層：`Removed`／`Stopping`／`Interrupted` 是 RPC error；`kind:"aos",code:1`、子程式非零退出、`timed_out:true`、`stopped:true` 則可能出現在 result。**有 result 不等於工作成功。**

- **U-5｜「收到回音」容易被誤認為「拿到模型答案」。**  
  [cpu stdout 規則](../../spec/cpu/methods.md)與 kernel once 需要放在同一個最小範例。建議補：

  > once 的回音只報執行狀態，不含模型答案或工具 stdout。需要輸出時，在工作 inst 指定 stdout 檔；收到成功的執行回音後，再讀該檔。輸入與答案格式由被呼叫的程式定義。

- **U-6｜CLI 的 ack、逾時及退出碼責任未寫齊。**  
  [kernel CLI](../../spec/kernel/cli.md)沒有明說：等到回音是否自動 ack、等不到之後去哪收、拿到 RPC error 時退幾。建議補定：

  > CLI 成功輸出已收到的回音或名稱後，代送 ack。未等待或等待逾時時，印出完整回音路徑，由呼叫者之後讀取與 ack；逾時不取消工作。JSON-RPC error 印代號與訊息、退 1；exec result 印完整內容，工作成敗由內容判讀。

  這是建議補定的契約，現文還不能當成已如此規定。

### 實作三支程式的 AI：骨架可寫，幾個初始化與介面角落仍得猜

照規範，實作者可以依序建立共用檔案送收／錯誤格式、cpu 執行迴圈、daemon 孩子表與停機階梯、kernel 帳本與十步流程。主要演算法已有落點；仍不能直接照抄的部分集中在前述矛盾、第一次沒有 state 的情況，以及 CLI 行為。這些比再增加復原解說更值得補。

- **U-7｜初始值與幾個介面規則尚未閉合。**  
  [kernel init／boot](../../spec/kernel/daemon-link.md)只說建預設 info，boot 又要求帳本其餘欄位「照舊」；第一次沒有舊帳本怎麼辦未定。至少補：

  > 第一次 boot 沒有 state 時，建立空的行程表、工作 cpu 表、佇列與四張出貨箱；其餘欄位依新鏈設定初始化。

  cpu 同理補「沒有舊 state 時，視為 `current:null`、`runs:0`」。此外還需明定 request 檔名與 `ack.params.name` 的合法範圍、前綴與 method 不符如何處理，以及 cpu `runs` 是否包含被拒絕的請求。

- **U-8｜tick 不限時，應直接寫出欄位值。**  
  [kernel](../../spec/kernel/tick.md)寫「沒有 timeout」，但 [cpu](../../spec/cpu/methods.md)省略欄位會套預設。建議改：

  > tick request 一律明寫 `timeout_ms:0`，不套用 kernel cpu 的預設逾時。

  [cpu `timed_out`](../../spec/cpu/methods.md)也仍明列底層 API 待補；這是已知未完成契約，定稿不能只留「之後一起加」。

- **U-9｜73 KB 可以瘦身，但應砍重複說明。**  
  可移到決策筆記的是三份末尾「已拍板／我自己選的」中重述正文的部分、名詞表裡的演算法說明，以及重複的設計理由。「等你確認」若仍保留，至少標明哪些條款尚未生效。欄位預設、錯誤形狀、判定優先序、必要操作順序應保留。

四件套可以一句話講完：

> **設定看 info，現況看 state；要它做事就往 requests 投件，從 responses 取同名回音，保存後送 ack。**

JSON-RPC 的固定 `jsonrpc:"2.0"` 對 Python 負擔很小，不值得另造簡版。**真正不 KISS 的是每位使用者都手寫唯一名、暫存檔、link、等待、兩層錯誤判斷與 ack。** 三檔在協議層可以接受，應提供一份可直接沿用的客戶端範例，把這些固定步驟包起來。

- **U-10｜go 對直接終端執行沒問題，對包裝程式容易意外。**  
  [cpu 啟動規則](../../spec/cpu/stop.md)已明定終端不等 go；但 Python `stdin=PIPE` 會切進控制協議。建議補：

  > 終端直接執行 `aos-cpu C` 不需要 go。普通獨立啟動可讓 stdin 繼承終端或接 `/dev/null`；指定 `stdin=PIPE` 就代表使用控制協議，父行程必須送 go 並持續持有管線。

## 4. C：未來

- **F-1｜多機不是把 pipe 換 socket 就完成。**  
  現在工作 target、輸出檔、狀態偷看、硬連結與 flock 都依賴本機。**現在應留範圍聲明：**

  > 本版只保證同一台機器、可直接存取各家與工作檔案的部署；多機的路徑、結果取得與活性查詢另訂。

  現在不用設計遠端協議。

- **F-2｜agent／`aos-llm-call` 必須接住真正的資料內容。**  
  核心 once 只交付執行結果；下一份規範若未定輸入、答案、工具輸出與清理責任，仍無法完成「問一次模型」。**現在應把這些列為下一份規範的責任邊界**；不用先在核心 response 塞模型專用欄位。

- **F-3｜更多能力沒有被擋，但 daemon 孩子的資格要說清楚。**  
  目標程式＋環境已能擴充能力，不必預留 cpu 種類清單。然而 daemon 開頭像是能管理任意程式，正文卻假設孩子懂 go／stop／EOF。**現在應補：**

  > daemon 的受管孩子必須遵守 cpu §6.1 的控制 pipe 契約；一般工作程式由 exec cpu 執行。

- **F-4｜Windows 原生支援不能逐句沿用現在的生命週期規則。**  
  fd、flock、POSIX 訊號、process group、fork／waitpid、`/dev/null` 都已寫進正文。**現在標明 POSIX 範圍即可**；不用提前增加 Windows 欄位或相容層設計。

## 5. 定稿前必改

1. **X-1**：修正不能照抄的 `$fmt` 範例。
2. **X-2**：統一時間單位與 `stopped` 的排隊例外。
3. **X-3**：固定 `SpawnFailed` 的錯誤欄位。
4. **X-4、X-5**：修掉 kernel 操作順序與回音流程的過度概括。
5. **X-6、X-7**：讓摘要、名詞表與正文條件一致。
6. **X-8**：選定接手舊孩子的唯一等待時間。
7. **W-6**：修正「daemon 自己重拉」的主詞。
8. **W-1、W-2**：kernel 先講用途，名詞表重排並補共用詞。
9. **U-1、U-2**：補完整啟停與既有 cpu 環境修改步驟。
10. **U-4**：保證退件後仍有失敗原因可查。
11. **U-5、U-6**：補一次工作的輸出、CLI 等待與 ack 契約。
12. **U-7、U-8**：補首次初始化、tick 明寫不限時，完成已知底層回傳契約。
13. **F-1、F-3、F-4**：明訂本機、受管孩子及 POSIX 的適用範圍。