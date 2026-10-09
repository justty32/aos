# prompt 包 spec（第一版）

← [prompt 包](README.md)｜指示詞機制：`lib/aos_directives.py`（只 import，不改）｜下游：[llmcall](../llmcall/README.md)

只寫規則。路徑一律相對 node（`<node>` 是命令列第一個參數，必須是已存在的資料夾）；絕對路徑照用。

## 1. prompt.json

頂層是物件，只認四個 key（其他 key＝壞輸入）：

| key | 必填 | 內容 |
|---|---|---|
| `messages` | 是 | 陣列（或解完是陣列的指示詞），見 §2 |
| `model` | 否 | 字串，預設 `chatgpt-gpt-6-sol-high` |
| `max_chars` | 否 | 非負整數（bool 不算），預設 6000；0＝不折疊；命令列 `--max-chars` 優先 |
| `note` | 否 | 任意值，給人看的註解，不輸出 |

每個值都先用 `aos_directives.resolve_located` 解：`Context(Document(prompt.json 的路徑, 原始物件), base_dir=<node>, env=os.environ)`，位置＝實體路徑。優先序沿用函式庫：`$opt > $ref > $fmt > $env`。

## 2. messages 的每一項

照順序處理，結果累積成一張訊息表：

- `{"role": R, "content": C}`：R 是非空字串；C 照 §3 解成一個字串。其他 key＝壞輸入。
- `{"$opt": "append", "$val": X}`：X 解完必須是陣列，裡面每項照本節遞迴處理後接在後面。同一條遞迴鏈再遇到同一個（文件, 位置）的陣列＝`ReferenceCycle`。
- `{"$opt": "clear"}`：丟掉目前累積的訊息（不能帶 `$val`）。
- 選項名用 `option_names` 驗，表＝`append`（val required, alone）、`clear`（val forbidden, alone）。
- 解完的訊息表是空的＝壞輸入。

## 3. content：一段或多段

C 解完後：

- 字串＝一段。
- 陣列＝多段，每一項是字串或下面的讀檔選項（項目先解指示詞；陣列裡再放陣列＝壞輸入）。
- 讀檔選項（`option_names` 驗，三個都 val required、alone）；`$val` 解完是路徑字串，`n` 是正整數（bool 不算）：
  - `{"$opt": "file", "$val": 路徑}`：整個檔的文字。
  - `{"$opt": "tail", "$val": 路徑, "n": 40}`：最後 n 行（預設 40，以 `\n` 分行，保留原本行尾）。
  - `{"$opt": "latest", "$val": 資料夾, "n": 5}`：資料夾頂層 `*.md`（不含 `.` 開頭）照**檔名**由大到小取 n 個（預設 5；wf 信件檔名以時間開頭，所以就是最新的 n 封），每封寫成 `### <檔名>\n<內容>`，彼此以 `\n\n` 相接；沒有信＝空字串。
- 其他型別＝壞輸入。
- 多段以 `\n\n` 相接成一個字串（折疊在相接前，§4）。

## 4. ref 折疊

`max_chars > 0` 時，任一段長度（Python `len`）超過 `max_chars` 就折：

1. `sha`＝該段 UTF-8 的 sha256 hex（64 字）。
2. `<node>/refs/<sha>.json` 寫 `{"v":1,"sha":sha,"chars":長度,"text":原文}`（`aos7_fs.write_json` 原子寫）；已存在且整份內容相同就不寫，否則重寫（內容由 sha 決定，重寫無害）。
3. 段換成 `ref://<sha> 已折疊 <長度> 字，預覽：\n` ＋ 原文前 200 字。

展開（`expand`）：在字串裡由左往右找 `ref://<64 hex> 已折疊 <數字> 字，預覽：\n`，讀該 ref 檔，驗 `sha256(text)==sha`、長度相符、後面接的正好是 `text[:200]`，整塊換回 `text`，從換回的文字之後繼續找（不展開原文內部）。任何一項不符或讀不到＝unknown。保證（原文本身不含 §4 標頭時）：`expand(render(P, max_chars=m)) == render(P, max_chars=0)`。

## 5. 命令列

`aos7-prompt render <node> <prompt.json> [--out FILE] [--max-chars N]`

- 先把整份解完、讀完檔，才開始寫 ref 檔，最後才寫輸出；任何失敗都**不輸出請求、不寫 FILE**（已有的 FILE 不動），只印失敗回條。請求已提交後回條印不出來，不改變結果（仍退出 0）。
- FILE 落在 `<node>/refs/` 底下＝bad（會跟 ref 檔撞名）。
- 請求＝`{"litellm": {"model": 模型, "messages": [{"role", "content"}...]}}`，正是 llmcall `--request` 吃的格式。
- 沒給 `--out`：請求（`json.dumps(…, ensure_ascii=False, indent=1)`）印到 stdout，回條印到 stderr。給了 `--out`：請求原子寫進 FILE，回條印到 stdout。
- 回條一行 JSON：成功 `{"v":1,"outcome":"rendered","messages":k,"chars":c,"tokens_est":t,"chars_full":cf,"tokens_est_full":tf,"folded":[sha…],"out":FILE 或 null}`；`chars`＝折疊後所有 content 字數和，`chars_full`＝不折疊的字數和，`tokens_est`＝`ceil(chars/3)`（`tf` 同理）；`folded` 依出現順序、不重複。失敗 `{"v":1,"outcome":"bad"|"unknown","code":代號,"why":白話}`。

`aos7-prompt expand <node> <ref://sha | request.json>`

- `ref://<sha>`：原文直接印到 stdout（不加換行、不包 JSON）。
- 檔案：讀 llmcall 請求（`litellm.model` 字串、每則訊息 role 非空字串、content 字串，否則 bad），把 `litellm.messages[*].content` 全部照 §4 展開，以 render 相同格式印到 stdout。
- 失敗回條印到 stderr。

## 6. 退出碼

| 碼 | 意義 |
|---|---|
| 0 | 成功 |
| 2 | bad：形狀不對、選項不認得、指示詞寫法錯（`UnknownDirective`、`DirectiveValueTypeMismatch`、`FormatVariableInvalid`、`UnknownFormatVariable`、`UnknownOption`、`OptionConflict`）、node 不是資料夾、值本身不合（`ValueInvalid`：路徑含 NUL、整數過長等） |
| 3 | unknown：讀不到或不知道（`ReferenceReadFailed`、`ReferenceJsonInvalid`、`ReferenceCycle`、`ReferencePointerInvalid`、`EnvironmentVariableMissing`、讀檔失敗、不是 UTF-8、ref 檔缺或對不上、寫檔失敗） |

## 7. 界線

不呼叫模型、不碰 llmcall／budget；不保證 token 估值準（字數／3 只看趨勢）；原文裡本來就寫著合乎 §4 格式的字串，`expand` 也會試著展開它。
