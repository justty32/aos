# 記錄格式

> **normative 在 [SPEC](../../../docs/SPEC.md)（C 區）**，本檔是說明與範例。欄位表＝
> §C-3、驗證狀態表＝§C-6——兩張表**只住在 SPEC**，本檔不再複製。本檔與 SPEC 不一致
> 時以 SPEC 為準。

這份文件回答「一份 instruction JSON 可以寫哪些欄位、如何驗證」。instruction 是描述
一個 POSIX 命令及其執行設定的 JSON 記錄。它不說投遞檔如何彙整（見
[handoff](handoff.md)），也不說 fork、逾時與狀態如何運作（見[執行語意](exec.md)）。
指示詞如何取得外部值則見[解析指南](resolve.md)。

`aos exec [folder]` 會讀取 `<folder>/.aos/inst.json` 的完整 JSON 文件；folder 省略時
使用目前目錄。頂層可以是：

- 一個指令物件，代表單筆執行。
- 一個由指令物件組成的陣列，代表按輸入順序啟動的批次；空陣列是合法的空批次。

文件可使用一般 JSON 空白與縮排。JSON Lines（連續放置多個頂層物件）不是合法
輸入；多筆指令必須放進同一個陣列。runner 會先讀到 EOF，再解析並驗證整份文件，
任何一筆失敗都不會執行其中任何指令。

## 綱要(schema)

欄位表是 normative 條款，見 [SPEC §C-3](../../../docs/SPEC.md)。以下只講表格讀不出來
的行為與理由。

所有字串值位置，也就是 `argv` 元素、五個路徑欄位及 `env` 的值，都可用
`{"$env":"NAME"}` 或 `{"$ref":"file.json#/pointer"}`。format 只保存未解析
指示詞；在執行前由 resolve 層讀取呼叫端明示的環境或 `base_path` 下的檔案。未解析時
寫回仍是同一個物件，解析後才輸出實際字串。`env` 的 key 與 `timeout_ms` 不接受
指示詞。`$ref` 的路徑、巢狀解析及循環規則見[解析指南](resolve.md)。

環境（變數）的 key 必須非空，且不得含有 `=`。JSON 物件的 key 在記憶體中的
指令裡是唯一的；來源中重複的 key 由 JSON 解析器處理，而非提供一套有序的
覆寫機制。

`stderr` 的物件形式是指示詞，必須剛好只有一個 `$opt` key，且值必須是字串
`"merge"`。這等同 shell 的 `2>&1`；字面字串 `"merge"` 仍表示名為 `merge` 的檔案。
若 C++ 呼叫端同時設定 `stderr_merge` 與 `stderr_path`，併流旗標優先，encode 只會
寫出 `{"$opt":"merge"}`，路徑會被忽略。

以下這筆完整記錄會在 `/tmp` 底下執行 `sh`、提供一個環境變數、
重導向全部三個標準串流、記錄狀態，並施加
五秒的上限：

```json
{"argv":["sh","-c","read line; printf '%s: %s\\n' \"$LABEL\" \"$line\"; printf 'diagnostic\\n' >&2"],"stdin":"/tmp/aos-input.txt","stdout":"/tmp/aos-output.txt","stderr":"/tmp/aos-error.txt","exit":"/tmp/aos-status.txt","cwd":"/tmp","env":{"LABEL":"worker"},"timeout_ms":5000}
```

被引用的 `/tmp/aos-input.txt` 必須事先存在。成功時，本範例會
寫出記錄中指定的另外三個 `/tmp/aos-*` 檔案。

## 驗證狀態

拒絕條件的完整表是 normative 條款，見 [SPEC §C-6](../../../docs/SPEC.md)。那張表就是
全部的拒絕條件；除此之外只要是合法 JSON 且符合綱要，就會被接受。

**沒有任何上限。** 位元組數（單筆與整份）、`argv` 元素數、`env` 條目數、JSON
巢狀深度，全部不設上界。上表就是全部的拒絕條件；除此之外只要是合法 JSON 且
符合綱要，就會被接受。

這是刻意的：每一條上限都是一個猜出來的常數，而它們保護的資源本來就有更好的
邊界（記憶體看 `ulimit`／cgroup，`argv` 長度看核心的 `ARG_MAX`，那是 `execve`
自己會回報的東西）。

代價要講明白：**深度沒有上限，代表深層巢狀的輸入會讓解析器遞迴爆堆疊。** 那是
行程崩潰（SIGSEGV），不是一個錯誤狀態。指令檔等同可執行程式碼，本來就只該來自
你信任的來源；不要拿這個 runner 直接讀不可信的輸入。

陣列元素驗證失敗時，CLI 會印出以 1 為起始的
record 序號並回傳 1；整份文件的 JSON 語法錯誤則只報告來源。該批次中不會有
任何記錄被執行。

未知的 key 是刻意拒絕的，而不是忽略。否則較舊的執行檔
可能會默默執行一筆含有較新安全欄位（例如
`timeout_ms`）的記錄，卻完全沒有 timeout。拒絕也能把像
`"stdou"` 這樣的拼寫錯誤變成明確的失敗，而不是默默失去重導向。

`write_one` 會先驗證整個指令，才會附加任何內容。它只輸出
非預設的選用欄位、緊湊的單一 JSON 物件，以及最後一個 LF。
`write_all` 對整個批次做同一件事，輸出一個緊湊的 JSON 陣列；它同樣是先驗證完
每一筆才寫出第一個位元組，空批次輸出 `[]`。兩者的輸出都能直接被讀回來。
