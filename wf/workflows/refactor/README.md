# refactor — 重構 / 拆檔 / 整理結構

[WORKFLOWS](../../WORKFLOWS.md)

只改結構、不改行為。方法在 [STRUCTURE](../../STRUCTURE.md)，本檔只管流程。

**何時用**：STRUCTURE 門檻超標（單檔過大、資料夾雜亂），或使用者要求整理。
**何時不用**：順手改了行為 → [feature-dev](../feature-dev/README.md)；還沒搞懂現況 → 只讀直接查、筆記寫進當天的 proto8/thinking（舊的 investigation 工作流 11-17 已封存）。

## Done when

- [testing](../testing.md) 的建置指令回傳 0；行為不變靠讀碼與手跑確認。
- [code map](../../knowledge/code-map.json) 中受影響領域的列已更新（`code-map.json` 本檔手寫；`code-map/` 底下的逐檔表是生成物，交件時由 `wf/tools/commit-request` 排隊重生，不手改，見 AGENTS.md 鐵律 3）。

## 流程

1. 先跑驗證指令記下基準；紅的先修掉，別和重構混在一起。
2. 照 [STRUCTURE](../../STRUCTURE.md) 按職責拆／分類，不等分硬切。
3. 一次搬一塊，搬完就跑驗證。
4. 更新 code map 的領域列與所有指向舊路徑的連結；逐檔表不手改，搬過或職責變了的檔改檔頭那一句就好。

## 內容

| 檔案 | 內容 |
|------|------|
| [moving-things.md](moving-things.md) | 搬檔／改目錄名／拆 repo：六類會斷的東西與驗證程序 |
| [reports/](reports/) | 各輪重構與審查的舊報告，一輪一夾；11-17 起凍結，新的報告寫進當天的 `proto8/thinking/<月>/<日>/`（使用者 11-17 待裁網頁 wf-5ii 選 a） |
| `archive/` | 封存（索引在它的 README；11-17 已刪，見 git 歷史 c97d6ade8） |

## 交接

- 結構就位後要加功能 → [feature-dev](../feature-dev/README.md)；為什麼這樣拆 → [decisions](../decisions.json)。
