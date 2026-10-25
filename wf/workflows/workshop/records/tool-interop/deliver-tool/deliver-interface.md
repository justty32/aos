# 追問輪：`aos deliver` 這支命令長什麼樣

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

投遞命令本身的介面與錯誤契約：合成版 `--help`、寫檔與 rename 順序、退出碼、誰驗證，以及驗不過時給模型看的那份 JSON。

---

## 追問輪：那支投遞 tool 到底長什麼樣

### `aos deliver` 的合成版 `--help`

工具叫 `aos deliver`，一個呼叫等於一批原子投遞。共同形狀（候選，不是已定規格）：

```text
aos deliver [WORLD] [-f FILE|-] [--key K] [--durable]

讀取：FILE 或 stdin；WORLD 預設目前資料夾。
輸入：一筆 instruction object 或一批 instruction array（是否兩者都收，仍未拍板）。
動作：全批驗證成功後，原子發布到 WORLD 的 instruction 投遞區；不執行、不彙整。
成功：stdout 輸出一筆 JSON，至少含 published 狀態、count，receipt 是否必備待定。
失敗：不發布；輸出結構化 JSON 錯誤並使用非零退出碼。
```

未定：

- 單筆 object 是否自動視為一筆的批次（多數接受，未全體一致）。
- `--key`、`--durable`、`--to`（由 `X.json` 推出 `X.tempd/`）哪些進第一版。
- 成功 JSON 的欄位：候選有 `ok`／`status`、`receipt`／`delivery`、`state`（`published|already`）、
  `count`、`hash`。

**`--key` 在沒有 ledger 前只能當 correlation／檔名，不能據此宣稱跨回合冪等**：aggregate 會刪除投遞檔
（見[回頭審視](../../step-back-review.md)），沒有 ledger 就無法承諾跨回合 Already／Conflict。

### 寫到哪裡、檔名怎麼配

1. 找到目標 world 的 `.aos/inst.tempd/`（廣義版本是 `X.json` 對應 `X.tempd/`）。
2. 以排他方式建立 `<pid>-<suffix>.json.temp`。suffix 用 nonce、隨機尾碼、首個空 `n` 或 `seq＋nonce`；
   **不能只靠 PID 保唯一。**
3. write-all；若有 durable 契約再做相應 fsync。
4. 驗證與寫入都完成後，在同一目錄 rename 去掉 `.temp`，成為 `.json`，此刻才讓彙整者看見。
5. 一個呼叫只發布一個檔；array 內順序保留。多次投遞的不同檔案之間不承諾順序。

這支 tool **只補「投遞」**。彙整、取件、執行、釋放仍由 `aos exec` 負責；它不把 payload 直接寫
進 `inst.json`，也不因投遞成功就推世界一回合。

### 退出碼還沒有共同編號

只有 `0＝成功` 是共識。已成形的是**錯誤種類要分開**：用法、world／版本、JSON parse、schema／大小、
key conflict（若有 key）、I/O／rename／durability。數字、Already 是否算 0、world 無效與 payload
無效誰先判，仍要拍板。

### 誰驗證、驗不過怎麼回

**Deliver 在 rename 前驗證完整 payload；驗不過就整批失敗，不發布任何可見檔案。**與 executor 共用
parser；aggregate 仍重驗，防止有人繞過 tool 直接塞檔。`$ref`／`$env` 這類執行期資料不在投遞時求值，
只驗它們的結構。

`.bad` 只隔離**繞過 Deliver**、直接進投遞區的壞檔。正常 tool-call 驗證失敗，不留下 `.bad`，也不留下
可見 temp；錯誤直接回給呼叫者修正。

## 給模型看的錯誤訊息

錯誤回 JSON，不回一句人類 prose（候選：寫到 stderr）。模型需要的不是「invalid input」，而是能定位、
能改參數的欄位：

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_FIELD",
    "record": 2,
    "pointer": "/1/argv/0",
    "expected": "string",
    "actual": "number",
    "hint": "argv 必須是字串陣列"
  }
}
```

欄位名（`path`／`field`／`at`／`pointer`）與 code 的大小寫寫法未定；共同語意是：

- 哪一筆 record；
- JSON Pointer 或至少欄位路徑；
- expected 與 actual；
- 穩定 machine code；
- 一句可執行的 hint，讓模型修 tool arguments 再呼叫。

**「給人看的版本長什麼樣」還沒有答案**：human-readable renderer、是否預設 JSON、或用 `--json` 切模式，
都沒人提出。
