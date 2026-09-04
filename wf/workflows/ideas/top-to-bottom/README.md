# top-to-bottom：「資料夾＝list」這一整套，從最上到最下

← [ideas](../README.md)｜[WORKFLOWS](../../../WORKFLOWS.md)｜裁決總表 [verdicts](../verdicts.md)

**使用者原話（2026-09-03）**：

> 我想請你在idea中新開一個資料夾，就存放我們這個從最上到最下面的，一整套的東西。包括我的原文、我們的討論、你的意見等等。就只要概念，還有最少的與概念有相關的牽扯的我們已經做了的aos的東西。一樣，要大白話

所以這個資料夾**不是新的構想**，是把 2026-09-01～09-03 散在五、六個檔裡的同一套模型，
**照「從上到下」重排一次，用大白話講完**。原始討論檔一個都沒刪，這裡只是另一種讀法。

## 怎麼讀

- **想快速知道整套在講什麼** → 看下面那張總表，再照 01→04 順序讀，一路從最上面讀到最底。
- **想知道為什麼要這樣設計** → 05。
- **想知道還有哪些沒定** → 06。
- **想知道今天的 aos 程式碼跟這套模型差多少** → 07。
- **想看時間怎麼走** → 08；**想知道能不能承載 LLM 這顆虛假 CPU** → 09。
- **想看原始的一問一答、以及被否決的東西** → 每檔文末都有「這節從哪來」指回原檔。

三種聲音在每一檔裡都分開標：**使用者原話**（引文，含日期）／**裁決**（明標，已拍板）／
**AI 觀察**（明標，非裁決，使用者可以否決）。**別混引。**

## 一張「從上到下」總表

| 層 | 大白話 | 學名／對照 | 哪一檔 |
|---|---|---|---|
| **最上** | **Linux**——開 daemon 的 shell／systemd 住這裡，aos 管不到 | 大核心 | [01](01-top.md) |
| ↓ | **你**（在 terminal 打一句），或**你開的 daemon** 幫你開 | daemon ＝ REPL | [01](01-top.md) |
| ↓ | **資料夾樹**——一個資料夾就是一個 list，`.aos` 是第一個元素，其餘是引數 | operative／fexpr；多個資料夾互投遞＝actor | [02](02-folders.md) |
| ↓ | **`.aos` 裡的那段腳本**——POSIX 指令 ＋ `aos` 子命令 | inst 鏈、機器層 | [03](03-inside-aos.md) |
| ↓ | **原子 inst**——一次工具呼叫、一次 LLM 呼叫，再也託付不下去 | primitive、求值碰到底 | [04](04-atoms.md) |
| 橫向的時間 | **一次 exec 是一格；一個 run 是一個時鐘**；同步子世界借父的鐘，async 自己走 | tick／clock | [08](08-time.md) |
| **最底** | **CPU 週期**——真的那台機器 | — | [04](04-atoms.md) |

**兩層之間唯一的橋**：`.aos` 腳本裡的 `aos run <子資料夾>` 那一行。**單向**——裡面可以開
外面的資料夾，外面**永遠不會**被折進裡面。（裁決，2026-09-03）

## 本套的裁決一覽

全部收在 [verdicts A 區](../verdicts.md)，這裡只列本套相關的，日期照拍板日。

