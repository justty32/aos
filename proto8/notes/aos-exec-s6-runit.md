# aos-exec 能從 s6／runit 那一族借什麼、叫什麼

← [notes](README.md)｜[proto8](../README.md)｜起點：[s6-runit 對照](s6-runit.md)（監管、重啟、日誌在那份，這份不重講）｜2026-10-22，AI 寫

**AI 寫的參考，不算數**：條文以 [CONCEPTS](../docs/CONCEPTS.md)、[NORMS](../docs/NORMS.md) 為準，要用哪一點由使用者決定（鐵律 5）。使用者 10-22 的題目：「讓fable去看看，s6/runit這些東西，是否有aos-exec能借用、參考，乃至於直接呼叫他們的地方。」所以這份只盯 **aos-exec 這一支**（入口怎麼寫、環境怎麼設、開跑前能接什麼）。

s6／runit 的事實查自官方文件（skarnet.org、smarden.org）與 Debian 套件清單，每點附連結。`s6`、`execline`、`runit`、`daemontools` 四個套件 Ubuntu 24.04 apt 都有（universe）；nosh、perp 不在 Debian／Ubuntu。例子照文件與 aos-exec 的規則推，**沒有實跑**，要驗的三條在 [04 § 4](aos-exec-s6-runit/04-不適合-衝突-方向題-套件.md)。

<!-- wf-nav -->
## 分檔

| 分檔 | 涵蓋 |
|---|---|
| [01-直接呼叫-環境與鎖](aos-exec-s6-runit/01-直接呼叫-環境與鎖.md) | (1) 現在就能接上去的：envdir 一族（祕密一個檔）、setlock 一族（一個工作區只跑一隻）、execlineb 當入口檔 |
| [02-直接呼叫-資源fd使用者](aos-exec-s6-runit/02-直接呼叫-資源fd使用者.md) | (1) 續：softlimit 一族（記憶體／CPU 上限）、redirfd／fdmove／umask、setuidgid（要放在 aos-exec **外面**）、setsid／pgrphack（只能最外層）、chpst 總表 |
| [03-借形狀](aos-exec-s6-runit/03-借形狀.md) | (2) 不裝對方、照抄形狀：加旗標前的判準、envdir 的「空檔＝拿掉」、envfile vs `.env`、鎖與限制當單子 key、結束碼 100／111／126／127、servicedir「一個 key 一個檔」 |
| [04-不適合-衝突-方向題-套件](aos-exec-s6-runit/04-不適合-衝突-方向題-套件.md) | (3) 只能參考的（要監工在上面才有用的那些）、跟原則的衝突（含兩個實際的坑）、方向題與使用者的回覆、套件名與可得性表 |

每一項都標：對應哪條原則（C-／N-）、是「現在就能用」「要改規範」還是「方向題」。

## 一句話的底

