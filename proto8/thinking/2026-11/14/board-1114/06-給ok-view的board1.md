給 ok-view 的布告欄格式 `board/1`（草案）：從 02 fable 稿第七節抽出、照 05 採納表 A7／A14／A16 改過，可整份轉交；欄位只加不改名，等使用者裁 U1～U7 後才算定。

# board-1114 06 給 ok-view：`board/1` 布告欄格式

← [board-1114](../board-1114.md)｜出處 [02 §七](02-fable稿.md#七給-ok-view-的布告欄-schema可單獨抽出先交)＋[05](05-採納表.md)｜2026-11-14

## 七、給 ok-view 的布告欄 schema（可單獨抽出，先交）

> 這一節自成一份，可以整節複製給 ok-view。狀態：**草案 `board/1`**，等使用者看過才算定；欄位只會加、不會改名。

### 7.1 檔在哪

| 誰的 | 路徑 |
|---|---|
| 任一隻 proc | `<它的 stack>/board.json`（跟 `state.json` 同一層；寫的人用「暫存檔＋rename」，讀的人不必加鎖） |
| 使用者 | `~/.aos/user/board.json`（定案前仍在 `~/.aos/view/board/user.json`，見待裁 U4） |

沒有這個檔＝沒貼，是常態，不是錯。全景頁只讀、不替 agent 寫；使用者那張由網頁的「貼上布告／清空」寫。

### 7.2 欄位

| 欄位 | 型別 | 必有 | 顯示建議 |
|---|---|---|---|
| `format` | `"board/1"` | 是 | 不是這個值就當沒貼 |
| `updated_at` | ISO 8601 UTC 毫秒 | 是 | 「幾分鐘前貼的」 |
| `mode` | `here`／`busy`／`dnd`／`away` | 是 | 卡片上的小標：在／在忙／請勿打擾／不在 |
| `text` | 字串 ≤1000 | 否 | 員工卡最上方主文 |
| `doing` | 字串 ≤200 | 否 | 一句「在忙什麼」 |
| `waiting_on` | `[{who, what, since_at, ref?, level?, notified_at?}]` ≤20（who／what／since_at 必有） | 否 | 「在等 X：什麼事（多久了）」；`who` 是 proc 名字或 `"user"` |
| `back_at` | 時間 | 否 | 「預計幾點回來」 |
| `back_text` | 字串 ≤100 | 否 | 有就優先顯示這句白話 |
| `expires_at` | 時間 | 否 | 過了就標灰 |
| `accept` | `low`／`normal`／`urgent`／`none` | 否 | 可不顯示 |
| `deputy` | 名字 | 否 | 「急事找 X」 |
| `by` | `self`／`auto`／`user` | 否 | 可不顯示 |
| `seq` | 整數 | 否 | 拿來判斷要不要重畫 |
| 其他 | — | — | **不認得的鍵一律忽略** |

### 7.3 讀進來之後照這四步算（照 Argon A7、A14 改過）

1. 讀不了或 `format` 不對 → 沒貼（讀失敗重試一次）。
2. 時鐘校正：`updated_at` 比現在晚超過 5 分鐘 → 當成現在（時鐘不準），標 `clock_odd`。
3. 過期：現在超過 `expires_at`；或沒有 `expires_at` 且超過 `updated_at` 加 24 小時（**不分 mode，here 也算**）→ **文字照顯示但標灰，`mode` 當 `here`，`waiting_on` 不算數**。
4. 這隻 proc 的 phase 是 sleeping／stopped → 不管布告欄寫什麼，都算「不在」（頁面本來就有灰燈，這裡只是讓計數一致）。

`back_at` 已過而貼文沒過期 → 加註「已超過預計時間」。

### 7.4 三個彙總數字怎麼算（都用第 7.3 算完的結果）

| 全景頁要的 | 算法 |
|---|---|
| 部門卡「幾隻請勿打擾」 | 沒過期且 `mode` 是 `dnd` 的隻數 |
| 部門卡「幾隻在等人」 | 沒過期且 `waiting_on` 不空的隻數 |
| 左欄待辦「在等使用者的」 | 沒過期且 `waiting_on` 有 `who == "user"` 的每一筆，顯示 proc 名字、`what`、`since_at` |

### 7.5 JSON Schema 草案骨架

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "comm/1/board",
  "title": "aos board (comm/1)",
  "type": "object",
  "required": ["format", "updated_at", "mode"],
  "additionalProperties": true,
  "properties": {
    "format": { "const": "board/1" },
    "updated_at": { "$ref": "#/$defs/time" },
    "mode": { "enum": ["here", "busy", "dnd", "away"] },
    "seq": { "type": "integer", "minimum": 0 },
    "by": { "enum": ["self", "auto", "user"] },
    "text": { "type": "string", "maxLength": 1000 },
    "doing": { "type": "string", "maxLength": 200 },
    "waiting_on": {
      "type": "array", "maxItems": 20,
      "items": {
        "type": "object", "required": ["who", "what", "since_at"], "additionalProperties": true,
        "properties": {
          "who": { "type": "string", "minLength": 1 },
          "what": { "type": "string", "maxLength": 200 },
          "since_at": { "$ref": "#/$defs/time" },
          "ref": { "type": "string" },
          "level": { "enum": ["urgent", "normal", "low"] },
          "notified_at": { "$ref": "#/$defs/time" }
        }
      }
    },
    "back_at": { "$ref": "#/$defs/time" },
    "back_text": { "type": "string", "maxLength": 100 },
    "expires_at": { "$ref": "#/$defs/time" },
    "accept": { "enum": ["low", "normal", "urgent", "none"] },
    "allow_from": { "type": "array", "items": { "type": "string" } },
    "wake_on_urgent": { "type": "boolean" },
    "clear_on_start": { "type": "boolean" },
    "deputy": { "type": "string" },
    "ext": { "type": "object" }
  },
  "$defs": {
    "time": { "type": "string", "format": "date-time",
              "description": "ISO 8601 UTC with milliseconds, same as letter.json sent_at" }
  }
}
```

### 7.6 假資料（照這個先做版面）

```json
{"format":"board/1","seq":7,"updated_at":"2026-11-14T06:30:00.000+00:00","by":"self",
 "mode":"dnd","text":"跑全量測試中，結果出來前別丟新工作給我",
 "doing":"ok-board 規劃第 2 稿",
 "waiting_on":[{"who":"user","what":"布告欄協議 6 題待裁","since_at":"2026-11-14T05:10:00.000+00:00"},
               {"who":"ok-sec","what":"uid 粒度","since_at":"2026-11-14T04:00:00.000+00:00"}],
 "back_text":"測試跑完（約一小時）","expires_at":"2026-11-14T08:30:00.000+00:00","deputy":"repo-aos"}
```

```json
{"format":"board/1","updated_at":"2026-11-14T15:00:00.000+00:00","by":"user",
 "mode":"away","text":"去睡了","back_text":"明早","back_at":"2026-11-15T00:00:00.000+00:00",
 "expires_at":"2026-11-15T03:00:00.000+00:00"}
```
