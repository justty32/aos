# aos-exec 能從 s6／runit 那一族借什麼、叫什麼

← [notes](README.md)｜[proto8](../README.md)｜起點：[s6-runit 對照](s6-runit.md)（10-22 opus 寫的九點對照，這份不重寫）｜2026-10-22，AI（fable）寫

**這份是 AI 寫的參考，不算數**：條文以 [CONCEPTS](../docs/CONCEPTS.md)、[NORMS](../docs/NORMS.md) 為準，要用哪一點由使用者決定（鐵律 5）。使用者 10-22 的題目：「讓fable去看看，s6/runit這些東西，是否有aos-exec能借用、參考，乃至於直接呼叫他們的地方。」所以這份只盯 **aos-exec 這一支**（入口怎麼寫、環境怎麼設、開跑前能接什麼），監管、重啟、日誌那些已在 s6-runit 對照裡，不重講。

s6／runit 的事實查自官方文件（skarnet.org、smarden.org）與 Debian 套件清單，每點附連結。WSL（Ubuntu 24.04）實查：`s6`、`execline`、`runit`、`daemontools` 四個套件 apt 都有（universe），本機一個都沒裝，所以**沒有實跑**，例子是照文件與 aos-exec 的規則推的；裝了之後要驗。nosh、perp 不在 Debian／Ubuntu（perp 官網 10-22 連不上）。

<!-- wf-nav -->
## 分檔

| 分檔 | 涵蓋 |
|---|---|
| [01-直接呼叫-環境與鎖](aos-exec-s6-runit/01-直接呼叫-環境與鎖.md) | (1) 現在就能接上去的：envdir 一族（祕密一個檔）、setlock 一族（一個工作區只跑一隻）、execlineb 當入口檔 |
| [02-直接呼叫-資源fd使用者](aos-exec-s6-runit/02-直接呼叫-資源fd使用者.md) | (1) 續：softlimit 一族（記憶體／CPU 上限）、redirfd／fdmove／umask、setuidgid（要放在 aos-exec **外面**）、setsid／pgrphack（只能最外層）、chpst 總表 |
| [03-借形狀](aos-exec-s6-runit/03-借形狀.md) | (2) 不裝對方、照抄形狀：加旗標前的判準、envdir 的「空檔＝拿掉」、envfile vs `.env`、鎖與限制當單子 key、結束碼 100／111／126／127、servicedir「一個 key 一個檔」 |
| [04-不適合-衝突-方向題-套件](aos-exec-s6-runit/04-不適合-衝突-方向題-套件.md) | (3) 只能參考的（要監工在上面才有用的那些）、跟原則的衝突（含兩個實際的坑）、原則推不出的方向題、套件名與可得性表 |

每一項都標：對應哪條原則（C-／N-）、是「現在就能用」「要改規範」還是「方向題」。

## 一句話的底

aos-exec 開跑那一步是 **exec**（N-59 第 5 件），而 s6／runit／daemontools 那一族的小工具全是「改一下行程狀態，再 exec 成 argv 剩下的部分」（chain loading，[execline grammar](https://skarnet.org/software/execline/grammar.html)）。兩邊天生接得上：**aos-exec 的 argv 陣列入口、單子的 `argv`、`.env`，三個地方都能把它們排在前面**，不用 `sh -c`、不用改 aos 一行。反過來說，它們能做的事（換使用者、上限、拿鎖、設環境、動 fd）**都不必長進 aos-exec 的旗標表**——這是這份最主要的結論，也是 opus 對照「別把 aos-exec 養肥」那點的落實。

## 最值得的三個「直接呼叫」

1. **`s6-envdir secrets …`（或 `chpst -e`、daemontools `envdir`）放 API key**：一個變數一個檔、各自 `chmod 600`，正是 C-64「用檔案借 Linux 權限」；`.env` 一份檔做不到分權限。入口寫 `["s6-envdir", "secrets", "aos-loop", "loop.json"]` 就好（[01 § 1](aos-exec-s6-runit/01-直接呼叫-環境與鎖.md)）。現在就能用。
2. **`s6-setlock -n $AOS_STACK/lock …`（或 `chpst -L`、`setlock -n`）讓同一個工作區同時只跑一隻**：aos 沒有鎖的概念（P-18 兩隻共用 stack 會互寫、aos-tick「同時 tick 不管」），鎖檔放 stack 就跟「同一個 agent 可同時被兩個工作區跑」不打架（[01 § 2](aos-exec-s6-runit/01-直接呼叫-環境與鎖.md)）。現在就能用。
3. **`s6-softlimit -m … -t …`（或 `chpst -m`）放在 think 格的 `argv` 前面**：單子只有 `timeout_ms`（牆上時間），記憶體與 CPU 上限交給它，不加 key（[02 § 1](aos-exec-s6-runit/02-直接呼叫-資源fd使用者.md)）。現在就能用。

## 最值得的三個「借形狀」

1. **加旗標前的判準**（N-58「以後會加旗標」）：新旗標若只是「改行程狀態再 exec」，就該是鏈上的一支小程式，不是 aos-exec 的旗標；aos-exec 的旗標只留「找入口要用的」（[03 § 1](aos-exec-s6-runit/03-借形狀.md)）。方向題。
2. **envdir 的「空檔＝拿掉變數」**：`.env` 現在沒有寫法能 unset（`X=` 是設成空字串），上層設了、一路往下拿不掉；要不要補是方向題（[03 § 2](aos-exec-s6-runit/03-借形狀.md)）。
3. **servicedir「一個 key 一個檔」**：s6 的 `notification-fd`、`down-signal`、`timeout-kill`、`lock-fd` 都是資料夾裡一個小檔＝一個設定，跟 C-51「資料夾＝object、檔名＝key」、C-68「資料夾＝程式」同一個形狀；單子的 key 以後要長時，記得它們也可以是資料夾裡的檔（[03 § 6](aos-exec-s6-runit/03-借形狀.md)）。方向題。

## 衝突與方向題（細節在 04）

- **兩個實際的坑**（不是原則衝突，是順序）：① `s6-setuidgid` 放在入口裡會太晚——aos-exec 第 1 件事就以 root 建好 `$AOS_STACK`，換了使用者之後寫不進去；要換使用者得放在 aos-exec **外面**（`s6-setuidgid agent aos-exec …`）。② `s6-setsid`／`chpst -P` 放在格或單子裡會讓子程式逃出 aos 的行程群組，逾時與訊號打不到（N-41 格自己不 setsid、P-36 打整群）；只能在最外層、上面沒有 aos 的 loop／fsm 時用。
- **要監工在上面才有意義的工具**（`s6-svwait`、`s6-notifyoncheck`、`s6-fdholder-*`、`s6-sudo`、`svlogd` 管道）靠 fifodir／socket／管道，跟 C-64「用檔案不用管道」反向，只參考。
- **方向題**：(a) aos-exec 要不要維持純標準庫、不 exec 成 `envfile` 這類外部程式替自己讀 `.env`；(b) `.env` 要不要補 unset／多行／引號，還是維持 KISS、需要時在鏈上接 `s6-envdir`；(c) 「一個 agent 一個 Linux 使用者」（C-64 的權限玩法）要不要走——要走就得由 root 起、每個子項前面接 `s6-setuidgid`；(d) 入口檔用 execlineb 寫算不算「少用 sh」的延伸，agent 資料夾能不能依賴 execline。
