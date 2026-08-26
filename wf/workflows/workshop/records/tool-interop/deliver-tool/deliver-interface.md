# 追問輪：`aos deliver` 這支命令長什麼樣

← [本檔索引](README.md)｜[本場索引](../README.md)｜[workshop](../../../README.md)

投遞命令本身的介面與錯誤契約：合成版 `--help`、寫檔與 rename 順序、退出碼、誰驗證，以及驗不過時給模型看的那份 JSON。

---

## 追問輪：那支投遞 tool 到底長什麼樣

### `aos deliver` 的合成版 `--help`

**四位獨立地都把工具命名為 `aos deliver`**，也都讓一個呼叫等於一批原子投遞。共同形狀可以先
寫成：

```text
aos deliver [WORLD] [-f FILE|-] [--key K] [--durable]

讀取：FILE 或 stdin；WORLD 預設目前資料夾。
輸入：一筆 instruction object 或一批 instruction array（是否兩者都收，仍未拍板）。
動作：全批驗證成功後，原子發布到 WORLD 的 instruction 投遞區；不執行、不彙整。
成功：stdout 輸出一筆 JSON，至少含 published 狀態、count，receipt 是否必備待定。
失敗：不發布；輸出結構化 JSON 錯誤並使用非零退出碼。
```

這是共同比例最高的介面形狀，不是已定規格。四份原始 `--help` 的差異如下：

| 誰 | 命令形狀 | 輸入單位 | 成功輸出 | 額外旗標／特點 |
|---|---|---|---|---|
| **資深工程師** | `aos deliver [--key K] [--durable] <inst-file>` | 只明寫 instruction array；一 array＝一批 | `{"ok":true,"receipt":"R","state":"published\|already","hash":"…"}` | 以 inst-file 當目標；把 key／durable 放進第一版 |
| **資深架構師** | `aos deliver [--file FILE] [FOLDER]` | 單筆 object 或 array | `{"ok":true,"delivery":"1234-k7pz","count":2}` | FOLDER 預設 `.`；沒有 key／durable 旗標 |
| **資深研究人員** | `aos deliver [W] [--to X.json]` | 單筆或 array | JSON，欄位未定 | W 預設 `.`；允許廣義 `--to`，由 `X.json` 推出 `X.tempd/` |
| **要接工具的開發者** | `aos deliver [WORLD] [-f FILE\|-] [--key K]` | 單筆或 array | `{"status":"published","receipt":"R","count":2}` | WORLD／FILE 均有預設；保留 key，沒有 durable |

三位允許單筆 object 或 array，工程師只明寫 array；所以「單筆自動視為一筆批次」很接近共同形狀，
但不是 4／4。`--key` 只有工程師與開發者在追問輪簽名中保留，架構師、研究人員沒有；`--durable`
只有工程師列入。這兩項不能從表決外推成已定。

更重要的是，`--key` 與[回頭審視](../../step-back-review.md)仍有未解矛盾：那輪四位剛指出 aggregate 會
刪除投遞檔，沒有 ledger 就不能承諾跨回合 Already／Conflict。本輪工程師、開發者重新寫回 key，
卻沒有補 ledger；架構師、研究人員則乾脆沒放。故 key 可以是候選 correlation／檔名，**目前仍
不能據此宣稱跨回合冪等。**

### 寫到哪裡、檔名怎麼配

**四位獨立地都給出同一個發布順序**：

1. 找到目標 world 的 `.aos/inst.tempd/`；研究人員的廣義版本是 `X.json` 對應 `X.tempd/`。
2. 以排他方式建立 `<pid>-<suffix>.json.temp`。suffix 分別是 nonce、隨機尾碼、首個空 `n`、
   `seq＋nonce`；**四位都沒有只靠 PID 保唯一。**
3. write-all；若有 durable 契約再做相應 fsync。
4. 驗證與寫入都完成後，在同一目錄 rename 去掉 `.temp`，成為 `.json`，此刻才讓彙整者看見。
5. 一個呼叫只發布一個檔；array 內順序保留。開發者另外明講：多次投遞的不同檔案之間不承諾順序。

這支 tool **只補「投遞」**。彙整、取件、執行、釋放仍由 `aos exec` 負責；它不把 payload 直接寫
進 `inst.json`，也不因投遞成功就推世界一回合。

### 退出碼還沒有共同編號

四位只對 `0＝成功` 有穩定重疊；其餘人把相同號碼分給不同錯誤，不能把任何一份直接稱為共同
契約：

| 誰 | 0 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| 工程師 | 成功／Already | 用法 | 格式／大小 | key 衝突 | I/O／耐久 | — |
| 架構師 | 成功 | payload 無效 | world／版本無效 | I/O／rename | — | — |
| 研究人員 | 成功 | 用法 | — | 驗證 | I/O | — |
| 開發者 | 成功／Already | 用法 | JSON | schema | key 衝突 | I/O |

已成形的是**錯誤種類要分開**：用法、world／版本、JSON parse、schema／大小、key conflict（若有
key）、I/O／rename／durability。數字、Already 是否算 0、world 無效與 payload 無效誰先判，仍要
拍板。

### 誰驗證、驗不過怎麼回

**四位獨立地都要求 Deliver 在 rename 前驗證完整 payload；驗不過就整批失敗，不發布任何可見
檔案。**工程師要求與 executor 共用 parser；開發者要求 aggregate 仍重驗，防止有人繞過 tool
直接塞檔。`$ref`／`$env` 這類執行期資料不在投遞時求值；能做的是驗它們的結構。

`.bad` 也因此有清楚邊界：它只隔離**繞過 Deliver**、直接進投遞區的壞檔。正常 tool-call 驗證
失敗，不留下 `.bad`，也不留下可見 temp；錯誤直接回給呼叫者修正。

## 給模型看的錯誤訊息

這題四份輸出非常接近。**四位獨立地都給了 JSON，而不是一句人類 prose**；架構師、開發者明確
指定寫到 stderr。模型需要的不是「invalid input」，而是能定位、能改參數的欄位：

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

四人的欄位名有 `path`／`field`／`at`／`pointer`，code 也有大寫與 snake_case 兩種；共同語意是：

- 哪一筆 record；
- JSON Pointer 或至少欄位路徑；
- expected 與 actual；
- 穩定 machine code；
- 一句可執行的 hint，讓模型修 tool arguments 再呼叫。

**沒有人真正回答「給人看的版本長什麼樣」。**四位都把 machine JSON 做得很具體，但沒有提出
human-readable renderer、是否預設 JSON、或用 `--json` 切模式。這一塊不能由書記補答案；只能記
成追問輪仍漏掉的半題。