| 日期 | 裁決（一句話） | 詳見 |
|---|---|---|
| 2026-09-01 | **留著批**：一次 exec 跑一批，不退回「一次一條」；該模仿的是遊戲引擎一 tick 掃全部 | [03](03-inside-aos.md) |
| 2026-09-01 | **複雜式由程式確定性拆平才進 series，LLM 不出場** | [03](03-inside-aos.md) |
| 2026-09-01 | **節奏差一個數量級不是缺陷**：快世界／慢世界，一次跑十幾分鐘很正常 | [01](01-top.md) |
| 2026-09-03 | **資料夾無序「沒差」**，重點在求值；**穩態／暫態就是 quote** | [02](02-folders.md) |
| 2026-09-03 | **三層各一個名字**：`aos exec` ＝一步歸約、`aos run` ＝算到底、**daemon ＝ REPL** | [01](01-top.md)、[03](03-inside-aos.md) |
| 2026-09-03 | **`.aos` 是 car，資料夾＝operative（fexpr）**；子資料夾跑不跑全由父 `.aos` 決定 | [02](02-folders.md) |
| 2026-09-03 | **兩層分開**：`.aos` 內是 inst 鏈（機器層）、`.aos` 外是資料夾樹（行程層） | [02](02-folders.md)、[03](03-inside-aos.md) |
| 2026-09-03 | **頂層資料夾由使用者開、或他開的 daemon 代開**，不是資料夾自宣告 `init` | [01](01-top.md) |
| 2026-09-03 | **inst 鏈（攤平／接力棒／`out/`）是為省成本的語法糖**，本體只有原子 inst ＋ 開／讀／選 | [03](03-inside-aos.md)、[04](04-atoms.md) |
| 2026-09-03 | **inst 層與資料夾層互不相關**（「編譯器把子資料夾壓成 inst」已被否決） | [03](03-inside-aos.md) |
| 2026-09-03 | **目標優化指標是金錢（token）／可預測性／人類可理解性**，時間空間只是粗淺優化 | [05](05-why.md) |
| 2026-09-03 | **三個指標裡可預測性最優先**（金錢與可理解性的相對順序未裁） | [05](05-why.md) |
| 2026-09-03 | **人寫的原稿放資料夾頂層**；被父層點名打開時 loader 才讀進 `.aos/`，**`.aos/` 仍是機器的** | [02](02-folders.md)、[03](03-inside-aos.md) |
| 2026-09-03 | **先停下設計，去用現有的東西玩** | [06](06-open.md) |

## 每一檔在講什麼

| 檔案 | 一行摘要 |
|---|---|
| [01-top](01-top.md) | **最上面**：頂層資料夾誰開的、daemon 就是 REPL、再往上是 Linux |
| [02-folders](02-folders.md) | **資料夾層**：資料夾＝list、`.aos`＝car、拿原料的廚師、沒被點名的躺著＝quote |
| [03-inside-aos](03-inside-aos.md) | **`.aos` 裡面**：一段命令腳本、走一步 vs 算到底、接力棒與 `out/`、為省成本的語法糖 |
| [04-atoms](04-atoms.md) | **最底下**：原子 inst 託付不下去了、機器層＝CPU 週期、一步＝一次歸約 |
| [05-why](05-why.md) | **為什麼這樣設計**：三個指標、套幾層＝幾輪回不來、RTOS、上微核心下大核心 |
| [06-open](06-open.md) | **還沒定的**：四條橋的缺口、agent 住錯位置、頂層 daemon 沒專屬格 |
| [07-existing-aos](07-existing-aos.md) | **現有 aos 對照**：模型裡的名字 ↔ 今天程式裡的名字 ↔ 符合／對不上 |
| [08-time](08-time.md) | **時間**：一格＝exec、一鐘＝run、同步借鐘、async 脫節、daemon 統管、時間有界 |
| [09-cpu-socket](09-cpu-socket.md) | **LLM 當虛假 CPU**：主機板已夠；四個工程腳位留作實作對照，概念層到此收工 |

## 原始討論檔（想看完整脈絡與被否決的部分，去這些）

- [program-form](../program-form.md)——檔案＝atom、資料夾＝list、穩態暫態＝quote、REPL、三層、四條裂縫
- [nested-eval](../nested-eval.md)——list 裡還有 list：運算式巢狀 vs 資料夾巢狀
- [nested-eval-car](../nested-eval-car.md)——`.aos` 是 car、資料夾＝operative（含裁決）
- [nested-eval-sugar](../nested-eval-sugar.md)——inst 鏈是語法糖、兩層互不相關（含裁決與被否決那三條）
- [play-watchlist](../play-watchlist.md)——概念主幹已齊，四條橋的缺口留給玩的時候看
- [assembly-and-chains/](../assembly-and-chains/README.md)——彙編線與 C 語言線，含[身分對照表](../assembly-and-chains/lisp-reconciliation.md)
- [os-metrics-and-resources](../os-metrics-and-resources.md)——三個指標、RTOS、微核心、「先去玩」
- [turing-to-os](../turing-to-os.md)——更上游的根基論證：agent loop ＝ CPU、檔案系統即記憶體
- [exec-run-async](../exec-run-async.md)、[exec-run-async-time](../exec-run-async-time.md)、
  [daemon-clocks](../daemon-clocks.md)、[land-rules](../land-rules.md)——2026-09-04 長出的時間、
  時鐘總管與一塊地的規則
