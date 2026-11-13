# kernel — 收請求、管資源與排程的範本（請求寄到哪，那裡對寄件人就是 kernel）

← [proto8](../README.md)｜用它們的 agent 範本：[templates](../templates/README.md)｜概念：[CONCEPTS kernel](../docs/CONCEPTS/04-kernel.md)、[NORMS kernel](../docs/NORMS/09-kernel.md)

這個資料夾放的是可以直接抄去用的 kernel 範本。掛 proc 的請求由「通用 kernel 的站」（下面簡稱**框架站**）處理，問腦的請求由 llm kernel 處理。

| 範本 | 是什麼 |
|---|---|
| `daemon-kernel/` | 一台 daemon，它自己的身體就是框架站：請求先過站的規則，放行的才轉寄進這台 daemon 的 ctl 信箱 |
| `procs-kernel/` | 同一支框架站，改成掛在一台普通 daemon 底下的一個 loop proc |
| `llm-kernel/` | 問腦的那台：agent 寄請求信、它挑能力包（`smart-high`、`stupid-fast`…）問模型、寄回信；自己一台 daemon |
| [`llm-team/`](llm-team/) | 隊 kernel：能力包寫下一層 stack 與代號，經 llm_forward 轉交；自己一台 daemon |

## 框架站是什麼

框架站是一支 Python 資料夾程式，在 [lib/aos/kernel](../lib/aos/kernel/README.md)。它每跑一次只做一輪：收信、照設定檔 `kernel.json` 判斷、放行的轉寄給下一站、不放行的回一封拒信、沒格的排隊。它自己不常駐，要有人一次次叫它（daemon 每一圈叫一次，或一個 loop proc 每一拍叫一次）。

框架只是一包方便的零件，不是概念。自己手寫一支收信的程式，一樣算 kernel。

| 零件 | 做什麼 | 在 `kernel.json` 怎麼開 |
|---|---|---|
| 收信 | 對外收件箱固定是站的 `$AOS_STACK/requests/`，每輪認領、逐封看 | 不用開 |
| 規則 | 名字白名單、同時最多幾個在跑、寄件人給的期限 | `allowed`、`max_running` |
| 下一站 | 放行的信原樣轉寄到哪個信箱 | `next`；沒寫看環境的 `AOS_KERNEL`，再沒有才 `AOS_DAEMON` |
| 數量另指 | 「幾個在跑」去哪一台 daemon 的表上數 | `count_daemon` |
| 回信 | 下游的回信直接回給寄件人，或先回到我這站再代回 | `reply_via_me` |
| 排隊 | 沒格時先來先掛地排，或立刻拒 | `queue` |
| hook | 在三個時機插自己的程式：判之前、判之後、代回回信之前 | `hooks` |

## `kernel.json` 的鍵

設定檔每一輪都重讀，改了下一輪生效。內容可以寫 `{"$env": …, "$path": …}` 這類指示詞。`next`、`count_daemon` 與 hook 的 `handler` 寫相對路徑時，從 `kernel.json` 所在的資料夾算。不認得的鍵不管。

| 鍵 | 意思 | 沒寫時 |
|---|---|---|
| `next` | 下一站的信箱資料夾 | 站的環境有 `AOS_KERNEL`、又不是指到自己＝它；否則 `$AOS_DAEMON` 那台的 ctl 信箱 |
| `count_daemon` | 去哪台 daemon 的表上數在跑的（值是那台的 stack 資料夾） | 下一站是 `$AOS_DAEMON` 那台時就是 `$AOS_DAEMON`；其他情形沒有預設 |
| `allowed` | `procs_added` 的名字白名單 | 不限 |
| `max_running` | 同時最多幾個在跑（非負整數） | 不限 |
| `queue` | 沒格時排隊（`true`）還是立刻拒（`false`） | `false` |
| `keep_ordered` | 有序信是否照有序轉寄 | `false` |
| `reply_via_me` | 下游的回信是否先回到我這站、再由我代回 | `false` |
| `hooks` | `{名字: 一格}`，每格寫 `event` 與 `handler` | 沒有 hook |

