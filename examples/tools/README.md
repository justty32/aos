# 工具範例

一份 `.json` 就是一個模型叫得動的工具，不用重新編譯。

```bash
export AOS_LLM_TOOLS=$PWD/examples/tools/wordcount.json
aos llm tools          # 應該印出 wordcount
aos llm ask 幫我數一下 README.md 有幾行
```

`wordcount.json` 示範了三種參數綁定：

| 宣告 | 命令列上長什麼樣 |
|---|---|
| `{"position": 2}` | 位置參數，直接放上去 |
| `{"position": 1, "flag": "-l"}` + `type: boolean` | 開關，**真值才放 `-l`**，假值連旗標都不放 |
| `{"flag": "-w", "separate": false}` | `-w=值`（這份沒用到） |

**沒有 kind 這種欄位**：命令列上長什麼樣是從 schema 的型別推導出來的，
同一件事不講第二遍。順序完全照 `position` 小到大，**沒寫就是 0**。

完整格式見 [`include/aos/tooljson/exec.hpp`](../../include/aos/tooljson/exec.hpp) 開頭那段。

## 自己寫一個

三件事要對得起來：

1. `function.parameters.properties` 裡宣告的參數名
2. `_extra.argv` 綁的參數名
3. 執行檔真的收的旗標

前兩項對不起來會在**載入時**就報錯（而不是等模型第一次叫它），
所以寫完先跑一次 `aos llm tools` 確認載得起來。
