# kernel — 收請求、管資源與排程的範本（請求寄到哪，那裡對寄件人就是 kernel）

← [proto8](../../../README.md)｜用它們的 agent 範本：[templates](../../README.md)｜概念：[CONCEPTS kernel](../../docs/CONCEPTS/04-kernel.md)、[NORMS kernel](../../docs/NORMS/09-kernel.md)

這個資料夾放的是可以直接抄去用的 kernel 範本。掛 proc 的請求由「通用 kernel 的站」（下面簡稱**框架站**）處理，問腦的請求由 llm kernel 處理。

| 範本 | 是什麼 |
|---|---|
| `daemon-kernel/` | 一台 daemon，它自己的身體就是框架站：請求先過站的規則，放行的才轉寄進這台 daemon 的 ctl 信箱 |
| `procs-kernel/` | 同一支框架站，改成掛在一台普通 daemon 底下的一個 loop proc |
| `llm-kernel/` | 問腦的那台：agent 寄請求信、它挑能力包（`smart-high`、`stupid-fast`…）問模型、寄回信；自己一台 daemon，主線是掛成板子上的一列（見下面「初始 kernel」） |
| [`llm-team/`](llm-team/) | 隊 kernel：能力包寫下一層 stack 與代號，經 llm_forward 轉交；自己一台 daemon |
| [`kernel-python/`](kernel-python/README.md) | 用一支 `kernel.py` 寫的 kernel 定義（`from aos.py.kernel import defs`；使用者 11-20 待裁第 9 題、11-21「編譯的kernel入口那塊可以派」，線 top-1121-kdefs）：`defs.Kernel("說明", knobs={…}, hooks=[…], program="kernel"／"kernel_llm", body=defs.loop()／defs.daemon())`，`python3 kernel.py --compile` 編譯出上面幾種的樣子（`_entry`、`loop.json` 或 `daemon.json`、`kernel.json`、`interfaces.json`、宣告 `kernel_hooks.json`、被勾清單 `kernel_hookeds.json`）；`@fn.hook` 的函數抽成 `fn/<名>.py`，跟 `agent.py` 同一套 |

## 初始 kernel：買了板子之後灌什麼

使用者 11-20：「兩件+最小核心。然後弄一串可選的，比如需要額外依賴的權限那塊，還有一堆比較麻煩的東西。」（八題與答案：[aos-init-kernel-1120](../../thinking/2026-11/20/aos-init-kernel-1120/06-使用者已答.md)）

**初始 kernel＝最小核心＋llm 件＋權限件，另有一串可選件。** 起手範本 [start-api](../start-api/README.md) 就是照這個擺的。

| 塊 | 是什麼 | 今天在哪 | 可不可選 |
|---|---|---|---|
| 最小核心 | 板子本身（daemon：表、ctl 信箱、limits、自動重起）、身分（信封的 `sender`＝寄件人自己的 stack，自報不驗）、信箱（`aos-post`）、時鐘 `_clock`、清道夫 `_sweeper` | 起根就有：[daemon-root](../daemon-root/README.md) | 一定有。鐘與清道夫也算核心（使用者 11-20「算核心」），不是可以拿掉的件 |
| llm 件 | llm kernel：排隊、格數、能力包、帳本、**問腦的額度**（`budget`，使用者 11-20「留在 llm 件」） | `llm-kernel/`，掛成板子上的一列 `llm`（使用者 11-20「掛同一塊板子」）；agent 從 `AOS_LLM_KERNEL` 找它 | 可選，但**只對不會想的 proc 成立**：agent-fsm、agent-python 只會寄信問 llm kernel，沒裝就在第一次問腦時 `LlmKernelMissing` 停下（使用者 11-20「不能，維持現狀」） |
| 權限件 | 決定准不准開 proc、同時幾個、上限夾、`users`→`sub:N` | 一台框架站（`procs-kernel/` 掛成一列；或 `daemon-kernel/`、`kernel_gate`），寄件人把 `AOS_KERNEL` 設成它的 `requests/` | 可選、預設不開；start-api 帶一份沒掛的 `perm/`。guard、sandbox 不算權限件（使用者 11-20「不算」），留在 agent 與工具那邊 |
| 一串可選件 | 使用者舉了「需要額外依賴的權限那塊，還有一堆比較麻煩的東西」 | 待定 | 有哪些件、怎麼裝：待定 |

