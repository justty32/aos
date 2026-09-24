← [tools](../README.md)｜人用的兩支指令：[aos-json／aos-directives](../../spec/aos-agent/tools-files.md)｜工具時代報告：[t3](../../notes/2026-09-24-tool-era/t3/README.md)

# files 工具包：按位置改 JSON、按標題改 Markdown

兩支給模型用的工具，都**不叫模型**、純 Python 標準庫。跟 base 的 `edit` 差在：不靠字串取代，模型改 JSON 不會再壞在逗號括號，改 md 不會切錯段。

```sh
aos-agent tools add files --target $W/bob     # 工作根目錄跟 base 一樣：關牢時是牢裡的起點，不關牢時看 tools/files/config.json 的 root
```

| 工具 | 一句話 | 參數（* 必填） |
|---|---|---|
| `json_edit` | 用 JSON Pointer 讀／改 JSON 檔的一個位置 | `path`*、`op`（`get` 預設／`set`／`del`／`append`／`merge`）、`pointer`（`""`＝整份、`/a/b/0`、set 的最後一段 `-`＝陣列尾巴）、`value`、`expect_sha` |
| `md_section` | 按標題讀／改 Markdown 的一節 | `path`*、`op`（`get` 預設／`list`／`replace`／`delete`／`append_item`／`remove_item`）、`heading`（`## 進度`，`#` 可省）、`text`、`expect_sha` |

## 怎麼用才不會蓋掉別人的改動

`get`（md_section 的 `list` 也是）結尾一行 `sha=…`。寫的時候帶 `expect_sha`：檔在這之間被改過就回 `Conflict`（附現在的 sha），什麼都不寫——重讀、在新內容上重做。
同一個請求（同一個 `expect_sha`）重送兩次，第二次一定是 `Conflict`，所以 `append` 這種不冪等的動作也不會多做一次。`set` 成跟原本一樣的值＝`no change`、不寫檔。

## 規則

- **json_edit**：改完整份重新產生、再解析一次，是合法 JSON 才寫（`NaN` 之類寫不出去的值＝`BadArguments`）；原檔不是合法 JSON＝`JsonSyntax`、不動。
  照原檔的寫法重寫：縮排（空白幾格或 tab）、單行緊湊或有空白、`\uXXXX` 跳脫或直接寫中文、CRLF、結尾換行。原本寫在同一行的小陣列會被展開成多行（整份用同一種縮排）。
  `set` 的 `pointer` 是 `""` 而檔不在＝建新檔（父資料夾自動建）。`merge`＝JSON merge patch（RFC 7396）：值是 `null` 的鍵刪掉。
- **md_section**：一節＝標題那行到下一個同級或更高級標題之前（含子節）；程式碼區塊裡的 `#` 不算標題。
  `replace` 換本文、標題留著；`delete` 連子節一起刪。標題不只一個＝`NotUnique`（附行號；加上 `#` 指定級數）。
  `append_item`／`remove_item` 只看這一節自己的清單（不含子節）：`text` 要是一行、`- ` 開頭；這節原有的項目**都是** `- [工作流] 狀態 → 下一步` 格式時，新項目也要照這個格式，否則 `BadItem`。
- 檔案上限 10 MB；輸出超過 50 KB 截斷。寫檔一律同資料夾暫存檔＋rename，被 KILL 在半路只會留下一個 `.檔名.*.aos-tmp`、原檔完整，重跑同一行就好。

## 碰不到的東西

- 路徑關在工作根目錄裡（`OutsideRoot`），跟 base 同一份 `_common.py`（逐字複製；base 那份改了，測試 `test_common_is_base_copy` 會紅，照它的訊息再複製一次）。
- **保護檔名**：`config.json` 的 `protected`（預設 `SESSION-LOG.md`、`WAIT_USER.md`，團隊裡是書記在寫）＝寫入回 `Protected`，讀可以。
- **信任資料**（沒關牢時）：工具的 cwd 是 agent 家，照家裡 `info.json` 的**實際設定**算出人格、記憶、access 檔、工具檔與工具程式、`$ref` 引用到的檔（一路追下去）、家裡固定的 `info.json`／`state.json`／`tools/`／`prompts/`…，目標落在裡面＝`TrustedData`，不看檔名。
  關牢時不另外擋：權限牆本來就不准可寫的資料夾蓋到信任資料，牢裡寫不到。用 `$env`／`$fmt` 拼出來的路徑算不到——這條是防手滑，真正的邊界是牆。

## 錯誤代號

照 [tools/README](../README.md#錯誤長怎樣) 的格式（最後一行 JSON、退 1）。base 已有的：`BadArguments`、`NotFound`、`OutsideRoot`、`IsADirectory`、`BinaryFile`、`NotARegularFile`、`FileTooLarge`、`NotUnique`、`NoMatch`、`WriteFailed`、`RootMissing`、`ConfigInvalid`、`InternalError`。這包新加的：

| 代號 | 什麼時候 | 模型能自己修嗎 |
|---|---|---|
| `JsonSyntax` | 原檔不是合法 JSON | 能：先用 edit／write 修好 |
| `BadPointer`／`PointerNotFound` | pointer 寫法錯／那個位置不在（訊息列出那裡有哪些鍵、陣列多長） | 能 |
| `TypeMismatch` | `append` 的目標不是陣列、`merge` 的目標或值不是物件 | 能 |
| `Conflict` | `expect_sha` 對不上（附 `sha`） | 能：重讀再做 |
| `HeadingNotFound` | 沒這個標題（列出有哪些） | 能 |
| `BadItem` | `append_item` 的 text 不是一行 `- ` 開頭，或不合這節的格式 | 能 |
| `Protected`／`TrustedData` | 保護檔名／agent 的信任資料 | 不能：訊息叫它轉告 |

## 測試

[`lib/test/test_tools_files.py`](../../lib/test/test_tools_files.py)：五種 op、壞 pointer、改完非法不寫、`Conflict` 與重送不多做、縮排風格、信任資料（含 `$ref`、自訂路徑、工具資料夾、符號連結）、保護檔名、`tools add files` 裝得起來、描述字數。
