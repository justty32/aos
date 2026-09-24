← [aos-agent](README.md)｜[spec 總導航](../README.md)｜模型用的工具包：[tools/files](../../tools/files/README.md)、[tools/wf](../../tools/wf/README.md)

# 人用的檔案指令：`aos-json`、`aos-directives`（09-24 tool-era T3）

兩支都不叫模型、只用標準庫。沒料到的檔案錯誤代號是 `IOFailed`。錯誤印一行 `指令: 代號: 白話` 到 stderr、退 1；用法錯先印原因再印用法、退 2；`-h` 印用法退 0。

## `aos-json`：人用的 JSON Pointer 改檔

```
aos-json get    FILE [POINTER]
aos-json set    FILE POINTER VALUE [--expect-sha S] [--check-directives [--center DIR]]
aos-json append|merge FILE POINTER VALUE [同上]
aos-json del    FILE POINTER [同上]
```

- 寫入時持檔案所在資料夾的 flock（跟 `json_edit`、`md_section` 同一把），讀、比 sha、寫整段在鎖內。
- 跟模型工具 `json_edit` 同一份程式（`tools/files/_jsonedit.py`）：op、pointer、縮排風格、改完合法才寫、`Conflict` 都一樣（[files README](../../tools/files/README.md)）。
- VALUE 是 JSON 原文（字串要帶引號 `'"abc"'`；`-`＝從 stdin）；不是 JSON＝用法錯 2。
- 跟工具不一樣的地方：路徑照殼的目前資料夾算、**不關在工作根目錄、不擋信任資料**（人本來就能改自己的 agent）。
- `--check-directives`：改好、還沒寫的內容先照[指示詞規範](../directives/README.md)整份解一次（`--center` 是 `$ref` 的中心，沒給＝檔所在的資料夾；環境＝殼的環境），解不過照指示詞的代號退 1、不寫。改 `info.json`、`access.json`、工具檔時用。

## `aos-directives`：人格分節編輯＋解指示詞

```
aos-directives ls|versions|export [--out F.md]  [--target 家]
aos-directives show [SECTION]                    [--target 家]
aos-directives set SECTION (--text T | --file F) [--target 家]
aos-directives add "## 標題" [--text T | --file F] [--after SECTION] [--target 家]
aos-directives rm SECTION | import F.md | revert [ID]   [--target 家]
aos-directives resolve FILE [--center DIR] [--pointer /x]
aos-directives check FILE [--center DIR]
```

### 人格

- 人格檔＝家裡 `info.json` 的 `system`（解完指示詞；沒寫＝`prompts/system.json`），格式 `{"content": 字串}`（[agent §3.1](../agent/info.md)）。檔不在＝空人格（`add`／`import` 會建）。
- **分節**跟 `md_section` 同一份程式（`tools/files/_mdsec.py`）：一節＝一行 `#`～`######` 標題到下一個同級或更高級標題之前（含子節）；程式碼區塊裡的 `#` 不算。
  SECTION＝`ls` 的編號（`0`＝第一個標題之前的開頭，`1` 起是各標題）或標題文字（`#` 可省；同名兩個＝`NotUnique`，請用編號）。
- `set` 換本文、標題留著；`add` 加在最後或 `--after` 那節（含子節）之後，同名同級已有＝`AlreadyExists`；`rm` 連子節刪。
- `export` 印出或寫成 md 檔，給文字編輯器改；`import F.md` 整份換回去。人也可以直接改人格檔的 JSON（縮排 2、不跳脫中文）。
- **版本**：每次寫之前把舊的整份存到人格檔旁邊的 `.versions/<檔名>-<奈秒>.json`，留最近 20 份；`versions` 列、`revert [ID]`（省略＝最近一份）還原——還原前也先存一份，所以還原可以再還原。選版、讀版、存現在的、寫回整段在管理鎖裡；選的版本不在＝`NotFound`（不會當成空人格）。內容沒變＝印「沒改」、不寫、不存版本。
- 寫入持 `<家>/.admin.lock`（跟 `tools`、`access` 的寫入指令同一把），整份 `.tmp`＋rename。成功最後一行「下一次問模型就用新的人格，不用重 start」。
- `content` 不是字面字串（用了指示詞）＝寫入指令 `FieldTypeMismatch`，請直接編輯；`show`／`ls` 也同樣拒絕（只能看原檔）。

### 解指示詞（catalog T-directive）

- `resolve` 把一份 aos JSON 檔的 `$env`／`$ref`／`$fmt` 全部解開、縮排 2 印出；`$opt` 選項物件原樣留著、只解它的 `$val`。`--pointer` 走的是**原文**的位置（先走到那格再解）。
- `check` 只驗解不解得開：好＝`ok：…`，壞＝指示詞規範的代號（`ReferenceReadFailed`、`EnvMissing`、`Cycle`…）退 1。
- `--center`＝`$ref` 的中心路徑，沒給＝檔所在的資料夾（inst.json 的中心是解出來的 `cwd`，要一樣就自己給）。環境＝殼的環境；`$env` 讀到的值會照印出來（包括金鑰，注意別貼給別人）。

## 這一節沒管的

- 鎖只管走這套的寫者；人用文字編輯器、agent 用 base `write`／`edit` 改同一個檔時靠 `--expect-sha`。
- 人格以外的檔（記憶、工具檔）沒有版本；要還原就靠 git 或自己備份。
