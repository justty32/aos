# 新手試用：author aos 題型（三關檢查器）

← [總表](README.md)｜受測：`proto7-2/packs/author/checkers/README.md`｜試用者：Claude Haiku、gpt-6-luna（effort low），只准讀 README 與 `--help`，在 `/tmp` 暫存目錄操作；原始回報見 [raw/author-aos-haiku.md](raw/author-aos-haiku.md)、[raw/author-aos-luna.md](raw/author-aos-luna.md)

## 結果

| 項目 | 值 | 門檻 | 過 |
|---|---|---|---|
| 第一次跑（人類估計分鐘） | 11 | ≤10 | 否 |
| 對外指令 | 3（brief／check／publish） | ≤3 | 是 |
| 新概念（兩位取多） | 6 | ≤5 | 否 |
| 分數（兩位取差） | 6.2 | ≥7 | 否 |
| **總判** | **不過**（分鐘、概念、分數） | | |

跑通情況：Haiku 跑通（改 --reviewer rules、publish 到臨時 clone）；**luna 失敗**：valid 候選在第二關「沒有實際測試」、連不到 user scope bus，publish 也失敗，後面取分支指令跟著錯。

## 五條分數

| 標準 | Haiku | luna |
|---|---|---|
| 容易上手 | 7 | 6 |
| 容易理解 | 5 | 5 |
| 複雜的藏起來 | 6 | 6 |
| 外層簡單但全面 | 7 | 7 |
| 要背的少 | 7 | 7 |
| 平均 | 6.4 | 6.2 |

## 卡點（新手視角，依嚴重度）

1. 沒有 user scope（systemd --user bus）的環境裡，第二關直接失敗，訊息只說「沒有實際測試」，README 沒說這時要加 `--no-scope`（luna；在 codex 沙箱裡發生，ssh／容器的新手也會碰到）
2. publish 預設寫進「檢查器所在的 git 根目錄」，第一次跑就照抄會在真 repo 開分支；新手不敢跑（Haiku 改用臨時 clone）
3. 預設 reviewer 是 astra，不知道 astra 要什麼環境；check JSON 的 gate 2、3 是 `ok: null` 沒解釋（Haiku）
4. 範例是 bash 寫法，zsh 照貼失敗，README 沒說要 bash（Haiku）

## ELI5

這是檢查學徒交來的新工具的三道門：先看格式、再跑測試對答案、最後審查。給它需求單和學徒的候選檔，三關都過才開一個新分支讓人決定要不要合併。看退出碼 0 還是 2 就知道過不過。

## ELI5 之後還複雜嗎

是（兩位都說是）。三個指令好懂，但退出碼 0／2／3／4、reviewer 選哪個、scope 失敗怎麼辦 ELI5 說不清。

## 回改

狀態：未改（交頂層轉該隊）。改完由 U 隊用同樣兩位新手再試一次。

- [ ] 第二關因 scope 起不來時，錯誤訊息直接提示「改用 --no-scope」，README 第一次跑也寫一句
- [ ] 第一次跑的 publish 改成預設寫臨時 clone，或明寫「這行會在你的 repo 開分支」
- [ ] 第一次跑直接用 `--reviewer rules`（不需外部環境），astra 留到進階
- [ ] 說明 gate `ok: null`＝前關失敗沒跑；範例標明用 bash
