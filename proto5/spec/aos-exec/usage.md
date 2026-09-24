← [aos-exec](README.md)｜[spec 總導航](../README.md)

# 用法

```
aos-exec [xxx] [--dir-target REL] [--timeout-ms N] [--stderr PATH|-] [-- ARG...]
```

`xxx` **留空＝`.`**：就是「跑我現在所在的這個資料夾」（`aos-exec` ＝ `aos-exec .` ＝ 跑
`./.aos/inst.json`）。（09-24 fix-r4 確認：`xxx` 本來就可省略，跟 `aos-cpu [DIR]`、`aos-llm call [AGENT_DIR]` 一致，行為不變。）

# 三種目標：`xxx` 是什麼決定怎麼跑

| `xxx` 是 | 做什麼 | base（`cwd` 沒寫時的預設、相對路徑的起點） | 串流 |
|---|---|---|---|
| 普通檔案（副檔名不是 `.json`） | 直接執行它：`argv[0]` 是它的絕對路徑，`--` 後面的東西原樣接成 `argv[1:]` | 它所在的資料夾 | **繼承** aos-exec 的 |
| `.json` 檔（**不存在也走這條**） | 讀進來當 inst.json 解析、執行 | 那個 `.json` 所在的資料夾 | 照 inst.json |
| 資料夾 | 執行 `xxx/.aos/inst.json`（`--dir-target` 可改） | `xxx` 自己 | 照 inst.json |

- **先看是不是資料夾、再看副檔名**：一個名字剛好以 `.json` 結尾的**資料夾**還是照資料夾走。
- **普通檔案模式**不解析 `--` 後的內容：空字串、空白、看起來像旗標的字串都原樣當一個 argv
  元素。環境就是繼承的、沒有 exit 檔、沒有重導向。它沒有執行位＝126。
- **`.json` 或資料夾目標給了 `--`**（就算後面沒有元素）是用法錯（退出碼 2）：inst 目標的參數
  寫在 inst.json 的 `argv` 裡。
- **一個以 `.json` 結尾但不存在的路徑不是用法錯**，是 aos-exec 自己失敗（125、`ReadFailed`）。
  不存在的**非** `.json` 路徑照舊是用法錯（2）。

# 旗標

| 旗標 | 意思 |
|---|---|
| `--dir-target REL` | `xxx` 是資料夾時要跑的相對路徑，預設 `.aos/inst.json`。指的檔不存在＝用法錯（2）。base 還是 `xxx` 自己，不是那個檔所在的資料夾 |
| `--timeout-ms N` | 這一次執行的上限（毫秒）。三種目標都吃；`0` 或不給＝不限；負數＝用法錯（2）。到了就砍整個 process group：SIGTERM、等 2 秒、還在就 SIGKILL（碼是 143／137，見下） |
| `--stderr PATH` / `--stderr -` | 蓋掉子程式的 stderr：`-`＝印到 aos-exec 自己的 stderr；給路徑＝寫進那個檔，路徑**以呼叫 aos-exec 時的 cwd 為中心**（不是 inst 的 cwd）。蓋的是 inst.json 的**整個** `stderr` 設定，包括 `merge`／`inherit`／`append`／`mkdir`（被蓋掉的 `mkdir` 也不會建）；stdin／stdout／exit 不受影響。普通檔案模式也吃 |
| `--` | 之後的東西原樣交給普通檔案當參數；inst 目標不准給 |

**看不到錯誤？** inst.json 沒寫 `stderr` 時，子程式的錯誤預設進 `/dev/null`。加 `--stderr -` 就看得到。
