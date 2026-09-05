> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# land-rules：一塊地看得到哪裡、怎麼死、怎麼搬

← [ideas](README.md)｜前篇 [daemon-clocks](daemon-clocks.md)｜[exec-run-async-time](exec-run-async-time.md)｜[play-watchlist](play-watchlist.md)｜[fuse-host-doorman](fuse-host-doorman.md)｜[top-to-bottom/01](top-to-bottom/01-top.md)

本篇是 [daemon-clocks](daemon-clocks.md) 的續篇。前篇把 daemon 說成所有時鐘的總管；本篇接著
記一塊地的可見範圍、生死，以及整個資料夾搬到別處算什麼。

**本檔無明說裁決。** 使用者的話分成**使用者定義／使用者傾向（未明說裁決）**；以下 AI
觀察也都可以否決。

## 使用者原話（2026-09-04）

> 兩塊地的互相影響這塊：一塊地只能看到自己地盤上的東西，若要看到../，那就只能掛載或symlink。生死這塊，一塊地的消失那就是資料夾被刪除，daemon那邊會定期檢索pid是否還在，然後清除登記，或是消失前通知daemon。然後若一塊地移動了地方，那等於是這塊地被刪除了，因為這塊地的所在(檔案路徑)就是他的唯一標示符，當然，這可以透過symlink來處理。(幫我考慮一下，類似git mv那樣，給daemon發訊息通知說某塊地移動了位置，這樣好不好，會影響到哪些、是不是真的需要)。先不考慮agent，我們還在打基礎。觀察者...？我不太懂

**使用者定義／傾向（未明說裁決）**：預設只看自己的地，掛載／symlink 才開洞；刪資料夾
就是死，路徑是唯一標示符，所以搬家也是死；消失前可通知 daemon，定期查 pid 則是保底。

**使用者看完搬家分析後回覆（2026-09-04）**：

> 那就先不管git mv這套。

## AI 觀察（非裁決，可否決）

### a. 可見範圍：list 裡有的，才是這塊地看得到的

資料夾＝list；list 的元素，就是這塊地看得到的全部。symlink 沒有另開一套權限系統，它只是
讓 list 多一個「指到外面」的元素。掛載也是同一種明白開洞。

「子看得到什麼」不是另一套權限系統，而是**父開子時決定放什麼進去**，包括 symlink。這正是
operative：**廚師拿到什麼食材，看上面遞了什麼。** `G03` 的方向是**預設封閉，開洞要明講。**

### b. 死：通知是快路，巡邏是保底

通知 daemon 是快路；daemon 定期查是保底。

Linux 有一個坑：**資料夾被刪掉，裡面的行程不會跟著死。** 行程可以帶著一個已不存在的 cwd
繼續跑。因此 daemon 判死要同時看兩樣：**pid 還在嗎、登記的路徑還在嗎。** 路徑不在而 pid
還活著，就是孤魂；daemon 要把它停掉，再清登記。

### c. 搬家就是死

搬家維持「死＋生」：現在不做 `git mv` 式通知，真要搬先停時鐘；symlink 只當轉寄地址，不當
第二個身分。完整分析與使用者原話移至 [land-rules-move](land-rules-move.md)。

### d. agent 先不談

使用者已說先不考慮 agent；這篇只把地、路徑、行程與 daemon 的基礎規則站穩。

### e. 「觀察者」不用另立概念

AI 原先說的觀察者，只是**站在旁邊記帳的人**：誰看得到所有地的讀寫，誰記下發生了什麼。
這不是新角色，就是 daemon；若將來走 FUSE，就是那個門房。daemon 已登記所有時鐘、定期巡邏，
記帳自然也歸它。**「觀察者」這條劃掉。**

## 現有 aos 對照

