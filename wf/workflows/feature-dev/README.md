# 功能開發（feature-dev）— 工作流入口

← [INDEX](../../INDEX.md)｜[AGENTS.md](../../../AGENTS.md)

新增／修改 aos 功能的工作流：加一個功能、修一個 bug，從動手到 commit。這是本工作流的**入口**：先讀本檔，再往下深入。always-on 鐵律見 [AGENTS.md](../../../AGENTS.md)；碰原始碼前先讀 [common/conventions](../common/conventions.md)（程式碼慣例 + code map 維護鏈）與 [common/code-map](../common/code-map.md)；要整理結構時參考 [STRUCTURE](../../STRUCTURE.md)（被動）。

**何時用**：使用者說「我想開發／修改某個功能」「這裡壞了，修一下」——**修 bug 也走這條**，產出一樣是「行為改變＋驗證綠燈」。
**何時不用**：只是要查清楚原因、還不動碼 → [investigation](../investigation.md)；行為不變、只重排結構 → [refactor](../refactor/README.md)；還在討論要不要做、方案長怎樣 → [planning](../planning.md)（ideas／roadmap）；動工前先過 [roadmap](../roadmap.md) 看這階段要先裁什麼。

## Done when

- [testing](../testing.md) 標「改完必跑」的驗證指令回傳 0，ctest 全綠。
- [common/code-map](../common/code-map.md) 中該領域的列已更新（新增／刪除的檔、職責變動、測試位置）。
- 下表對應的文檔已補；要使用者實機驗證的在 [WAIT_USER](../../WAIT_USER.md) 有一行；跨 session 沒收尾的在 [SESSION-LOG](../../SESSION-LOG.md) 有一行。

## 流程

```
讀 code map 找到相關領域（只讀清單裡的檔）
  → 增量修改（守 conventions）
  → 跑自動驗證（從 repo 根目錄 cmake --build --preset default && ctest --preset default）綠燈
  → 交使用者驗證（若需實機/實環境）→ 回報問題 → 修 → 重複
  → 全數通過後：補齊 code map → 補文檔 → commit
```

- **自動驗證是你（Claude）自己跑**的把關（鐵律：改完跑驗證）。
- **Claude 跑不了的驗證一律由使用者做**——先靠自動驗證＋結構性檢查把握到極限再交付；需使用者驗證的記到 [WAIT_USER](../../WAIT_USER.md)（見 [testing](../testing.md) 的「誰跑」欄）。
- 測試迭代期間，code map / 文檔可暫時落後；**commit 前必須對齊**。
- **「補文檔」要補哪幾份**，依改動的性質而定，不要漏：

  | 改了什麼 | 要跟著改 |
  |---|---|
  | 某個小專案的內部行為 | 該小專案的 `docs/`（如 `core/inst/docs/`）＋ [code map](../common/code-map.md) |
  | 建置骨架、CMake 函式、相依管理 | [`docs/build.md`](../../../docs/build.md)、[`docs/subprojects.md`](../../../docs/subprojects.md)、[add-subproject 工作流](../add-subproject.md) |
  | 公開 API、子命令、退出碼 | [`docs/usage.md`](../../../docs/usage.md)、[use-aos 工作流](../use-aos.md) |
  | `.aos` 版面、回合模型、交接協定 | [PROTOCOL](../dispatch/proto/PROTOCOL.md)（唯一真源）＋ 對應的 ideas 檔與 [verdicts](../ideas/verdicts.md) |
  | 頂層結構（多／少了目錄）| [INDEX](../../INDEX.md)、根 `README.md` |

  **文件裡寫的每一條指令與輸出都要真的跑過再寫上去**，不要照推論寫。
- 實作中被迫下的新裁決＝正式裁決：記回 ideas 對應檔 ＋ [verdicts](../ideas/verdicts.md)（[roadmap](../roadmap.md) 常備規則 2）。
- 跨 session 時在本工作流 `session-log.md` 補一行 `[功能名] 文檔/code map 待同步`，下個 session 不會誤判已同步。

## 內容

| 檔案 | 內容 |
|------|------|
| `landed/`（長出來才建）| 已落地功能目錄（時間序；功能在哪、實作細節指標）|
| `gotchas.md`（長出來才建）| 本工作流專屬踩坑（共通的在 [common/gotchas](../common/gotchas.md)）|
| `session-log.md`（長出來才建）| 本工作流 open / in-flight 進度（hub 在 [SESSION-LOG](../../SESSION-LOG.md)）|
| `archive/`（長出來才建）| 過時／被取代的文檔封存（保留歷史、不污染現役；規則見 [STRUCTURE](../../STRUCTURE.md)）|

> 上表各檔都是**長出來才建**（見 STRUCTURE 四級成長軌跡），不要預先建空檔。本入口檔若膨脹，照 [STRUCTURE](../../STRUCTURE.md) 拆。

## 交接

- 驗證怎麼跑 → [testing](../testing.md)；改到一半發現該先整理結構 → [refactor](../refactor/README.md)。
- 為什麼選這個做法 → [decisions](../decisions.md)（verdicts）；卡在使用者 → [WAIT_USER](../../WAIT_USER.md)。
