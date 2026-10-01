# 第一段：tick 核心

← [plan 入口](README.md)｜正本：[通用 tick](../spec/settled/tick.md)｜格式：[tick 協議](../spec/settled/protocol/tick.md)

**做完的樣子**：沒有 daemon、git、cgroup、helper 的機器上，`aos-tick ~~--node~~ ~~--target~~ [<資料夾~~或任務表檔~~>]`（~~/絕對路徑~~，2026-10-01 改，見待問 10；`--node` 改名 `--target` 見待問 16；再改成位置參數見待問 17；給檔當任務表同日撤回見待問 18）直接跑一格：照 `.aos/tasks.json` 依序跑、每項怎麼結束都寫進 `.aos/tick/current.json`、~~整格回 0／1~~ 照表跑完回 0（任務成敗只記、不影響 tick 的碼；2026-10-01 改，見待問 9）。這是 [B-626](../spec/settled/tick.md#b-626核心與系統級任務的界線) 驗收的 POC 版；同資料夾只能一格（最簡版，拿不到鎖回 ~~2~~ 0；2026-10-01 先拿掉、同日加回，見待問 12、15）、~~算得出預設上層~~（2026-10-01 作廢，見待問 8）。

> **POC 總原則（2026-10-01，見待問 8）**：默認一切正常——寫得進、讀得懂、不斷電、~~沒有別人同時在跑~~（同日加回最簡互斥，見待問 12）、表是對的、帳號是對的。不寫異常處理，出事讓 Python 自然丟錯、回 1。下面各步裡跟這條衝突的句子都劃掉、註明 2026-10-01 作廢。
>
> **結束碼（2026-10-01，見待問 9、15）**：照 aos 體系慣例（~~0 正常結束、1 錯誤結束、2 正常中斷~~ 同日改版：0＝預料之中（含正常中斷）、非 0＝要額外處理、1＝通用錯誤；全文在 [verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)，已寫入 spec（commit 前由我補號））。`aos-tick` 只回：照表跑完、停格檔停下、鎖被占（busy）、擋板檔 0（擋板、busy 原本 2）、tick 自己出錯 1；任務的碼只記進紀錄、完全不影響 tick。~~`--node` 底下必須有 `.aos/inst.json`，沒有回 1~~（拿掉交給 aos-exec 的退路；inst.json 那半句同日再改，見下條）。下面各步跟這條衝突的句子劃掉、註明。
>
> **~~`--node`~~ ~~`--target`~~ 目標（位置參數）（2026-10-01，見待問 10、16、17，已寫入 spec（commit 前由我補號））**：省略用 `./`、相對路徑轉絕對；資料夾要有 `.aos/tasks.json`（不看 `.aos/inst.json`，tick 跟 inst.json 分開），沒有回 1；~~給檔就拿它當這一格的任務表、它所在的資料夾當工作資料夾（檔在 `.aos/` 裡時取上一層）~~（同日撤回，待問 18：目標只能是資料夾，給檔＝stderr `usage:`、回 1）；不存在回 1（stderr ~~`no_node:`~~ `no_target:`）。
>
> **工作資料夾、`AOS_TICK_CWD`（2026-10-01，見待問 16，已寫入 spec（commit 前由我補號））**：「工作資料夾」＝這一格 aos-tick 的 cwd（目標指的資料夾~~；給檔時是檔所在的資料夾~~，待問 18）。給任務的 ~~`AOS_NODE_DIR`~~ 改名 `AOS_TICK_CWD`（它的絕對路徑）；~~`AOS_TICK_RECORD`~~ 拿掉，任務從 `$AOS_TICK_CWD/<狀態資料夾>/tick/current.json` 找紀錄。node 是之後 aos-tick 的 node 模組的事，tick 這層不談；本檔舊文字裡的「node」在 tick 這層都讀成工作資料夾。
>
> **`AOS_DIRNAME`（2026-10-01，見待問 13、15，已寫入 spec（commit 前由我補號））**：本檔所有 `.aos` 都是環境變數 `AOS_DIRNAME` 給的名字（沒設＝`.aos`；~~空＝`.aos`~~ 設了但空字串＝不用子資料夾，狀態檔直接在 node 資料夾下；含 `/`、是 `.`、`..` 算用法錯回 1）。只換名字、位置仍在 node 資料夾裡；`aos-exec` 找資料夾目標的 inst 也照它（空字串時只找 `<目標>/inst.json`）。
>
> **任務表頂層預設、只展開到 `tasks`（2026-10-01，見待問 18，已寫入 spec（commit 前由我補號））**：tasks.json 頂層可放 inst 的七個欄位當每一項的預設，淺層合併、項蓋過；頂層 `cwd` 不改 tick 自己的 cwd、相對以工作資料夾為起點；讀表時只解到 `tasks` 這層，每項內部跑到時合併預設後才照 inst 展開；頂層可選 `modules`，核心照收不理、不當預設。細節見步驟 4。

- 由 AI 隊實作、照各步驟驗收試跑，做完交使用者看；每步的「要使用者裁定的點」集中在文末待問。
- Python 3.9、只用標準庫。inst 的解析、驗證、開程序用從 proto5 複製來的 [src/py/lib/](../src/py/README.md)：`aos_inst.load(path, base)`／`aos_inst.load_obj(obj, base)` 讀驗解一份 inst（壞就丟 `InstError`，`str(e)` 是「代號: 白話」），`aos_exec` 開程序。lib 沒有、tick 要自己接的東西寫在步驟 4 的「注意」與步驟 5 的「tick 要自己接」。
- 建議（非定案）：程式放 `proto6/src/py/aos_tick/`，入口 `proto6/src/bin/aos-tick`；測試用 `unittest`。
- 一格的順序（[B-620「一格怎麼走」](../spec/settled/tick.md#b-620任務註冊表照表依序跑)，POC 版）：取鎖 → 看擋板 → 讀表（極簡檢查）→ 換紀錄 → 照表跑（每項後寫紀錄、查停格檔）→ 回結束碼。~~驗表~~（2026-10-01 作廢）；取鎖同日先拿掉又加回、讀表同日移到換紀錄之前（待問 12）。下面的步驟大致照這個順序長出來。

## 步驟 1：找資料夾、取鎖

- ~~**2026-10-01（待問 8）**：取鎖整個拿掉——不建 `.aos/tick.lock`、不回 75、不傳鎖 fd、沒有 `AOS_TICK_LOCK_FD`。本步只剩「認資料夾」。~~（同日加回最簡版，見下條）
- **2026-10-01 再改（待問 12）**：加回最簡互斥——外層定期跑 `aos-tick`，上一格沒跑完下一格就來是正常使用。認完資料夾後對 `.aos/tick.lock` 取非阻塞 `flock`（不存在就建，`.aos/` 不在就建）；拿不到就 stderr 一行 `busy:`、回 ~~2（正常中斷）~~ 0（待問 15），不寫紀錄、不加 `seq`、不看擋板。拿到就整格持鎖。不回 75、鎖 fd 不傳給任務、沒有 `AOS_TICK_LOCK_FD`。
- **要做到**：認出要跑哪個資料夾，取鎖。~~對 `.aos/tick.lock` 取非阻塞獨占鎖；拿不到就回 75、什麼都不動。拿到就整格持鎖。~~（2026-10-01 改成上一條）
- **spec**：[B-602](../spec/settled/tick.md#b-602同一資料夾一次一格互斥鎖)；argv 見 [P-203](../spec/settled/protocol/tick.md#p-203aos-tick-與任意任務程式建議預設未拍板)。
- **做法**：
  - ~~`--node` 可以是資料夾、`.aos/inst.json` 或 `inst.json`，一律正規化成 node 資料夾；~~省略時用目前目錄。（2026-10-01 改，待問 10：）
  - 相對路徑一律轉成絕對再用。是資料夾：要有 `.aos/tasks.json`，沒有就 stderr `no_tasks:`、回 1、什麼都不建。~~是檔：這個檔就是這一格的任務表（照步驟 4 的極簡檢查），它所在的資料夾當 node（擋板檔、停格檔、紀錄都在 node 的 `.aos/` 下，`.aos/`、`.aos/tick/` 不在就建，只建資料夾）；那個資料夾若叫 `.aos`，node 取它的上一層。~~（2026-10-01 撤回，待問 18）是檔：stderr `usage:`（說明目標要是資料夾）、回 1、什麼都不建。不存在：stderr `no_node:`、回 1。
  - 取鎖是「定位資料夾之後第一件事」，在看擋板檔之前；拿不到直接回 ~~75~~ ~~2~~ 0（2026-10-01，待問 12、15），不重試、不寫紀錄。認資料夾失敗（`no_tasks`、`no_node`、用法錯）時還沒取鎖、什麼都不建。
  - ~~鎖 fd 要留給任務繼承（步驟 5 用）。~~（2026-10-01 作廢：鎖 fd 不傳給任務）
  - argv 解析、用法錯回 ~~2~~ 1（2026-10-01，待問 9）、鎖檔不存在就建立（2026-10-01 加回）、`chdir` 到 node 資料夾。
- **要使用者裁定的點**：已裁定（待問 5、6）：`.aos/` 不存在時照 aos-exec 找檔——有 `inst.json` 就像 aos-exec 跑一次（不取鎖、不寫紀錄、退出碼照 aos-exec）；兩個都沒有才直接報錯、不自建~~，回 2、stderr `config_invalid: …`（照 P-203 碼表「任務表不合法」歸 2）。`.aos/` 在時鎖檔不存在照 B-602 建立。~~ ~~（2026-10-01 改：整個交給 aos-exec，兩個都沒有時就是 aos-exec 自己的用法錯 2、stderr `aos-exec: …`；鎖檔不建）（2026-10-01 再改，待問 9：退路整個拿掉——`--node` 指的資料夾必須有 `.aos/inst.json`，沒有就 stderr `no_inst: …`、回 1、什麼都不建；只有頂層 `inst.json` 也一樣回 1）~~（2026-10-01 三改，待問 10：改看 `.aos/tasks.json`，見上面「做法」）
- **注意**：
  - Python 開的 fd 預設不會傳給子程序（`os.open` 預設不可繼承、`Popen` 預設 `close_fds`），正好合用：任務拿不到鎖 fd（2026-10-01，待問 12）。
  - 鎖檔放 `.aos/tick.lock`，**不是**探針原型放的 git 管理目錄。
  - ~~`--node` 指定時要是絕對路徑（node id 的定義，P-002）；~~不往上層目錄找。（2026-10-01 改，待問 10：相對路徑轉成絕對，node id 仍是絕對路徑）
- **驗收**：
  - ~~同資料夾同時跑兩個（第一格的任務 `sleep 5`）：一個回 75、另一個照跑。~~（2026-10-01 作廢）改成（待問 12）：第一格的任務卡住時同資料夾再跑一格：回 ~~2~~ 0（待問 15）、stderr 一行 `busy:`、`current.json`／`last.json` 與 `seq` 都不動（這時有擋板檔也是 `busy:`，鎖先）；第一格照跑完，之後下一格照常。任務裡看不到鎖檔的 fd、沒有 `AOS_TICK_LOCK_FD`。
  - ~~用資料夾路徑跑一格佔著，同時用 `.aos/inst.json` 路徑跑另一格：回 75（同一把鎖）。~~（2026-10-01 作廢）改成：~~用資料夾、`.aos/inst.json`、`inst.json` 三種路徑各跑一格，都跑在同一個 node（`seq` 接著數）。~~（2026-10-01 作廢，待問 10）
  - 資料夾不是 git repo 也跑得動~~拿得到鎖~~。
  - ~~（2026-10-01，待問 9）沒有 `.aos/inst.json`（不管有沒有頂層 `inst.json`、有沒有 `.aos/`）：回 1、stderr `no_inst:`、沒跑任務、沒建紀錄；argv 錯、`--node` 不是絕對路徑或不是資料夾：回 1。~~（2026-10-01 作廢，待問 10）
  - （2026-10-01，待問 10）不給 ~~`--node`~~ ~~`--target`~~ 目標（待問 17）用目前目錄、給相對路徑也跑在同一個工作資料夾（~~`AOS_NODE_DIR`~~ `AOS_TICK_CWD` 是絕對路徑；待問 16）。
  - 資料夾沒有 `.aos/tasks.json`（有沒有 `.aos/`、只有 `.aos/inst.json` 或頂層 `inst.json` 都一樣）：回 1、stderr `no_tasks:`、沒跑任務、沒建紀錄；有 `tasks.json` 沒有 `inst.json` 照跑。
  - ~~給檔：照這個檔跑（不看 node 的 `.aos/tasks.json`），紀錄寫在所在資料夾的 `.aos/tick/`；所在資料夾沒有 `.aos/` 也能跑、連跑 `seq` 接著數；給 `yyy/.aos/tasks.json` 跟給 `yyy` 是同一個 node；檔壞回 1。~~（2026-10-01 撤回，待問 18）給檔（含 `yyy/.aos/tasks.json` 本身）：回 1、stderr `usage:`、什麼都不建。
  - ~~`--node`~~ ~~`--target`~~ 目標指的東西不存在：回 1、stderr ~~`no_node:`~~ `no_target:`（待問 16）；argv 錯：回 1。

## 步驟 2：擋板檔與結束碼骨架

- **要做到**：取鎖後（2026-10-01 加回，待問 12）先看 `.aos/tick-blocked`；有就一項都不跑、不寫紀錄、回 ~~1~~ ~~2~~ 0（正常中斷也是 0；2026-10-01，待問 9、15）。順便把整格的結束碼（~~0／1／2／75~~；2026-10-01 待問 9、15：0 照表跑完、擋板、busy，1 tick 自己出錯（含 argv 用法錯））和 stderr 代碼的出口定好。
- **spec**：[B-620 停格檔與擋板檔](../spec/settled/tick.md#b-620任務註冊表照表依序跑)；檔名與內容 [P-213](../spec/settled/protocol/tick.md#p-213每項結束碼紀錄停格檔與擋板檔建議預設未拍板)；碼表 P-203。
- **做法**：擋板檢查放在取鎖之後、讀表與換紀錄之前；擋住時不加 `seq`、不刪停格檔。stderr 統一印 `代碼: 說明`；讀擋板檔的一行原因。
- **要使用者裁定的點**：無。
- **驗收**：先跑一格建出紀錄，再 `echo 壞了 > .aos/tick-blocked`，跑 `aos-tick`：回 ~~1~~ ~~2~~ 0（待問 15）、stderr 有 `blocked: 壞了`、任務沒跑、`current.json` 與 `last.json` 內容不變；刪掉擋板後下一格照常。

## 步驟 3：結束碼紀錄與格數

- **要做到**：每格開頭把 `current.json` 換成 `last.json`，寫一份新的（`seq` 加 1、`ended:false`、`tasks:[]`）；每跑完一項整份重寫；跑完寫 `ended:true` 與整格結束碼。
  - **2026-10-01 第八批補註**（[verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第八批紀錄只記非-0)）：使用者「tasks如果結果是0，那就不用紀錄了。hooks也是。」新紀錄開格時多 `ran:0`；每跑完一項 `ran` 加 1，結束碼不是 0 的才在 `tasks` 加一筆 `{"id","index","exit"}`（訊號殺的是 `signal`）。已改程式與測試（`RecordOnlyFailures` 等）。
- **spec**：[B-633](../spec/settled/tick.md#b-633每項結束碼紀錄與格數)；格式 P-213 與 [tick-record schema](../spec/protocol/schemas/tick-record.schema.json)。
- **做法**：
  - 算 `seq`：有 `current.json` 取它加 1，沒有取 `last.json` 加 1，都沒有是 1；~~讀不懂的當沒有~~（2026-10-01 作廢：默認讀得懂）。
  - 換檔四步照 B-633「開格：換檔」；特別是「沒有 current 卻有 last」要刪掉 last。
  - 每次寫都是「寫暫存檔 → rename」。
  - 紀錄的讀寫小函式、`started_at_ms`、用 schema 核對紀錄的測試輔助。
- **要使用者裁定的點**：無。
- **驗收**（任務表先只放 `true`）：
  - 同資料夾連跑十格，`seq` 從 1 到 10；中間換成 cron 或另一個 shell 跑，照樣接著數。
  - 鎖被占回 ~~75~~ ~~2~~ 0 時兩份紀錄都不變（2026-10-01 加回，待問 12）；表壞回 1 時也不變（待問 12）。
  - 用 schema 核對 `current.json` 與 `last.json` 都合格。

## 步驟 4：讀任務表~~、只驗四件事~~

- **2026-10-01（待問 8）**：驗表整個拿掉——默認表是對的，不回 2、不印 `config_invalid`、表壞也不佔 `seq`；表壞了就讓 Python 自然丟錯（回 1，紀錄停在 `ended:false`）。本步只剩「開格讀表、拿每項的 `id`」。下面講驗表的句子都作廢。
- **2026-10-01 三改（待問 12）**：讀表移到換紀錄之前——表讀不到或極簡檢查不過就 `bad_table:`、回 1，**不算開過一格**：`current.json`／`last.json` 不換、`seq` 不加（第一次跑就壞時連 `.aos/tick/` 都不建）。
- **2026-10-01 四改（待問 18，頂層預設）**：讀表只解到 `tasks` 這層——整份是指示詞先解；`tasks`、`modules` 與七個預設鍵（`argv`、`cwd`、`envs`、`stdin`、`stdout`、`stderr`、`exit`）的值各解一層（`$opt` 原樣留）；`tasks` 每一元素解一層（整項 `$ref`）。這層以工作資料夾為中心，`$ref:""`／`#…` 指整份 tasks.json；解不開算 `bad_table`。極簡檢查改成「每項解一層後是物件、合併頂層預設後有 `argv`」。跑到某項時才淺層合併（項蓋過頂層，`envs` 整包換），合併結果當獨立的記憶體 inst 交給 `aos_inst.load_obj`，這時 `$ref:""`／`#…` 指合併後的這一項。頂層 `_metainfo`、`id`、`kind`、`modules` 不當預設；頂層 `cwd` 不改 tick 自己的 cwd。
- **2026-10-01 再改（待問 11）**：開格做極簡檢查——合法 JSON、頂層物件有 `tasks` 陣列、每項（`$ref` 展開後）是物件且有 `argv`；不過就 stderr `bad_table:`、回 1。其他（`_metainfo`、`id`、`kind`、型別、`id` 重複、陌生鍵）都不查；`methods` 從規範拿掉、當陌生鍵。
- **要做到**：開格讀一次 `.aos/tasks.json`（目標給檔時讀那個檔——2026-10-01 待問 10，同日撤回，待問 18，只讀 `.aos/tasks.json`）~~，只驗：合法 JSON、`_metainfo` 是 `aos-tasks` 第 1 版、每項（整份 `$ref` 展開後）是合法 inst、`id` 在表內唯一。不合就整表拒絕、回 2~~（2026-10-01 作廢）。
- **spec**：[B-620 讀表與「誰驗什麼」](../spec/settled/tick.md#b-620任務註冊表照表依序跑)；[P-202](../spec/settled/protocol/tick.md#p-202任務註冊表建議預設未拍板)；[inst](../spec/base/inst.md)。
- **做法**：
  - ~~只驗這四件，~~其餘（缺 `kind`、`system.x`、~~`methods` 形狀~~）核心**不驗、照跑**。
  - ~~表壞時：stderr 印 `config_invalid: 哪裡錯`，紀錄寫 `ended:true`、`exit:2`、`tasks:[]`，回 2。紀錄在讀表之前就換好了，所以表壞的格也佔一個 `seq`。~~（2026-10-01 作廢）
  - 陌生鍵（包括舊的 `group`、`needs`）照收、忽略。
  - ~~用 `aos_inst.load_obj(項, node 資料夾)` 驗每一項，`str(InstError)` 就是一行說明。~~（2026-10-01 作廢）
- **要使用者裁定的點**：已裁定（待問 6）：~~有 `.aos/` 但沒有 `tasks.json` 算表壞，照表壞的做法回 2（紀錄照換、佔一個 `seq`）。~~（2026-10-01 作廢：默認表在，不在就自然丟錯）
- **注意**：`id`、`kind`、`methods` 不是 inst 的欄位。整份 `$ref` 的項就照 `$ref` 的規則展開（已裁定，見待問 2）。**tick 要自己接**：`load_obj` 只回七個執行欄位，不認得的鍵（`id`、`kind`、`methods`）直接丟掉，也不回原始 `user`；`id` 要 tick 自己拿（整份 `$ref` 的項先用 `aos_directives.resolve_located` 展開頂層再讀），~~原始 `user` 直接讀項目的字面值~~。~~另外 `load_obj` 看到跟目前身分不同的 `user` 會丟 `UserNotGranted`——開格驗表時別讓它把整表打成壞表，先自己判 `user`、再把拿掉 `user` 的項交給 `load_obj`~~（2026-10-01：lib 撤回「認得頂層 `user`」、回到 proto5 原樣，`load_obj` 把 `user` 當陌生鍵忽略，tick 直接交給它，不用先拿掉；見待問 14）。
- **開格只拿 `id`、不留結果**：~~這一步的展開只為了驗合不合法；~~驗過的結果不留，跑到那一項時才展開成 inst（步驟 5，已裁定，見待問 3）。
- **找表**：~~資料夾沒有 `.aos/` 時去找 `inst.json`（跟 inst 目標找檔同一套：先 `.aos/`，沒有就 `inst.json`）；已裁定，見待問 5。~~（2026-10-01 作廢，待問 9：必須有 `.aos/inst.json`，任務照 `.aos/tasks.json`）
  - ~~跟待問 6 怎麼並存：待問 5 講的是「認這個 node 的 inst」怎麼找（步驟 1 正規化 `--node`、步驟 8 判上層都照它）；`aos-tick` 跑一格要的鎖檔、任務表、紀錄都在 `.aos/` 裡，所以資料夾沒有 `.aos/` 時不跑一格：有 `inst.json` 就像 aos-exec 跑它一次（不取鎖、不寫紀錄），兩個都沒有才回 2、不自建（待問 6）。~~（2026-10-01 作廢，待問 9）
- **驗收**：
  - ~~表裡 `id` 重複：一項都不跑、回 2、stderr 有 `config_invalid`、紀錄 `exit:2`。~~（2026-10-01 作廢）
  - 帶 `group`、`needs` 的表照跑；帶 `kind:"system.x"` 的表也照跑；整份 `$ref` 的項拿得到 `id`。
  - ~~拿 spec 的反例與正例表（[examples/tick/](../spec/protocol/examples/tick/) 裡的 `tasks.*.json`）各跑一次，看核心只擋「四件事」的那幾份。~~（2026-10-01 作廢）

## 步驟 5：照表跑每一項

- **要做到**：照陣列順序一項一項跑，前一項結束才開下一項；每項用 inst 的規則跑，環境多放~~五~~ ~~四~~ 三個變數（2026-10-01：沒有 `AOS_TICK_LOCK_FD`；同日再拿掉 `AOS_TICK_RECORD`，見待問 16）；結束後把 `exit` 或 `signal` 寫進紀錄。
- **spec**：[B-620 跑每一項、任務的帳號](../spec/settled/tick.md#b-620任務註冊表照表依序跑)；環境與介面 P-203。
- **做法**：
  - 每項跑到時才重新展開（含整份 `$ref`）再開程序；不重用開格驗過的結果，所以前面的項改了 `$ref` 指到的檔，後面的項看到新內容。~~重新展開後不合法照失敗處理（不回頭改整格結果，只是這一項失敗），這一條 spec 沒寫、屬待問 6。~~（2026-10-01 作廢：重新展開壞了就自然丟錯、整格回 1，不另記 125）
  - 成敗：~~正常退出 0 才算成功；非零、被訊號結束、exec 失敗都算失敗。任務回 3、100、125 都只是一般失敗，後面照跑。~~（2026-10-01 改，待問 9）任務怎麼結束（0、1、2、125～127、被訊號殺）都照實記進紀錄、照常跑下一項，不影響 tick 的結束碼。
  - ~~帳號：項目帶 `user` 而且解析成的 UID 跟 tick 自己不同 → 不跑、紀錄 `exit:125`、stderr `user_mismatch: <id>`，其餘照跑。~~（2026-10-01 作廢：tick 不看 `user`，照 tick 自己的帳號跑；`load_obj` 本來就忽略它，見待問 14）核心**不切帳號**。
  - 三個變數：~~`AOS_NODE_DIR`~~ `AOS_TICK_CWD`（2026-10-01 改名，待問 16）、~~`AOS_TICK_LOCK_FD`~~（2026-10-01 作廢）、~~`AOS_TICK_RECORD`~~（2026-10-01 拿掉，待問 16）、`AOS_TASK_ID`、`AOS_TASK_INDEX`。
  - 整格結束碼：~~全成功 0，有失敗 1~~ 照表跑完就是 0（2026-10-01，待問 9）。
  - 用複製來的 lib 跑單項（`load_obj` 解出的 inst：cwd 預設 base＝node 根、串流預設 `/dev/null`、`envs` 疊上去；`aos_exec_run` 開子程序另開 session）；把 wait 結果轉成 `exit`／`signal`。
- **要使用者裁定的點**：已裁定（待問 6）：開格驗過之後到跑到該項之間，假設檔案不會變，不為這種情況特別設計。實作走最自然的行為：~~重新展開丟錯就當那一項沒跑成（照 inst 算 125），後面照跑~~（2026-10-01 改：重新展開丟錯就讓它丟，整格回 1）。
- **tick 要自己接**（lib 沒有，別去改 lib）：公開的 `aos_exec.run_inst()` 會接管 stdin／stdout，不合用；照 inst 開檔、開程序的是私有的 `aos_exec_run._execute_inst()`。~~它的 `Popen` 用預設 `close_fds`，鎖 fd 繼承不到；~~四個 `AOS_*` 要自己塞進 `envs`~~，而且 `clear` 時 `AOS_TICK_LOCK_FD` 仍要留~~（2026-10-01 作廢）；回的是單一結束碼（被訊號 N 殺是 128+N），紀錄要分 `exit`／`signal` 得自己等子程序。
- **注意**：
  - 核心**不清後代**（B-602）。~~任務留下還握著鎖 fd 的程序，下一格會回 75；~~（2026-10-01 作廢）第一段沒人收，測完自己殺。探針原型在 tick 裡設了 subreaper 收後代，那是舊做法，別照抄。
  - 子程序另開 session，所以直接跑時按 Ctrl-C 只停得了 tick 本身。
  - 任務沒有逾時（延後，P-008）。
- **驗收**：
  - 第一項 `env > out.env`：~~四~~三個變數都在（沒有 `AOS_TICK_LOCK_FD`、`AOS_TICK_RECORD`、`AOS_NODE_DIR`；待問 16），`AOS_TASK_INDEX` 是 0、`AOS_TICK_CWD` 是工作資料夾的絕對路徑。
  - （2026-10-01，待問 12）任務看不到 `.aos/tick.lock` 的 fd。
  - 第二項讀 ~~`$AOS_TICK_RECORD`~~ `$AOS_TICK_CWD/<狀態資料夾>/tick/current.json`（待問 16），看得到第一項的 `exit`。
  - 第三項 `sh -c 'kill -9 $$'`：紀錄是 `signal:9`，後面照跑，整格回 ~~1~~ 0（2026-10-01，待問 9）。
  - （2026-10-01，待問 9）任務回 1、2、127、被訊號 2 殺：紀錄照實記原碼、後面照跑，整格回 0、stderr 空。
  - ~~某項帶別的帳號（例如 `"user":"root"`）：那一項 `exit:125`、stderr 有 `user_mismatch`，其餘照跑。~~（2026-10-01 改：照 tick 自己的帳號跑、沒有 `user_mismatch`）
  - ~~任務裡用 `AOS_TICK_LOCK_FD` 核對得到獨占鎖；它跑著時同資料夾另一格回 75。~~（2026-10-01 作廢；它跑著時另一格回 ~~2~~ 0 見步驟 1 驗收）

## 步驟 6：停格檔

- **要做到**：開第一項前（不在了就不刪）刪掉上一格留下的 `.aos/tick/stop`；每跑完一項就看有沒有它，有就不開後面的項，這格回 ~~1~~ 0（停格不算中斷；2026-10-01 暫定，待問 9）。
- **spec**：[B-620 停格檔與擋板檔](../spec/settled/tick.md#b-620任務註冊表照表依序跑)；紀錄欄位 P-213。
- **做法**：看到停格檔 → 紀錄寫 `ended:true`、`exit:~~1~~ 0`、`stopped_after:<剛跑完那項的 id>`；stderr 印 `stopped:` 加檔內原因。最後一項建的也算停下。
- **要使用者裁定的點**：無。
- **驗收**：第二項 `sh -c 'echo 手動停 > .aos/tick/stop'`：第三項沒跑、紀錄有 `stopped_after`、整格回 ~~1~~ 0；下一格照常三項都跑，停格檔已被刪。

## 步驟 7：紀錄寫不進、`--firstdo-fsync`

- **已裁定取消（待問 7）**：紀錄寫不進的處理（`record_unwritable`、失效開關、唯讀／滿碟驗收）不再要求，默認一定寫得進去；程式與測試已在 10-01 拿掉（下面「做法」「驗收」裡講寫不進的幾條一併作廢，留著只當紀錄）。
- **整步取消（2026-10-01，待問 8）**：`--firstdo-fsync`（含 `AOS_TICK_FIRSTDO_FSYNC`）POC 先不做；「兩份舊紀錄都讀不懂」默認不會發生，`record_unreadable` 不做。程式與測試已拿掉；下面整步只當紀錄。

- **要做到**：紀錄寫失敗時照表跑完、不再寫；帶 `--firstdo-fsync`（或環境有 `AOS_TICK_FIRSTDO_FSYNC=1`）時在規定的幾個點 fsync。
- **spec**：[B-633 落盤與失效](../spec/settled/tick.md#b-633每項結束碼紀錄與格數)。
- **做法**：
  - 「本格紀錄失效」是一個開關：任何一次寫失敗就打開，之後不再寫、之後開的項不設 `AOS_TICK_RECORD`、stderr 只印一次 `record_unwritable`。
  - 開格就失敗 vs 跑到一半才失敗，下一格看到的不一樣（B-633 失效表），分開處理。
  - ~~兩份舊紀錄都讀不懂：當開格失敗、兩份都不動、另印 `record_unreadable`。~~（2026-10-01 作廢）
  - ~~fsync 檔案與目錄的小函式；~~（2026-10-01 作廢）測試用的寫入失敗注入（建議用環境變數或替換寫檔函式，只在測試開）。
- **要使用者裁定的點**：無。
- **驗收**：
  - `chmod a-w .aos/tick`（或整個 `.aos/`）再跑：任務照跑完、stderr 有 `record_unwritable`、任務拿不到 `AOS_TICK_RECORD`。
  - 用注入讓第二項後寫失敗：第三項沒有 `AOS_TICK_RECORD`；下一格的 `last.json` 是 `ended:false`、只有前兩項。
  - ~~帶 `--firstdo-fsync` 用 `strace -f -e trace=fsync,fdatasync,rename` 看順序對得上 B-633 的表。真的斷電測試不在這段做。~~（2026-10-01 作廢）

## 步驟 8：~~上下層判定~~（2026-10-01 整步取消）

- **2026-10-01（待問 8）**：不需要判斷上下層，`default_parent()` 與測試已拿掉。下面只當紀錄。

- **要做到**：從本資料夾往上找，最近一個有 `.aos/inst.json` 或 `inst.json` 的資料夾就是預設上層；找不到就沒有。純路徑計算。
- **spec**：[B-628](../spec/settled/deferred/tick.md#b-628上下層判定預設看資料夾包含可登記覆蓋)（登記覆蓋是第三段 daemon 的事）。
- **做法**：路徑逐段往上比、不展開 symlink、不看 daemon。照 spec 實作判定即可，不另加子命令、旗標或輸出（已裁定）。
- **要使用者裁定的點**：無。
- **驗收**：`/a`、`/a/b` 都有 `.aos/inst.json`、`/a/x` 沒有：`/a/b` 與 `/a/x/c` 的上層都是 `/a`，`/a` 沒有上層。上下層判定只是函式，不另加指令或輸出，驗收不用印結果（已裁定，見待問 1）；用單元測試直接呼叫函式核對。

## 步驟 9：整段驗收

照 [V-03 第二十批新增場景](../spec/conformance.md#第二十批新增場景)「tick 核心、停格檔與擋板檔」和[第十九批](../spec/conformance.md#第十九批新增場景)「tick 核心」挑出不需要 daemon 的幾條，全部重跑一次：

- 任務表只放一項 `true`、機器上沒有 daemon、git、cgroup、helper：互斥、照表跑~~、上下層~~、紀錄都成立（2026-10-01：上下層 POC 先不做；互斥同日加回最簡版）（[B-626](../spec/settled/tick.md#b-626核心與系統級任務的界線)）。
- 直接跑的格照常做完、stderr 沒有 `standard:` 行（[B-627](../spec/settled/tick.md#b-627人手或-cron-直接跑一格風險自負)）。
- 步驟 1～6 的驗收合成一個 `unittest` 檔，一條指令跑完（7、8 已取消）；10-01 的結束碼另成 `ExitCodes` 類別（待問 9）。

## 做完了沒（2026-09-30 晚）

- **步驟 1～6 做完**（7、8 在 10-01 取消），程式在 [src/py](../src/py/README.md)（`bin/aos-tick`、`lib/aos_tick*.py`），驗收在 `tests/test_tick.py`（一步一個類別，10-01 第二輪後 12 條；全部 389 條全過）。
- **步驟 9**：B-626、B-627 兩條寫成 `Step9Whole`；其餘 V-03 條目散在各步的測試裡。
- ~~**還沒做**：步驟 7 用 `strace` 看 fsync 順序那條（這台機器沒有 strace）；目前只測了帶旗標／環境變數時照常跑完。~~（2026-10-01 作廢，fsync 不做）
- 實作時自己做的判斷列在 [src/py README「review 導讀」](../src/py/README.md#review-導讀)，都照「最小合理」做、可改。
- **10-01 收尾（待問 7）**：拿掉紀錄寫不進的處理（`record_unwritable`、失效開關、失敗注入、鎖檔唯讀退路）與三條測試，寫失敗就照常丟錯；「舊紀錄讀不懂」照 B-633 留著；spec 殘留提及標作廢。
- **10-01 第二輪（待問 8，POC 默認一切正常）**：拿掉互斥鎖（75、`lock_unavailable`、鎖 fd、`AOS_TICK_LOCK_FD`）、驗表（2、`config_invalid`）、`user` 判定（125、`user_mismatch`）、上下層 `default_parent()`、`--firstdo-fsync`、`record_unreadable`、停格檔刪不掉的 `stop_unremovable`、讀不到表、`exit` 檔寫不進、重新展開壞掉記 125；`aos_tick*.py` 從 552 行減到 339 行，`test_tick.py` 從 22 條減到 12 條。
- **10-01 第四輪（待問 10，`--node`）**：`node_dir_from_arg()` 換成 `resolve_node()`，回 (node, 任務表)；拿掉「必須絕對路徑」與 `.aos/inst.json`／`inst.json` 正規化；資料夾改看 `.aos/tasks.json`（`no_inst` → `no_tasks`），給檔當任務表，不存在 `no_node`；`read_table()` 改吃表的路徑。同日又加（待問 11）：讀表極簡檢查 `aos_tick_table.check_table()`（`bad_table`）、沒 `id` 的項用位置字串當 id。`test_tick.py` 15 條 → 27 條（`Step1Node` 4 條換成 12 條、新 `Step4Check` 4 條；`TickCase` 不再寫 `.aos/inst.json`，測試的項都帶 `_metainfo`），全部 392 → 404 條全過。
- **10-01 第三輪（待問 9，結束碼慣例）**：擋板檔回 2；停格檔回 0；任務的碼只記、不影響 tick（照表跑完一律 0）；argv 用法錯改回 1；拿掉「沒有 `.aos/` 交給 aos-exec」的退路，改成沒有 `.aos/inst.json` 就 stderr `no_inst:`、回 1；tick 自用檔出事照舊自然丟錯回 1。`test_tick.py` 12 條 → 15 條（拿掉兩條退路測試，加 `no_inst`、停格檔在錯之後、`ExitCodes` 三條），全部 389 → 392 條全過。
- **10-01 第五輪（待問 12、13）**：加回最簡互斥 `aos_tick.take_lock()`（`.aos/tick.lock` 非阻塞 `flock`，拿不到 `busy:` 回 2；順序：認資料夾 → 取鎖 → 擋板 → 讀表 → 換紀錄）；讀表移到換紀錄之前，表壞不換紀錄、不加 `seq`。新 `lib/aos_dirname.py`：`AOS_DIRNAME` 決定狀態資料夾名，`aos-tick` 全部照它、`aos-exec` 找資料夾目標的 inst 也照它（不合法：tick 回 1、aos-exec 照它的用法錯回 2、spawn 丟 `SpawnFailed`）。`test_tick.py` 27 條 → 34 條（新 `Step1Lock` 2 條、`Step4Check` 加 1 條、新 `DirName` 4 條；`test_file_mode_creates_aos_dir` 改成 `.aos/` 下也有 `tick.lock`、`Step4Check.bad` 加「沒建 `.aos/tick`」），`test_exec.py` +2、`test_exec_spawn.py` +1；全部 404 → 414 條全過。
- **10-01 第六輪（待問 14）**：`lib/aos_inst.py` 換回 proto5 原檔（拿掉 `_check_user`、`UserNotGranted`／`UserInvalid`），刪 `tests/test_user.py`（7 條）；`aos_tick_table.load_inst()` 不再先拿掉 `user`；`test_exec.py` 加一條「頂層 `user` 忽略、照跑」。全部 414 → 408 條全過。
- **10-01 第八輪（待問 16）**：給任務的 `AOS_NODE_DIR` 改名 `AOS_TICK_CWD`、拿掉 `AOS_TICK_RECORD`（`aos_tick.run_one()` 不再收 `record`）；`--node` 改名 `--target`（不留舊名）、`resolve_node()` → `resolve_target()`、stderr `no_node:` → `no_target:`；tick 各檔內部的 `node`／`node_dir` 變數改叫 `cwd`，說明改用「工作資料夾」。測試照改（任務改從 `$AOS_TICK_CWD/<dirname>/tick/current.json` 讀紀錄、確認沒有 `AOS_TICK_RECORD`／`AOS_NODE_DIR`；`Step1Node` → `Step1Target`），條數不變，全部 469 條全過。
- **10-01 第九輪（待問 17）**：目標改成位置參數 `aos-tick [<目標>]`（跟 aos-exec 一樣），拿掉 `--target` 旗標（不留，給了算用法錯；目標多於一個也算）；`aos_tick.main()` 改解位置參數，`resolve_target()`、`no_target:` 不變，說明裡的 `--target` 改叫「目標」。`test_tick.py`、`test_ctl.py` 呼叫改成位置參數，用法錯那條改成「給 `--target` 回 1」「給兩個目標回 1」，條數不變，全部 469 條全過。
- **10-01 第七輪（待問 15）**：結束碼慣例改版——`aos_tick` 拿掉 `EXIT_INTERRUPTED`，busy、擋板回 0；`aos_exec` 用法錯 2 → 1（`aos_exec_run.EXIT_USAGE`、argparse 換成回 1 的 `_Parser`）。`aos_dirname.name()` 分「沒設」與「空字串」，空字串＝資料夾本身：tick 的 `take_lock()` 不建資料夾、檔案模式不往上取一層；aos-exec `_dir_targets()` 只剩 `inst.json`。`test_tick.py` 34 條 → 37 條（新 `EmptyDirName` 3 條，busy／擋板改 0），`test_exec.py` +1（空字串）、用法錯改 1，`test_exec_spawn.py` 空字串補一段；全部 408 → 412 條全過。
- **10-01 第十輪（待問 18）**：`resolve_target()` 拿掉「目標是檔就當任務表」，給檔 stderr `usage:`、回 1；`aos_tick_table` 改成讀表只解到 `tasks`、回 `Table`（頂層預設、各項、id、`modules`），`load_inst(defaults, item, cwd)` 跑到時才合併再交給 `load_obj`（`aos_inst.py` 沒改）；`run_one()` 跟著多收預設。`test_tick.py` 拿掉給檔的 7 條（`Step1Target` 5、`DirName` 1、`EmptyDirName` 1），其中「相對檔名以工作資料夾為中心」改成資料夾模式另寫 1 條；`test_bad_item_metainfo_value_is_error` 改用資料夾模式；加「給檔回 1、什麼都不建」1 條、`Step4Check` 加 1 條、新 `Step4Defaults` 8 條（41 條）。`test_ctl.py` 的 `test_keep_schedule` 偶發失敗是 WSL 牆上時鐘被校時往前跳，任務改寫 `/proc/uptime`、判準改成「t3－t2 < 週期」，單跑 30 次全過（細節見該測試註解）。全部 471 → 475 條，連跑 3 次全過。
- **已結案的 spec 疑點**：B-633「第二項後滿碟」驗收句跟失效表對不上；兩者都已作廢。

## 第一段不做的，先怎麼擋著

| 不做 | 第一段的樣子 | 哪段做 |
|---|---|---|
| 系統級任務（`aos-git`、`aos-publish`〔2026-10-01 搬暫緩區〕、`aos-clean`）、標準任務表範本 | 測試用的表只放 `true`、`sh -c` 這類普通指令；範本表裡的程式還不存在，跑了是 127 | 第二段 |
| 普通程式 `aos-needs`〔2026-10-01 改寫成 `aos-tick-check-task`〕、`aos-cg`、`aos-as` | 同上，不放進測試表 | 二、四、五段 |
| daemon、runner、通道、佇列 | 只有直接跑；環境裡沒有 `AOS_DAEMON_SOCKET`，核心也不看它 | 三、四段 |
| 清任務留下的後代 | 核心本來就不清；測試結束自己殺 | 第三段（runner 格後收屍） |
| 恢復前驗證（完整 schema、`kind` 的值） | 核心只做極簡檢查（B-620） | 第二段 |
| 任務逾時 | 沒有 | 延後（P-008） |
| ~~同資料夾互斥、~~上下層判定、驗表、`user` 判定、`--firstdo-fsync`、各種異常處理 | 默認一切正常，出事自然丟錯、回 1（待問 8）；互斥 10-01 加回最簡版（待問 12） | POC 不做；C++11 改寫時再看 |
| tick 被殺時清它的孩子 | 不做（任務另開 session，tick 被殺孩子照跑） | 留給 daemon 段（待問 12） |

## 待問

〔使用者方向 2026-09-30 晚〕前五條已裁定：

1. **上下層判定怎麼給人看？已裁定：** 不另加指令或輸出，只在必要時才有影響；第一段照 spec 實作判定即可，驗收不用印結果。
2. **整份 `$ref` 的項怎麼拿 `id`？已裁定：** 就照 `$ref` 的規則展開，不是問題（`id` 由 tick 自己從項目拿，見步驟 4「注意」）。
3. **開格驗過的展開結果要不要重用？已裁定：不重用。** 跑到那一項時重新展開。
4. **`system.x` 擋不擋？已裁定：** 核心不擋、不管，自己承擔風險；以 B-620 為準。[V-03](../spec/conformance.md#第十八批新增場景) 原本寫「整份拒收」的那句已改成跟 B-620 一致（核心照跑、不擋）。
5. **資料夾沒有 `.aos/` 時怎麼算？已裁定：** 去找 `inst.json`（跟 inst 目標找檔同一套：先 `.aos/`，沒有就 `inst.json`）。〔使用者方向 2026-09-30 晚〕有 `inst.json` 就像 aos-exec 把它跑一次（直接用 aos_exec 的函式；不取鎖、不寫紀錄；退出碼照 aos-exec）。spec B-620「任務表」處已補同義的話。〔2026-10-01 作廢，見待問 9：退路拿掉，沒有 `.aos/inst.json` 就回 1〕

6. **`.aos/`、`tasks.json` 不在，和驗表後檔案被改，怎麼算？已裁定**〔使用者方向 2026-09-30 晚〕：
   - 〔2026-10-01 作廢，見待問 9：一律要有 `.aos/inst.json`，沒有回 1〕~~資料夾沒有 `.aos/` 也沒有 `inst.json`：直接報錯，不自建（只有 `inst.json` 時照待問 5 像 aos-exec 跑）。碼用 2（P-203「任務表不合法」；B-602／B-620 沒有更貼的），stderr `config_invalid:`，不取鎖、不寫紀錄。~~
   - ~~有 `.aos/` 但沒有 `tasks.json`：算表壞，回 2。~~（2026-10-01 作廢：待問 8 起自然丟錯，照待問 9 是 tick 自己出錯、回 1）
   - 開格驗過表之後、跑到某項重新展開之間，假設檔案不會變；不為這種情況特別設計，出事就出事，實作走最簡單的自然行為。
   - spec B-620「任務表」已補一句同義的話。

7. **結束碼紀錄寫不進怎麼辦？已裁定**〔使用者方向 2026-09-30 晚〕：寫不寫得進去不管，默認一定寫得進去。B-633「失效：寫不進時」一小節、`record_unwritable`、相關驗收（唯讀資料夾、開格滿碟、第二項後滿碟）都不再要求；步驟 7 對應的程式與測試已在 10-01 拿掉（見「做完了沒」）。

8. **POC 要不要處理異常、互斥、驗表、帳號、上下層？已裁定**〔使用者方向 2026-10-01〕：**默認一切正常，都不做。** 使用者原話：「我們都默認所有東西都OK都正常，先不考慮邊緣狀況」「紀錄這邊，我們都默認紀錄是好的」「舊紀錄不管，我們都默認紀錄能讀得懂」「--firstdo-fsync...先不做吧，我們先做單純的」「別人正在跑？默認沒有別人在跑，這個不管，或是直接報錯。然後也不需要判斷上下層。」「表不合法也拿掉，回 0／1 就好」「帳號不對，也不管」。
   - 檔案寫得進、讀得懂、沒壞、不斷電：不寫處理，出事自然丟錯（traceback、回 1）。寫紀錄失敗回 1、跟任務失敗分不出來，照舊。
   - 同資料夾互斥（B-602）整個拿掉：不取鎖、不回 75、不傳鎖 fd。上下層判定（B-628）拿掉。
   - 任務表不驗（不回 2、`config_invalid`）；`user` 不看（不回 125、`user_mismatch`）；`--firstdo-fsync`、`record_unreadable` 不做。
   - ~~整格碼只剩 0／1；argv 用法錯仍回 2（不是一格）。~~（10-01 再改，見待問 9：照表跑完 0、擋板 ~~2~~ 0（待問 15）、tick 自己出錯 1，argv 用法錯也是 1）
   - spec 規定不刪，2026-10-01 統一更新時搬到[暫緩區](../spec/settled/deferred/README.md)。

9. **aos-tick 的結束碼怎麼對上 aos 體系慣例？已裁定**〔使用者方向 2026-10-01〕：慣例全文（~~0 正常結束、1 錯誤結束、2 正常中斷~~ 同日改版見待問 15）與原話記在 [verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)，**已寫入 spec（commit 前由我補號）**（這輪 spec 一字未動）。
   - `aos-tick` 的碼只講 tick 自己：照表跑完 0（不管任務成敗）、停格檔停下 0（不算中斷，暫定）、擋板檔 ~~2~~ 0（待問 15；不寫紀錄、不加 `seq`）、tick 自己出錯 1。
   - tick 自己出錯：argv 用法錯（不再回 2）、`--node` 不是絕對路徑／不是資料夾、`--node` 底下沒有 `.aos/inst.json`；自用檔（`tick-blocked`、`stop`、`current.json`、`last.json`、`tasks.json`）讀不到／寫不進／格式壞就自然丟錯（traceback、回 1），不分時機、不補救。
   - 任務回 0、1、2、其他碼、被訊號殺：都照實記進紀錄、照常跑下一項，不影響 tick 的碼（使用者原話「任務出錯，不算在tick的錯誤內」「任務回2也只記一筆，照常跑下一項」）。
   - 拿掉待問 5、6 的退路：不再「沒有 `.aos/` 就交給 aos-exec 跑 `inst.json`」；任務仍照 `.aos/tasks.json`。
   - 擋板檔與停格檔的機制使用者之後會詳細設計，目前做法是暫定。2026-10-01 使用者：先照現狀（「tick-blocked, tick/stop就先這樣。」）。
   - 〔2026-10-01 再改，見待問 10〕「`--node` 底下沒有 `.aos/inst.json` 回 1」改成看 `.aos/tasks.json`。

10. **`--node` 怎麼認？已裁定**〔使用者方向 2026-10-01，已寫入 spec（commit 前由我補號）〕：原話與全文在 [verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#aos-tick---node-怎麼認待統一更新-spec)（使用者寫 `task.json` 即 `tasks.json`）。
   - 省略用 `./`；相對路徑一律轉絕對（拿掉「必須絕對路徑」）。
   - 資料夾：合法＝有 `.aos/tasks.json`，不看 `.aos/inst.json`（tick 跟 inst.json 分開）；沒有回 1。
   - 檔：當這一格的任務表，所在資料夾 yyy 當 node（擋板、停格、紀錄都在 `yyy/.aos/`，不在就建資料夾）；`yyy/.aos/tasks.json` 在不在都不管。格式照待問 11 的極簡檢查，不過回 1。
   - 不存在回 1。結束碼照待問 9 不變。
   - 表裡的相對路徑與指示詞以 node 根為中心（給檔時＝檔所在的資料夾）。
   - 實作自己定的（可改）：檔所在的資料夾叫 `.aos` 時 node 取上一層（`--node yyy/.aos/tasks.json` ≡ `--node yyy`），不照字面當 `yyy/.aos`；舊的 `--node …/.aos/inst.json` 現在會被當任務表讀、讀壞回 1；stderr 代碼 `no_tasks`、`no_node`。

11. **任務表格式錯怎麼算？已裁定**〔使用者方向 2026-10-01，已寫入 spec（commit 前由我補號）〕：全文在 [verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#aos-tick-讀任務表的極簡檢查待統一更新-spec)。
   - 格式錯算 tick 自己的錯：stderr 一行 `bad_table:`、回 1（給檔時一樣）。取代待問 8「表不驗」。
   - 只查：合法 JSON、頂層物件有 `tasks` 陣列、每項（`$ref` 展開後）是物件且有 `argv`。外層與每項的 `_metainfo`、`id`、`kind` 都不查（`_metainfo` 格式上照寫）；`kind` 不必填；`methods` 從規範拿掉、當陌生鍵。
   - 沒 `id` 的項：id＝它在 `tasks` 陣列的位置（從 0 起）轉字串（例如 `"3"`），紀錄與 `AOS_TASK_ID` 都用它；撞了不管（「默認不重複」）。
   - ~~實作自己定的（可改）：檢查在換紀錄之後，表壞仍佔 `seq`。~~（2026-10-01 改，見待問 12：移到換紀錄之前，不佔 `seq`）

12. **同資料夾互斥、讀表的時機？已裁定**〔使用者方向 2026-10-01，已寫入 spec（commit 前由我補號）〕：全文在 [verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#aos-tick-最簡互斥與讀表時機待統一更新-spec)。
   - 加回最簡互斥（理由：外層定期跑 `aos-tick`，上一格沒跑完下一格就來是正常使用會碰到的）：開格前對 `.aos/tick.lock` 取非阻塞 `flock`（不存在就建）；拿不到 stderr 一行 `busy:`、回 ~~2（正常中斷）~~ 0（待問 15），不寫紀錄、不加 `seq`。鎖 fd 不傳給任務、沒有 `AOS_TICK_LOCK_FD`。取代待問 8「互斥整個拿掉」。
   - 讀表移到換紀錄之前：表讀不到／極簡檢查不過 → 回 1，不算開過一格（不換 current／last、不加 `seq`）。取代待問 11「實作自己定的」那條。
   - 不做：任務逾時、tick 被殺時清孩子（留給 daemon 段）。任務輸出預設照 inst 接 `/dev/null`，不動。
   - 照舊：檔在 `.aos/` 裡時 node 取上一層；只寫 `--node` 不給值算用法錯回 1；`id` 非字串照 `str()`。
   - 實作自己定的（可改）：鎖在擋板之前（照原 B-602／B-620 順序「取鎖是第一件事」）；兩個都在時回 `busy:`（都是 ~~2~~ 0，差別只在 stderr）。鎖檔 tick 不刪，留在 `.aos/` 裡。

13. **狀態資料夾的名字？已裁定**〔使用者方向 2026-10-01，已寫入 spec（commit 前由我補號）〕：全文在 [verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#aos_dirname-狀態資料夾的名字待統一更新-spec)。
   - 環境變數 `AOS_DIRNAME` 決定 node 狀態資料夾的**名字**（只換名字，位置仍在 node 資料夾裡）；沒設~~或空字串~~＝`.aos`（空字串同日再改，見待問 15）；含 `/`、或是 `.`、`..` 算用法錯。
   - `aos-tick` 所有寫死 `.aos` 的地方都照它（`tasks.json`、`tick.lock`、`tick-blocked`、`tick/stop`、`tick/current.json`／`last.json`、`--node` 合法判斷、檔案模式「所在資料夾叫這個名字就往上取一層」）；用法錯回 1。環境變數照常傳給任務。
   - `aos-exec` 找資料夾目標的 inst 時 `.aos/inst.json` 的 `.aos` 也照它（使用者原話「aos-exec那邊，我覺得可以加上這個AOS_DIRNAME」）；不合法照 aos-exec 的用法錯回 ~~2（碼表不動）~~ 1（待問 15）。
   - 之後 aos 所有程式都照這個變數。

14. **aos-exec 要不要認得頂層 `user`？已裁定：不要**〔使用者方向 2026-10-01，已寫入 spec（commit 前由我補號）〕：原話「aos-exec應該也不需要認得頂層user吧。」全文在 [verdicts 11 篇末](../notes/verdicts/11-tick-as-unit.md#aos-exec-不認得頂層-user待統一更新-spec)。
   - 從 proto5 複製的 lib 撤回「認得頂層 `user`」：回到 proto5 原樣，`user` 當不認得的鍵照 inst 規則忽略、照目前身分跑；沒有 `UserNotGranted`／`UserInvalid`、不因 `user` 回 125。
   - aos-tick 原本交給 `load_obj` 前先拿掉 `user`，因此多餘，拿掉。

15. **結束碼慣例改版、`AOS_DIRNAME` 空字串？已裁定**〔使用者方向 2026-10-01，同日再改，已寫入 spec（commit 前由我補號）〕：全文在 [verdicts 11 篇末「aos 結束碼慣例」](../notes/verdicts/11-tick-as-unit.md#aos-結束碼慣例待統一更新-spec)與[「`AOS_DIRNAME`」](../notes/verdicts/11-tick-as-unit.md#aos_dirname-狀態資料夾的名字待統一更新-spec)。
   - 原話：「結束碼這塊，我覺得不要2了，只要是正常的，不須多做處理的，通通0，0以外就是需要額外處理的東西。」「只有0才是普通結束，正常中斷也改成0。」「1就是通用錯誤，所以沒特別設置結束碼的錯誤都設1。」「如果AOS_DIRNAME是空的，那就從找.aos/inst.json改成找inst.json。」
   - 慣例：0＝預料之中（含正常中斷）、非 0＝要額外處理、1＝通用錯誤；特別指定的碼（inst 的 125／126／127、子程式碼原樣傳出）保留。取代待問 9 的 0／1／2。
   - `aos-tick`：busy、擋板都改回 0（stderr 那一行照印）；現在只回 0／1。
   - `aos-exec`：用法錯（含 argparse、`AOS_DIRNAME` 不合法）2 → 1；125、126／127、子程式碼照舊。
   - `AOS_DIRNAME` 三態：沒設＝`.aos`；設了但空字串＝不用子資料夾（tick 的 `tasks.json`、`tick.lock`、`tick-blocked`、`tick/stop`、`tick/current.json`／`last.json` 都直接在 node 下，檔案模式「往上取一層」不適用；aos-exec 資料夾目標只找 `<目標>/inst.json`）；其他值照舊。取代待問 13「空字串＝`.aos`」。

16. **`AOS_NODE_DIR`、`AOS_TICK_RECORD`、`--node` 改名？已裁定**〔使用者方向 2026-10-01，已寫入 spec（commit 前由我補號）〕：
   - 原話：「AOS_NODE_DIR改成AOS_TICK_CWD，也就是aos-tick在跑的時候，他的cwd的絕對路徑。node這個概念目前還沒到出場的時候，那是後續aos-tick的node模組的事情。AOS_TICK_RECORD應該可以拿掉，反正有AOS_TICK_CWD，就從那邊找就好。」「aos-tick --node改成aos-tick --target，也就是跟daemon和aos-exec一樣。」
   - 給任務的變數剩 `AOS_TICK_CWD`（工作資料夾的絕對路徑：`--target` 指的資料夾，給檔時是檔所在的資料夾）、`AOS_TASK_ID`、`AOS_TASK_INDEX`。任務要看紀錄就從 `$AOS_TICK_CWD/<狀態資料夾>/tick/current.json` 找（狀態資料夾照 `AOS_DIRNAME` 三態，空字串時直接是 `$AOS_TICK_CWD/tick/current.json`）。
   - `--node` 改名 `--target`，不留舊名；語意不變（沒給＝`./`；資料夾要有 `<狀態資料夾>/tasks.json`；給檔就是任務表、所在資料夾當工作資料夾）。
   - 實作自己定的（可改）：stderr `no_node:` 跟著改 `no_target:`；`resolve_node()` 改 `resolve_target()`。aos-exec 的目標是位置參數（`aos-exec [xxx]`），aos-daemon 是設定檔 `insts` 的鍵，都沒有 `--target` 旗標；~~這裡照原話做成 `--target`~~（同日改，見待問 17）。

17. **目標改成位置參數？已裁定**〔使用者 2026-10-01，已寫入 spec（commit 前由我補號）〕：`aos-tick [<目標>]`，跟 aos-exec 一樣；目標可為資料夾~~或任務表檔~~（給檔同日撤回，待問 18），沒給＝`./`；拿掉 `--target` 旗標（剛改的，不留）。其餘語意全不變，stderr `no_target:` 保留。
   - 實作自己定的（可改）：`-h`／`--help` 照舊印用法回 0；其他 `-` 開頭的參數（含 `--target`）、目標多於一個都算用法錯回 1（stderr `usage:`）。目標名字本身以 `-` 開頭時要寫成 `./-xxx`。

18. **目標給檔、任務表頂層預設、`modules`？已裁定**〔使用者 2026-10-01，已寫入 spec（commit 前由我補號）〕：
   - 拿掉「目標給檔案就當任務表」：目標只能是資料夾（沒給＝`./`），任務表只有 `<目標>/<狀態資料夾>/tasks.json`；給檔＝用法錯（stderr `usage:`、回 1）；不存在 `no_target:`、沒表 `no_tasks:` 照舊。取代待問 10、16、17 裡「給檔」的部分。
   - 頂層預設，原話：「好，就這個。tick執行時後他自己有自己的cwd，這個頂層key cwd不會影響tick自己的cwd，但是其相對路徑由tick的cwd開始算。」「展開指示詞的時候不整份解好，而是只解到tasks。」細節（七個欄位當預設、淺層合併、讀表時解到 `tasks` 與每項一層、跑到時合併再照 inst 展開、`$ref:""` 指合併後那一項、合併後要有 `argv`）見步驟 4 的「四改」。
   - `modules`，原話：「tasks.json頂層也應該有modules。」比照 daemon 設定檔，放 tick 模組的設定；目前沒有模組，核心照收不理，~~讀表時只解一層、內部不展開~~（使用者裁定 2026-10-01 改成讀表時整個展開，展開失敗＝`bad_table`，見 [verdicts 11 第三批](../notes/verdicts/11-tick-as-unit.md#2026-10-01-第三批tasksjson-的-metainfo-與-modules)）、型別不查，不當預設合併。
   - 實作自己定的（可改）：頂層 `_metainfo`、`id`、`kind`、`modules` 以外的陌生鍵讀表時不解（解壞了也不會 `bad_table`）；某項解一層後是選項物件（`$opt`）時極簡檢查不擋，跑到時 `load_obj` 自然丟錯。
