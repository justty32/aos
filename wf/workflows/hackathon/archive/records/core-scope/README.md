# core scope 黑客松紀錄

> **以下是風格模擬，不是本人的意見。** 文中的 Carmack、Armstrong、Cantrill、Thompson 都是 persona 名稱，不是本人發言或引述。

| 項目 | 內容 |
|---|---|
| 題目 | 用現有的 `aos`（不改 C++、不 build）跑出一條三回合 agent loop，中途以 Ctrl-C、`kill -9`、rename 前中止，記錄重開後必須自行補上的工作；問出 temp＋rename 手寫次數、哪種 unknown 無法由本機補回、是否出現第二個需同時管理的工作，以對應近期 core scope 的三種大小。此題承接 OPEN-QUESTIONS 第 2 題「近期 core 要回撤到哪裡」。 |
| 開場日期 | 2026-08-26 |
| 環境 | WSL Ubuntu；codex 0.149.1；`-s workspace-write`；無網路；四位平行；單輪逾時 1800 秒。 |
| Reasoning effort | `model_reasoning_effort=high` |
| 狀態 | 第 3 輪已完成 |

| 參賽者 | persona | 場地 | codex thread id（續輪 resume 用） |
|---|---|---|---|
| p1 | John Carmack | `~/aos-hack/core-scope/p1` | `01a03cea-1d12-7132-9ec5-8e10bf7e113c` |
| p2 | Joe Armstrong | `~/aos-hack/core-scope/p2` | `01a03cea-1d11-74a2-97ac-ecb1356772ff` |
| p3 | Bryan Cantrill | `~/aos-hack/core-scope/p3` | `01a03cea-1d15-74a3-9e2d-6fc47eec1671` |
| p4 | Ken Thompson | `~/aos-hack/core-scope/p4` | `01a03cea-1d12-7603-bf3d-b304f25b365b` |

---

## 結論

- **評委最終建議（第 3 輪）**：選 (b) Publish → Deliver → Effect，分段驗收；第一步做 Publish。Deliver 的 completion 由 consumer／aggregate ack，不是 Publish 外的薄殼；Effect 只保存 phase、evidence、`unknown` 與明示 reconcile，不承諾 exactly-once。(c) 完整控制平面沒有實測需求（三輪「第二個要同時管的工作」都是 0），不做。使用者尚未拍板。詳見 [第 3 輪評分與意見](verdicts/round-3.md)。
- **致命坑**：無 query／idempotency 的遠端 effect 在 acceptance 與本機 result commit 之間中止，本機無法自動判定真相。
- **三個數字**：① 手寫 temp＋rename：1／1／2／6（p1～p3 數實作份數，p4 數靜態實作位置）；② 本機補不回的「不知道做了沒」：四位都是 1 類；③ 第二個要同時管的工作：四位都是 0。見 [第 3 輪結算](rounds/round-3/wrap-up.md)。

## 怎麼讀

四個角色各一個資料夾，按輪次分檔；書記與資料員的輪次檔再按段落職責分一層，輪次檔本身只留導航。

| 角色 | 導航 | 內容 | 分檔 |
|---|---|---|---|
| 祕書 | [白話導讀](plain/README.md) | **使用者從這裡開始讀。** 每輪發生的事的白話版、錯誤訊息翻譯、「所以呢」。 | [R1](plain/round-1.md)｜[R2](plain/round-2.md)｜[R3](plain/round-3.md) |
| 書記 | [每輪紀錄](rounds/README.md) | 坑的總表、好處／壞處、三個數字、仍然不知道的。不含判斷。 | [R1](rounds/round-1/README.md)｜[R2](rounds/round-2/README.md)｜[R3](rounds/round-3/README.md) |
| 評委 | [評分與意見](verdicts/README.md) | Torvalds persona 的評分、路線判斷、「現在就得拍板會選哪個」。 | [R1](verdicts/round-1.md)｜[R2](verdicts/round-2.md)｜[R3](verdicts/round-3.md) |
| 資料員 | [資料包](packs/README.md) | 卡點在 repo 與兄弟專案裡的現成資料（附路徑）、還是查不到的。第 3 輪之後沒有備料。 | [R1 後](packs/after-round-1/README.md)｜[R2 後](packs/after-round-2/README.md) |

> 只看坑，直接進 [`rounds/round-N/pits.md`](rounds/round-2/pits.md)。
