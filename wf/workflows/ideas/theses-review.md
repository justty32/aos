# 根基三論的複審（2026-09-01，主 session ＋ 兩個 fork）

← [ideas](README.md)｜上游 [turing-to-os](turing-to-os.md)、[program-form](program-form.md)｜[WORKFLOWS](../../WORKFLOWS.md)

**這一整篇都是 AI 的觀察，不是裁決，使用者可否決。** 記的是 2026-09-01 上午主 session 與
兩個 fork（理論／工程）就根基論證做的一次複審。它**不新增方向**，只指出既有論證的
**承重點放錯了位置**，以及缺口裡哪幾條是真的會鎖死。

## 一、同像性的承重點是「自我改寫」，不是表達力

**主 session 與理論 fork 各自獨立得到同一結論。**

使用者當日收回了「只有 lisp 承載得了」的排他性（改為偏好；Python／Lua 也適合，見
[program-form](program-form.md)）。這留下一個問題：**那 `G24`（同像性要在資料夾樹上成立）
到底在撐什麼？**

答案是**自我改寫**，不是表達力。所以 `G24` 該重問成：

> **一個正在跑的資料夾，能不能被另一個 agent loop 當成資料讀進來、改寫、再放回去跑？**

而這件事在這台機器上**本來就成立**——agent 的工具本來就是檔案工具：

| lisp | aos |
|---|---|
| eval | loop 消化資料夾 |
| macro | agent 寫資料夾 |

**寫程式的手與跑程式的手讀同一種 form**，這才是同像性在撐的東西。Python／Lua「也適合」
只在**「寫程式」**那一格成立，在**「程式改寫程式」**那一格不成立——這也是為什麼收回排他性
不等於 `G24` 消失。

**`G07`（程式與行程的分界）不是與同像性相撞，而是它的代價**：既然刻意讓兩者同型，就
**必須另外付一個顯式標記**去分「這份是碼」與「這份正在跑」。而——

> **那個標記就是這台機器的 quote。**

所以 [program-form](program-form.md) 四條裂縫裡的**第 3 條（哪棵樹正在被求值）與第 4 條
（quote 從哪來）是同一題**，不是兩題。

## 二、CPU 與 REPL 兩讀法的唯一不矛盾映射（理論 fork）

`program-form` 說 agent loop 同時可讀成 **CPU**（它是什麼計算單元）與 **REPL**（人怎麼跟
它互動）。兩種讀法只有**一組**映射能同時成立：

> **一個 REPL 句 ＝ 一個回合 ＝ 一批，依賴一律跨回合。**

**推論**：為了效率把相依步驟塞進同一批的那一天，**REPL 讀法即刻破產**——REPL 的語意是
一句求值完看到結果再下一句，同批內有依賴就沒有「看到結果」這個點。所以
[verdicts B3](verdicts.md)（一回合內沒有資料流，已寫進
[PROTOCOL §5](../dispatch/proto/PROTOCOL.md#5-一回合)）不只是實作現況，它**還是 REPL
讀法的存在條件**。

**兩條讀法在缺口上收斂到同一處**：

- CPU 線要**回合編號**做去重（第十輪「PC 不存在」）
- REPL 線要**輸入歷程**做 replay（[prior-work](prior-work.md)：git 買不到 replay）

兩者都由同一件事餵飽：**給「批」名字與 header**（[verdicts B1](verdicts.md)、
[machine-shape/instruction](machine-shape/instruction.md)）。所以它的槓桿**比 verdicts
原本記的更高**——原本記成「一次解決 B1／B2／B4 與去重」，實際上它同時是**兩種讀法的共同
地基**。

## 三、三要件的分派有層次錯位：分支發生在 LLM（理論 fork）

[turing-to-os §一](turing-to-os.md) 把「可根據條件分支」派給 **tooling**。這是層次錯位：

- **tooling ＝感覺器官與效果器**——讓環境可見、讓反應落地
- **「看見之後決定要不要改行為」＝計算**，發生在 **LLM**

**錯位的代價正好就是 `G05`**（可分支的機器狀態）：分支被記在「回合內的 tooling」身上，
於是 **loop 層沒有分支也不覺得缺**——實測也對得上（[verdicts D2](verdicts.md)：loop 看
回傳值了，但不重試、不停、不改節奏）。

**修正案**：

| 要件 | 承載者（修正後） |
|---|---|
| 可計算 | LLM |
| 可根據條件分支 | **LLM**（決定）＋ tooling（**可觀察性**）＋ **loop（把分支結果接上控制流）** |
| 可連續執行自身 | agent loop |

第三件的**空間論證**（體積不能無限膨脹）成立，但**誠實的承載者是
[top-down-cli](top-down-cli.md) 的「自我複製投遞」**——那才是這台機器上「執行自己」的
實際機制。

## 四、缺口分流：哪些會自己消失，哪兩條拖了會鎖死（工程 fork）

工程 fork 的判定（部分已行動，這裡只記結論）。

**會自己消失的假缺口**：`G04`／`G09`／`G07`／`G24` 這一類——實作走到那裡時自然會得到
形狀，不需要現在拍板。與使用者「之後實作的時候自然能有解」的通則一致。

**唯二拖了會鎖死的是 `G13` 與 `G18`。** `G13`（命名空間、掛載與權限位）鎖死是因為
namespace **必須在 `fork` 之後、`execve` 之前**建，只有 exec 層碰得到
（[verdicts B13](verdicts.md)）——**介面每凍結一天就更難插進去**。`G18`（成本作為一等
資源）鎖死是因為成本帳是**量測儀**：沒有它，`G15`–`G17`（資源管理那一層）全在盲飛，而
事後補帳等於**重寫所有 LLM 呼叫點**。

**`fsync` 該插隊到實作的第一位**（[verdicts D2](verdicts.md)：`fs::write_atomic()` 檔案
與目錄都沒 `fsync`）。理由不是資料安全，是**基礎設施缺陷會污染實驗的證據鏈**——原型掛了，
分不清是設計錯還是撿到零長度檔。

**「文件是程式碼的上游」成立的前提是有回寫協定。** 當日 `verdicts.md` 漂掉已修復，
「**實作閉合就在同一個 commit 回寫文件**」的提議也已在該次 commit 落實為做法。要不要立成
[AGENTS.md](../../../AGENTS.md) 鐵律第 3 條（改程式碼就同步 code map）的姊妹條，
**使用者未裁——記為開放**。

## 相關

- [turing-to-os](turing-to-os.md)——三要件、agent loop ＝ CPU、缺口總表的來歷
- [program-form](program-form.md)——檔案＝atom／資料夾＝list、REPL 讀法、四條裂縫
- [game-process-model](game-process-model.md)——同日的第三個模型：一次 exec ＝ 一格 tick
- [verdicts](verdicts.md)——B1 批的 header、B3 回合內無資料流、B13 capability、D2 實測
- [cpu-to-os-gaps](cpu-to-os-gaps.json)——`G05`／`G07`／`G13`／`G14`／`G18`／`G24`
- [machine-shape/instruction](machine-shape/instruction.md)——批需要 header、opcode 懸空、footprint
- [top-down-cli](top-down-cli.md)——自我複製投遞（「執行自身」的實際承載者）