最小的設定是 `{}`：什麼都不管，全部原樣轉給下一站（啥都不管也是一種管理）。寫了 `next` 又寫了 `max_running` 的話，一定要寫 `count_daemon`，不然報 `CfgBad`（站不去猜下一站是哪一台）；下一站取自 `AOS_KERNEL` 時也一樣。

### 下一站怎麼找：`next`、`AOS_KERNEL`、`AOS_DAEMON` 三段

`AOS_KERNEL` 是要掛 proc 時沒特別指定就用的通用目標：一般 proc 的請求寄到 `$AOS_KERNEL`。站自己放行之後信要轉去哪，照三段找：

1. `kernel.json` 寫了 `next`：用它。它指到自己的 `requests/`＝設定錯（`CfgBad`），明寫的值照字面、不跳過。
2. 沒寫 `next`、站的環境有 `AOS_KERNEL`：指到自己的 `requests/` 就跳過這一段；指到別的信箱就轉去那裡，不需要 `AOS_DAEMON`。
3. 前兩段都沒有：`$AOS_DAEMON` 那台的 ctl 信箱。

三段都用不上＝`DaemonMissing`。

整棵樹 export `AOS_KERNEL` 時，沒寫 `next` 的站也會繼承到它：指到自己才跳過，指到別站就把信轉給那一站。不想要就在起那一站的殼 `unset AOS_KERNEL`，或明寫 `next`。

使用者 11-13 原話：

> 「Hmmm，好啦，next也可以。只是說，我會覺得AOS_KERNEL他就是在有需要掛一個aos proc的時候，就使用的一個目標，一個通用的，基礎的目標。好比所有C語言程式使用syscall的時候，只要沒有特別指定，不然就是走linux kernel那個記憶體位置。啊如果有需要其他目標...那就自己找方法指定」

所以框架站設定檔的 `next` 留著。三段的順序是使用者 11-13 待裁頁的裁定（`kf-next:B*（備註：如果覺得麻煩，那就直接報錯算了）`，[回覆檔](../thinking/2026-11/13/decide_20261113_wu-r2.reply.txt)、[開工紀錄](../thinking/2026-11/13/kernel-framework-開工.md)）。

## 三種擺法

三種都只是範例，不是只有這三種。

| 擺法 | 怎麼掛 | 寄件人的 `AOS_KERNEL` 指哪 | 範本 |
|---|---|---|---|
| daemon 的身體 | `daemon.json` 的 `exec` 寫框架站，daemon 每一圈跑一輪 | `<那台 daemon 的 stack>/requests` | `daemon-kernel/` |
| daemon 底下一個 loop proc | `loop.json` 的 `exec` 寫框架站，掛到一台普通 daemon 上 | `<那個 proc 的 stack>/requests` | `procs-kernel/` |
| 鏈的中間站 | 上面兩種任一種，`kernel.json` 多寫 `next` 指到別的站（或站的環境 `AOS_KERNEL` 指到別的站） | 同上 | 沒有現成範本，例子在 [02](docs/02-kernel-modes.md) |

手跑的指令、鏈的例子、hook 的例子、已知限制都在 [02-kernel-modes](docs/02-kernel-modes.md)。

## 分檔目錄

| 分檔 | 涵蓋的段 |
|---|---|
| [01-llm-kernel](docs/01-llm-kernel.md) | llm kernel 範本 llm-kernel（問腦＝寄信給它、收回信；自己一台 daemon；能力包、`aos-llm ls`） |
| [02-kernel-modes](docs/02-kernel-modes.md) | kernel 是什麼（資源管理＋排程、從寄件人看）；框架站怎麼判、怎麼排隊、怎麼回信；三種擺法與手跑指令；鏈與 hook 的例子；`AOS_KERNEL`、誰能繞過 kernel（靠 Linux 權限）；已知限制 |
| [03-feat-proto](docs/03-feat-proto.md) | 新功能原型的假腦劇本：agent 給自己加工具、能力包與排程、agent 生 agent、資源份額 |
