# 07 · 現有 aos 對照：模型裡的名字 ↔ 今天程式裡的名字

← [top-to-bottom](README.md)｜上一層 [06-open](06-open.md)

**只取最少量**——這一檔的用途是：讀完前面六檔之後，知道「今天真的存在的東西」有哪些、
哪些**符合**模型、哪些**對不上**。**別把現有程式碼當成這套模型的實作。**

## 今天真的有的子命令

| 子命令 | 做什麼（大白話） |
|---|---|
| `aos run` | 推進一個資料夾：把收件匣的東西湊成一批、一次全部跑掉、回合數 +1。`--step 0`／`--daemon` 就一直跑下去 |
| `aos deliver` | 把**一條**指令原子地丟進某個資料夾的收件匣 |
| `aos stop` | 叫正在跑的那條 loop 停下來 |
| `aos agent` | 建立並推進一隻住在 `.aos/agents/<name>/` 的 agent |
| `aos chat` | 從空資料夾開始的一步入口：沒有 agent 就先建、送一則訊息、自己推回合到出現回覆為止 |
| `aos llm` | 呼叫一次 OpenAI 相容端點 |
| `aos tick` 等 | 心跳：掃到期的例行事務與行程，投進收件匣 |

`core/exec` 是**純函式庫**，**沒有 `aos exec` 這個子命令**。

## 今天真的有的 `.aos/` 版面

一個「會跑的資料夾」底下長這樣（只列本模型會碰到的）：

| 路徑 | 是什麼 |
|---|---|
| `.aos/inbox/*.json` | **收件匣**——`aos deliver` 把一條指令寫進來 |
| `.aos/every/*.json` | **常駐指令**——每回合複製一份出來跑（可設間隔） |
| `.aos/batch/<turn>/insts/` | 這一回合實際要跑的**那一批** |
| `.aos/batch/<turn>/out/` | 這一回合跑出來的結果 |
| `.aos/turn` | 現在第幾回合 |
| `.aos/state.json` | 這回合誰在跑（含 pid） |
| `.aos/agents/<name>/` | 一隻 agent 的對話、狀態、工具往返 |
| `.aos/run.pid`／`run.lock`／`run.log` | 正在跑的那條 loop 的地址、鎖、log |

## 對照表：模型 ↔ 今天 ↔ 符不符合

| 模型裡的名字 | 今天程式裡的名字 | 符合／對不上 |
|---|---|---|
| **一步歸約**（`aos exec`） | **沒有這個子命令**；最接近的是 `aos run --step 1` | **對不上**（名字不存在，`core/exec` 是函式庫） |
| **算到底**（`aos run`） | `aos run`（`--step 0`／`--daemon`） | **符合**——但停在哪是靠步數，不是靠「不再變」 |
| **daemon＝REPL** | `aos run --daemon` 是**單一資料夾**一直跑；「盯著桌子、有指令才去跑某個資料夾」的那種 daemon **還沒有一次性入口** | **部分對不上**（見 [06](06-open.md)） |
| **丟訊息**（`deliver`） | `aos deliver` | **符合**——但一次只送**一條**，「批」是 loop 每回合開頭自己湊的 |
| **批＝一格** | `.aos/batch/<turn>/` | **符合** |
| **`.aos` ＝ car** | `.aos/` 目錄**存在**，但它今天是**機器的暫存區**，不是「一段可以寫的腳本」 | **對不上**——沒有「`.aos` 是一段命令腳本」這回事 |
| **接力棒**（`series.json`） | **不存在**；今天最接近的是 `.aos/every/`（每回合自投） | **對不上**（還沒實作） |
| **中間值**（`out/`） | `.aos/batch/<turn>/out/<id>.json` | **符合**——但是每回合一份，不是「一個有名字的中間值」 |
| **原子 inst** | 一條 `Inst`（argv／env／cwd／stdin／timeout），由 `core/exec` fork 出去跑 | **符合** |
| **一隻 agent＝一個獨立資料夾** | 今天住在 `.aos/agents/<name>/` **裡面** | **對不上**——見 [06](06-open.md) |
| **人在桌邊按 enter** | `aos chat` 是今天唯一「讀一句→算→印回覆→等你下一句」四格都齊的入口 | **符合**（但它的「算」是推好幾回合，不是走一步） |

## 一個順帶的邊緣狀況：源碼與產物住同一個資料夾

**AI 觀察（非裁決，可否決）**：你放的檔、接力棒、跑出來的產物**全住在同一個資料夾**，
等於**在源碼目錄裡 build**。這對「人類可理解性」（[05](05-why.md)）不利，需要**版面慣例**
把「人放的」與「機器長的」分開。

方向現成：**`.aos/` 給機器、頂層給人**。判別的尺也現成：**刪掉它，世界的意思會不會變？**
只影響節奏的歸機器，會改變意思的歸世界。

今天**沒有**一份專講「哪條路徑歸誰、誰能寫」的文件；最接近的位置是
[machine-shape/layout-and-spec](../machine-shape/layout-and-spec.md) 講的 **ownership table**
（每條路徑標唯一的 writer 與方向；有兩個 writer 的路徑就是未來壞掉的準確位置）——**那張表
還沒做**。

---

**這節從哪來**：[core/loop](../../../../core/loop/README.md)、
[core/exec](../../../../core/exec/README.md)、[core/agent](../../../../core/agent/README.md)、
[core/README](../../../../core/README.md)（子命令表）、
[program-form](../program-form.md)（`aos chat` 是四格最齊的入口、在源碼目錄裡 build）、
[machine-shape/layout-and-spec](../machine-shape/layout-and-spec.md)（ownership table）、
[play-watchlist](../play-watchlist.md)（agent 住錯位置）。
