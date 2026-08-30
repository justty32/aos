# 使用 aos

← [文件索引](README.md)｜[總覽](overview.md)｜[建置細節](build.md)

## 建置與安裝

從 repo 根目錄執行：

```bash
cmake --preset default && cmake --build --preset default && ctest --preset default
```

執行檔會在 `build/bin/aos`；安裝方式、平台、vcpkg、preset 與產物見
[build.md](build.md)。

## 推進世界：`run`

```text
aos run [folder] [--step N] [--interval MS]
```

`--step N` 推進 N 回合，預設 1；`--step 0` 持續執行。回合間隔由
`--interval MS` 指定，預設 100 毫秒。

省略 `folder` 時依序解析：

1. `AOS_FOLDER` 指定的資料夾。
2. 從目前工作目錄往上，最近一個含 `.aos/` 的目錄。
3. 都找不到時使用目前工作目錄。

## 投遞一條指令：`deliver`

```text
aos deliver [folder] <inst.json>
aos deliver [folder] -- <argv...>
```

第一種讀取一份指令 JSON，第二種直接把 `argv` 做成指令；兩者都原子投遞到
`.aos/inbox/`，等待後續回合執行。例如 `aos deliver job.json`，或
`aos deliver -- printf 'hello\n'`。省略
`folder` 時使用與 `run` 相同的解析規則。

## 把 LLM 當成一條指令：`llm`

prompt 從 stdin 進，回覆文字從 stdout 出：

```bash
echo '只回一個字：好' | aos llm
aos llm --messages messages.json
```

`--messages` 讀取 OpenAI messages 陣列的 JSON。連線設定來自：

| 環境變數 | 用途 | 預設 |
|---|---|---|
| `AOS_LLM_URL` | OpenAI 相容 base URL | `http://localhost:1234/v1` |
| `AOS_LLM_MODEL` | 模型名稱 | `qwen/qwen3.5-9b` |
| `AOS_LLM_KEY` | 選填的 Bearer token | 無 |

## 建立與操作 agent

在要成為世界的資料夾裡執行 `aos agent init`。它會建立這個世界唯一的 agent，
名字就是資料夾名，並在 `.aos/every/` 放入每回合
執行 `step` 的常駐指令。`aos agent step` 通常由 loop 呼叫，不必手動執行。

| 指令 | 行為 |
|---|---|
| `aos say "文字"` | 對目前資料夾唯一的 agent 說話 |
| `aos listen` | 跟讀新增的對話記錄 |
| `aos talk` | 從 stdin 逐行交談，等待外部 loop 推進並印出新記錄 |
| `aos state` | 印出 agent 的 `status.json` |

這四條會自動解析所在世界與唯一的 agent。舊形式
`aos agent say|listen|talk|state <folder> <name>` 仍可用；需要操作多隻 agent，或人不在
該世界的資料夾裡時，就用這種明確指定資料夾與名字的形式。

## 兩個視窗跑起一隻 agent

先確認 OpenAI 相容端點可用。視窗一在一個空目錄的上一層執行：

```bash
mkdir bob && cd bob && aos agent init
```

視窗二從同一個上一層進入世界，讓 loop 持續推進：

```bash
cd bob
aos run --step 0
```

回到視窗一送出訊息，再跟讀回覆：

```bash
aos say "你叫什麼名字"
aos listen
```
