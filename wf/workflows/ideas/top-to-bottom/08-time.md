# 08 · 時間：一格、一個時鐘，以及脫節的子世界

← [top-to-bottom](README.md)｜上一節 [07-existing-aos](07-existing-aos.md)｜下一節 [09-cpu-socket](09-cpu-socket.md)

前面 01～07 把**空間**一路排好：Linux、資料夾樹、`.aos`、原子 inst。這一篇只把今天長出的
**時間**那條線照原意排在一起。**本篇無新裁決、無新主張。**

## 一格時間＝一次 `exec`

**使用者定義（2026-09-04，未明說裁決）**：一次 tick，就是父世界與它這一格要推進的東西動
一次；沿用先前遊戲引擎的比喻，**一格時間＝一次 `exec`**。（來源：
[exec-run-async-time](../exec-run-async-time.md)、[04-atoms](04-atoms.md)）

大白話：`exec` 不是把整件事做完，只是讓世界往前走**一格**。這一格做完，控制權就交回去；
下一格要不要再走，是外面的時鐘決定。（來源：[04-atoms](04-atoms.md)）

## 一個時鐘＝一個 `run`

**使用者原話的模型（2026-09-04，停止條件未定）**：`run` 會反覆 `exec`，可以固定次數、隔一段
時間再跑，或一直跑到某個條件成立；那個條件「還沒想好」。（來源：
[exec-run-async](../exec-run-async.md)）

因此可以把它讀成：**一個 `aos run` 就是一個時鐘**，它一格一格地 tick，直到停止條件成立。
（來源：[exec-run-async-time](../exec-run-async-time.md)）

**AI 觀察（非裁決，可否決）**：停止條件最好是**看得見的檔案或步數**，不要藏在 daemon 的
記憶體裡；這樣重開之後，人仍看得出為什麼停、接下來會怎樣。這個格式尚未決定。
（來源：[exec-run-async §b](../exec-run-async.md#b-run-就是反覆-exec直到跑到定點)）

**2026-09-04 使用者定義**：**這次 exec 沒產出新的 inst 就停**；上面的「停止條件未定」保留為
歷史。見 [agent-loop-answers 第 2 題](../agent-loop-answers.md#第-2-題跑到什麼時候)。

## 同步子世界：借父的時鐘

**使用者定義（2026-09-04，未明說裁決）**：通常父世界動一格，父 `.aos` 點到的子世界也跟著
動；**全部動完，父的這一格才算完**。（來源：[exec-run-async-time](../exec-run-async-time.md)）

**AI 觀察（非裁決，可否決）**：這就是 02 的**正常次序求值的時間版**——父點名才開子，沿
`aos run <child>` 那座橋推它，而且等這次求值完成。同步子世界沒有另一只鐘，它借父的鐘。
（來源：[exec-run-async-time §B](../exec-run-async-time.md#b-async-世界時序脫節)、
[02-folders](02-folders.md)）

## async 子世界：自己的時鐘

**使用者定義（2026-09-04，未明說裁決）**：`async` 不是「同一格裡偷偷開執行緒」，而是讓
**子世界的時間與父世界脫節**。子世界有自己的時鐘，父 tick 不等它。（來源：
[exec-run-async-time](../exec-run-async-time.md)）

父要結果時，做法仍很單純：**父在自己的 tick 看子的 `out/` 在不在**；不在就繼續別的事，
在了才讀。（來源：[exec-run-async-time §B](../exec-run-async-time.md#b-async-世界時序脫節)）

> 「結果固定落在子資料夾 `out/` 的固定路徑」是 **AI 提議，未裁**，不是本篇新定義。
> （來源：[exec-run-async §d](../exec-run-async.md#d-asynctrueai-反對開執行緒贊成開子資料夾)）

## daemon＝所有時鐘的總管

**使用者傾向（2026-09-04，未明說裁決）**：所有時鐘都交給 daemon 走；父時鐘死了，脫節的
子時鐘仍可繼續。所有時鐘集中登記，關機時才能一次全停。**fork 先不考慮。**（來源：
[daemon-clocks](../daemon-clocks.md)）

**AI 觀察（非裁決，可否決）**：daemon 的工作因此是三件事——**登記、走、關機一次全停**；
登記表可以就是 daemon 資料夾這個 list。出生時要先登記再開始走，重啟後則拿總表與各地的
`run.pid` 對帳。（來源：[daemon-clocks §1～6](../daemon-clocks.md#1-daemon-時鐘總管)）

行程的空間規則也接得上：**路徑是身分，刪資料夾就是死**；daemon 判死時，AI 建議同時看 pid
與路徑，避免留下還在跑的孤魂。這是來源檔的使用者定義與 AI 建議，並非本篇新裁決。
（來源：[land-rules](../land-rules.md)）

## 時間要有界

**使用者傾向（2026-09-04，未明說裁決）**：主要靠環境限制，讓同步世界能用的指令都很快
結束；timeout 可以有，但不是首選。（來源：[exec-run-async-time](../exec-run-async-time.md)）

**AI 觀察（非裁決，可否決）**：完整規則是：**同步世界只放時間有上限的原子；時間由網路、
外部服務或別人決定的慢工作，搬去脫節子世界。** 有限個原子各自有上限，一個 tick 才天生有
上限；**timeout 是保險絲**，不是主要保證。（來源：
[exec-run-async-time §A](../exec-run-async-time.md#a-環境限制-vs-timeout)）

## 現有 aos 對照

以下只彙整來源檔已查證的結果，**沒有重查程式碼**。

| 模型裡的說法 | 今天程式裡的情況 | 對照來源 |
|---|---|---|
| 慢工作不該卡在同步 tick | `aos llm`、agent 的 LLM 步都會**同步等 curl** | [exec-run-async 現有對照](../exec-run-async.md#現有-aos-對照) |
| 一格內的 inst 一起動、全做完才收格 | `start_all()` 先全 fork，`wait_all()` 等最慢的一個，再一起寫 `out/` | [exec-run-async 現有對照](../exec-run-async.md#現有-aos-對照) |
| 每個時鐘要能被找到 | 每個無限 run 各寫自己的 `.aos/run.pid` | [daemon-clocks 現有對照](../daemon-clocks.md#現有-aos-對照) |
| 關掉一個時鐘 | `aos stop <folder>` 只停指定資料夾那一個 | [daemon-clocks 現有對照](../daemon-clocks.md#現有-aos-對照) |
| daemon 管全部時鐘 | 今天**沒有跨資料夾總表，也沒有一次全停** | [daemon-clocks 現有對照](../daemon-clocks.md#現有-aos-對照) |

## 相關清單

- `G01`：一格何時交回控制權，以及卡住時怎麼回到 OS。
- `G06`：時鐘是正在走的行程，要可登記、列舉與終止。
- `G09`：有界原子自然返回；timeout 只是強制收尾。
- `G10`：daemon 統管子時鐘，是跨資料夾排程的形狀。
- `G19`：LLM／網路的時間由外面決定，必須把不確定隔開。

以上對應均沿用 [exec-run-async-time](../exec-run-async-time.md) 與
[daemon-clocks](../daemon-clocks.md) 文末的「相關清單」。

---

**這節從哪來**：[exec-run-async](../exec-run-async.md)、
[exec-run-async-time](../exec-run-async-time.md)、[daemon-clocks](../daemon-clocks.md)、
[land-rules](../land-rules.md)、[04-atoms](04-atoms.md)。