- **沒裝權限件時**，擋得住的只剩 Linux 的檔案權限，與 daemon 本體的 limits、`sub:N`（表上那列寫了才套）；daemon 自己來者不拒。
- **權限件是給守規矩的人用的規矩，不是牆；牆是換 Linux 帳號**（使用者 11-20「明寫」）。`AOS_KERNEL` 是寄件人自己的環境變數，拿掉它、直接寫 daemon 的 ctl 信箱就繞過站；`aos-daemon-ctl` 也一律直寄 daemon。同一個 Linux 帳號底下擋不住（[02「誰能繞過 kernel」](docs/02-kernel-modes.md#誰能繞過-kernel靠-linux-權限)）。
- **開了權限件就要知道**（基底體檢 P4，使用者 11-19 選「維持現狀，只寫明」）：寄件人的「我是誰」、讀自己信箱、設鬧鐘都先問那一站，站 3 秒不回＝全部 `KernelFailed`。
- **`AOS_KERNEL` 不要寫在根的 `.env`**：整塊板子都會繼承，llm kernel 也會把問腦的 proc 經那一站掛到根上、它自己的表上看不到（11-20 實跑：問腦失敗）。寫在要經過站的那隻 agent 的 `.env`（start-api 的 `agents/ann/.env` 有一行註解好的）。
- 鐘、清道夫「算核心」只是說法：今天的程式照樣讓人從 `daemon.json` 刪掉那兩列，沒有擋。

## 框架站是什麼

框架站是一支 Python 資料夾程式，在 [py/tools/aos/kernel](../../py/tools/aos/kernel/README.md)。它每跑一次只做一輪：收信、照設定檔 `kernel.json` 判斷、放行的轉寄給下一站、不放行的回一封拒信、沒格的排隊。它自己不常駐，要有人一次次叫它（daemon 每一圈叫一次，或一個 loop proc 每一拍叫一次）。

框架只是一包方便的零件，不是概念。自己手寫一支收信的程式，一樣算 kernel。

框架分兩層（使用者 11-13：「我們做的是框架，最底層就是最簡單的hook+判斷。你說的上限這塊，是在框架之上的通用基礎包」）：骨架只管收信、叫 hook、照判決放行／拒／留著、轉寄與代回；白名單、數量上限、排隊、期限是蓋在骨架上的「掛 proc 那一包」的做法。下表「規則」「數量另指」「排隊」三列屬於那一包。

| 零件 | 做什麼 | 在 `kernel.json` 怎麼開 |
|---|---|---|
| 收信 | 對外收件箱固定是站的 `$AOS_STACK/requests/`，每輪認領、逐封看 | 不用開 |
| 規則 | 名字白名單、同時最多幾個在跑、寄件人給的期限 | `allowed`、`max_running` |
| 下一站 | 放行的信原樣轉寄到哪個信箱 | `next`；沒寫看環境的 `AOS_KERNEL`，再沒有才 `AOS_DAEMON`。`next` 只有一個；照規則分流用 `after_verdict` hook 替單封信指定 |
| 數量另指 | 「幾個在跑」去哪一台 daemon 的表上數 | `count_daemon` |
| 回信 | 下游的回信直接回給寄件人，或先回到我這站再代回 | `reply_via_me` |
| 排隊 | 沒格時先來先掛地排，或立刻拒 | `queue` |
| hook | 在三個時機插自己的程式：判之前、判之後、代回回信之前 | 不在 `kernel.json`：同夾 `interfaces.json` 最外層 `hookeds` 指的 `kernel_hookeds.json` |
| 留著等表態 | `after_verdict` hook 回 `{"verdict": "hold"}`：信留在站裡，等有人把 pass／refuse 寫進 `decisions/<信名>.json`，站再照平常的路轉寄或回拒信 | 寫在 hook 裡；agent 當 kernel 用工具 `kernel_gate`（[02](docs/02-kernel-modes.md#agent-當-kernel請求先留著等它表態)） |

## `kernel.json` 的鍵

設定檔每一輪都重讀，改了下一輪生效。內容可以寫 `{"$env": …, "$path": …}` 這類指示詞。`next`、`count_daemon` 寫相對路徑時，從 `kernel.json` 所在的資料夾算（hook 的 `handler` 從被勾清單所在的資料夾算，範本裡是同一夾）。不認得的鍵不管。

| 鍵 | 意思 | 沒寫時 |
|---|---|---|
| `next` | 下一站的信箱資料夾 | 站的環境有 `AOS_KERNEL`、又不是指到自己＝它；否則 `$AOS_DAEMON` 那台的 ctl 信箱 |
| `count_daemon` | 去哪台 daemon 的表上數在跑的（值是那台的 stack 資料夾） | 下一站是 `$AOS_DAEMON` 那台時就是 `$AOS_DAEMON`；其他情形沒有預設 |
| `allowed` | `procs_added` 的名字白名單 | 不限 |
| `max_running` | 同時最多幾個在跑（非負整數） | 不限 |
| `queue` | 沒格時排隊（`true`）還是立刻拒（`false`） | `false` |
| `keep_ordered` | 有序信是否照有序轉寄 | `false` |
| `reply_via_me` | 下游的回信是否先回到我這站、再由我代回 | `false` |

最小的設定是 `{}`：什麼都不管，全部原樣轉給下一站（啥都不管也是一種管理）。寫了 `next` 又寫了 `max_running` 的話，一定要寫 `count_daemon`，不然報 `CfgBad`（站不去猜下一站是哪一台）；下一站取自 `AOS_KERNEL` 時也一樣。

### 下一站怎麼找：`next`、`AOS_KERNEL`、`AOS_DAEMON` 三段

`AOS_KERNEL` 是要掛 proc 時沒特別指定就用的通用目標：一般 proc 的請求寄到 `$AOS_KERNEL`。站自己放行之後信要轉去哪，照三段找：

1. `kernel.json` 寫了 `next`：用它。它指到自己的 `requests/`＝設定錯（`CfgBad`），明寫的值照字面、不跳過。
2. 沒寫 `next`、站的環境有 `AOS_KERNEL`：指到自己的 `requests/` 就跳過這一段；指到別的信箱就轉去那裡，不需要 `AOS_DAEMON`。
3. 前兩段都沒有：`$AOS_DAEMON` 那台的 ctl 信箱。

三段都用不上＝`DaemonMissing`。

`next` 只能寫一個信箱。要照規則把不同的信轉給不同的下一站（一封信只去一處），分流規則寫在 hook 裡（使用者 11-13：「按照規則分流吧。就用hook」）：`after_verdict` hook 回 `{"next": "<信箱的絕對路徑>"}`，這一封就寄去那裡；沒回的照上面三段。例子在 [02「分流的例子」](docs/02-kernel-modes.md#分流的例子照規則把信分到兩個下一站)，限制在 [py/tools/aos/kernel README「分流」](../../py/tools/aos/kernel/README.md#分流hook-替這一封指定下一站)。

整棵樹 export `AOS_KERNEL` 時，沒寫 `next` 的站也會繼承到它：指到自己才跳過，指到別站就把信轉給那一站。不想要就在起那一站的殼 `unset AOS_KERNEL`，或明寫 `next`。

使用者 11-13 原話：

> 「Hmmm，好啦，next也可以。只是說，我會覺得AOS_KERNEL他就是在有需要掛一個aos proc的時候，就使用的一個目標，一個通用的，基礎的目標。好比所有C語言程式使用syscall的時候，只要沒有特別指定，不然就是走linux kernel那個記憶體位置。啊如果有需要其他目標...那就自己找方法指定」

所以框架站設定檔的 `next` 留著。三段的順序是使用者 11-13 待裁頁的裁定（`kf-next:B*（備註：如果覺得麻煩，那就直接報錯算了）`，[回覆檔](../../thinking/2026-11/13/decide_20261113_wu-r2.reply.txt)、[開工紀錄](../../thinking/2026-11/13/kernel-framework-開工.md)）。

## 三種擺法

三種都只是範例，不是只有這三種。

| 擺法 | 怎麼掛 | 寄件人的 `AOS_KERNEL` 指哪 | 範本 |
|---|---|---|---|
| daemon 的身體 | `daemon.json` 的 `exec` 寫框架站，daemon 每一圈跑一輪 | `<那台 daemon 的 stack>/requests` | `daemon-kernel/` |
| daemon 底下一個 loop proc | `loop.json` 的 `exec` 寫框架站，掛到一台普通 daemon 上 | `<那個 proc 的 stack>/requests` | `procs-kernel/` |
| 鏈的中間站 | 上面兩種任一種，`kernel.json` 多寫 `next` 指到別的站（或站的環境 `AOS_KERNEL` 指到別的站） | 同上 | 沒有現成範本，例子在 [02](docs/02-kernel-modes.md) |

**每個 kernel 定義夾的 hook 檔**（11-21 新格式，線 top-1121-hooknew）：`interfaces.json` 最外層寫 `"hooks"`（hook 點的宣告：`kernel_hooks.json`＝kernel 三點，正本在 [py/tools/aos/kernel](../../py/tools/aos/kernel/kernel_hooks.json)、每夾一份抄本；loop 身體另加一項指示詞指 aos-loop 的 [loop_hooks.json](../../py/aos/apps/hook/loop_hooks.json)；只是參考，程式不讀）與 `"hookeds": "kernel_hookeds.json"`（被勾清單，kernel 三點與 loop 四點的格都放這一份，kernel 程式每輪照它讀；出廠是空的），另有 `"kernel": {}`（這次裡面沒東西）。**loop 身體（`procs-kernel/`、`kernel-python/`）每一輪的前後也能掛 hook**（使用者 11-20 待裁第 7 題選「接：改 procs-kernel 範本的 loop.json」）：`loop.json` 的 `on_start`／`on_stop` 經 `aos-hook fire -q --stop-on-nonzero --def $AOS_CD` 發 `after_start`／`after_stop`；`before_run`（每一輪之前）／`after_run`（每一輪之後）只在編譯時有 hook 掛才接，手寫範本預設不接（要掛就照 `on_start` 的樣子加 `on_before_run`／`on_after_run` 再重起這一站）。handler 的碼原樣交給 aos-loop：`before_run` 退 10＝這一輪不跑；其他非 0（四個點都一樣）＝站停下。代價：站每次起、停各多起一支 `aos-hook`（約 36 毫秒）。`daemon-kernel/` 是 daemon 的身體，aos-daemon 不收 `on_before_run`／`on_after_run`，沒接。

`daemon-kernel/`、`procs-kernel/` 兩份範本原樣只能當**最後一站**用：它們的 `kernel.json` 寫了 `max_running`、沒寫 `next` 與 `count_daemon`，所以站的環境裡 `AOS_KERNEL` 要嘛沒設、要嘛指到這一站自己的 `requests/`（跳過，轉給 `$AOS_DAEMON` 那台、也在那台的表上數）。繼承到指向**別站**的 `AOS_KERNEL` 時，每一輪都是 `CfgBad`（站不猜要去哪台數）。要改當鏈的中間站，自己在 `kernel.json` 補上 `count_daemon`（或寫 `next` 連同 `count_daemon`），或在起那一站的殼 `unset AOS_KERNEL`。範本沒有預先寫 `count_daemon`：寫死某一台就等於替你猜了要數哪台。

手跑的指令、鏈的例子、hook 的例子、已知限制都在 [02-kernel-modes](docs/02-kernel-modes.md)。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-llm-kernel](docs/01-llm-kernel.md) | llm kernel 範本 llm-kernel（問腦＝寄信給它、收回信；自己一台 daemon；能力包、`aos-llm ls`） |
| [02-kernel-modes](docs/02-kernel-modes.md) | kernel 是什麼（資源管理＋排程、從寄件人看）；框架站怎麼判、怎麼排隊、怎麼回信；三種擺法與手跑指令；鏈與 hook 的例子；agent 當 kernel（留著等表態、`kernel_gate`）；`AOS_KERNEL`、誰能繞過 kernel（靠 Linux 權限）；已知限制 |
| [03-feat-proto](docs/03-feat-proto.md) | 新功能原型的假腦劇本：agent 給自己加工具、能力包與排程、agent 生 agent、資源份額 |
