<!-- 說明離線待裁頁的產生、回覆讀寫、裁定落地與 SVG 樣式。 -->
# 這是什麼

把一批題目資料做成離線互動頁，點選、補充後複製一行回覆，再讀回原資料。沒看過的題帶 `?`，仍算待定、不算裁定，之後再問。

## 指令

以下省略共同前綴 `python3 wf/tools/decide_page/decide_page.py`；`DATA` 是題目 JSON。

| 範例 | 用途 |
| --- | --- |
| `check DATA` | 檢查欄位、題號、推薦與來源；缺來源或原話只提醒。 |
| `build DATA --out ~/Desktop/review.html` | 產生單檔頁；省略 `--out` 時寫到 `~/Desktop/aos-<batch>-待你裁.html`。 |
| `parse DATA REPLY_FILE` | 按題目順序印 JSON Lines；也收 `-`、`--text STR` 或 `--from-board ASK_ID`。 |
| `apply DATA REPLY_FILE` | 把回答、狀態、備註與本機日期寫回資料；輸入方式同 `parse`。 |
| `land DATA` | 依來源分組印出可貼回文件的裁定；未回答的題列在末尾。 |

## 錯誤代號表

錯誤訊息在 stderr，結束碼非零；`--help` 印英文用法，結束碼 0。

| 代號 | 意思 |
| --- | --- |
| `ArgumentsBad` | 參數缺漏或組合不合規定。 |
| `FlagUnknown` | 未知旗標。 |
| `CommandUnknown` | 未知子指令。 |
| `FileMissing` | 找不到資料檔或輸入檔。 |
| `FileBad` | 其他檔案讀寫或文字編碼錯誤。 |
| `JsonBad` | JSON 無法讀取。 |
| `ContractBad` | `contract` 或 `kind` 不符。 |
| `FieldBad` | 欄位缺漏、型別或內容不符。 |
| `IdDuplicate` | 題號重複。 |
| `SectionUnknown` | 題目所屬章節不存在。 |
| `RecommendBad` | 推薦代號不在該題選項。 |
| `AnswerMissing` | 看板沒有該題回答。 |
| `BatchBad` | 回覆批名與資料不符。 |
| `ChoiceBad` | 回覆選項代號無效。 |

## SVG 可用 class 表

SVG 使用下列 class，顏色會隨「淺／深」切換。

| class | 用途 |
| --- | --- |
| `t12`、`t13`、`t14`、`t16` | 文字大小（px）。 |
| `s-ink`、`s-muted` | 正文、次要文字填色。 |
| `s-line` | 線條。 |
| `s-ask`、`s-fix` | 待裁、已修填色。 |
| `s-on`、`s-onfix` | 待裁、已修底色上的文字。 |
| `s-good`、`s-bad` | 正面、負面填色。 |
| `s-quote` | 原話底色。 |

## 檔案位置

| 路徑 | 用途 |
| --- | --- |
| `decide_page.py` | 命令列入口。 |
| `model.py` | 資料讀取、檢查與來源路徑。 |
| `render.py`、`web/page.css`、`web/page.js` | 完整靜態 HTML 與內嵌樣式、互動。 |
| `reply.py` | 回覆解析、套用與裁定文字。 |
| 出題線的 `decide_YYYYMMDD_短名.json` | 批次資料；來源路徑相對此檔所在資料夾。 |
| `${AOS_PROGRESS_DIR:-~/Desktop/aos-進度}/data/answers.jsonl` | `--from-board` 讀取的回答紀錄；同題取最後一筆。 |

瀏覽器用 `aos-decide-<batch>-<題號與選項短雜湊>` 保存選擇、備註與看過狀態；無法存取時仍可操作。主題使用 `aos-theme`。看板整批意見上限 20,000 字，請求上限 65,536 bytes。
