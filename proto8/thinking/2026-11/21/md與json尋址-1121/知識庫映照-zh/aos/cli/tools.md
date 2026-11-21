# `knowledge/aos/cli/tools.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/tools.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 登記與呼叫工具

用 aos-tools 編輯登記表（registry），並用 stdin 給 JSON 呼叫一個登記過的工具。

```sh
aos-tools --file tools.json add --name read ../lib/tools/base/read
aos-tools --file tools.json ls --json
printf '%s' '{"path":"a.txt"}' | aos-tools --file tools.json call read
aos-tools --file tools.json rm read
```

---

**`#/registry`**

# 登記表

預設的登記表是 `./tools.json`；登記表不存在就表示沒有工具。`--file` 放在子指令前面或後面都可以。登記表可以帶 `"$override": OTHER_FILE`（或一串檔案）：這時它只記和那個檔不同的地方，後面的勝出，值是 `null` 的項目就不是工具。add/rm 只寫 `--file` 那份登記表，絕不寫它蓋過的那個檔。`aos-tools --file F override BASE`（或 `--path-json JSON`）把 F 變成這樣一份差異清單。

---

**`#/add`**

# add

add 接受資料夾、JSON 檔或可執行檔。路徑從 cwd 解析。存下的路徑保留你給的形式：絕對路徑存成絕對的；相對路徑存成相對於被寫入的那份登記表所在的資料夾。`--path-json JSON` 把路徑字串或指示詞（directive）照給的存，例如 `{"$env": "AOS_HOME", "$path": "/lib/tools/base/shell"}`（每台機器設一次 `AOS_HOME`）；它每次使用時才解析，絕不寫回去。解析不到東西的路徑給 `PathMissing`（get 和 call 還會指出它來自登記表的哪個欄位）。它印一行 `added NAME -> PATH (FILE: STORED)`。`--name` 蓋過預設的檔名／資料夾名；名字是 `[A-Za-z0-9_-]`，最多 64 個字元（不然是 `NameBad`）。重複給 `ToolExists`；`--replace` 取代它。旗標放在路徑前面或後面都可以。`--no-cache` 只用於可執行的工具定義。

---

**`#/ls_rm_get`**

# ls、get、rm

rm 先比對登記的名字，比不到再比路徑。它移除所有比中的，每個印一行 `removed NAME (FILE: key deleted)`（被蓋過的檔有這個名字時印 `set to null over BASE`）；檔案本身留著。ls 印 NAME TAB 它描述的第一句（要看完整的用 get）；`ls -l` 印 NAME TAB KIND TAB PATH TAB FROM TAB STORED TAB ENV；`--json` 印一個帶工具定義的陣列；`-l` 和 `--json` 一起用是 `ArgumentsBad`。get 把比中的定義印成 JSON 物件。壞掉的登記工具（路徑不見、定義缺了或壞了）不會擋住 ls：它會得到一行警告，指出它是誰、怎麼修，ls 顯示 `NAME TAB broken: CODE (...)`（在 `-l` 裡 KIND 是 `broken`），`--json` 把它略掉，ls 以 0 結束。對它做 get NAME 和 call NAME 會用它自己的錯誤失敗（例如 PathMissing）。登記表檔案不是 JSON 或形狀不對，仍然是錯誤。

---

**`#/call`**

# call

`call NAME [ARGS_JSON]`：參數來自第二個引數，省略時來自 stdin。每個工具都在 stdin 收到原封不動的 JSON 輸入。`aos-tools call` 給它一個臨時 stack：有設 `$AOS_STACK` 時是 `<parent>/tools/<registered-name>/`，不然是 aos-exec 的預設。登記表的 `env` 改不了那個 stack。有設 `$AOS_STACK` 時，工具還會拿到 `AOS_STACK_IN_CALLER=tools/NAME`（它的資料夾在你 stack 裡的位置），所以它印出的 `$AOS_STACK/tools/NAME/...` 這種路徑，照寫的從你的 stack 就打得開。臨時資料夾不會事先建好（aos-exec `--stack-lazy`）；寫到那裡的工具自己建。

call 回傳工具的結束碼（訊號 N = 128+N）。非零結束且帶 `aos-tools: error:`，表示是 aos-tools 失敗；沒有那行，就是工具自己的代碼。要把同一批工具給外部 agent，用 `aos-mcp`（`aos/cli/mcp.json`）。

其他代號：`CommandUnknown`、`RegistryBad`、`ToolDefMissing`、`ToolDefBad`、`ToolMissing`、`DotenvBad`、`DirectiveBad`、`CommandMissing`、`WriteFailed`（見 aos/errors.json）。更多旗標：跑 `aos-tools SUBCOMMAND --help`。
