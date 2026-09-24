# dev-env — 開發環境、指令、外部工具

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

這台機器上要能開發需要什麼、怎麼裝、跑什麼指令；外部工具設定與 env var 也收在這裡。

**何時用**：fresh clone、換機器、裝不起來、忘了指令、要加一個外部工具或環境變數。
**何時不用**：驗證 / 測試怎麼跑 → [testing](testing.md)；程式碼慣例 → [common/conventions](common/conventions.md)。

## Done when

- 照「流程（fresh clone 後）」走完，`{{冒煙指令，如 npm run build}}` 回傳 0。
- 下面三張表沒有空欄；要使用者親自做的（帳號、授權、金鑰）在 [WAIT_USER](../WAIT_USER.md) 各佔一行。

## 流程（fresh clone 後）

1. {{取得完整原始碼，如 git submodule update --init}}
2. {{安裝依賴，如 npm ci}}
3. {{設定 env var：複製 .env.example → .env，填下方「外部工具與 env var」表的值}}
4. {{跑一次冒煙指令確認裝好了，如 npm run build}}

## 指令表

| 做什麼 | 指令 | 備註 |
|--------|------|------|
| 安裝依賴 | `{{npm ci}}` | {{何時要重跑}} |
| build | `{{npm run build}}` | |
| 跑起來 | `{{npm run dev}}` | {{port / 進入點}} |
| lint / format | `{{npm run lint}}` | |

驗證與測試指令不列這裡——連同「誰跑」一起在 [testing](testing.md)。

## 跨機 / 離線差異

| 環境 | 能跑 | 跑不了的 → 怎麼辦 |
|------|------|------------------|
| `{{主力機}}` | {{全部}} | — |
| `{{離線機 / CI / 容器}}` | {{可跑的子集}} | {{改跑什麼；真的跑不了就記 WAIT_USER}} |

> 〔導入判斷〕只有單一開發環境、沒有離線／CI 差異 → 刪掉本節與上表。同步：`workflows/testing.md` 三欄表的「誰跑」欄（全部由 agent 跑）、`WAIT_USER.md` 裡因環境而卡的條目。

## 外部工具與 env var

| 名稱 | 用途 | 怎麼取得 / 設定 |
|------|------|----------------|
| `{{工具名}}` | {{用途}} | {{安裝方式與版本要求}} |
| `{{ENV_VAR}}` | {{用途}} | {{放哪、預設值；金鑰不進 repo}} |

需要帳號、付費、授權才能取得的：守鐵律 2（授權來源），並在 [WAIT_USER](../WAIT_USER.md) 記一行。

## 交接

- 環境就緒要開工 → [feature-dev](feature-dev/README.md)；先確認驗證跑得動 → [testing](testing.md)。
- 同一個裝機坑第二次撞到 → [common/gotchas](common/gotchas.md)。
