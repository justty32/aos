# deploy — 部署 / 上線 / 回滾

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

把指定版本送上目標環境並驗證；不對就回滾。

**何時用**：「部署」「上線」「發版」「回滾」。
**何時不用**：只想看現況 → [inventory](inventory.md)；線上壞了還沒定位 → [incident](incident.md)。

## Done when

- `{{部署驗證指令，如 curl -fsS https://<站>/version}}` 回傳這次的版本且健康檢查通過。
- 本次部署在 [WAIT_USER](../WAIT_USER.md) 開的列都已刪（＝沒有卡住的交接點）。

## 流程

1. **定版**：部署哪個 commit / tag、送哪個環境，寫出來讓使用者看到。
2. **建置**：`{{建置指令，如 npm run build}}`。
3. **交接點**：對照下表，本次會碰到的每列在 [WAIT_USER](../WAIT_USER.md) 記一行（`- [deploy] 請使用者… → 做完我接著…`），做完即刪。
4. **送上去**：`{{部署指令}}`。不可逆且對外，守**鐵律 2（授權來源）**——沒有當場確認就不送。
5. **驗證**：跑 Done when 的指令，再跑一輪 [inventory](inventory.md)。
6. 驗證不過 → 走下面「回滾」。

## WAIT_USER 交接點（哪幾關要人）

| 交接點 | 為什麼要人 |
|--------|-----------|
| `{{如：在 <平台> 後台按下 Deploy}}` | 需要使用者的帳號權限 |
| `{{如：填入 <服務> 的 token / 憑證}}` | 憑證不進 repo，agent 拿不到 |
| `{{如：實機 / 真裝置驗收}}` | 只有人看得出對錯 |

> 〔模板說明〕本表是**長期有效**的「這專案哪幾關要人」清單，填一次即可；每次部署當下卡住的那關才寫進 WAIT_USER.md（只列 open）。

## 回滾

1. 上一個正常版本：`{{如 git tag / 映像 tag}}`。
2. `{{回滾指令}}`——同樣守鐵律 2。
3. 回滾後跑 [inventory](inventory.md) 確認回穩，再開 [incident](incident.md) 查因。

## 交接

- 部署後出現異常 → [incident](incident.md)。
- 為什麼選這個部署方式 / 為何不回滾 → [decisions](decisions.md)。
