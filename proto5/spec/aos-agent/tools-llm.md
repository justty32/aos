← [aos-agent](README.md)｜[tools-dev.md](tools-dev.md)｜wrap-cli 細節：[tools-wrapcli.md](tools-wrapcli.md)｜實作：[tools_dev](../../lib/aos_agent_tools_dev.py)｜模型入口：[aos_llm_ask](../../lib/aos_llm_ask.py)

# 1.8（續二）模型提案、人確認才寫入：`--describe-with-llm`（09-24 第三波 W3-2）

```
aos-agent tools wrap-cli CMD [--name PACK] [--out DIR] [--force] [--help-file F]
                             [--describe-with-llm [--model ALIAS] | --spec FILE]
aos-agent tools wrap-py  FILE.py [既有選項] [--describe-with-llm [--model ALIAS] | --describe FILE]
```

共通規矩同 [tools-dev.md](tools-dev.md)（不收 `--target`、用法錯退 2、其他錯 `aos-agent: 代號: 白話` 退 1、暫存資料夾＋rename、`--force`、`BadName`）。

## 模型那一步（兩個指令一樣）

- `--describe-with-llm`：叫模型**一次**（`aos_llm_ask`：`AOS_LLM_CONFIG`、temperature 0、不重試；`--model` 是 llm.json 的代號，省略＝`default`）。模型回的東西逐格過**機械檢查**，不過的那格丟掉並列出。
- **不產包**：只寫提案檔（暫存＋rename；已在要 `--force`，而且在叫模型之前就先擋），印表，stderr 印一行 token 與毫秒，最後一行告訴人怎麼套用。
- 人看過（可以改）→ 用 `--spec`／`--describe` 產包，這一步**不叫模型**。提案檔記原文的 sha256，對不上就拒。人給的提案要整份過機械檢查，有一條不過就整個拒（不像模型那次只丟那格）。
- `--model` 只跟 `--describe-with-llm`；`--describe-with-llm` 不跟 `--spec`／`--describe` 一起給（都是用法錯）。
- 模型那一步的錯：沒設 `AOS_LLM_CONFIG`＝`ConfigInvalid`，端點錯＝`EngineFailed`／`Timeout`，回的不是 JSON 或沒 `params`＝`BadModelOutput`；這些都不寫提案檔。
- 怎麼從回話抽 JSON（`aos_llm_ask.parse_json`，09-25 收尾 S4）：前後多的話、``` 圍欄（大小寫、沒收尾的也行）都容忍；只收物件或陣列；整段只是純量（數字、一句字串、`"[]"`）、同一物件重複 key、`NaN`／`Infinity`（含 `1e999` 這種溢位成無限大的數字）一律 `BadModelOutput`，整份不收。往後找只在最外層找：一個 `{`／`[` 解不開（例如被截斷），它裡面的片段一律不撿（複審 M1、M3）。欄位少了、型別錯了不算這一步的錯，照下面的機械檢查逐格或逐條丟。

## `tools wrap-py FILE.py --describe-with-llm`／`--describe FILE`

**問什麼**：收了的函式裡，沒 docstring 的要描述、沒說明的參數要說明；一個檔**一次呼叫**，送那些函式的原始碼。全都有＝`NothingToDescribe`（不叫模型）。

**模型回** `{函式名: {"description", "params": {參數: 說明}}}`。機械檢查：只收這次收了的函式與它的參數名；非空、壓成一行後 ≤ 200 字、不含控制字元（ESC、NUL…，審查 S1）；**已有 docstring 的描述、已有說明的參數不覆蓋**（丟掉並列出）。

**提案** `<out>/<PACK>.describe.json`：`{"_type": "aos_wrap_py_describe", "_version": 1, "source", "sha256"（原檔）, "generated", "model", "alias", "usage", "ms", "functions", "dropped"}`。印表「函式｜現在的描述（沒 docstring＝函式名）｜模型提的」＋參數說明，最後一行 `aos-agent tools wrap-py FILE --describe <提案檔>`（原本帶的 `--only`／`--name`／`--out` 照抄；路徑都做 shell quoting）。

**`--describe FILE`**：`_type` 不對或任何一條不過檢查＝`DescribeInvalid`；原檔 sha256 不同＝`SourceChanged`；提案裡這次沒收（`--only` 沒點名）的函式略過並警告。補好後照一般 wrap-py 產包，`wrap.json` 多 `describe: {file, sha256, functions}`。

## `tools wrap-cli CMD`

一支命令列指令 → 一支工具：參數表從 argparse 原始碼或 help 文字機械解出來（或模型提案、人看過），產包重用 wrap-py 那套發布。細節（解析規則、參數表格式、`--spec`、產的 `run`）見 [tools-wrapcli.md](tools-wrapcli.md)。
