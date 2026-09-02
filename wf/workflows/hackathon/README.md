# hackathon — 黑客松（多 agent 動手做、只收坑）

← [WORKFLOWS](../../WORKFLOWS.md)｜[專案 INDEX](../../INDEX.md)

> **本檔＝流程**。這資料夾有什麼、已辦過哪幾場，看 **[INDEX.md](INDEX.md)**。
> 題目書與參賽者任務書在 **[briefs.md](briefs.md)**；收場四棒（書記／評委／資料員／祕書）的任務書在 **[staff.md](staff.md)**；
> **辦一場會撞到的坑在 [gotchas.md](gotchas.md)——第一次辦之前先讀那份。**

**做什麼**：使用者出題（或從研討會的待答問題裡挑），**我當主辦人**備一份資料包，派幾個
`codex exec` 實例**各自去真的做做看**——做法不指定、隨意發想、可以推翻現有設計。
做完收兩樣東西：**踩坑報告**（撞到什麼、哪裡舒服、哪裡難用、哪裡放棄），以及**評委對路線的判斷**。

**成功條件不是做出東西。做不完是正常的，卡住的地方就是最有價值的產出。**

**不追求可合併的程式碼**——參賽者寫的是拋棄式的，真有價值就轉交
[feature-dev](../feature-dev/README.md) 重做。

## 跟 workshop / experiments 的分界

| | [workshop](../workshop/README.md) | [experiments](../experiments/README.md) | **hackathon（本檔）** |
|---|---|---|---|
| 動手 | 唯讀，只講 | 動手，我自己跑 | 動手，多個 agent 平行跑、**跨輪迭代** |
| 目標 | 想法的「多」 | 驗一個明確假設（是／否）| 同一題不同做法**各撞到什麼** |
| 產出 | 紀錄 | 實測證據 | **坑／好處／壞處** ＋ **每輪評分與意見** |
| 誰拍板 | 使用者 | 事實 | 評委給建議，**使用者拍板** |

> workshop 的硬規則是 read-only、不准 build，所以它結構上**只能**產出「應該」。
> 2026-08-25 那次「你直接去試」的 [T5 實測](../experiments/t5-agent-loop.md)一次就抓到
> 規格與 roadmap 互相矛盾，比七場研討會的轉交提案都硬。**黑客松＝把那次的做法變成常設、
> 而且多人平行。**

## 題目哪裡來

**優先挑 [workshop/BACKGROUND.md](../workshop/BACKGROUND.md) 的「最小的驗證方式」**——
`background/` 那 17 檔裡每題結尾都有一條，共 20 條，**每條祕書都明寫「一小時內做得完」**，
是現成的題目卡。其次是 [OPEN-QUESTIONS](../workshop/OPEN-QUESTIONS.md) 的阻塞題
（使用者不想用想的拍板的，改成用做的），再來是使用者臨時起意。

資料包通常是：對應那場的 `records/*.md` ＋ 該題的 `background/*.md` ＋
[PROTOCOL](../dispatch/proto/PROTOCOL.md)（規格唯一真源）＋
[`roadmap`](../roadmap.md)。


## 細節在哪（從本檔拆出去的）

| 檔案 | 裡面有什麼 | 什麼時候看 |
|---|---|---|
| [roles.md](roles.md) | 六個角色的分工、名人 persona 名單與挑人判準 | 決定這場派誰上場時 |
| [rounds.md](rounds.md) | 三輪迭代每一輪的五棒順序、跨輪 resume、評委的評分表 | 排一場的流程、每輪收場時 |
| [arena.md](arena.md) | 場地怎麼建（整包複製的指令）、為什麼在 WSL、`codex exec` 的指令形態 | 建場地、下指令開跑時 |

## 紀錄

- 落點 `records/<題目-kebab>.md`，**一題一檔、每輪四層追加**（書記→評委→資料員→祕書）。
- 檔頭要標**參賽者是哪幾位名人**、**這是風格模擬**、以及**每位的 codex session id**
  （續輪要用；只在開場那台機器上有效）。
- **跨工作流通用的坑**往 [common/gotchas](../common/gotchas.md) 併一條；題目專屬的留紀錄裡。
- 驗出結論要改規格 → **轉交提案，我不自己改 `docs/`**，要使用者拍板。
- 值得做成真功能 → 轉 [feature-dev](../feature-dev/README.md) 重做，**不要合併黑客松的程式碼**。