| 模型名稱 | 程式裡的名字 | 合不合／`mv` 後會不會壞 |
|---|---|---|
| 地的路徑 | `core/loop/src/layout.cpp`：`layout_of()`／`find_folder()` 以 realpath 建 `Layout::folder` | **記憶體裡是絕對路徑**：新命令會重算；舊 loop 抓舊字串，搬後仍找舊 `.aos/`，甚至可能重建舊版面 |
| `state.json` | `core/loop/src/state.cpp` `write_state()`；`core/wire/src/state.cpp` `to_json_text(State)` | **不存地的目標路徑**，只有 turn、phase、running、agents；但 running.argv0 可碰巧是絕對執行檔路徑。檔案會跟著搬，舊 loop 不會更新新位置 |
| `series.json` | `core/loop`、`core/wire`、`core/tick` 都沒有讀寫函式 | **尚未實作**，今天 `.aos/` 沒這份檔，沒有可壞的既有路徑 |
| `run.pid` | `core/loop/src/run.cpp` `RunPidFile::write()`／`aos_run_cli_main()`；`core/loop/src/stop_cli.cpp` `aos_stop_cli_main()` | **只寫 pid，檔的位置是索引**：新位置可 stop；舊 loop 析構刪舊路徑，會留下新位置的 stale pid |
| `aos deliver` | `core/loop/src/deliver_cli.cpp` `aos_deliver_cli_main()`；`core/loop/src/deliver.cpp` `deliver()` | **folder 路徑指目標，inst 無 target**：舊信跟著搬；搬後舊路徑失敗或投到重建的舊地。`cwd` 通常相對地解讀，也容許絕對值 |
| `aos contact` 的目標 | `core/tool/src/contact_cli.cpp` 的 `add()` 把輸入交給 `add_contact()`；`core/tool/src/contacts.cpp` 的 `write_contacts()` 在 `.aos/contacts.json` 原樣存 name＋folder | **名字查表、folder 才指路**：相對路徑以寄件地為基準，絕對路徑也照存。目標搬後，舊 contact 會壞；若父與子一起搬、相對關係不變，仍可用 |
| `aos say --to` | `core/agent/src/run_top.cpp` `say_dispatch()` 合成目標；`core/agent/src/init.cpp` `say()` 寫收件匣 | **contact 名字→folder 路徑→agent 名字**：搬家是否壞同 contact；已投信件跟目標一起搬不壞 |
| say 信裡的寄件者 | `core/agent/src/user.cpp` 的 `say_from()` 取 `AOS_FOLDER`／目前世界的絕對路徑；`core/agent/src/store.cpp` 的 `message_body()` 寫成 `from: <絕對路徑>` | **確實在 `.aos/` 存了絕對路徑**：寄件地搬家後，舊信的 from 過期；目前只是信件文字，不是 contact 路由鍵 |
| tick 投遞 | `core/tick/src/tick.cpp` `run_tick()`／`say_message()`；`core/tick/src/init.cpp` `heartbeat_init()` | **目標是目前 Layout，不另存目標**：搬後重開可用；舊 loop 仍抓舊 Layout。排程 argv 可由使用者放絕對路徑 |

另有一個不是「地的身分」但確實是絕對路徑的例子：`core/agent/src/init.cpp` 的 `initialize()`
會把 `aos_program_path()` 找到的 aos 執行檔絕對路徑寫進 `.aos/every/agent-<name>.json`。搬世界不
影響它；搬或刪 aos 執行檔才會壞。

## 相關清單

- `G03`（隔離／作用域）：預設只看自己的 list；掛載或 symlink 是明說的洞。
- `G06`（行程抽象）：路徑是地的 id；死要能列舉、終止並清登記。
- `G07`（程式／行程分界）：資料夾還在不等於時鐘正在走，pid 與路徑要分開看。
- `G10`（排程）：daemon 定期巡邏、清孤魂，是跨資料夾排程器的家務。
- `G14`（載入器）：父開子時遞哪些元素，決定子拿到的環境。
- `G19`（資源不可靠與不確定）：漏通知、突然刪除、stale pid 都靠定期對帳收斂。
