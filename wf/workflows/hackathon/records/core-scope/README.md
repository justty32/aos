# core scope 黑客松紀錄

> **以下是風格模擬，不是本人的意見。** 文中的 Carmack、Armstrong、Cantrill、Thompson 都是 persona 名稱，不是本人發言或引述。

| 項目 | 內容 |
|---|---|
| 題目 | 用現有的 `aos`（不改 C++、不 build）跑出一條三回合 agent loop，中途以 Ctrl-C、`kill -9`、rename 前中止，記錄重開後必須自行補上的工作；問出 temp＋rename 手寫次數、哪種 unknown 無法由本機補回、是否出現第二個需同時管理的工作，以對應近期 core scope 的三種大小。此題承接 OPEN-QUESTIONS 第 2 題「近期 core 要回撤到哪裡」。 |
| 開場日期 | 2026-08-26 |
| 環境 | WSL Ubuntu；codex 0.149.1；`-s workspace-write`；無網路；四位平行；單輪逾時 1800 秒；R1 費時 9.5 分鐘。 |
| Reasoning effort | `model_reasoning_effort=high` |
| 狀態 | 第 3 輪已完成 |

| 參賽者 | persona | 場地 | codex thread id（續輪 resume 用） |
|---|---|---|---|
| p1 | John Carmack | `~/aos-hack/core-scope/p1` | `01a03cea-1d12-7132-9ec5-8e10bf7e113c` |
| p2 | Joe Armstrong | `~/aos-hack/core-scope/p2` | `01a03cea-1d11-74a2-97ac-ecb1356772ff` |
| p3 | Bryan Cantrill | `~/aos-hack/core-scope/p3` | `01a03cea-1d15-74a3-9e2d-6fc47eec1671` |
| p4 | Ken Thompson | `~/aos-hack/core-scope/p4` | `01a03cea-1d12-7603-bf3d-b304f25b365b` |

---

## 這場的結構：先按「誰寫的」，再按輪次

四個角色檔各自再拆成一層按輪次的子資料夾；角色檔本身留在原路徑當導航。書記與資料員的輪次檔仍然超標，因此又各自按段落職責拆了第三層——那兩排的輪次連結都是只留導航的指標檔，真正的內容在同名子資料夾裡。

| 角色 | 導航 | 內容 | 分檔 |
|---|---|---|---|
| 祕書 | [白話導讀](plain/README.md) | **使用者從這裡開始讀。** 每輪祕書把發生的事翻成白話，錯誤訊息一條一句翻譯，最後一塊講「所以呢」。 | [R1](plain/round-1.md)｜[R2](plain/round-2.md)｜[R3](plain/round-3.md) |
| 書記 | [每輪紀錄](rounds/README.md) | 發生了什麼：各人做了什麼、坑的總表、三個數字收到什麼答案。不含判斷。每輪再拆成〈各人做了什麼〉〈坑的總表〉〈好處／壞處〉〈結算〉四份。 | [R1](rounds/round-1/README.md)｜[R2](rounds/round-2/README.md)｜[R3](rounds/round-3/README.md) |
| 評委 | [評分與意見](verdicts/README.md) | Torvalds persona 逐輪逐位打分（證據強度與誠實度權重最重）、指出下一輪該修什麼、以及「現在就得拍板會選哪個」。 | [R1](verdicts/round-1.md)｜[R2](verdicts/round-2.md)｜[R3](verdicts/round-3.md) |
| 資料員 | [資料包](packs/README.md) | 每輪之後針對卡住的地方找出的可參考資料，每條都有 repo 內路徑。每份再拆成〈卡住的清單〉〈repo 裡已經有答案的〉〈兄弟專案裡可以抄的〉〈還是查不到的〉等分塊。 | [R1 後](packs/after-round-1/README.md)｜[R2 後](packs/after-round-2/README.md) |

> 資料包只有兩份：第 3 輪之後沒有再備料。
>
> 想整輪橫著讀（同一輪的四個角色），就照上表同一欄的 R1／R2／R3 走。
>
> 只想看某一輪的坑與現場原文，直接進 [`rounds/round-N/pits.md`](rounds/round-2/pits.md)——那是書記紀錄裡份量最重的一塊。

> 原本是單檔 `core-scope.md`，三輪跑完膨脹到 115 KB，照 [DEV-GUIDE](../../../../DEV-GUIDE.md) 的「膨脹即拆」按用途拆成本資料夾；四個角色檔隨後又各自超標，再按輪次拆一層；書記與資料員的輪次檔仍超標，再按段落職責拆第三層。舊路徑 `plain.md`、`rounds.md`、`verdicts.md`、`packs.md`，以及 `rounds/round-N.md`、`packs/after-round-N.md` 都仍在，只留導航。