aos-exec 開跑那一步是 **exec**（N-59 第 5 件），而 s6／runit／daemontools 那一族的小工具全是「改一下行程狀態，再 exec 成 argv 剩下的部分」（chain loading，[execline grammar](https://skarnet.org/software/execline/grammar.html)）。兩邊天生接得上：**aos-exec 的 argv 陣列入口、單子的 `argv`、`.env`，三個地方都能把它們排在前面**，不用 `sh -c`、不用改 aos 一行。它們能做的事（換使用者、上限、拿鎖、設環境、動 fd）**都不必長進 aos-exec 的旗標表**。

## 最值得的三個「直接呼叫」

1. **`s6-envdir secrets …`（或 `chpst -e`、daemontools `envdir`）放 API key**：一個變數一個檔、各自 `chmod 600`，正是 C-64「用檔案借 Linux 權限」；`.env` 一份檔做不到分權限。入口寫 `["s6-envdir", "secrets", "aos-loop", "loop.json"]` 就好（[01 § 1](aos-exec-s6-runit/01-直接呼叫-環境與鎖.md)）。現在就能用。
2. **`s6-setlock -n $AOS_STACK/lock …`（或 `chpst -L`、`setlock -n`）讓同一個工作區同時只跑一隻**：aos 沒有鎖的概念（P-18 兩隻共用 stack 會互寫、aos-tick「同時 tick 不管」），鎖檔放 stack 就跟「同一個 agent 可同時被兩個工作區跑」不打架（[01 § 2](aos-exec-s6-runit/01-直接呼叫-環境與鎖.md)）。現在就能用。
3. **`s6-softlimit -m … -t …`（或 `chpst -m`）放在 think 格的 `argv` 前面**：單子只有 `timeout_ms`（牆上時間），記憶體與 CPU 上限交給它，不加 key（[02 § 1](aos-exec-s6-runit/02-直接呼叫-資源fd使用者.md)）。現在就能用。

## 最值得的三個「借形狀」

1. **加旗標前的判準**（N-58「以後會加旗標」）：新旗標若只是「改行程狀態再 exec」，就該是鏈上的一支小程式，不是 aos-exec 的旗標；aos-exec 的旗標只留「找入口要用的」（[03 § 1](aos-exec-s6-runit/03-借形狀.md)）。方向題，未決。
2. **envdir 的「空檔＝拿掉變數」**：`.env` 沒有寫法能 unset，也不補（使用者 10-22：「然後我會覺得拿掉變數這個功能沒必要。」）；真要拿掉就在鏈上接 `s6-envdir` 放空檔（[03 § 2](aos-exec-s6-runit/03-借形狀.md)）。
3. **servicedir「一個 key 一個檔」**：s6 的 `notification-fd`、`down-signal`、`timeout-kill`、`lock-fd` 都是資料夾裡一個小檔＝一個設定，跟 C-51「資料夾＝object、檔名＝key」、C-68「資料夾＝程式」同一個形狀；單子的 key 以後要長時，記得它們也可以是資料夾裡的檔（[03 § 6](aos-exec-s6-runit/03-借形狀.md)）。方向題。

## 衝突與方向題（細節在 04）

- **兩個實際的坑**（不是原則衝突，是順序）：① `s6-setuidgid` 放在入口裡會太晚——aos-exec 第 1 件事就以 root 建好 `$AOS_STACK`，換了使用者之後寫不進去；要換使用者得放在 aos-exec **外面**（`s6-setuidgid agent aos-exec …`）。② `s6-setsid`／`chpst -P` 放在格或單子裡會讓子程式逃出 aos 的行程群組，逾時與訊號打不到（N-41 格自己不 setsid、P-36 打整群）；只能在最外層、上面沒有 aos 的 loop／fsm 時用。
- **要監工在上面才有意義的工具**（`s6-svwait`、`s6-notifyoncheck`、`s6-fdholder-*`、`s6-sudo`、`svlogd` 管道）靠 fifodir／socket／管道，跟 C-64「用檔案不用管道」反向，只參考。
- **方向題與使用者的回覆**（10-22，[ideas 10-22 § 2](../thinking/2026-10-22-ideas.md)）：「這份報告很有價值，這會減少我們以後的工作量，等於說我們想要的很多功能都有現成輪子，不必重新造。然後方向題這塊，a.我覺得OK，aos-exec先維持只用標準庫。b.看看工作量、看看大家都是怎麼做的。cde.都先不要討論agent」
  - (a) aos-exec 只用標準庫、不 exec 外部程式替自己做事——**定**。
  - (b) `.env` 補不補 unset／多行／引號——**定**：格式做 python-dotenv 的基礎子集（引號、註解、去空白），unset、多行、跳脫不做（[dotenv-格式比較](dotenv-格式比較.md)、[ideas 10-22 § 3](../thinking/2026-10-22-ideas.md#3-env-基礎子集與---dotenv-override10-22)）。
  - (c) 一個 agent 一個 Linux 使用者、(d) agent 資料夾依賴 execline／s6、(e) 單子長 `limits`／`lock` key——10-22 先不討論；(c) 10-24 起以 `aos-sandbox` 試做（[thinking 10-24 sandbox](../thinking/2026-10-24-sandbox.md)）。
  - (f) 旗標表的邊界判準要不要寫進 N-58——未決。
